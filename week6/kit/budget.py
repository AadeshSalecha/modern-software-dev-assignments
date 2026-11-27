#!/usr/bin/env python3
"""What this run has spent and how much room is left: for run.sh, the stop hook and the agent.

    python3 kit/budget.py              one line: money and time used, and what is left
    python3 kit/budget.py --json       the same as JSON
    python3 kit/budget.py --room 0.10  exit status 0 if the run can spend another 0.10 dollars
                                       and stay under its limit
    python3 kit/budget.py --session-room
                                       exit status 0 if the session that asks still has money
                                       and time worth going on with
    python3 kit/budget.py --nudge N    for the stop hook, which has sent N such messages so far:
                                       a message if this session is stopping with a good part
                                       of its share unused, else nothing. The first lists
                                       checks to spend it on; later ones name the ledger lines
                                       that are still open

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
import sys
import time

KIT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KIT)
import spend  # noqa: E402

NUDGE_MIN_MONEY = 0.05    # dollars of the session's share still unused
NUDGE_MIN_SECONDS = 75    # seconds before the session is stopped
NUDGE = """Budget check (kit/budget.py): this session has used about ${used:.2f} of the ${share:.2f} set aside
for it, and {gone} of its {limit} seconds. Nothing is gained by handing in early, and one missed
case costs far more than everything that is left. Use what is left to look for a miss. Work
through this list in order, and change code only when a check fails:

1. `work/ledger.md`: every line needs a scenario or a query that proves it. Do the lines that
   are not ticked, and the ones ticked on reasoning alone.
2. Each way into the defect, and each case the ticket names ("including ...", "regardless of
   ...", "even when ..."): one scenario each that fails on the shipped release
   (`--release old`) and passes on your change.
3. `python3 kit/rollout.py work/scenarios/*.json --handed-over` and the same with
   `--restarted`. A failure there is a lead, not a verdict: decide it by the ticket.
4. The report: reach the number of entries by a second query that goes another way through
   the tables, and read each sentence of the report request against your script once more.

Stop when the list is done or about a minute is left. `python3 kit/budget.py` shows where you are."""


OPEN = """Budget check (kit/budget.py): about ${left:.2f} and {seconds} s are left for this session, and
`work/ledger.md` still has {count} open line(s):

{lines}

An open line is a requirement you have not shown to hold, and handing in with one is the most
likely way to fail this job. For each: write the scenario or query that proves it and tick the
line, or fix what it shows. If the ticket and `app/contracts` do not require it after all, tick
it and add the sentence that says so. Do not tick a line you have not run a check for."""


def open_ledger_lines():
    """Lines of work/ledger.md that are still `- [ ]`."""
    try:
        with open(os.path.join(os.path.dirname(KIT), "work", "ledger.md"), encoding="utf-8") as handle:
            return [line.strip() for line in handle if line.lstrip().startswith(("- [ ]", "* [ ]"))]
    except OSError:
        return []


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
    for path in sorted(glob.glob(os.path.join(logs, "*.jsonl"))):
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


def nudge(now, given=0):
    """The message for a session that is stopping with room left, or an empty string. `given`
    is how many such messages it has had."""
    room = session_room(now)
    if room < NUDGE_MIN_MONEY or now["session_share"] is None:
        return ""
    if given == 0:
        limit = now["session_deadline"]
        return NUDGE.format(used=now["session_spent"], share=now["session_share"],
                            gone=now["seconds"], limit=limit if limit is not None else "?")
    lines = open_ledger_lines()
    if not lines:
        return ""
    shown = "\n".join("  " + line[:200] for line in lines[:8])
    return OPEN.format(left=room, seconds=now["seconds_left"], count=len(lines), lines=shown)


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
        text = nudge(now, given)
        if text:
            print(text)
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
