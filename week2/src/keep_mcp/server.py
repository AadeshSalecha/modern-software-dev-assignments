"""FastMCP server wiring.

``build_server`` is the single seam the tests use: pass a fake ``KeepApi`` and a
fake auth provider and the *same* FastMCP app, tool definitions, schemas, and
docstrings run over real MCP framing in memory.
"""

from __future__ import annotations

import inspect
import logging
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.tools import FunctionTool
from mcp.types import ToolAnnotations

from .auth import KeepAuth, TokenProvider
from .config import Config
from .guard import ManagedNotes
from .keep_client import HttpKeepClient, KeepApi
from .tools import KeepTools

logger = logging.getLogger(__name__)

SERVER_NAME = "keep"
SERVER_VERSION = "0.1.0"

INSTRUCTIONS = """\
Access to the signed-in user's Google Keep account.

Workflow:
1. Start with `search_notes` when the user describes a note by title/content or
   has not supplied a resource name. Use its returned `name` (or the `name` from
   `create_note`) exactly as-is; never invent or rewrite one. If the user supplies
   an explicit `notes/...` resource name, pass it unchanged to `get_note` rather
   than searching for that ID as text.
2. Use `get_note` when the user asks about a note's contents: it returns the shaped
   text or checklist (with `checked` state) plus collaborators. On
   `note_not_accessible`, do not retry the same name; report the error or search
   only if the user asks you to find a different note.
3. `create_note` writes a new note and returns its `name`; pass that `name` to
   `share_note` or `delete_note` in the same turn.
4. `share_note` grants WRITER to the addresses you pass and is idempotent: people
   who already have access come back under `skipped`.
5. `delete_note` is permanent, so it previews by default. Call it with its defaults
   and show the `preview` to the user. Then stop and ask for confirmation: never
   call `dry_run=false` in the same assistant turn as the preview, even if the user
   initially asked to delete the note. Only a clear confirmation in a later user
   turn authorizes the commit. Notes this server did not create are refused unless
   you pass `allow_foreign=true`.

Every tool answers with structured content: `ok=true` plus data, or `ok=false` plus
an `error` object. Branch on `error.category` and `error.retryable`:
- "input" or "policy": do not retry; fix the arguments or ask the user to confirm.
- "not_found": the name is stale or foreign; run `search_notes` again for a fresh one.
- "auth_setup" or "auth_revoked": a human must sign in again (`uv run keep-mcp login`);
  do not retry and do not expect a browser to open.
- "rate_limited" or "transient": retryable; wait `error.retry_after_seconds` (if given)
  and repeat the same call.
- "internal": a bug in this server; `error.message` carries a request id worth reporting.

When `search_notes` returns `truncated=true`, more notes matched than were returned:
narrow `query`, raise `max_results`, or page by raising `updated_after`.
"""

#: annotations per tool: what the agent should assume about side effects
TOOL_ANNOTATIONS: dict[str, ToolAnnotations] = {
    "search_notes": ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    "get_note": ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    "create_note": ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True),
    "delete_note": ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=True),
    "share_note": ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True),
}

CORE_TOOLS: tuple[str, ...] = tuple(TOOL_ANNOTATIONS)


def build_server(
    *,
    config: Config | None = None,
    api: KeepApi | None = None,
    auth: TokenProvider | None = None,
    registry: ManagedNotes | None = None,
) -> FastMCP:
    """Create the MCP server, injecting the API client, auth provider, and registry."""
    resolved = config or Config.from_env()
    provider: TokenProvider = auth if auth is not None else KeepAuth(resolved)
    client: KeepApi = api if api is not None else HttpKeepClient(provider, base_url=resolved.keep_base_url)
    store = registry if registry is not None else ManagedNotes(resolved.state_file)
    tools = KeepTools(api=client, registry=store, safe_mode=resolved.safe_mode)

    mcp = FastMCP(name=SERVER_NAME, version=SERVER_VERSION, instructions=INSTRUCTIONS)
    for name in CORE_TOOLS:
        function = getattr(tools, name)
        # FastMCP parses a docstring and drops its "Args:"/"Returns:" sections
        # from the tool description. Those sections hold half the contract, so
        # pass the whole docstring through explicitly.
        description = inspect.getdoc(function)
        mcp.add_tool(
            FunctionTool.from_function(
                function,
                name=name,
                description=description,
                annotations=TOOL_ANNOTATIONS[name],
            )
        )
    logger.debug("registered %d tools with state file %s", len(CORE_TOOLS), Path(resolved.state_file))
    return mcp


def tool_names() -> tuple[str, ...]:
    """Names of the tools this server exposes."""
    return CORE_TOOLS
