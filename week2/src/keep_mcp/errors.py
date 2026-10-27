"""Error taxonomy for keep-mcp.

Every failure a tool can hit becomes an :class:`ErrorInfo` that is returned as
structured content (``ok=false``) instead of being raised out of the tool. The
``category`` is the field the agent is meant to branch on:

``input`` / ``policy``
    Do not retry. Fix the arguments or ask the user.
``not_found``
    The note name is stale, deleted, or foreign. Re-run ``search_notes``.
``auth_setup`` / ``auth_revoked``
    Login or an admin grant is missing. Do not retry; a human must act.
``rate_limited`` / ``transient``
    Retry later (``retry_after_seconds`` when the API supplied one).
``internal``
    A bug in this server; the message carries a request id, never a traceback.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel

ErrorCategory = Literal[
    "input",
    "not_found",
    "auth_setup",
    "auth_revoked",
    "rate_limited",
    "transient",
    "policy",
    "internal",
]

# OAuth client id the Workspace admin must authorize for domain-wide delegation.
DWD_CLIENT_ID = "105913096817318059135"
DWD_HINT = (
    "Ask a Workspace admin to authorize client ID "
    f"{DWD_CLIENT_ID} under Admin console > Security > API controls > Domain-wide delegation "
    "with the scope https://www.googleapis.com/auth/keep, then retry "
    "(propagation can take about a minute)."
)
LOGIN_HINT = "Run `uv run keep-mcp login` in the week2 directory to sign in again."
TOKEN_CREATOR_HINT = (
    "Grant the signed-in user the Service Account Token Creator role on the service account, then retry."
)
SEARCH_HINT = (
    "The name does not exist, was deleted, or is not visible to this account; "
    "get a fresh name from search_notes."
)


class ErrorInfo(BaseModel):
    """A structured, actionable failure."""

    code: str
    category: ErrorCategory
    message: str
    retryable: bool = False
    retry_after_seconds: int | None = None
    hint: str | None = None
    override: str | None = None


class ToolFailure(Exception):
    """Raised while building a tool result; the tool boundary turns it into ``ok=false``."""

    def __init__(self, info: ErrorInfo) -> None:
        super().__init__(info.message)
        self.info = info


# --------------------------------------------------------------------------- #
# taxonomy constructors
# --------------------------------------------------------------------------- #
def invalid_argument(message: str, *, hint: str | None = None) -> ErrorInfo:
    return ErrorInfo(code="invalid_argument", category="input", message=message, hint=hint)


def unknown_recipient(email: str | None = None, *, field: str | None = None) -> ErrorInfo:
    if email:
        return ErrorInfo(
            code="unknown_recipient",
            category="input",
            message=(
                f"The Keep API rejected the share target {email!r}: no Google account with "
                "that address can receive this note."
            ),
            hint="Check the address for typos, or share the note from the Keep web UI instead.",
        )
    detail = f" (field {field})" if field else ""
    return ErrorInfo(
        code="unknown_recipient",
        category="input",
        message=f"The Keep API rejected one of the share targets{detail}.",
        hint="Check every address for typos; Keep can only share with existing Google accounts.",
    )


def note_not_accessible() -> ErrorInfo:
    return ErrorInfo(
        code="note_not_accessible",
        category="not_found",
        message=(
            "The Keep API refused this note. Google never distinguishes 'does not exist' from "
            "'not yours', so this covers a deleted, mistyped, or foreign note."
        ),
        hint=SEARCH_HINT,
    )


def not_logged_in() -> ErrorInfo:
    return ErrorInfo(
        code="not_logged_in",
        category="auth_setup",
        message=(
            "No cached Google login was found for keep-mcp, so no Keep token can be derived. "
            "No browser was opened: tool calls never open one."
        ),
        hint=LOGIN_HINT,
    )


def login_revoked() -> ErrorInfo:
    return ErrorInfo(
        code="login_revoked",
        category="auth_revoked",
        message=(
            "The cached Google login was rejected (invalid_grant): the refresh token was revoked, "
            "expired, or the app grant was removed. No browser was opened."
        ),
        hint=LOGIN_HINT,
    )


def delegation_missing() -> ErrorInfo:
    return ErrorInfo(
        code="delegation_missing",
        category="auth_setup",
        message=(
            "Google refused the domain-wide delegation assertion (unauthorized_client): the Keep "
            "scope is not authorized for this OAuth client in the Workspace domain."
        ),
        hint=DWD_HINT,
    )


def signer_permission(message: str | None = None) -> ErrorInfo:
    return ErrorInfo(
        code="signer_permission",
        category="auth_setup",
        message=(
            "The IAM Credentials API refused to sign the delegation JWT with the user's token "
            f"(403){f': {message}' if message else ''}."
        ),
        hint=TOKEN_CREATOR_HINT,
    )


def auth_setup_error(code: str, message: str, *, hint: str | None = None) -> ErrorInfo:
    return ErrorInfo(code=code, category="auth_setup", message=message, hint=hint)


def rate_limited(retry_after_seconds: int | None = None) -> ErrorInfo:
    return ErrorInfo(
        code="rate_limited",
        category="rate_limited",
        message=(
            "The Keep API is rate limiting this account (HTTP 429). "
            + (
                f"Retry after about {retry_after_seconds}s."
                if retry_after_seconds
                else "Retry after a short delay."
            )
        ),
        retryable=True,
        retry_after_seconds=retry_after_seconds,
        hint="Wait for the retry window, then repeat the same call.",
    )


def transient(message: str) -> ErrorInfo:
    return ErrorInfo(
        code="transient",
        category="transient",
        message=f"Temporary failure talking to Google: {message}",
        retryable=True,
        retry_after_seconds=None,
        hint="Retry the same call; if it keeps failing, check network access to *.googleapis.com.",
    )


def internal_error(where: str) -> ErrorInfo:
    request_id = uuid.uuid4().hex[:12]
    return ErrorInfo(
        code="internal",
        category="internal",
        message=(
            f"Unexpected error in keep-mcp while handling {where} (request id {request_id}). "
            "This is a bug in the server, not in the request."
        ),
        hint=f"Retry once; if it persists, report request id {request_id}.",
    )


def managed_notes_only(name: str) -> ErrorInfo:
    return ErrorInfo(
        code="managed_notes_only",
        category="policy",
        message=(
            f"Safe mode refuses to delete {name!r} because keep-mcp did not create it. "
            "This is an intentional safety guard against deleting a real note by mistake, "
            "not a malfunction."
        ),
        hint="Ask the user to confirm, then delete that single note with allow_foreign=true.",
        override=(
            "Pass allow_foreign=true to delete this one foreign note, "
            "or start the server with KEEP_SAFE_MODE=false to switch the guard off."
        ),
    )


# --------------------------------------------------------------------------- #
# HTTP -> taxonomy
# --------------------------------------------------------------------------- #
def google_error(payload: Any) -> tuple[str | None, str | None, list[str]]:
    """Pull ``(status, message, violating_fields)`` out of a Google error body."""
    if not isinstance(payload, dict):
        return None, None, []
    error = payload.get("error")
    if isinstance(error, str):  # OAuth-style {"error": "invalid_grant"}
        return error, payload.get("error_description"), []
    if not isinstance(error, dict):
        return None, None, []
    fields: list[str] = []
    for detail in error.get("details") or []:
        if not isinstance(detail, dict):
            continue
        for violation in detail.get("fieldViolations") or []:
            if isinstance(violation, dict) and violation.get("field"):
                fields.append(str(violation["field"]))
    return error.get("status"), error.get("message"), fields


def _retry_after_from_seconds(retry_after: int | None) -> int | None:
    if retry_after is None:
        return None
    return max(0, int(retry_after))


def from_http(
    status: int,
    payload: Any,
    *,
    context: Literal["note", "keep", "signjwt", "token", "login"],
    retry_after: int | None = None,
) -> ErrorInfo:
    """Map an HTTP failure onto the taxonomy.

    ``context`` matters because the same status means different things on
    different endpoints: a 403 on a note-scoped Keep call means "no such note"
    (Google never returns 404), while a 403 from ``signJwt`` means the caller
    lacks Token Creator.
    """
    status_name, message, fields = google_error(payload)
    raw_error = payload.get("error") if isinstance(payload, dict) else None
    error_code = raw_error if isinstance(raw_error, str) else None

    if context == "login":
        return auth_setup_error(
            "login_failed",
            f"The Google authorization code exchange failed (HTTP {status})"
            + (f": {error_code}" if error_code else ""),
            hint="Re-run `uv run keep-mcp login`; authorization codes are single-use and short-lived.",
        )

    if context == "token":
        if error_code == "invalid_grant" or status_name == "invalid_grant":
            return login_revoked()
        if error_code == "unauthorized_client" or status_name == "unauthorized_client":
            return delegation_missing()
        if status == 429 or status_name == "RESOURCE_EXHAUSTED":
            return rate_limited(_retry_after_from_seconds(retry_after))
        if status >= 500:
            return transient(f"token endpoint returned HTTP {status}")
        return auth_setup_error(
            "refresh_failed",
            f"Google refused to mint a Keep token (HTTP {status}"
            + (f", error {error_code}" if error_code else "")
            + ").",
            hint=LOGIN_HINT,
        )

    if status == 429 or status_name == "RESOURCE_EXHAUSTED":
        return rate_limited(_retry_after_from_seconds(retry_after))
    if status >= 500 or status == 408:
        return transient(f"the API returned HTTP {status}")
    if context == "signjwt":
        return signer_permission(message)

    if status in (403, 404):
        if context == "note":
            return note_not_accessible()
        return auth_setup_error(
            "permission_denied",
            f"The Keep API denied this call (HTTP {status})"
            + (f": {message}" if message else "")
            + ".",
            hint="Check that the service account is delegated for the Keep scope, then retry.",
        )

    if status == 400:
        permission_fields = [f for f in fields if f.endswith("permission")]
        if permission_fields:
            return unknown_recipient(field=permission_fields[0])
        if fields:
            return invalid_argument(
                f"The Keep API rejected the request"
                + (f" ({message})" if message else "")
                + f". Offending field(s): {', '.join(fields)}."
            )
        return invalid_argument(f"The Keep API rejected the request (HTTP 400){f': {message}' if message else ''}.")

    if status in (401,):
        return auth_setup_error(
            "unauthorized",
            f"The Keep API rejected the access token (HTTP 401).",
            hint=LOGIN_HINT,
        )

    return internal_error(f"a Keep API call (HTTP {status})")
