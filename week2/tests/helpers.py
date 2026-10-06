"""Shared helpers for the offline (L1) test layer."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from fastmcp import Client, FastMCP
from mcp.types import Tool

from keep_mcp.config import DEFAULT_SERVICE_ACCOUNT, Config
from keep_mcp.fake_client import FakeAuth, FakeKeepClient
from keep_mcp.guard import ManagedNotes
from keep_mcp.server import build_server

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> Any:
    """Load a scrubbed probe fixture (``name`` without the ``.json``)."""
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def make_config(tmp_path: Path, **overrides: Any) -> Config:
    base = Config(
        oauth_client_file=FIXTURES / "auth_oauth_client_placeholder.json",
        token_file=tmp_path / "token.json",
        state_file=tmp_path / "managed_notes.json",
        service_account=DEFAULT_SERVICE_ACCOUNT,
        safe_mode=True,
    )
    return replace(base, **overrides) if overrides else base


def write_token_file(config: Config, payload: dict[str, Any] | None = None) -> Path:
    config.token_file.parent.mkdir(parents=True, exist_ok=True)
    config.token_file.write_text(json.dumps(payload or fixture("auth_token_file_existing_format")), encoding="utf-8")
    config.token_file.chmod(0o600)
    return config.token_file


def make_server(
    config: Config,
    *,
    api: FakeKeepClient | None = None,
    auth: FakeAuth | None = None,
    registry: ManagedNotes | None = None,
    wire_auth: bool = True,
) -> FastMCP:
    """Build the real server around fake pieces (same schemas, same docstrings)."""
    client = api if api is not None else FakeKeepClient()
    provider = auth if auth is not None else FakeAuth()
    store = registry if registry is not None else ManagedNotes(config.state_file)
    if wire_auth and isinstance(client, FakeKeepClient):
        client.set_token_provider(provider)
    return build_server(config=config, api=client, auth=provider, registry=store)


async def call(client: Client, tool: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call a tool and return its structured content (``ok`` + data or ``error``)."""
    result = await client.call_tool_mcp(tool, arguments or {})
    assert result.structured_content is not None, (
        f"{tool} returned no structured content (is_error={result.is_error})"
    )
    return result.structured_content


async def raw(client: Client, tool: str, arguments: dict[str, Any] | None = None):
    """Call a tool and return the raw MCP result (for schema-rejection tests)."""
    return await client.call_tool_mcp(tool, arguments or {})


def error_of(result: dict[str, Any]) -> dict[str, Any]:
    assert result["ok"] is False, f"expected ok=false, got {result}"
    error = result["error"]
    assert error is not None
    return error


async def tools_by_name(client: Client) -> dict[str, Tool]:
    return {tool.name: tool for tool in await client.list_tools()}


def note_names(result: dict[str, Any]) -> list[str]:
    return [hit["name"] for hit in result["notes"]]
