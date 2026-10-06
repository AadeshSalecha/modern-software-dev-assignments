"""Runtime configuration for keep-mcp.

Everything is read from the environment (plus an optional `week2/.env`, which is
gitignored). No secret ever has a default value baked into the code.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SERVICE_ACCOUNT = "keep-mcp-probe@keep-mcp-week2.iam.gserviceaccount.com"
DEFAULT_CLIENT_FILE = "~/.config/keep-mcp/client_secret.json"
DEFAULT_TOKEN_FILE = "~/.local/state/keep-mcp/token.json"
DEFAULT_STATE_FILE = "~/.local/state/keep-mcp/managed_notes.json"
KEEP_BASE_URL = "https://keep.googleapis.com/v1"

# week2/.env (src/keep_mcp/config.py -> src -> week2)
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

_TRUTHY = {"1", "true", "yes", "on"}


def load_env_file(path: Path | None = None) -> None:
    """Load ``KEY=VALUE`` lines into ``os.environ`` without overriding real env vars."""
    env_path = path or ENV_FILE
    try:
        raw = env_path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _flag(value: str | None, default: bool = True) -> bool:
    if value is None or not value.strip():
        return default
    return value.strip().lower() in _TRUTHY


@dataclass(frozen=True, slots=True)
class Config:
    """Resolved server settings."""

    oauth_client_file: Path | None
    token_file: Path
    state_file: Path
    service_account: str = DEFAULT_SERVICE_ACCOUNT
    safe_mode: bool = True
    keep_base_url: str = KEEP_BASE_URL

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Config:
        load_env_file()
        source = env if env is not None else os.environ
        client = source.get("KEEP_OAUTH_CLIENT_FILE")
        return cls(
            oauth_client_file=Path(client or DEFAULT_CLIENT_FILE).expanduser(),
            token_file=Path(source.get("KEEP_TOKEN_FILE") or DEFAULT_TOKEN_FILE).expanduser(),
            state_file=Path(source.get("KEEP_STATE_FILE") or DEFAULT_STATE_FILE).expanduser(),
            service_account=source.get("KEEP_DWD_SERVICE_ACCOUNT") or DEFAULT_SERVICE_ACCOUNT,
            safe_mode=_flag(source.get("KEEP_SAFE_MODE")),
        )
