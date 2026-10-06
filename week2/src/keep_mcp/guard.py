"""Safe-mode guard: keep-mcp only deletes notes it created, unless told otherwise.

``create_note`` registers every note it makes in a small JSON registry
(``KEEP_STATE_FILE``). ``delete_note`` refuses to commit on a note that is not in
that registry while ``KEEP_SAFE_MODE`` is on. The refusal is a ``policy`` error
that names both escape hatches, so an agent can tell "you are not allowed" apart
from "the API broke" and from "bad input".
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .errors import ErrorInfo, managed_notes_only

VERSION = 1


class ManagedNotes:
    """Registry of the notes this server created, persisted as JSON."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._notes: dict[str, dict[str, Any]] = self._load()

    # ------------------------------------------------------------------ #
    def _load(self) -> dict[str, dict[str, Any]]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, NotADirectoryError):
            return {}
        except (OSError, ValueError):
            # A corrupt registry must never take the server down; refusing
            # deletes (empty registry) is the fail-safe direction.
            return {}
        notes = raw.get("notes") if isinstance(raw, dict) else None
        return dict(notes) if isinstance(notes, dict) else {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.path.parent, 0o700)
        except OSError:  # pragma: no cover - best effort on odd filesystems
            pass
        payload = {"version": VERSION, "notes": self._notes}
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)
        os.chmod(self.path, 0o600)

    # ------------------------------------------------------------------ #
    def contains(self, name: str) -> bool:
        return name in self._notes

    def add(self, name: str, title: str = "") -> None:
        self._notes[name] = {"title": title, "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        self._save()

    def remove(self, name: str) -> None:
        if self._notes.pop(name, None) is not None:
            self._save()

    def names(self) -> list[str]:
        return sorted(self._notes)


def delete_policy(*, name: str, registry: ManagedNotes, safe_mode: bool, allow_foreign: bool) -> ErrorInfo | None:
    """Return the refusal to surface, or ``None`` when the delete is allowed."""
    if not safe_mode or allow_foreign or registry.contains(name):
        return None
    return managed_notes_only(name)
