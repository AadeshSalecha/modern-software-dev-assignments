"""The real HTTP client: the requests it sends and the taxonomy it maps back.

``httpx.MockTransport`` stands in for the network, so these tests cover
``keep_client.py`` (the only code that would talk to Google) without touching
``keep.googleapis.com``.
"""

from __future__ import annotations

import json

import httpx
import pytest

from helpers import fixture
from keep_mcp.errors import ToolFailure
from keep_mcp.keep_client import HttpKeepClient

BASE = "https://keep.googleapis.com/v1"


class StubTokenProvider:
    def __init__(self, token: str = "keep-access-token") -> None:
        self.token = token
        self.calls = 0

    async def keep_access_token(self) -> str:
        self.calls += 1
        return self.token

    async def aclose(self) -> None:  # pragma: no cover
        return None


def make_client(handler) -> tuple[HttpKeepClient, StubTokenProvider]:
    provider = StubTokenProvider()
    return HttpKeepClient(provider, base_url=BASE, transport=httpx.MockTransport(handler)), provider


async def test_list_notes_sends_page_size_filter_and_bearer_token() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json=fixture("list_empty"))

    api, provider = make_client(handler)
    assert await api.list_notes(page_size=100, filter="-trashed") == {}
    assert seen["method"] == "GET"
    assert seen["url"] == f"{BASE}/notes?pageSize=100&filter=-trashed"
    assert seen["auth"] == "Bearer keep-access-token"
    assert provider.calls == 1


async def test_list_notes_treats_the_empty_body_as_an_empty_list() -> None:
    api, _ = make_client(lambda request: httpx.Response(200, json=fixture("list_empty")))
    assert (await api.list_notes()).get("notes") is None


async def test_note_scoped_calls_hit_the_documented_paths() -> None:
    requests: list[tuple[str, str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content) if request.content else None
        requests.append((request.method, str(request.url), payload or {}))
        return httpx.Response(200, json=fixture("note_text"))

    api, _ = make_client(handler)
    await api.get_note("notes/abc")
    await api.create_note({"title": "t", "body": {"text": {"text": "hi"}}})
    await api.delete_note("notes/abc")
    await api.create_permissions("notes/abc", ["a@example.com"])

    assert requests[0] == ("GET", f"{BASE}/notes/abc", {})
    assert requests[1][0] == "POST" and requests[1][1] == f"{BASE}/notes"
    assert requests[1][2] == {"title": "t", "body": {"text": {"text": "hi"}}}
    assert requests[2] == ("DELETE", f"{BASE}/notes/abc", {})
    assert requests[3][1] == f"{BASE}/notes/abc/permissions:batchCreate"
    assert requests[3][2] == {"requests": [{"permission": {"email": "a@example.com", "role": "WRITER"}}]}


async def test_403_on_a_note_call_maps_to_not_found() -> None:
    api, _ = make_client(lambda request: httpx.Response(403, json=fixture("error_403_note")))
    with pytest.raises(ToolFailure) as excinfo:
        await api.get_note("notes/abc")
    assert (excinfo.value.info.category, excinfo.value.info.code) == ("not_found", "note_not_accessible")


async def test_404_on_a_note_call_also_maps_to_not_found() -> None:
    api, _ = make_client(lambda request: httpx.Response(404, json={}))
    with pytest.raises(ToolFailure) as excinfo:
        await api.delete_note("notes/abc")
    assert excinfo.value.info.category == "not_found"


async def test_unknown_recipient_field_violation_maps_to_input() -> None:
    api, _ = make_client(lambda request: httpx.Response(400, json=fixture("error_400_unknown_recipient")))
    with pytest.raises(ToolFailure) as excinfo:
        await api.create_permissions("notes/abc", ["ghost@example.com"])
    assert (excinfo.value.info.category, excinfo.value.info.code) == ("input", "unknown_recipient")


async def test_invalid_filter_maps_to_input_naming_the_field() -> None:
    api, _ = make_client(lambda request: httpx.Response(400, json=fixture("error_400_invalid_filter")))
    with pytest.raises(ToolFailure) as excinfo:
        await api.list_notes(filter="trashed = false")
    assert excinfo.value.info.category == "input"
    assert "filter" in excinfo.value.info.message


async def test_429_keeps_the_retry_after_header() -> None:
    api, _ = make_client(
        lambda request: httpx.Response(429, json=fixture("error_429_rate_limited"), headers={"Retry-After": "42"})
    )
    with pytest.raises(ToolFailure) as excinfo:
        await api.list_notes()
    assert excinfo.value.info.category == "rate_limited"
    assert excinfo.value.info.retryable is True
    assert excinfo.value.info.retry_after_seconds == 42


async def test_5xx_and_transport_failures_are_transient() -> None:
    api, _ = make_client(lambda request: httpx.Response(503, json=fixture("error_503_unavailable")))
    with pytest.raises(ToolFailure) as excinfo:
        await api.list_notes()
    assert (excinfo.value.info.category, excinfo.value.info.retryable) == ("transient", True)

    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("connection timed out")

    api, _ = make_client(timeout)
    with pytest.raises(ToolFailure) as excinfo:
        await api.list_notes()
    assert (excinfo.value.info.category, excinfo.value.info.retryable) == ("transient", True)


async def test_unexpected_status_becomes_internal_without_leaking_the_body() -> None:
    api, _ = make_client(lambda request: httpx.Response(418, json={"error": {"code": 418, "message": "teapot"}}))
    with pytest.raises(ToolFailure) as excinfo:
        await api.list_notes()
    assert excinfo.value.info.category == "internal"
    assert "teapot" not in excinfo.value.info.message
