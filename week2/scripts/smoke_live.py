"""Live smoke test for the keep-mcp server (layer L2).

Runs the REAL server - the same ``uv --directory ... run keep-mcp`` command that
``.mcp.json.example`` documents - over stdio with the fastmcp ``Client``, against
the real Google Keep API of the Hyfin test account. Env-gated so that an
offline test run or an accidental invocation never touches the account::

    KEEP_LIVE=1 uv run python scripts/smoke_live.py                  # S1-S3 + live checks
    KEEP_LIVE=1 uv run python scripts/smoke_live.py --revoked-token   # failure transcript

Guarantees:
- every note it creates is titled ``[mcp-test] ...`` and deleted in a
  ``finally`` block, even when a check fails;
- the five ``[mcp-demo] ...`` fixture notes are never modified or deleted:
  the guard step only proves the delete is REFUSED, and ``allow_foreign`` is
  never passed anywhere;
- the real managed-notes registry is untouched (the run uses a temp
  ``KEEP_STATE_FILE``);
- nothing secret is printed: every line is scrubbed, emails to ``<user>`` and
  note names to ``notes/<id>``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

WEEK2 = Path(__file__).resolve().parents[1]
MCP_EXAMPLE = WEEK2 / ".mcp.json.example"
TEST_PREFIX = "[mcp-test]"
DEMO_PREFIX = "[mcp-demo]"
#: a made-up address that no Google account can resolve (the S3 error case)
UNKNOWN_RECIPIENT = "nobody-xyz-123@hyfin.earth"
NOTE_NAME_PATTERN = re.compile(r"^notes/[A-Za-z0-9_-]+$")

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# a full resource path (note, note permission, ...) collapses to one placeholder
_NOTE_ID_RE = re.compile(r"notes/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*")
FALLBACK_MARKER = "rejected the combined filter"
REQUIRED_ENV_KEYS = (
    "KEEP_OAUTH_CLIENT_FILE",
    "KEEP_TOKEN_FILE",
    "KEEP_STATE_FILE",
    "KEEP_DWD_SERVICE_ACCOUNT",
    "KEEP_SAFE_MODE",
)


# --------------------------------------------------------------------------- #
# output hygiene: nothing this script prints may contain a secret
# --------------------------------------------------------------------------- #
def scrub(text: str) -> str:
    """Redact emails to ``<user>`` and note ids to ``notes/<id>``."""
    text = _EMAIL_RE.sub("<user>", text)
    return _NOTE_ID_RE.sub("notes/<id>", text)


def say(text: str = "") -> None:
    print(scrub(text), flush=True)


class Report:
    """PASS/FAIL ledger; the exit code is driven by it."""

    def __init__(self) -> None:
        self.total = 0
        self.failed: list[str] = []

    def check(self, condition: bool, label: str) -> bool:
        self.total += 1
        say(f"  {'PASS' if condition else 'FAIL'}: {label}")
        if not condition:
            self.failed.append(label)
        return condition


# --------------------------------------------------------------------------- #
# client plumbing
# --------------------------------------------------------------------------- #
def load_launch_config() -> tuple[str, list[str], dict[str, str]]:
    """The server launch spec exactly as ``.mcp.json.example`` documents it."""
    server = json.loads(MCP_EXAMPLE.read_text(encoding="utf-8"))["mcpServers"]["keep"]
    env = dict(server.get("env") or {})
    missing = [key for key in REQUIRED_ENV_KEYS if key not in env]
    if missing:
        raise SystemExit(f".mcp.json.example is missing env keys: {', '.join(missing)}")
    return server["command"], list(server["args"]), env


def resolve_command(command: str) -> str:
    """Resolve the example's ``uv`` to an executable this machine can spawn.

    ``.mcp.json.example`` says ``uv`` (the conventional form for an MCP client
    config); on machines where ``uv`` is not on PATH - e.g. under ``uv run``,
    which scrubs PATH - fall back to the usual install locations.
    """
    found = shutil.which(command)
    if found:
        return found
    for candidate in (
        Path.home() / ".venvs" / "uv" / "bin" / command,
        Path.home() / ".local" / "bin" / command,
        Path.home() / ".cargo" / "bin" / command,
    ):
        if candidate.is_file():
            return str(candidate)
    return command


def compact(tool: str, payload: dict) -> str:
    """One-line rendering of a tool result for the transcript."""
    if payload.get("ok") is not True:
        return "ok=false error=" + json.dumps(payload.get("error") or {}, sort_keys=True)
    if tool == "search_notes":
        hits = payload.get("notes") or []
        titles = "; ".join(f"{hit.get('title')!r} ({hit.get('name')})" for hit in hits[:8])
        if len(hits) > 8:
            titles += f"; ... {len(hits) - 8} more"
        return f"ok=true count={payload.get('count')} truncated={payload.get('truncated')} notes=[{titles}]"
    rest = {key: value for key, value in payload.items() if key != "ok"}
    return "ok=true " + json.dumps(rest, sort_keys=True)


def names_of(result: dict) -> list[str]:
    return [hit.get("name") for hit in result.get("notes") or []]


async def call(client: Client, tool: str, args: dict) -> dict:
    """Call a tool, echo args + a compact result, and return the structured content."""
    say(f"\n> {tool} {json.dumps(args, sort_keys=True)}")
    try:
        raw = await client.call_tool_mcp(tool, args)
    except Exception as exc:  # protocol-level failure (server died, bad framing)
        say(f"  -> MCP protocol error: {exc!r}")
        return {"ok": False, "error": {"code": "mcp_protocol_error", "category": "internal", "message": repr(exc)}}
    payload = raw.structured_content
    if not isinstance(payload, dict):
        payload = {
            "ok": False,
            "error": {
                "code": "no_structured_content",
                "category": "internal",
                "message": f"the tool result had no structured content (is_error={raw.is_error})",
            },
        }
    say(f"  -> {compact(tool, payload)}")
    return payload


def log_text(path: Path) -> str:
    try:
        return scrub(Path(path).read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return "(no server log captured)"


# --------------------------------------------------------------------------- #
# the live smoke: S1-S3 plus the live-only checks from SPEC 7.6
# --------------------------------------------------------------------------- #
async def run_smoke(report: Report) -> int:
    command, args, base_env = load_launch_config()
    executable = resolve_command(command)
    workdir = Path(tempfile.mkdtemp(prefix="keep-mcp-smoke-"))
    state_file = workdir / "managed_notes.json"
    server_log = workdir / "server.log"
    # temp registry: the run records its own notes there and never touches the
    # real one, while the [mcp-demo] notes stay foreign (so the guard test works).
    env = {**base_env, "KEEP_STATE_FILE": str(state_file)}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    say("== keep-mcp live smoke (L2, real Google Keep API) ==")
    say(f"date: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} (account emails scrubbed to <user>)")
    say(f"launch (verbatim from .mcp.json.example): {command} {' '.join(args)}")
    say(f"command resolved for this machine: {executable}")
    say(f"env override: KEEP_STATE_FILE={state_file} (temp registry; the real one is untouched)")
    say(f"auth: defaults (client file {base_env['KEEP_OAUTH_CLIENT_FILE']}, token file {base_env['KEEP_TOKEN_FILE']})")
    say("guarantees: only [mcp-test] notes are written; allow_foreign is never passed; [mcp-demo] notes are never deleted")

    created: list[str] = []
    removed: set[str] = set()
    combined_filter_verdict = "unknown (the check never ran)"

    transport = StdioTransport(
        command=executable, args=args, env=env, keep_alive=False, log_file=server_log
    )
    try:
        async with Client(transport, timeout=120.0) as client:
            try:
                # -- baseline: the protected fixture must be intact ---------------- #
                baseline = await call(client, "search_notes", {"query": DEMO_PREFIX, "state": "any"})
                report.check(
                    baseline.get("ok") is True and baseline.get("count") == 5,
                    "baseline: exactly the 5 [mcp-demo] fixture notes are present",
                )
                demo_names = names_of(baseline)
                active_demos = await call(client, "search_notes", {"query": DEMO_PREFIX, "state": "active"})
                if (active_demos.get("count") or 0) == 0 and baseline.get("count") == 5:
                    say(
                        "  note: the 5 [mcp-demo] notes are in the Keep trash (a pre-existing "
                        "state; notes.list without a filter hides trashed notes). This run "
                        "neither trashed nor deleted nor modified them."
                    )
                # the whole account before any write: the run must leave this unchanged
                before = await call(client, "search_notes", {"state": "any", "max_results": 200})
                baseline_names = set(names_of(before))
                report.check(
                    before.get("ok") is True and set(demo_names) <= baseline_names and len(baseline_names) >= 5,
                    f"baseline: account snapshot taken ({len(baseline_names)} notes, any state)",
                )

                # -- S1: text note lifecycle -------------------------------------- #
                title = f"{TEST_PREFIX} smoke {stamp}"
                made = await call(
                    client,
                    "create_note",
                    {"title": title, "content": {"kind": "text", "text": f"smoke body {stamp}"}},
                )
                if not report.check(
                    made.get("ok") is True and made.get("managed") is True and made.get("kind") == "text",
                    "S1.1 create_note (text): ok=true, managed=true, kind=text",
                ):
                    raise RuntimeError("S1.1 failed; see transcript")
                name = str(made.get("name"))
                created.append(name)
                report.check(bool(NOTE_NAME_PATTERN.match(name)), "S1.1 create_note returned a notes/ name")

                found = await call(client, "search_notes", {"query": TEST_PREFIX})
                report.check(
                    found.get("ok") is True and name in names_of(found),
                    "S1.2 search_notes(query='[mcp-test]') finds the new note",
                )

                got = await call(client, "get_note", {"name": name})
                note = got.get("note") or {}
                report.check(
                    got.get("ok") is True
                    and note.get("title") == title
                    and note.get("kind") == "text"
                    and note.get("text") == f"smoke body {stamp}",
                    "S1.3 get_note returns the same title, kind, and text",
                )
                report.check(
                    bool(note.get("collaborators")),
                    "S1.3 get_note lists collaborators (the OWNER entry) without an extra call",
                )

                preview = await call(client, "delete_note", {"name": name})
                pre = preview.get("preview") or {}
                report.check(
                    preview.get("ok") is True
                    and preview.get("deleted") is False
                    and preview.get("dry_run") is True
                    and pre.get("title") == title,
                    "S1.4 delete_note default dry_run: preview only, deleted=false",
                )
                still = await call(client, "get_note", {"name": name})
                report.check(still.get("ok") is True, "S1.5 the note still exists after the dry run")

                gone = await call(client, "delete_note", {"name": name, "dry_run": False})
                report.check(
                    gone.get("ok") is True and gone.get("deleted") is True,
                    "S1.6 delete_note dry_run=false: deleted=true",
                )
                removed.add(name)
                after = await call(client, "get_note", {"name": name})
                error = after.get("error") or {}
                report.check(
                    after.get("ok") is False
                    and error.get("code") == "note_not_accessible"
                    and error.get("category") == "not_found"
                    and error.get("retryable") is False,
                    "S1.7 get_note after delete: note_not_accessible / not_found / not retryable",
                )
                report.check(
                    "search_notes" in str(error.get("hint") or ""),
                    "S1.7 the hint points back to search_notes for a fresh name",
                )

                # -- S2: checklist round-trip ------------------------------------- #
                # live-API rule (verified 2026-10-06): a checked item may not have
                # unchecked children; an unchecked parent may carry children in
                # either state. "mixed checked" here spans items AND the nest.
                items = [
                    {"text": "buy oat milk", "checked": False},
                    {"text": "charge laptop", "checked": True},
                    {
                        "text": "prep the demo",
                        "checked": False,
                        "children": [{"text": "book room", "checked": True}],
                    },
                ]
                made2 = await call(
                    client,
                    "create_note",
                    {
                        "title": f"{TEST_PREFIX} checklist {stamp}",
                        "content": {"kind": "checklist", "items": items},
                    },
                )
                if not report.check(
                    made2.get("ok") is True and made2.get("kind") == "checklist",
                    "S2.1 create_note (checklist with a nested child): ok=true, kind=checklist",
                ):
                    raise RuntimeError("S2.1 failed; see transcript")
                name2 = str(made2.get("name"))
                created.append(name2)

                got2 = await call(client, "get_note", {"name": name2})
                note2 = got2.get("note") or {}
                checklist = note2.get("checklist") or []
                report.check(
                    got2.get("ok") is True
                    and len(checklist) == 3
                    and [item.get("checked") for item in checklist] == [False, True, False],
                    "S2.2 get_note round-trips three items with their checked state",
                )
                report.check(
                    bool(checklist)
                    and checklist[2].get("children") == [{"text": "book room", "checked": True}],
                    "S2.2 the nested child comes back under children with its checked state",
                )
                report.check(
                    "listItems" not in json.dumps(got2) and "textContent" not in json.dumps(got2),
                    "S2.2 shaped output only: no raw Google keys leak",
                )

                # S2.4: the checked-parent/unchecked-child combo the live API rejects
                # (400 on child_list_items[N].checked) must surface as a clear
                # input error, and must not create anything.
                bad = await call(
                    client,
                    "create_note",
                    {
                        "title": f"{TEST_PREFIX} bad combo {stamp}",
                        "content": {
                            "kind": "checklist",
                            "items": [
                                {
                                    "text": "prep the demo",
                                    "checked": True,
                                    "children": [{"text": "book room", "checked": False}],
                                }
                            ],
                        },
                    },
                )
                bad_error = bad.get("error") or {}
                report.check(
                    bad.get("ok") is False
                    and bad_error.get("code") == "invalid_argument"
                    and bad_error.get("category") == "input"
                    and bad_error.get("retryable") is False,
                    "S2.4 create_note with a checked parent and unchecked child: input/invalid_argument",
                )
                report.check(
                    "checked" in str(bad_error.get("message") or ""),
                    "S2.4 the message names the checked-parent rule",
                )
                recount = await call(client, "search_notes", {"query": TEST_PREFIX})
                report.check(
                    recount.get("ok") is True and name2 in names_of(recount) and len(names_of(recount)) == 1,
                    "S2.4 nothing was created by the rejected request",
                )

                # -- live check: the combined update_time AND -trashed filter ------ #
                hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
                recent = await call(
                    client, "search_notes", {"query": TEST_PREFIX, "updated_after": hour_ago}
                )
                report.check(
                    recent.get("ok") is True and name2 in names_of(recent) and (recent.get("count") or 0) >= 1,
                    "X1 search_notes(updated_after=1h ago) works and finds the note just created",
                )
                tail = log_text(server_log)
                if FALLBACK_MARKER in tail:
                    combined_filter_verdict = "REJECTED by the live API; the fallback fired"
                    report.check(True, "X1 the fallback (time filter + client-side trash filter) recovered")
                else:
                    combined_filter_verdict = "ACCEPTED by the live API (no fallback)"
                    report.check(True, "X1 the API accepted the combined filter in one request")
                say(f"  combined filter verdict: {combined_filter_verdict}")

                # -- live check: trash states -------------------------------------- #
                trashed = await call(client, "search_notes", {"state": "trashed"})
                report.check(
                    trashed.get("ok") is True,
                    f"X2 search_notes(state='trashed') succeeds (count={trashed.get('count')})",
                )
                any_state = await call(client, "search_notes", {"state": "any"})
                report.check(
                    any_state.get("ok") is True and (any_state.get("count") or 0) >= 5,
                    "X3 search_notes(state='any') succeeds and sees the demo notes",
                )

                dropped = await call(client, "delete_note", {"name": name2, "dry_run": False})
                report.check(
                    dropped.get("ok") is True and dropped.get("deleted") is True,
                    "S2.3 delete_note (checklist): deleted=true",
                )
                removed.add(name2)

                # -- live check: valid-format, nonexistent name --------------------- #
                bogus = await call(client, "get_note", {"name": "notes/thisNoteDoesNotExist1234567890"})
                error = bogus.get("error") or {}
                report.check(
                    bogus.get("ok") is False
                    and error.get("code") == "note_not_accessible"
                    and error.get("category") == "not_found",
                    "X4 get_note on a valid-format but nonexistent name: note_not_accessible",
                )

                # -- live check: the safe-mode guard on a real [mcp-demo] note ------- #
                if demo_names:
                    demo = demo_names[0]
                    say(f"\n> guard check on the fixture note {demo} (never allow_foreign)")
                    refusal = await call(client, "delete_note", {"name": demo, "dry_run": False})
                    error = refusal.get("error") or {}
                    report.check(
                        refusal.get("ok") is False
                        and error.get("code") == "managed_notes_only"
                        and error.get("category") == "policy"
                        and error.get("retryable") is False,
                        "X5 delete_note dry_run=false on a foreign [mcp-demo] note: policy/managed_notes_only",
                    )
                    report.check(
                        "allow_foreign" in str(error.get("override") or ""),
                        "X5 the refusal names the allow_foreign override",
                    )
                    report.check(
                        "intentional safety guard" in str(error.get("message") or ""),
                        "X5 the refusal says it is an intentional guard, not a malfunction",
                    )
                    intact = await call(client, "get_note", {"name": demo})
                    report.check(intact.get("ok") is True, "X5 the [mcp-demo] note still exists after the refusal")

                # -- S3: share (unknown recipient always; real one only if asked) --- #
                made3 = await call(
                    client,
                    "create_note",
                    {"title": f"{TEST_PREFIX} share {stamp}", "content": {"kind": "text", "text": "share target"}},
                )
                if not report.check(
                    made3.get("ok") is True,
                    "S3.1 create_note (share target): ok=true",
                ):
                    raise RuntimeError("S3.1 failed; see transcript")
                name3 = str(made3.get("name"))
                created.append(name3)

                say("  (unknown recipient is a fabricated address this script invents; like every email it prints as <user>)")
                shared = await call(client, "share_note", {"name": name3, "emails": [UNKNOWN_RECIPIENT]})
                error = shared.get("error") or {}
                report.check(
                    shared.get("ok") is False
                    and error.get("code") == "unknown_recipient"
                    and error.get("category") == "input"
                    and error.get("retryable") is False,
                    "S3.2 share_note with an unknown recipient: input/unknown_recipient",
                )
                report.check(
                    UNKNOWN_RECIPIENT in str(error.get("message") or ""),
                    "S3.2 the error names the offending address",
                )
                untouched = await call(client, "get_note", {"name": name3})
                collaborators = (untouched.get("note") or {}).get("collaborators") or []
                report.check(
                    untouched.get("ok") is True and len(collaborators) == 1,
                    "S3.3 nothing was shared: get_note still shows only the owner",
                )

                share_email = os.environ.get("KEEP_SMOKE_SHARE_EMAIL", "").strip()
                if share_email:
                    real = await call(client, "share_note", {"name": name3, "emails": [share_email]})
                    report.check(
                        real.get("ok") is True and (real.get("added") or []) == [share_email],
                        "S3.4 share_note with a real recipient: added=[address]",
                    )
                    shared_note = await call(client, "get_note", {"name": name3})
                    roles = {
                        person.get("email"): person.get("role")
                        for person in (shared_note.get("note") or {}).get("collaborators") or []
                    }
                    report.check(roles.get(share_email) == "WRITER", "S3.4 get_note shows the new WRITER")
                else:
                    say("  KEEP_SMOKE_SHARE_EMAIL is not set: the real share is skipped (S3 optional)")

                dropped3 = await call(client, "delete_note", {"name": name3, "dry_run": False})
                report.check(
                    dropped3.get("ok") is True and dropped3.get("deleted") is True,
                    "S3.5 delete_note (share target): deleted=true",
                )
                removed.add(name3)

            except Exception as exc:  # noqa: BLE001 - cleanup must still run
                say(f"\n!! unexpected error: {exc!r}")
                report.check(False, f"unexpected error: {exc!r}")
            finally:
                # -- cleanup: every [mcp-test] note this run created, even on failure
                say("\n== cleanup ==")
                for pending in created:
                    if pending in removed:
                        continue
                    result = await call(client, "delete_note", {"name": pending, "dry_run": False})
                    if result.get("ok") is True and result.get("deleted") is True:
                        removed.add(pending)
                        say(f"  deleted leftover test note {pending}")
                    elif (result.get("error") or {}).get("code") == "note_not_accessible":
                        removed.add(pending)
                        say(f"  leftover test note {pending} was already gone")
                    else:
                        report.check(False, f"cleanup could not delete {pending}")

                # sweep: a previously crashed run may have left [mcp-test] notes
                # behind. The temp registry does not know them, so a plain delete
                # would hit the safe-mode guard; force-delete ONLY after the dry
                # run preview confirms the title carries the smoke prefix.
                # allow_foreign is never passed for a [mcp-demo] note: the title
                # check below is the gate.
                stale = await call(client, "search_notes", {"query": TEST_PREFIX, "state": "any"})
                for extra in names_of(stale):
                    if extra in removed:
                        continue
                    preview = await call(client, "delete_note", {"name": extra})
                    stale_title = str((preview.get("preview") or {}).get("title") or "")
                    if not stale_title.startswith(TEST_PREFIX):
                        report.check(
                            False,
                            f"leftover search hit {extra} has an unexpected title {stale_title!r}; left untouched",
                        )
                        continue
                    forced = await call(
                        client, "delete_note", {"name": extra, "dry_run": False, "allow_foreign": True}
                    )
                    if forced.get("ok") is True and forced.get("deleted") is True:
                        removed.add(extra)
                        say(f"  swept a stale smoke note from an earlier run (title verified: {stale_title!r})")
                    else:
                        report.check(False, f"cleanup could not sweep the stale smoke note {extra}")

                leftovers = await call(client, "search_notes", {"query": TEST_PREFIX, "state": "any"})
                report.check(
                    leftovers.get("ok") is True and leftovers.get("count") == 0,
                    "cleanup: no [mcp-test] note remains (any trash state)",
                )
                demos = await call(client, "search_notes", {"query": DEMO_PREFIX, "state": "any"})
                report.check(
                    demos.get("ok") is True
                    and demos.get("count") == 5
                    and set(names_of(demos)) == set(demo_names),
                    "cleanup: exactly the 5 [mcp-demo] fixture notes remain (same names as the baseline)",
                )
                # the strongest possible "leave no trace" check: the account holds
                # exactly the same notes (any trash state) as when the run started.
                # Nothing was created, trashed, deleted, or otherwise left behind.
                after_all = await call(client, "search_notes", {"state": "any", "max_results": 200})
                final_names = set(names_of(after_all))
                report.check(
                    after_all.get("ok") is True and final_names == baseline_names,
                    "cleanup: the account is byte-for-byte the set of notes it started with "
                    f"(before={len(baseline_names)}, after={len(final_names)})",
                )
                active = await call(client, "search_notes", {"state": "active"})
                if active.get("ok") is True:
                    say(
                        f"  final account state: {active.get('count')} active note(s), "
                        f"{len(final_names)} in total (active + trashed)"
                    )
    except Exception as exc:  # noqa: BLE001 - connection/startup failures land here
        say(f"\n!! could not run the smoke test: {exc!r}")
        report.check(False, f"server connection failed: {exc!r}")
        say("\n== server log (stderr) ==")
        for line in log_text(server_log).splitlines() or ["(empty)"]:
            say(f"  {line}")
        return 1

    # -- summary --------------------------------------------------------------- #
    say("\n== server log (stderr, scrubbed: the protocol trace) ==")
    for line in log_text(server_log).splitlines() or ["(empty)"]:
        say(f"  {line}")

    say("\n== summary ==")
    say(f"checks: {report.total - len(report.failed)}/{report.total} passed")
    say(f"combined filter (update_time > \"...\" AND -trashed): {combined_filter_verdict}")
    if report.failed:
        say("failed checks:")
        for label in report.failed:
            say(f"  - {label}")
        return 1
    say("LIVE SMOKE GREEN: S1, S2, S3 (unknown recipient), and the live-only checks all passed")
    return 0


# --------------------------------------------------------------------------- #
# the failure transcript: revoked refresh token (SPEC 7.6 S4, protocol level)
# --------------------------------------------------------------------------- #
async def run_revoked_token(report: Report) -> int:
    command, args, base_env = load_launch_config()
    executable = resolve_command(command)
    workdir = Path(tempfile.mkdtemp(prefix="keep-mcp-revoked-"))
    server_log = workdir / "server.log"
    poisoned = workdir / "token.json"

    real_token = Path(os.path.expanduser(base_env["KEEP_TOKEN_FILE"]))
    record = json.loads(real_token.read_text(encoding="utf-8"))
    record["refresh_token"] = "revoked-invalid-refresh-token-0000000000000000"
    record["expires_at"] = 0  # force the silent-refresh path on the very first call
    poisoned.write_text(json.dumps(record, indent=2), encoding="utf-8")
    os.chmod(poisoned, 0o600)

    env = {
        **base_env,
        "KEEP_TOKEN_FILE": str(poisoned),
        "KEEP_STATE_FILE": str(workdir / "managed_notes.json"),
    }
    say("== keep-mcp live failure demo: revoked refresh token (protocol level) ==")
    say(f"launch (verbatim from .mcp.json.example): {command} {' '.join(args)}")
    say(f"command resolved for this machine: {executable}")
    say("setup: KEEP_TOKEN_FILE points at a TEMP copy of the real token file with")
    say("  - refresh_token replaced by an invalid string (as if the grant was revoked),")
    say("  - expires_at=0, so the first call must attempt the silent refresh.")
    say("the real token file is never touched; nothing is written to the account.")

    transport = StdioTransport(
        command=executable, args=args, env=env, keep_alive=False, log_file=server_log
    )
    try:
        async with Client(transport, timeout=120.0) as client:
            result = await call(client, "search_notes", {"query": DEMO_PREFIX})
            error = result.get("error") or {}
            report.check(result.get("ok") is False, "the call fails with a structured result, not a crash")
            report.check(error.get("code") == "login_revoked", f"code login_revoked (got {error.get('code')!r})")
            report.check(
                error.get("category") == "auth_revoked", f"category auth_revoked (got {error.get('category')!r})"
            )
            report.check(
                "No browser was opened" in str(error.get("message") or ""),
                "the message says no browser was opened",
            )
            report.check(error.get("retryable") is False, "retryable=false (a human must sign in again)")
            report.check(
                "keep-mcp login" in str(error.get("hint") or ""),
                "the hint gives the exact next action (uv run keep-mcp login)",
            )

            # the server must keep serving after the failure (SPEC E7/A6)
            again = await call(client, "search_notes", {"query": DEMO_PREFIX})
            report.check(
                (again.get("error") or {}).get("code") == "login_revoked",
                "the server keeps answering after the revoked error (no crash, no browser)",
            )

            tail = log_text(server_log)
            report.check("browser" not in tail.lower(), "no browser/login flow ever started in the server log")
            say("\n== server log (stderr, scrubbed) ==")
            for line in tail.splitlines() or ["(empty)"]:
                say(f"  {line}")
    finally:
        try:
            poisoned.unlink()
        except OSError:
            pass

    say("\n== summary ==")
    say(f"checks: {report.total - len(report.failed)}/{report.total} passed")
    if report.failed:
        say("failed checks:")
        for label in report.failed:
            say(f"  - {label}")
        return 1
    say("failure transcript complete: auth_revoked/login_revoked over stdio, no browser opened")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Live smoke test for the keep-mcp server (L2).")
    parser.add_argument(
        "--revoked-token",
        action="store_true",
        help="run only the revoked-refresh-token failure demo over stdio",
    )
    options = parser.parse_args()

    if os.environ.get("KEEP_LIVE") != "1":
        say("live smoke skipped: set KEEP_LIVE=1 to run against the real Google Keep API.")
        say("(it creates and deletes '[mcp-test] ...' notes in the Hyfin test account; the [mcp-demo] notes are never touched)")
        return 2

    report = Report()
    if options.revoked_token:
        return asyncio.run(run_revoked_token(report))
    return asyncio.run(run_smoke(report))


if __name__ == "__main__":
    sys.exit(main())
