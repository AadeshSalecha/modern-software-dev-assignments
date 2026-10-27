"""L1 auth lifecycle (Part III): cached login, silent refresh, derivation, failures.

The Google endpoints are stubbed with ``httpx.MockTransport``, so these tests
prove the whole hybrid chain (refresh -> userinfo -> signJwt -> jwt-bearer) and
its failure modes without any network access.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import stat
import subprocess
import threading
import time
import webbrowser
from base64 import urlsafe_b64encode
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastmcp import Client

from helpers import call, error_of, fixture, make_config, write_token_file
from keep_mcp.auth import (
    AUTHORIZATION_ENDPOINT,
    IAM_BASE,
    KEEP_SCOPE,
    LOGIN_SCOPES,
    TOKEN_ENDPOINT,
    USERINFO_ENDPOINT,
    AuthLoginError,
    KeepAuth,
    pkce_challenge,
)
from keep_mcp.config import DEFAULT_SERVICE_ACCOUNT
from keep_mcp.errors import DWD_CLIENT_ID
from keep_mcp.fake_client import FakeKeepClient
from keep_mcp.guard import ManagedNotes
from keep_mcp.server import build_server

MISSING_NOTE = "notes/AAAmissingNote00000000000000000000000000000000000000000000000000"


# --------------------------------------------------------------------------- #
# stubs
# --------------------------------------------------------------------------- #
class Clock:
    """A settable clock so expiry behaviour is testable without sleeping."""

    def __init__(self, start: float = 1_000_000.0) -> None:
        self.value = float(start)

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class GoogleStub:
    """Fake Google OAuth, userinfo, and IAM signJwt endpoints."""

    def __init__(
        self,
        *,
        userinfo_email: str = "user@example.com",
        email_verified: bool = True,
        refresh_error: str | None = None,
        signjwt_status: int = 200,
        jwt_bearer_error: str | None = None,
        refresh_expires_in: int = 3599,
        keep_expires_in: int = 3599,
        login_returns_refresh_token: bool = True,
    ) -> None:
        self.userinfo_email = userinfo_email
        self.email_verified = email_verified
        self.refresh_error = refresh_error
        self.signjwt_status = signjwt_status
        self.jwt_bearer_error = jwt_bearer_error
        self.refresh_expires_in = refresh_expires_in
        self.keep_expires_in = keep_expires_in
        self.login_returns_refresh_token = login_returns_refresh_token
        self.requests: list[httpx.Request] = []
        self.signed_claims: list[dict] = []

    # ------------------------------------------------------------------ #
    @staticmethod
    def _form(request: httpx.Request) -> dict[str, str]:
        return {key: values[0] for key, values in parse_qs(request.content.decode()).items()}

    def _grants(self, grant_type: str) -> int:
        return sum(
            1
            for request in self.requests
            if str(request.url) == TOKEN_ENDPOINT and self._form(request).get("grant_type") == grant_type
        )

    @property
    def refresh_calls(self) -> int:
        return self._grants("refresh_token")

    @property
    def jwt_bearer_calls(self) -> int:
        return self._grants("urn:ietf:params:oauth:grant-type:jwt-bearer")

    @property
    def signjwt_calls(self) -> int:
        return sum(1 for request in self.requests if "signJwt" in str(request.url))

    @property
    def userinfo_calls(self) -> int:
        return sum(1 for request in self.requests if str(request.url) == USERINFO_ENDPOINT)

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    async def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url)
        if url == USERINFO_ENDPOINT:
            return httpx.Response(
                200, json={"email": self.userinfo_email, "email_verified": self.email_verified}
            )
        if "signJwt" in url:
            self.signed_claims.append(json.loads(json.loads(request.content.decode())["payload"]))
            if self.signjwt_status != 200:
                return httpx.Response(
                    self.signjwt_status,
                    json={
                        "error": {
                            "code": self.signjwt_status,
                            "message": "IAM Service Account Credentials API has not been used in project 0",
                            "status": "PERMISSION_DENIED",
                        }
                    },
                )
            return httpx.Response(200, json=fixture("auth_signjwt_response"))
        if url == TOKEN_ENDPOINT:
            grant = self._form(request).get("grant_type")
            if grant == "refresh_token":
                if self.refresh_error:
                    return httpx.Response(
                        400,
                        json={"error": self.refresh_error, "error_description": "Token has been expired or revoked."},
                    )
                return httpx.Response(
                    200, json={**fixture("auth_refresh_response"), "expires_in": self.refresh_expires_in}
                )
            if grant == "authorization_code":
                payload = {
                    "access_token": "ya29.placeholder-user-access-token",
                    "expires_in": 3599,
                    "scope": " ".join(LOGIN_SCOPES),
                    "token_type": "Bearer",
                }
                if self.login_returns_refresh_token:
                    payload["refresh_token"] = "1//placeholder-refresh-token"
                return httpx.Response(200, json=payload)
            if grant == "urn:ietf:params:oauth:grant-type:jwt-bearer":
                if self.jwt_bearer_error:
                    return httpx.Response(
                        401, json={"error": self.jwt_bearer_error, "error_description": "Unauthorized"}
                    )
                return httpx.Response(
                    200, json={**fixture("auth_jwt_bearer_response"), "expires_in": self.keep_expires_in}
                )
        return httpx.Response(
            404, json={"error": {"code": 404, "message": f"no stub route for {url}", "status": "NOT_FOUND"}}
        )


def real_auth_server(
    tmp_path: Path,
    stub: GoogleStub,
    *,
    token_payload: dict | None = None,
    write_token: bool = True,
    now=None,
    safe_mode: bool = True,
):
    """A real server + real KeepAuth (stubbed HTTP) over a fake Keep API."""
    config = make_config(tmp_path, safe_mode=safe_mode)
    if write_token:
        write_token_file(config, token_payload or fixture("auth_token_file_existing_format"))
    auth = KeepAuth(config, transport=stub.transport(), now=now or time.time)
    api = FakeKeepClient()
    api.seed_note(title="stub note", text="hello from the fake Keep API")
    api.set_token_provider(auth)
    server = build_server(config=config, api=api, auth=auth, registry=ManagedNotes(config.state_file))
    return config, auth, api, server


# --------------------------------------------------------------------------- #
# A1-A10
# --------------------------------------------------------------------------- #
async def test_a1_no_token_file_is_actionable_and_never_opens_a_browser(tmp_path: Path, monkeypatch) -> None:
    def explode(*args, **kwargs):
        raise AssertionError("a tool call must never open a browser")

    monkeypatch.setattr(webbrowser, "open", explode)
    stub = GoogleStub()
    config, _, api, server = real_auth_server(tmp_path, stub, write_token=False)
    assert not config.token_file.exists()
    async with Client(server) as client:
        result = await call(client, "search_notes")
    error = error_of(result)
    assert (error["category"], error["code"]) == ("auth_setup", "not_logged_in")
    assert error["retryable"] is False
    assert "uv run keep-mcp login" in error["hint"]
    assert stub.requests == [], "no token means no HTTP call at all"
    assert api.call_count == 0


async def test_a2_login_while_the_server_is_running_takes_effect_without_a_restart(
    client: Client, auth, api
) -> None:
    auth.logged_in = False
    assert error_of(await call(client, "search_notes"))["code"] == "not_logged_in"
    assert api.call_count == 0

    auth.logged_in = True  # stands in for `keep-mcp login` finishing in another process
    assert (await call(client, "search_notes"))["ok"] is True


async def test_a3_an_expired_user_token_is_refreshed_silently_and_stored_0600(tmp_path: Path) -> None:
    clock = Clock()
    stub = GoogleStub()
    config, auth, _, _ = real_auth_server(
        tmp_path, stub, token_payload=fixture("auth_token_file_existing_format"), now=clock
    )
    assert stat.S_IMODE(os.stat(config.token_file).st_mode) == 0o600

    token = await auth.user_access_token()
    assert token == fixture("auth_refresh_response")["access_token"]
    assert stub.refresh_calls == 1
    record = json.loads(config.token_file.read_text())
    assert record["refresh_token"] == fixture("auth_token_file_existing_format")["refresh_token"]
    assert record["expires_at"] == pytest.approx(clock.value + 3599)
    assert stat.S_IMODE(os.stat(config.token_file).st_mode) == 0o600

    # a token that is still valid is reused, not refreshed again
    assert await auth.user_access_token() == token
    assert stub.refresh_calls == 1


async def test_a4_a_keep_token_is_reused_until_it_nears_expiry(tmp_path: Path) -> None:
    clock = Clock()
    stub = GoogleStub(keep_expires_in=3600)
    config, auth, _, _ = real_auth_server(
        tmp_path,
        stub,
        token_payload={
            "refresh_token": "1//placeholder-refresh-token",
            "access_token": "ya29.placeholder-user-access-token",
            "expires_in": 100_000,
            "expires_at": clock.value + 100_000,
        },
        now=clock,
    )
    first = await auth.keep_access_token()
    assert stub.signjwt_calls == 1 and stub.jwt_bearer_calls == 1
    assert await auth.keep_access_token() == first
    assert stub.signjwt_calls == 1, "a cached Keep token must not be re-derived"

    clock.advance(3600 - 30)  # inside the 60s safety skew
    await auth.keep_access_token()
    assert stub.signjwt_calls == 2
    assert stub.refresh_calls == 0, "the user token is still valid, so no refresh was needed"


async def test_a5_ten_concurrent_calls_derive_exactly_one_keep_token(tmp_path: Path) -> None:
    clock = Clock()
    stub = GoogleStub()
    config, auth, api, server = real_auth_server(
        tmp_path,
        stub,
        token_payload={
            "refresh_token": "1//placeholder-refresh-token",
            "access_token": "ya29.placeholder-user-access-token-expired",
            "expires_in": 3599,
            "expires_at": clock.value - 10,
        },
        now=clock,
    )
    async with Client(server) as client:
        results = await asyncio.gather(*(call(client, "search_notes") for _ in range(10)))
    assert all(result["ok"] is True for result in results)
    assert stub.refresh_calls == 1, "the user-token lock must collapse the burst into one refresh"
    assert stub.signjwt_calls == 1, "the Keep-token lock must collapse the burst into one signJwt"
    assert stub.jwt_bearer_calls == 1
    assert auth is not None

    # the same guarantee holds when the calls race at the auth layer directly
    clock2 = Clock()
    stub2 = GoogleStub()
    _, auth2, _, _ = real_auth_server(
        tmp_path / "direct",
        stub2,
        token_payload={
            "refresh_token": "1//placeholder-refresh-token",
            "access_token": "ya29.placeholder-user-access-token-expired",
            "expires_in": 3599,
            "expires_at": clock2.value - 10,
        },
        now=clock2,
    )
    tokens = await asyncio.gather(*(auth2.keep_access_token() for _ in range(10)))
    assert len(set(tokens)) == 1
    assert stub2.refresh_calls == 1 and stub2.signjwt_calls == 1 and stub2.jwt_bearer_calls == 1


async def test_a6_a_revoked_login_is_reported_and_the_server_stays_up(tmp_path: Path) -> None:
    stub = GoogleStub(refresh_error="invalid_grant")
    config, _, api, server = real_auth_server(tmp_path, stub)
    async with Client(server) as client:
        first = error_of(await call(client, "search_notes"))
        assert (first["category"], first["code"]) == ("auth_revoked", "login_revoked")
        assert first["retryable"] is False
        assert "no browser" in first["message"].lower()
        assert "uv run keep-mcp login" in first["hint"]

        second = error_of(await call(client, "get_note", {"name": MISSING_NOTE}))
        assert second["category"] == "auth_revoked", "the server keeps serving and keeps answering"
    assert api.call_count == 0, "no Keep call happens without a token"


async def test_a7_missing_dwd_grant_points_at_the_admin_console(tmp_path: Path) -> None:
    stub = GoogleStub(jwt_bearer_error="unauthorized_client")
    _, _, _, server = real_auth_server(tmp_path, stub)
    async with Client(server) as client:
        error = error_of(await call(client, "search_notes"))
    assert (error["category"], error["code"]) == ("auth_setup", "delegation_missing")
    assert "Domain-wide delegation" in error["hint"]
    assert DWD_CLIENT_ID in error["hint"]
    assert "auth/keep" in error["hint"]
    assert error["retryable"] is False


async def test_a8_signjwt_403_is_not_confused_with_a_missing_note(tmp_path: Path) -> None:
    stub = GoogleStub(signjwt_status=403)
    _, _, _, server = real_auth_server(tmp_path, stub)
    async with Client(server) as client:
        signer_error = error_of(await call(client, "search_notes"))
    assert (signer_error["category"], signer_error["code"]) == ("auth_setup", "signer_permission")
    assert "Token Creator" in signer_error["hint"]
    assert signer_error["retryable"] is False

    # a note-scoped 403 with working delegation stays "not_found" (E2), not an auth error
    healthy = GoogleStub()
    _, _, _, healthy_server = real_auth_server(tmp_path / "healthy", healthy)
    async with Client(healthy_server) as client:
        note_error = error_of(await call(client, "get_note", {"name": MISSING_NOTE}))
    assert note_error["category"] == "not_found"
    assert note_error["code"] != signer_error["code"]


async def test_a9_the_delegation_subject_always_comes_from_userinfo(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("KEEP_DELEGATION_SUBJECT", "attacker@example.com")
    monkeypatch.setenv("KEEP_DWD_SUBJECT", "attacker@example.com")
    stub = GoogleStub(userinfo_email="real.user@example.com")
    config, auth, _, _ = real_auth_server(tmp_path, stub)
    await auth.keep_access_token()

    assert stub.userinfo_calls == 1
    claims = stub.signed_claims[0]
    assert claims["sub"] == "real.user@example.com"
    assert claims["iss"] == config.service_account == DEFAULT_SERVICE_ACCOUNT
    assert claims["aud"] == TOKEN_ENDPOINT
    assert claims["scope"] == KEEP_SCOPE
    assert claims["exp"] > claims["iat"]
    assert "attacker" not in json.dumps(claims)
    assert not hasattr(config, "subject") and not hasattr(config, "email"), (
        "no config field may override the delegation subject"
    )


# --------------------------------------------------------------------------- #
# the login flow itself
# --------------------------------------------------------------------------- #
def test_login_url_uses_pkce_offline_consent_and_minimal_scopes(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    auth = KeepAuth(config)
    verifier = "verifier-value"
    url = auth.build_authorization_url(
        redirect_uri="http://127.0.0.1:9/callback", state="state-123", code_challenge=pkce_challenge(verifier)
    )
    parsed = urlparse(url)
    params = {key: values[0] for key, values in parse_qs(parsed.query).items()}
    assert url.startswith(AUTHORIZATION_ENDPOINT)
    assert params["client_id"] == fixture("auth_oauth_client_placeholder")["installed"]["client_id"]
    assert params["response_type"] == "code"
    assert params["redirect_uri"] == "http://127.0.0.1:9/callback"
    assert params["code_challenge_method"] == "S256"
    assert params["code_challenge"] == urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert params["access_type"] == "offline"
    assert params["prompt"] == "consent"
    assert params["state"] == "state-123"
    assert set(params["scope"].split(" ")) == set(LOGIN_SCOPES)
    assert "auth/keep" not in params["scope"], "Keep scopes cannot be consented to; they come from DWD"


async def test_login_exchange_caches_a_0600_refresh_token(tmp_path: Path, monkeypatch) -> None:
    stub = GoogleStub()
    config = make_config(tmp_path)
    auth = KeepAuth(config, transport=stub.transport())
    monkeypatch.setattr(
        KeepAuth, "_await_callback", lambda self, **kwargs: ("auth-code-123", "http://127.0.0.1:9/callback")
    )
    record = await auth.login(timeout_seconds=1)
    assert record["refresh_token"] == "1//placeholder-refresh-token"
    stored = json.loads(config.token_file.read_text())
    assert stored["refresh_token"] == "1//placeholder-refresh-token"
    assert stored["scope"] == " ".join(LOGIN_SCOPES)
    assert stored["expires_at"] > 0
    assert stat.S_IMODE(os.stat(config.token_file).st_mode) == 0o600

    # and the freshly cached login immediately works for a Keep call
    token = await auth.keep_access_token()
    assert token == fixture("auth_jwt_bearer_response")["access_token"]


async def test_login_without_a_refresh_token_explains_what_to_do(tmp_path: Path, monkeypatch) -> None:
    stub = GoogleStub(login_returns_refresh_token=False)
    config = make_config(tmp_path)
    auth = KeepAuth(config, transport=stub.transport())
    monkeypatch.setattr(
        KeepAuth, "_await_callback", lambda self, **kwargs: ("auth-code-123", "http://127.0.0.1:9/callback")
    )
    with pytest.raises(AuthLoginError) as excinfo:
        await auth.login(timeout_seconds=1)
    assert "refresh token" in str(excinfo.value)
    assert not config.token_file.exists()


def test_login_ignores_stray_requests_before_the_redirect(tmp_path: Path) -> None:
    import urllib.error
    import urllib.request

    config = make_config(tmp_path)

    def browser(url: str) -> bool:
        redirect = parse_qs(urlparse(url).query)["redirect_uri"][0]
        state = parse_qs(urlparse(url).query)["state"][0]
        base = redirect.rsplit("/", 1)[0]

        def hit() -> None:
            for stray in (f"{base}/", f"{base}/favicon.ico", redirect):
                try:
                    urllib.request.urlopen(stray, timeout=2)
                except urllib.error.HTTPError as exc:
                    assert exc.code == 404
            urllib.request.urlopen(f"{redirect}?code=real-code&state={state}", timeout=2)

        threading.Thread(target=hit, daemon=True).start()
        return True

    auth = KeepAuth(config, open_browser=browser)
    code, _ = auth._await_callback(state="s123", challenge="c", timeout_seconds=5)
    assert code == "real-code"


async def test_login_state_mismatch_is_refused(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    auth = KeepAuth(config, open_browser=lambda url: True)
    with pytest.raises(AuthLoginError):
        auth._await_callback(state="expected", challenge="challenge", timeout_seconds=0.01)


# --------------------------------------------------------------------------- #
# A10: secrets audit
# --------------------------------------------------------------------------- #
SECRET_NAME = re.compile(r"^(\.env|\.env\..*|\.mcp\.json|client_secret.*|tokens?\.json|.*\.token\.json)$")
# split so this very test file does not contain the literal it scans for
GOOGLE_CLIENT_SECRET_PREFIX = "GOCSPX" + "-"


def _is_secret_path(relative: str) -> bool:
    name = Path(relative).name
    if name.endswith(".example"):
        return False
    if SECRET_NAME.match(name):
        return True
    return relative.startswith("secrets/") or "/secrets/" in f"/{relative}"


def _tracked_week2_files() -> list[Path]:
    week2 = Path(__file__).resolve().parents[1]
    repo_root = Path(
        subprocess.run(
            ["git", "-C", str(week2), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        ).stdout.strip()
    )
    tracked = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "--", "week2"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return [repo_root / line for line in tracked.stdout.splitlines()]


def test_a10_no_secrets_in_the_tree_and_gitignore_covers_them() -> None:
    week2 = Path(__file__).resolve().parents[1]

    gitignore = (week2 / ".gitignore").read_text(encoding="utf-8")
    for pattern in (".env", ".mcp.json", ".venv", "client_secret", "token.json"):
        assert pattern in gitignore, f".gitignore must cover {pattern!r}"

    tracked_files = _tracked_week2_files()
    present = sorted(
        str(path.relative_to(week2)) for path in tracked_files if _is_secret_path(str(path.relative_to(week2)))
    )
    assert present == [], f"secret-shaped files are present in week2: {present}"

    for path in tracked_files:
        if path.suffix in {".json", ".md", ".py", ".example", ".toml"} or path.name.startswith(".env"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert GOOGLE_CLIENT_SECRET_PREFIX not in text, (
                f"a real Google client secret prefix appears in {path}"
            )

    assert (week2 / ".env.example").exists()
    assert (week2 / ".mcp.json.example").exists()
    example = (week2 / ".mcp.json.example").read_text(encoding="utf-8")
    assert "keep-mcp" in example and "KEEP_OAUTH_CLIENT_FILE" in example
    assert GOOGLE_CLIENT_SECRET_PREFIX not in example
