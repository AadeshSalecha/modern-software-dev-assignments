#!/usr/bin/env python3
"""What this run has spent and how much room is left: for run.sh, the stop hook and the agent.

    python3 kit/budget.py              one line: money and time used, and what is left
    python3 kit/budget.py --json       the same as JSON
    python3 kit/budget.py --room 0.10  exit status 0 if the run can spend another 0.10 dollars
                                       and stay under its limit
    python3 kit/budget.py --session-room
                                       exit status 0 if the session that asks still has money
                                       and time worth going on with
    python3 kit/budget.py --nudge N [--last FILE]
                                       for the stop hook, which has sent N such messages so far
                                       and saved what the harness handed it in FILE: a message
                                       naming what is still open by the agent's own account
                                       (unticked ledger lines, and cases its last message says
                                       are not covered), while the run has money and the
                                       session time; else nothing
    python3 kit/budget.py --open FILE  those open items, one per line (for a follow-up prompt)

The run has one limit for money and one clock. run.sh exports what is needed:

    KIT_LOGS      folder with the sessions' logs (kit/spend.py prices them)
    KIT_STARTED   when the run started, in epoch seconds
    KIT_MONEY     dollars the whole run means to stay under
    KIT_SESSION   which session is asking: the first part of its log's name (a, b, fix, judge)
    KIT_SHARE     dollars set aside for that session
    KIT_DEADLINE  the second, counted from the start of the run, at which that session is stopped

Money is an estimate from the harnesses' own logs, a little behind for a session that is
still running. Without the variables this prints that it does not know and exits 0: nothing
here may ever fail a session or hold one up.
"""

import glob
import json
import os
import re
import sys
import time

KIT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KIT)
import spend  # noqa: E402

NUDGE_MIN_MONEY = 0.05    # dollars of the session's share still unused
NUDGE_MIN_SECONDS = 75    # seconds before the session is stopped
OPEN_MIN_MONEY = 0.12     # dollars the whole run still has, for a round on what the agent says is open
OPEN = """Budget check (kit/budget.py): the run has about ${left:.2f} left and this session {seconds} s, and
by your own account these are not shown to hold:

{lines}

A case you name as not covered is the most likely place for this job to fail, and there is
room to close it. For each one do one of these, and say which:

- The ticket or `app/contracts` requires it: write the scenario or the query, run it, and fix
  what it shows.
- It cannot be played with the harness (two copies of a service at once, for example): point
  to the lines of your change that make it hold whichever copy runs, or change them so that
  they do.
- Neither the ticket nor a contract requires it: quote the sentence that says so.

Tick a ledger line only after its check has run."""

# What an agent writes when it knows of a gap. Matched per line of its last message.
ADMITS = re.compile(
    r"not covered|not verified|unverified|unproven|untested|(?:not|n't) (?:been )?(?:tested|run|played|exercised)|not proven"
    r"|did(?: not|n't) (?:test|verify|write|run|cover|add|re-?run|play)|only (?:the )?[\w` -]{1,40} (?:case|path) (?:has been|was) (?:run|tested)"
    r"|no scenario|without a scenario|could(?: not|n't) (?:verify|test|reproduce|cover)|cannot be tested|can't be tested"
    r"|have(?: not|n't) (?:tested|verified|covered)|still open|remains? (?:open|untested|unproven)|may still",
    re.IGNORECASE)


def open_ledger_lines():
    """Lines of work/ledger.md that are still `- [ ]`."""
    try:
        with open(os.path.join(os.path.dirname(KIT), "work", "ledger.md"), encoding="utf-8") as handle:
            return [line.strip() for line in handle if line.lstrip().startswith(("- [ ]", "* [ ]"))]
    except OSError:
        return []


def last_message(path):
    """The agent's last message, from what the harness hands a stop hook (its JSON on a file):
    the message itself where the harness gives it, else the last text in the transcript."""
    try:
        with open(path, encoding="utf-8") as handle:
            given = json.load(handle)
    except (OSError, ValueError, TypeError):
        return ""
    if not isinstance(given, dict):
        return ""
    if isinstance(given.get("last_assistant_message"), str):
        return given["last_assistant_message"]
    text = ""
    try:
        with open(given.get("transcript_path") or "", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                message = event.get("message") if isinstance(event, dict) else None
                if event.get("type") == "assistant" and isinstance(message, dict):
                    said = [b.get("text", "") for b in message.get("content") or [] if isinstance(b, dict) and b.get("type") == "text"]
                    if any(said):
                        text = "\n".join(said)
    except OSError:
        return ""
    return text


def admitted_gaps(text):
    """Lines of the agent's last message in which it says something is not covered."""
    found = []
    for line in text.splitlines():
        line = line.strip().lstrip("-*• ").strip()
        if line and ADMITS.search(line) and line not in found:
            found.append(line)
    return found


def number(name, default=None):
    try:
        return float(os.environ[name])
    except (KeyError, ValueError):
        return default


def state():
    """Money and time, or None where run.sh has not said."""
    logs = os.environ.get("KIT_LOGS") or ""
    started = number("KIT_STARTED")
    if not os.path.isdir(logs) or started is None:
        return None
    card = spend.rates()
    sessions = {}
    session = os.environ.get("KIT_SESSION") or ""
    total = mine = 0.0
    for path in spend.in_order(glob.glob(os.path.join(logs, "*.jsonl"))):
        try:
            cost = spend.cost_of(path, card, sessions)
        except Exception:  # noqa: BLE001 - a log that cannot be read costs nothing here
            cost = 0.0
        total += cost
        if session and os.path.basename(path).split(".")[0] == session:
            mine += cost
    seconds = time.time() - started
    money = number("KIT_MONEY")
    share = number("KIT_SHARE")
    deadline = number("KIT_DEADLINE")
    return {
        "spent": round(total, 4),
        "money": money,
        "money_left": None if money is None else round(money - total, 4),
        "session": session or None,
        "session_spent": round(mine, 4),
        "session_share": share,
        "seconds": int(seconds),
        "session_deadline": None if deadline is None else int(deadline),
        "seconds_left": None if deadline is None else int(deadline - seconds),
    }


def line(now):
    if now is None:
        return "budget: not known here (run.sh sets it during a run)"
    parts = [f"the run has spent about ${now['spent']:.2f}"]
    if now["money"] is not None:
        parts[0] += f" of ${now['money']:.2f}"
    if now["session"] and now["session_share"] is not None:
        parts.append(f"this session ${now['session_spent']:.2f} of the ${now['session_share']:.2f} set aside for it")
    parts.append(f"{now['seconds']} s gone")
    if now["seconds_left"] is not None:
        parts.append(f"this session is stopped in {max(now['seconds_left'], 0)} s")
    return "budget: " + "; ".join(parts)


def session_room(now):
    """Dollars this session can still spend: what is left of its share, and never more than the
    run has left. 0.0 where that is not known or the session is about to be stopped."""
    if now is None or now["seconds_left"] is None or now["seconds_left"] < NUDGE_MIN_SECONDS:
        return 0.0
    room = now["money_left"]
    if now["session_share"] is not None:
        unused = now["session_share"] - now["session_spent"]
        room = unused if room is None else min(unused, room)
    return max(room or 0.0, 0.0)


def open_items(said):
    """What the agent itself has left open: unticked ledger lines, and lines of its last
    message that say something is not covered."""
    return ["ledger: " + line for line in open_ledger_lines()] + admitted_gaps(said)


def nudge(now, given=0, said=""):
    """The message for a session that is stopping while, by its own account, something is not
    shown to hold, or an empty string. It is sent while the RUN has money and the session has
    time, whatever is left of the session's own share: that share is a plan, not a limit.
    (There used to be a second message, a fixed list of checks for a session with money left.
    In nine rounds it cost 19 cents and led to no change; this one led to a fix.)"""
    if now is None or now["seconds_left"] is None or now["seconds_left"] < NUDGE_MIN_SECONDS:
        return ""
    run_room = now["money_left"]
    if run_room is None or run_room < OPEN_MIN_MONEY:
        return ""
    gaps = open_items(said)
    if not gaps:
        return ""
    shown = "\n".join("  - " + line[:260] for line in gaps[:8])
    return OPEN.format(left=run_room, seconds=now["seconds_left"], lines=shown)


def main(argv):
    try:
        now = state()
    except Exception:  # noqa: BLE001
        now = None
    if "--json" in argv:
        print(json.dumps(now))
    elif "--nudge" in argv:
        try:
            given = int(argv[argv.index("--nudge") + 1])
        except (IndexError, ValueError):
            given = 0
        said = last_message(argv[argv.index("--last") + 1]) if "--last" in argv and argv.index("--last") + 1 < len(argv) else ""
        text = nudge(now, given, said)
        if text:
            print(text)
    elif "--open" in argv:
        said = last_message(argv[argv.index("--open") + 1]) if argv.index("--open") + 1 < len(argv) else ""
        for item in open_items(said):
            print("- " + item[:260])
    elif "--session-room" in argv:
        return 0 if session_room(now) >= NUDGE_MIN_MONEY else 1
    elif "--room" in argv:
        try:
            wanted = float(argv[argv.index("--room") + 1])
        except (IndexError, ValueError):
            return 2
        if now is None or now["money_left"] is None:
            return 1
        return 0 if now["money_left"] >= wanted else 1
    else:
        print(line(now))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
