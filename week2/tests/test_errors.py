"""L1 error semantics: every failure is data the agent can branch on (Part II)."""

from __future__ import annotations

import json
from pathlib import Path

from fastmcp import Client

from helpers import call, error_of, fixture, make_config, make_server, raw

# a name that passes the schema but cannot exist
MISSING_NOTE = "notes/AAAmissingNote00000000000000000000000000000000000000000000000000"


async def test_e1_a_malformed_name_is_rejected_by_the_schema_before_any_api_call(client: Client, api) -> None:
    result = await raw(client, "get_note", {"name": "bogus"})
    assert result.is_error is True
    assert result.structured_content is None
    assert api.call_count == 0, "the schema must reject the name before the API is touched"


async def test_e2_403_on_a_note_scoped_call_is_reported_as_not_found(client: Client, api) -> None:
    result = await call(client, "get_note", {"name": MISSING_NOTE})
    error = error_of(result)
    assert (error["category"], error["code"]) == ("not_found", "note_not_accessible")
    assert error["retryable"] is False
    assert "search_notes" in error["hint"]
    assert api.calls_for("GET", MISSING_NOTE), "the API really was called (and really answered 403)"


async def test_e3_an_unknown_share_recipient_names_the_address(tmp_path: Path) -> None:
    from keep_mcp.fake_client import FakeKeepClient

    api = FakeKeepClient(known_emails={"friend@example.com"})
    name = api.seed_note(title="Share me", text="body")
    server = make_server(make_config(tmp_path), api=api)
    async with Client(server) as client:
        result = await call(client, "share_note", {"name": name, "emails": ["ghost@example.com"]})
    error = error_of(result)
    assert (error["category"], error["code"]) == ("input", "unknown_recipient")
    assert "ghost@example.com" in error["message"]
    assert error["retryable"] is False


async def test_e4_rate_limiting_is_retryable_with_the_retry_after_hint(client: Client, api) -> None:
    api.queue_http_error(
        429, payload=fixture("error_429_rate_limited"), retry_after=42, method="GET", path_contains="/notes"
    )
    result = await call(client, "search_notes")
    error = error_of(result)
    assert (error["category"], error["code"]) == ("rate_limited", "rate_limited")
    assert error["retryable"] is True
    assert error["retry_after_seconds"] == 42

    api.queue_http_error(
        429, payload=fixture("error_429_rate_limited"), retry_after=7, method="GET", path_contains="/notes/"
    )
    note_error = error_of(await call(client, "get_note", {"name": MISSING_NOTE}))
    assert note_error["category"] == "rate_limited" and note_error["retry_after_seconds"] == 7


async def test_e5_server_errors_and_timeouts_are_transient(client: Client, api) -> None:
    import httpx

    api.queue_http_error(503, payload=fixture("error_503_unavailable"))
    error = error_of(await call(client, "search_notes"))
    assert (error["category"], error["retryable"]) == ("transient", True)

    api.queue_exception(httpx.ConnectTimeout("connect timed out"))
    error = error_of(await call(client, "search_notes"))
    assert (error["category"], error["retryable"]) == ("transient", True)


async def test_e6_an_unexpected_exception_becomes_internal_without_leaking_it(client: Client, api) -> None:
    api.queue_exception(RuntimeError("secret-traceback-fragment"))
    result = await call(client, "search_notes")
    error = error_of(result)
    assert (error["category"], error["code"]) == ("internal", "internal")
    assert error["retryable"] is False
    blob = json.dumps(result)
    assert "secret-traceback-fragment" not in blob
    assert "Traceback" not in blob and "RuntimeError" not in blob
    assert "request id" in error["message"]

    # the server keeps serving
    assert (await call(client, "search_notes"))["ok"] is True


async def test_e7_errors_are_structured_content_not_protocol_errors(client: Client, api) -> None:
    api.queue_http_error(503, payload=fixture("error_503_unavailable"))
    # raise_on_error=True: an MCP-level error would raise here, ours must not
    result = await client.call_tool("search_notes", {})
    assert result.is_error is False
    assert result.structured_content["ok"] is False
    assert result.structured_content["error"]["category"] == "transient"

    missing = await client.call_tool("get_note", {"name": MISSING_NOTE})
    assert missing.is_error is False
    assert missing.structured_content["error"]["category"] == "not_found"
