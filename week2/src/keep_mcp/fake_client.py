"""In-memory ``KeepApi`` used by the offline test layer (L1).

It is deliberately *quirky*: it reproduces what the live probe observed about
``keep.googleapis.com/v1`` so that tests exercise the same behaviour the real
client will hit.

* ``notes.get`` on a missing/malformed name -> **403 PERMISSION_DENIED**, never 404.
* ``notes.list`` with nothing to return -> ``{}`` (no ``notes`` key).
* ``notes.list`` with no filter -> only non-trashed notes (the live default
  view hides the trash), while a time filter alone does **not** constrain the
  trash state (trashed notes are included) - both verified live 2026-10-06.
* ``notes.create`` without a body -> 400 on field ``note.body``.
* ``notes.create`` with a checked list item that has an unchecked child -> 400
  on field ``note.body.list.list_items[N].child_list_items[M].checked``
  (verified live 2026-10-06: a checked parent must have all children checked;
  unchecked parents may carry children in either state).
* filters: ``trashed``, ``-trashed``, ``NOT trashed``, ``update_time > "..."`` and
  ``create_time > "..."`` are valid; anything with ``=`` or ``:`` is a 400
  invalid filter. A time filter combined with a trash filter is accepted by
  default, but ``reject_combined_filter=True`` simulates the API rejecting it,
  which is how the client-side fallback in ``search_notes`` gets tested.
* ``permissions.batchCreate`` with an unknown address -> 400 on
  ``requests[N].permission``.
* every call is recorded, so tests can assert on emitted filter strings and
  call counts.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

import httpx

from .errors import ToolFailure, from_http, not_logged_in, transient

JSON = dict[str, Any]

# --------------------------------------------------------------------------- #
# payloads (shapes taken from secrets/probe_output.txt, emails/ids scrubbed)
# --------------------------------------------------------------------------- #
PERMISSION_DENIED_403: JSON = {
    "error": {"code": 403, "message": "The caller does not have permission", "status": "PERMISSION_DENIED"}
}
INVALID_FILTER_400: JSON = {
    "error": {
        "code": 400,
        "message": "Request contains an invalid argument.",
        "status": "INVALID_ARGUMENT",
        "details": [
            {
                "@type": "type.googleapis.com/google.rpc.BadRequest",
                "fieldViolations": [
                    {"field": "filter", "description": "Request contains an invalid filter."}
                ],
            }
        ],
    }
}
EMPTY_BODY_400: JSON = {
    "error": {
        "code": 400,
        "message": "Request contains an invalid argument.",
        "status": "INVALID_ARGUMENT",
        "details": [
            {
                "@type": "type.googleapis.com/google.rpc.BadRequest",
                "fieldViolations": [
                    {"field": "note.body", "description": "Note contains an empty body."}
                ],
            }
        ],
    }
}
UNKNOWN_RECIPIENT_400: JSON = {
    "error": {
        "code": 400,
        "message": "Request contains an invalid argument.",
        "status": "INVALID_ARGUMENT",
        "details": [
            {
                "@type": "type.googleapis.com/google.rpc.BadRequest",
                "fieldViolations": [
                    {
                        "field": "requests[0].permission",
                        "description": "Requested user does not exist or cannot be shared with.",
                    }
                ],
            }
        ],
    }
}
#: verified live 2026-10-06: a checked list item may not have unchecked children
CHECKED_CHILD_400: JSON = {
    "error": {
        "code": 400,
        "message": "Request contains an invalid argument.",
        "status": "INVALID_ARGUMENT",
        "details": [
            {
                "@type": "type.googleapis.com/google.rpc.BadRequest",
                "fieldViolations": [
                    {"field": "note.body.list.list_items[0].child_list_items[0].checked"}
                ],
            }
        ],
    }
}
RATE_LIMITED_429: JSON = {
    "error": {"code": 429, "message": "Resource has been exhausted (e.g. check quota).", "status": "RESOURCE_EXHAUSTED"}
}
UNAVAILABLE_503: JSON = {
    "error": {"code": 503, "message": "The service is currently unavailable.", "status": "UNAVAILABLE"}
}

_TERM_RE = re.compile(r'^(update_time|create_time)\s*>\s*"([^"]+)"$')


def _timestamp(value: datetime | None = None) -> str:
    moment = value or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _parse_time(raw: str) -> datetime:
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def _time_of(note: JSON, key: str) -> str:
    """Timestamp of a note, falling back to the epoch when Keep omits it."""
    value = note.get(key)
    return value if isinstance(value, str) and value else "1970-01-01T00:00:00Z"


@dataclass(slots=True)
class RecordedCall:
    """One request the server made through the client."""

    method: str
    path: str
    params: JSON | None = None
    payload: JSON | None = None

    @property
    def filter(self) -> str | None:
        return (self.params or {}).get("filter")


@dataclass(slots=True)
class _Failure:
    method: str | None
    path_contains: str | None
    status: int | None = None
    payload: JSON | None = None
    retry_after: int | None = None
    context: str | None = None
    exc: BaseException | None = None
    remaining: int = 1

    def matches(self, method: str, path: str) -> bool:
        if self.method is not None and self.method != method:
            return False
        return self.path_contains is None or self.path_contains in path


class FakeKeepClient:
    """A scriptable, in-memory stand-in for the official Keep API."""

    def __init__(
        self,
        *,
        owner_email: str = "owner@example.com",
        known_emails: Iterable[str] | None = None,
        reject_combined_filter: bool = False,
    ) -> None:
        self.notes: dict[str, JSON] = {}
        self.calls: list[RecordedCall] = []
        self.owner_email = owner_email
        # ``None`` means "accept every address" (permissive default for tests
        # that are not about recipients).
        self.known_emails: set[str] | None = (
            None if known_emails is None else {email.lower() for email in known_emails}
        )
        self.reject_combined_filter = reject_combined_filter
        self._failures: list[_Failure] = []
        self._token_provider: Any | None = None
        self._counter = 0

    # ------------------------------------------------------------------ #
    # test helpers
    # ------------------------------------------------------------------ #
    def set_token_provider(self, provider: Any) -> None:
        """Ask ``provider.keep_access_token()`` before every request.

        ``HttpKeepClient`` does this for real, so wiring it here keeps the auth
        path (and its failure modes) inside the offline layer.
        """
        self._token_provider = provider

    async def _authorize(self) -> None:
        if self._token_provider is not None:
            await self._token_provider.keep_access_token()
    def seed_note(
        self,
        *,
        title: str = "",
        text: str | None = None,
        items: list[JSON] | None = None,
        trashed: bool = False,
        collaborators: Iterable[tuple[str, str]] = (),
        attachments: Iterable[str] = (),
        updated: datetime | None = None,
        created: datetime | None = None,
        name: str | None = None,
    ) -> str:
        """Insert a note and return its name.

        ``items`` are Keep-shaped dicts: ``{"text": ..., "checked": ...,
        "children": [{"text": ..., "checked": ...}]}``.
        """
        if text is not None and items is not None:
            raise ValueError("a note body is either text or items")
        if text is None and items is None:
            body: JSON = {"text": {"text": ""}}
        elif items is not None:
            body = {"list": {"listItems": self._items(items)}}
        else:
            body = {"text": {"text": text}}
        note_name = name or self._new_name()
        note: JSON = {
            "name": note_name,
            "createTime": _timestamp(created),
            "updateTime": _timestamp(updated),
            "permissions": [
                {
                    "name": f"{note_name}/permissions/{self._new_id()}",
                    "role": "OWNER",
                    "email": self.owner_email,
                    "user": {"email": self.owner_email},
                }
            ],
            "title": title,
            "body": body,
        }
        for email, role in collaborators:
            note["permissions"].append(
                {
                    "name": f"{note_name}/permissions/{self._new_id()}",
                    "role": role,
                    "email": email,
                    "user": {"email": email},
                }
            )
        if attachments:
            note["attachments"] = [
                {"name": f"{note_name}/attachments/{self._new_id()}", "mimeType": "text/plain"}
                for _ in attachments
            ]
        if trashed:
            note["trashTime"] = _timestamp(updated)
        self.notes[note["name"]] = note
        return note["name"]

    def seed_wire(self, note: JSON) -> str:
        """Insert a raw (scrubbed) probe response verbatim."""
        stored = copy.deepcopy(note)
        stored.setdefault("name", self._new_name())
        stored.setdefault("permissions", [])
        stored.setdefault("title", "")
        self.notes[stored["name"]] = stored
        return stored["name"]

    def queue_http_error(
        self,
        status: int,
        *,
        payload: JSON | None = None,
        retry_after: int | None = None,
        method: str | None = None,
        path_contains: str | None = None,
        context: str | None = None,
        times: int = 1,
    ) -> None:
        """Make the next matching request(s) fail with ``status``."""
        self._failures.append(
            _Failure(
                method=method,
                path_contains=path_contains,
                status=status,
                payload=payload,
                retry_after=retry_after,
                context=context,
                remaining=times,
            )
        )

    def queue_exception(self, exc: BaseException, *, method: str | None = None, path_contains: str | None = None) -> None:
        """Make the next matching request raise ``exc`` (simulates a timeout or a genuine bug)."""
        self._failures.append(_Failure(method=method, path_contains=path_contains, exc=exc))

    def calls_for(self, method: str, path_contains: str = "") -> list[RecordedCall]:
        return [call for call in self.calls if call.method == method and path_contains in call.path]

    @property
    def call_count(self) -> int:
        return len(self.calls)

    # ------------------------------------------------------------------ #
    # KeepApi
    # ------------------------------------------------------------------ #
    async def aclose(self) -> None:  # pragma: no cover - nothing to release
        return None

    async def list_notes(
        self,
        *,
        page_size: int = 100,
        page_token: str | None = None,
        filter: str | None = None,
    ) -> JSON:
        await self._authorize()
        self._record("GET", "/notes", params={"pageSize": page_size, "pageToken": page_token, "filter": filter})
        self._maybe_fail("GET", "/notes")
        predicates = self._compile_filter(filter)
        matching = [note for note in self._sorted_notes() if all(predicate(note) for predicate in predicates)]
        offset = int(page_token) if page_token else 0
        page = matching[offset : offset + page_size]
        if not page:
            return {}
        result: JSON = {"notes": [copy.deepcopy(note) for note in page]}
        next_offset = offset + page_size
        if next_offset < len(matching):
            result["nextPageToken"] = str(next_offset)
        return result

    async def get_note(self, name: str) -> JSON:
        await self._authorize()
        self._record("GET", f"/{name}")
        self._maybe_fail("GET", f"/{name}")
        return copy.deepcopy(self._require(name))

    async def create_note(self, payload: JSON) -> JSON:
        await self._authorize()
        self._record("POST", "/notes", payload=payload)
        self._maybe_fail("POST", "/notes")
        body = payload.get("body") if isinstance(payload, dict) else None
        if not body or not (body.get("text") or body.get("list")):
            raise ToolFailure(from_http(400, EMPTY_BODY_400, context="keep"))
        if "list" in body and not (body["list"] or {}).get("listItems"):
            raise ToolFailure(from_http(400, EMPTY_BODY_400, context="keep"))
        for index, item in enumerate((body.get("list") or {}).get("listItems") or []):
            if not item.get("checked"):
                continue
            for child_index, child in enumerate(item.get("childListItems") or []):
                if not child.get("checked"):
                    # verified live 2026-10-06: the API rejects a checked parent
                    # with an unchecked child on create
                    failure = copy.deepcopy(CHECKED_CHILD_400)
                    violations = failure["error"]["details"][0]["fieldViolations"]
                    violations[0]["field"] = (
                        f"note.body.list.list_items[{index}].child_list_items[{child_index}].checked"
                    )
                    raise ToolFailure(from_http(400, failure, context="keep"))
        now = _timestamp()
        name = self._new_name()
        note: JSON = {
            "name": name,
            "createTime": now,
            "updateTime": now,
            "permissions": [
                {
                    "name": f"{name}/permissions/{self._new_id()}",
                    "role": "OWNER",
                    "email": self.owner_email,
                    "user": {"email": self.owner_email},
                }
            ],
            "title": payload.get("title") or "",
            "body": copy.deepcopy(body),
        }
        self.notes[name] = note
        return copy.deepcopy(note)

    async def delete_note(self, name: str) -> JSON:
        await self._authorize()
        self._record("DELETE", f"/{name}")
        self._maybe_fail("DELETE", f"/{name}")
        self._require(name)
        del self.notes[name]
        return {}

    async def create_permissions(self, name: str, emails: list[str]) -> JSON:
        payload = {"requests": [{"permission": {"email": email, "role": "WRITER"}} for email in emails]}
        await self._authorize()
        self._record("POST", f"/{name}/permissions:batchCreate", payload=payload)
        self._maybe_fail("POST", f"/{name}/permissions:batchCreate")
        note = self._require(name)
        for index, email in enumerate(emails):
            if self.known_emails is not None and email.lower() not in self.known_emails:
                failure = copy.deepcopy(UNKNOWN_RECIPIENT_400)
                violations = failure["error"]["details"][0]["fieldViolations"]
                violations[0]["field"] = f"requests[{index}].permission"
                raise ToolFailure(from_http(400, failure, context="note"))
        created = []
        for email in emails:
            permission = {
                "name": f"{name}/permissions/{self._new_id()}",
                "role": "WRITER",
                "email": email,
                "user": {"email": email},
            }
            note["permissions"].append(permission)
            created.append(copy.deepcopy(permission))
        return {"permissions": created}

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #
    def _new_id(self) -> str:
        self._counter += 1
        # shape of the real id: url-safe characters
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        value = self._counter
        out = ""
        while value:
            value, rem = divmod(value, len(alphabet))
            out = alphabet[rem] + out
        return (out or "A").rjust(24, "0") + "fake"

    def _new_name(self) -> str:
        return f"notes/{self._new_id()}"

    def _record(self, method: str, path: str, *, params: JSON | None = None, payload: JSON | None = None) -> None:
        self.calls.append(RecordedCall(method=method, path=path, params=params, payload=payload))

    def _maybe_fail(self, method: str, path: str) -> None:
        for index, failure in enumerate(self._failures):
            if not failure.matches(method, path):
                continue
            failure.remaining -= 1
            if failure.remaining <= 0:
                self._failures.pop(index)
            if failure.exc is not None:
                exc = failure.exc
                # mirror HttpKeepClient: transport failures become retryable
                if isinstance(exc, httpx.TimeoutException):
                    raise ToolFailure(
                        transient(f"the Keep API did not answer in time ({type(exc).__name__})")
                    ) from None
                if isinstance(exc, httpx.HTTPError):
                    raise ToolFailure(
                        transient(f"could not reach the Keep API ({type(exc).__name__}: {exc})")
                    ) from None
                raise exc
            context = failure.context or ("note" if path != "/notes" else "keep")
            raise ToolFailure(
                from_http(
                    failure.status or 500,
                    failure.payload if failure.payload is not None else {},
                    context=context,  # type: ignore[arg-type]
                    retry_after=failure.retry_after,
                )
            )

    def _require(self, name: str) -> JSON:
        note = self.notes.get(name)
        if note is None:
            raise ToolFailure(from_http(403, PERMISSION_DENIED_403, context="note"))
        return note

    def _sorted_notes(self) -> list[JSON]:
        return sorted(self.notes.values(), key=lambda note: str(note.get("updateTime") or ""), reverse=True)

    @staticmethod
    def _items(raw_items: list[JSON]) -> list[JSON]:
        items = []
        for raw in raw_items:
            item: JSON = {
                "text": {"text": raw["text"]},
                "checked": bool(raw.get("checked", False)),
            }
            children = raw.get("children")
            if children:
                item["childListItems"] = [
                    {"text": {"text": child["text"]}, "checked": bool(child.get("checked", False))}
                    for child in children
                ]
            items.append(item)
        return items

    def _compile_filter(self, filter: str | None):
        """Validate a filter the way the API does, and return predicates."""
        if not filter:
            # the live API's default list view hides trashed notes (verified
            # 2026-10-06: no filter and "-trashed" return the same notes)
            return [lambda note: not self._is_trashed(note)]
        # colons inside a quoted timestamp are fine; "=" and "trashed:false" are not
        unquoted = re.sub(r'"[^"]*"', '""', filter)
        if "=" in unquoted or ":" in unquoted:
            raise ToolFailure(from_http(400, INVALID_FILTER_400, context="keep"))
        predicates = []
        trash_predicates = 0
        time_predicates = 0
        for term in (part.strip() for part in filter.split(" AND ")):
            if term == "trashed":
                trash_predicates += 1
                predicates.append(lambda note: self._is_trashed(note))
            elif term in ("-trashed", "NOT trashed"):
                trash_predicates += 1
                predicates.append(lambda note: not self._is_trashed(note))
            else:
                match = _TERM_RE.match(term)
                if not match:
                    raise ToolFailure(from_http(400, INVALID_FILTER_400, context="keep"))
                time_predicates += 1
                field_name, raw_time = match.group(1), match.group(2)
                threshold = _parse_time(raw_time)
                key = "updateTime" if field_name == "update_time" else "createTime"
                predicates.append(
                    lambda note, key=key, threshold=threshold: _parse_time(_time_of(note, key)) > threshold
                )
        if trash_predicates and time_predicates and self.reject_combined_filter:
            # The live probe never confirmed that a time filter may be combined
            # with a trash filter; this switch simulates the API rejecting it.
            raise ToolFailure(from_http(400, INVALID_FILTER_400, context="keep"))
        return predicates

    @staticmethod
    def _is_trashed(note: JSON) -> bool:
        return bool(note.get("trashTime"))


@dataclass(slots=True)
class FakeAuth:
    """Auth stand-in: no network, no browser, an explicit login state."""

    logged_in: bool = True
    failure: Exception | None = None
    tokens_minted: int = 0

    async def keep_access_token(self) -> str:
        if self.failure is not None:
            raise self.failure
        if not self.logged_in:
            raise ToolFailure(not_logged_in())
        self.tokens_minted += 1
        return "fake-keep-access-token"

    async def aclose(self) -> None:  # pragma: no cover - nothing to release
        return None
