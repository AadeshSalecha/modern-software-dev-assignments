"""Hybrid auth: a user OAuth login feeds a domain-wide-delegated Keep token.

Google refuses the Keep scope on a consent screen (issue 210500028), so the Keep
authority has to come from an admin-approved domain-wide delegation (DWD) grant.
This module keeps the user login real and load-bearing:

1. ``keep-mcp login`` runs an authorization-code + PKCE flow with
   ``openid email https://www.googleapis.com/auth/iam`` and caches the refresh
   token at ``KEEP_TOKEN_FILE`` (mode 0600).
2. Every Keep call lazily derives a Keep access token: refresh the user token
   silently -> ``GET userinfo`` for the *verified* email -> ``signJwt`` on the
   service account **with the user's own token** (so delegation only ever
   happens for the person who logged in) -> jwt-bearer exchange -> Keep token,
   cached in memory until ~60s before it expires.

Neither credential works alone: the user scopes cannot read Keep, and the DWD
grant cannot be asserted without the user's token. Revoking the "Keep MCP" app
grant breaks the next refresh, which surfaces as ``auth_revoked``.

No tool call ever opens a browser; only the ``login`` subcommand does.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import secrets
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from .config import Config
from .errors import (
    ToolFailure,
    auth_setup_error,
    delegation_missing,
    from_http,
    internal_error,
    login_revoked,
    not_logged_in,
    transient,
)

logger = logging.getLogger(__name__)

AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"
IAM_BASE = "https://iamcredentials.googleapis.com/v1"
KEEP_SCOPE = "https://www.googleapis.com/auth/keep"

# Minimal scopes: prove the identity ("openid email") and let that user call
# signJwt on the service account ("iam"). No Keep scope is requested because
# Google refuses it on the consent screen.
LOGIN_SCOPES: tuple[str, ...] = ("openid", "email", "https://www.googleapis.com/auth/iam")

#: derive a fresh Keep token this many seconds before the old one expires
EXPIRY_SKEW = 60.0
#: assumed lifetime when Google omits ``expires_in``
DEFAULT_LIFETIME = 3600.0

JSON = dict[str, Any]


class TokenProvider(Protocol):
    """What the Keep client needs from auth."""

    async def keep_access_token(self) -> str:
        """Return a valid Keep access token, deriving or refreshing as needed."""
        ...

    async def aclose(self) -> None:
        """Release network resources."""
        ...


class AuthLoginError(Exception):
    """Raised by ``keep-mcp login``; the CLI prints it and exits non-zero."""


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def pkce_verifier() -> str:
    return _b64url(secrets.token_bytes(64))


def pkce_challenge(verifier: str) -> str:
    return _b64url(hashlib.sha256(verifier.encode("ascii")).digest())


def _safe_json(response: httpx.Response) -> JSON:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {"data": payload}


def _retry_after(response: httpx.Response) -> int | None:
    raw = response.headers.get("Retry-After")
    if not raw:
        return None
    try:
        return int(float(raw.strip()))
    except ValueError:
        return None


class _CallbackHandler(BaseHTTPRequestHandler):
    """Captures the one OAuth redirect that matters."""

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        parsed = urlparse(self.path)
        params = {key: values[0] for key, values in parse_qs(parsed.query).items()}
        # Browsers fetch /favicon.ico and port forwarders probe new ports; only the
        # real redirect may end the wait, or the code arriving later is lost.
        if parsed.path != "/callback" or not ("code" in params or "error" in params):
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.server.captured is None:  # type: ignore[attr-defined]
            self.server.captured = params  # type: ignore[attr-defined]
        body = (
            b"<html><body style='font-family:sans-serif'>"
            b"<h3>keep-mcp: login complete.</h3>"
            b"<p>You can close this tab and return to the terminal.</p>"
            b"</body></html>"
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: Any) -> None:  # keep the terminal clean
        return None


class KeepAuth:
    """Cached user token + derived Keep token, with one lock each."""

    def __init__(
        self,
        config: Config,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        client: httpx.AsyncClient | None = None,
        now: Callable[[], float] = time.time,
        open_browser: Callable[[str], Any] | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._config = config
        self._transport = transport
        self._client = client
        self._now = now
        self._open_browser = open_browser
        self._timeout = timeout
        self._user_lock = asyncio.Lock()
        self._keep_lock = asyncio.Lock()
        self._keep_token: str | None = None
        self._keep_expires_at = 0.0

    # ------------------------------------------------------------------ #
    # plumbing
    # ------------------------------------------------------------------ #
    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout, transport=self._transport)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _post_form(self, url: str, fields: JSON, *, context: str) -> JSON:
        client = await self._http()
        try:
            response = await client.post(url, data=fields)
        except httpx.TimeoutException:
            raise ToolFailure(transient(f"{url} did not answer within {self._timeout:g}s")) from None
        except httpx.HTTPError as exc:
            raise ToolFailure(transient(f"could not reach {url} ({type(exc).__name__}: {exc})")) from None
        if response.status_code >= 400:
            raise ToolFailure(
                from_http(
                    response.status_code,
                    _safe_json(response),
                    context=context,  # type: ignore[arg-type]
                    retry_after=_retry_after(response),
                )
            )
        return _safe_json(response)

    def _client_secret(self) -> JSON:
        path = self._config.oauth_client_file
        if path is None:
            raise ToolFailure(
                auth_setup_error(
                    "oauth_client_missing",
                    "KEEP_OAUTH_CLIENT_FILE is not set, so the OAuth client used for login cannot be read.",
                    hint=(
                        "Point KEEP_OAUTH_CLIENT_FILE at the downloaded Desktop client JSON "
                        "(Google Cloud Console > APIs & Services > Credentials)."
                    ),
                )
            )
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except OSError as exc:
            raise ToolFailure(
                auth_setup_error(
                    "oauth_client_unreadable",
                    f"Cannot read the OAuth client file {str(path)!r}: {type(exc).__name__}.",
                    hint="Check KEEP_OAUTH_CLIENT_FILE.",
                )
            ) from None
        except ValueError as exc:
            raise ToolFailure(
                auth_setup_error(
                    "oauth_client_invalid",
                    f"The OAuth client file {str(path)!r} is not valid JSON: {exc}.",
                    hint="Download the client secret JSON again from the Google Cloud Console.",
                )
            ) from None
        client = payload.get("installed") or payload.get("web")
        if not isinstance(client, dict) or not client.get("client_id") or not client.get("client_secret"):
            raise ToolFailure(
                auth_setup_error(
                    "oauth_client_invalid",
                    f"The OAuth client file {str(path)!r} has no 'installed' (or 'web') client_id/client_secret pair.",
                    hint="Use the Desktop app client secret JSON.",
                )
            )
        return client

    # ------------------------------------------------------------------ #
    # token file
    # ------------------------------------------------------------------ #
    def _load_record(self) -> JSON | None:
        path = self._config.token_file
        try:
            raw = path.read_text(encoding="utf-8")
        except (FileNotFoundError, NotADirectoryError):
            return None
        except OSError as exc:
            raise ToolFailure(internal_error(f"the token file ({type(exc).__name__})")) from None
        try:
            record = json.loads(raw)
        except ValueError:
            raise ToolFailure(not_logged_in()) from None
        return record if isinstance(record, dict) else None

    def _save_record(self, record: JSON) -> None:
        path = self._config.token_file
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(path.parent, 0o700)
        except OSError:  # pragma: no cover - best effort
            pass
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(record, indent=2), encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(path)
        os.chmod(path, 0o600)

    def login_record(self) -> JSON | None:
        """Return the cached record (without secrets) for diagnostics."""
        return self._load_record()

    # ------------------------------------------------------------------ #
    # user token
    # ------------------------------------------------------------------ #
    async def user_access_token(self) -> str:
        """A valid user access token, refreshed silently when expired."""
        async with self._user_lock:
            return await self._user_token_locked()

    async def _user_token_locked(self) -> str:
        record = self._load_record()
        if record is None:
            raise ToolFailure(not_logged_in())
        token = record.get("access_token")
        expires_at = record.get("expires_at")
        if (
            isinstance(token, str)
            and token
            and isinstance(expires_at, (int, float))
            and expires_at - EXPIRY_SKEW > self._now()
        ):
            return token
        refreshed = await self._refresh_user_token(record)
        token = refreshed.get("access_token")
        if not isinstance(token, str) or not token:
            raise ToolFailure(internal_error("the user token refresh"))
        return token

    async def _refresh_user_token(self, record: JSON) -> JSON:
        refresh_token = record.get("refresh_token")
        if not refresh_token:
            raise ToolFailure(not_logged_in())
        client = self._client_secret()
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client["client_id"],
            "client_secret": client["client_secret"],
        }
        data = await self._post_form(TOKEN_ENDPOINT, payload, context="token")
        updated = dict(record)
        for key in ("access_token", "expires_in", "scope", "token_type", "refresh_token"):
            if data.get(key) is not None:
                updated[key] = data[key]
        updated["expires_at"] = self._now() + float(data.get("expires_in") or DEFAULT_LIFETIME)
        self._save_record(updated)
        return updated

    # ------------------------------------------------------------------ #
    # identity + delegation + Keep token
    # ------------------------------------------------------------------ #
    async def delegation_subject(self, user_token: str | None = None) -> str:
        """The verified email from ``userinfo``; never a config value."""
        token = user_token or await self.user_access_token()
        client = await self._http()
        try:
            response = await client.get(USERINFO_ENDPOINT, headers={"Authorization": f"Bearer {token}"})
        except httpx.TimeoutException:
            raise ToolFailure(transient(f"{USERINFO_ENDPOINT} did not answer within {self._timeout:g}s")) from None
        except httpx.HTTPError as exc:
            raise ToolFailure(transient(f"could not reach {USERINFO_ENDPOINT} ({type(exc).__name__}: {exc})")) from None
        if response.status_code >= 400:
            if response.status_code in (401, 403):
                raise ToolFailure(
                    auth_setup_error(
                        "identity_unavailable",
                        "Google rejected the user access token while resolving the delegation subject "
                        f"(HTTP {response.status_code}). No browser was opened.",
                        hint="Run `uv run keep-mcp login` to sign in again.",
                    )
                )
            raise ToolFailure(
                from_http(response.status_code, _safe_json(response), context="token", retry_after=_retry_after(response))
            )
        info = _safe_json(response)
        email = info.get("email")
        if not info.get("email_verified"):
            raise ToolFailure(
                auth_setup_error(
                    "identity_unverified",
                    "Google did not report a verified email for the logged-in user, so no delegation "
                    "subject can be trusted.",
                    hint="Log in with a Google Workspace account whose email is verified.",
                )
            )
        if not isinstance(email, str) or not email:
            raise ToolFailure(
                auth_setup_error(
                    "identity_missing",
                    "The userinfo response contained no email address.",
                    hint="Run `uv run keep-mcp login` again.",
                )
            )
        return email

    async def _sign_jwt(self, user_token: str, subject: str) -> str:
        service_account = self._config.service_account
        issued = int(self._now())
        claims = {
            "iss": service_account,
            "sub": subject,
            "aud": TOKEN_ENDPOINT,
            "scope": KEEP_SCOPE,
            "iat": issued,
            "exp": issued + 3600,
        }
        url = f"{IAM_BASE}/projects/-/serviceAccounts/{service_account}:signJwt"
        client = await self._http()
        try:
            response = await client.post(
                url,
                json={"payload": json.dumps(claims)},
                headers={"Authorization": f"Bearer {user_token}"},
            )
        except httpx.TimeoutException:
            raise ToolFailure(transient(f"{url} did not answer within {self._timeout:g}s")) from None
        except httpx.HTTPError as exc:
            raise ToolFailure(transient(f"could not reach the IAM Credentials API ({type(exc).__name__}: {exc})")) from None
        if response.status_code >= 400:
            raise ToolFailure(
                from_http(
                    response.status_code,
                    _safe_json(response),
                    context="signjwt",
                    retry_after=_retry_after(response),
                )
            )
        signed = _safe_json(response).get("signedJwt")
        if not isinstance(signed, str) or not signed:
            raise ToolFailure(internal_error("the signJwt response"))
        return signed

    async def _exchange_assertion(self, assertion: str) -> JSON:
        payload = {"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion}
        data = await self._post_form(TOKEN_ENDPOINT, payload, context="token")
        if not data.get("access_token"):
            raise ToolFailure(delegation_missing())
        return data

    async def keep_access_token(self) -> str:
        """A Keep access token, derived at most once per hour (and once per call burst)."""
        async with self._keep_lock:
            if self._keep_token and self._keep_expires_at - EXPIRY_SKEW > self._now():
                return self._keep_token
            user_token = await self._user_token_locked()
            subject = await self.delegation_subject(user_token)
            assertion = await self._sign_jwt(user_token, subject)
            data = await self._exchange_assertion(assertion)
            self._keep_token = str(data["access_token"])
            self._keep_expires_at = self._now() + float(data.get("expires_in") or DEFAULT_LIFETIME)
            logger.debug("derived a Keep token for %s", subject)
            return self._keep_token

    # ------------------------------------------------------------------ #
    # login flow (the only place a browser is ever opened)
    # ------------------------------------------------------------------ #
    def build_authorization_url(self, *, redirect_uri: str, state: str, code_challenge: str) -> str:
        params = {
            "client_id": self._client_secret()["client_id"],
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(LOGIN_SCOPES),
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{AUTHORIZATION_ENDPOINT}?{urlencode(params)}"

    def _await_callback(self, *, state: str, challenge: str, timeout_seconds: float) -> tuple[str, str]:
        """Serve one localhost redirect and return ``(code, redirect_uri)``."""
        server = ThreadingHTTPServer(("127.0.0.1", 0), _CallbackHandler)
        server.captured = None  # type: ignore[attr-defined]
        port = server.server_address[1]
        redirect_uri = f"http://127.0.0.1:{port}/callback"
        url = self.build_authorization_url(redirect_uri=redirect_uri, state=state, code_challenge=challenge)
        opener = self._open_browser or webbrowser.open
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True)
        thread.start()
        try:
            print(
                "Opening your browser for Google sign-in.\n"
                "If nothing opens, paste this URL into a browser:\n"
                f"  {url}\n"
                f"Waiting for the redirect to {redirect_uri} ...",
                file=sys.stderr,
            )
            try:
                opened = opener(url)
            except Exception as exc:  # pragma: no cover - environment specific
                logger.warning("could not open a browser (%s); use the URL above", exc)
                opened = False
            if not opened:
                print("Could not open a browser automatically; use the URL above.", file=sys.stderr)
            deadline = time.monotonic() + timeout_seconds
            while server.captured is None and time.monotonic() < deadline:
                time.sleep(0.1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        captured: JSON = server.captured or {}  # type: ignore[attr-defined]
        if not captured:
            raise AuthLoginError(f"Timed out after {timeout_seconds:g}s waiting for the OAuth redirect.")
        if captured.get("state") != state:
            raise AuthLoginError("The OAuth redirect carried an unexpected state value; refusing to continue.")
        if captured.get("error"):
            detail = captured.get("error_description") or captured["error"]
            raise AuthLoginError(f"Google refused the login: {detail}")
        code = captured.get("code")
        if not code:
            raise AuthLoginError("The OAuth redirect contained no authorization code.")
        return str(code), redirect_uri

    async def login(self, *, timeout_seconds: float = 300.0) -> JSON:
        """Run the interactive authorization-code + PKCE flow and cache the refresh token."""
        client = self._client_secret()
        verifier = pkce_verifier()
        challenge = pkce_challenge(verifier)
        state = secrets.token_urlsafe(24)
        code, redirect_uri = self._await_callback(
            state=state, challenge=challenge, timeout_seconds=timeout_seconds
        )
        data = await self._post_form(
            TOKEN_ENDPOINT,
            {
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": verifier,
                "client_id": client["client_id"],
                "client_secret": client["client_secret"],
                "redirect_uri": redirect_uri,
            },
            context="login",
        )
        if not data.get("refresh_token"):
            raise AuthLoginError(
                "Google returned no refresh token. The consent was probably already granted; "
                "revoke the app's access in your Google Account permissions, then log in again "
                "(the flow requests prompt=consent and access_type=offline)."
            )
        record: JSON = {
            "refresh_token": data["refresh_token"],
            "access_token": data.get("access_token"),
            "expires_in": data.get("expires_in"),
            "scope": data.get("scope"),
            "token_type": data.get("token_type"),
            "client_id": client["client_id"],
            "expires_at": self._now() + float(data.get("expires_in") or DEFAULT_LIFETIME),
        }
        self._save_record(record)
        self._keep_token = None
        self._keep_expires_at = 0.0
        return record
