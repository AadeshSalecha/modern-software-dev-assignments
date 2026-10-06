"""Console entry point.

``keep-mcp`` (or ``keep-mcp serve``) speaks MCP over stdio. ``keep-mcp login`` is
the only command that opens a browser.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections.abc import Sequence

from .auth import AuthLoginError, KeepAuth
from .config import Config
from .errors import ToolFailure
from .server import build_server


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="keep-mcp", description="MCP server for the official Google Keep API.")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", help="Run the MCP server over stdio (default).")
    sub.add_parser("login", help="Run the one-time Google OAuth login (opens a browser).")
    return parser


def _login() -> int:
    config = Config.from_env()
    auth = KeepAuth(config)
    try:
        record = asyncio.run(auth.login())
    except (AuthLoginError, ToolFailure) as exc:
        message = exc.info.message if isinstance(exc, ToolFailure) else str(exc)
        print(f"keep-mcp login failed: {message}", file=sys.stderr)
        if isinstance(exc, ToolFailure) and exc.info.hint:
            print(f"hint: {exc.info.hint}", file=sys.stderr)
        return 1
    finally:
        try:
            asyncio.run(auth.aclose())
        except RuntimeError:  # pragma: no cover - loop already closed
            pass
    print(f"Logged in. Refresh token cached at {config.token_file} (mode 0600).")
    print(f"Granted scopes: {record.get('scope')}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.command == "login":
        return _login()

    # stdio transport: stdout belongs to JSON-RPC, so the banner stays off.
    build_server().run(transport="stdio", show_banner=False)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
