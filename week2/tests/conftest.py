"""Fixtures for the offline protocol layer.

Every test in this suite runs the real FastMCP app over real MCP framing (the
in-memory ``fastmcp.Client``), with the API client and the auth provider swapped
for in-memory stand-ins. No network, no browser, no Google account.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastmcp import Client, FastMCP

from keep_mcp.config import Config
from keep_mcp.fake_client import FakeAuth, FakeKeepClient
from keep_mcp.guard import ManagedNotes

from helpers import make_config, make_server


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return make_config(tmp_path)


@pytest.fixture
def api() -> FakeKeepClient:
    return FakeKeepClient()


@pytest.fixture
def registry(config: Config) -> ManagedNotes:
    return ManagedNotes(config.state_file)


@pytest.fixture
def auth() -> FakeAuth:
    return FakeAuth()


@pytest.fixture
def server(config: Config, api: FakeKeepClient, registry: ManagedNotes, auth: FakeAuth) -> FastMCP:
    return make_server(config, api=api, auth=auth, registry=registry)


@pytest.fixture
async def client(server: FastMCP):
    async with Client(server) as connected:
        yield connected
