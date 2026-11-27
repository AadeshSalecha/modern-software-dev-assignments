#!/usr/bin/env python3
"""Check the INC-2318 packet, its truth and the kit's loader against each other.

    python3 crosscheck_2318.py [inc-2318] [--write <dir>]

1. Counts corrupted rows with a small reading of contracts/evidence.md written here
   (not the kit's) and compares with what the generator says it cut.
2. Loads the packet with week6/kit/evidence.py and derives the report the ticket asks for
   from its tables alone: the off periods from the api's endpoint records, the events
   accepted in them from the api's event records, and for each the deliveries any file
   names. Compares it with truth.json, which the generator wrote from what it did.
--write puts the derived report in <dir>/out/impact.json, so judge.py can score it.
Exits 0 when everything agrees.
"""

import json
import os
import sqlite3
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from crosscheck import REPO, corrupted_by_the_contract  # noqa: E402  the rule is the packet format's, not the incident's


def report_from_the_kit(incident):
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "evidence.db")
        done = subprocess.run(
            [sys.executable, os.path.join(REPO, "week6", "kit", "evidence.py"), "build", incident, db_path],
            capture_output=True, text=True,
        )
        if done.returncode != 0:
            raise SystemExit("the kit's loader failed:\n" + done.stdout[-600:] + done.stderr[-600:])
        db = sqlite3.connect(db_path)

        # every switch-on, with the start of the off period it ended
        merchant_of, enabled, since, periods = {}, {}, {}, []
        for endpoint, msg, merchant, on, stamp in db.execute(
            "SELECT endpoint, msg, merchant, enabled, ts_iso FROM api "
            "WHERE msg IN ('endpoint.created', 'endpoint.updated') ORDER BY endpoint, version"
        ):
            if msg == "endpoint.created":
                merchant_of[endpoint] = merchant
                enabled[endpoint] = bool(on)
                since[endpoint] = None if on else stamp
                continue
            if enabled[endpoint] and not on:
                since[endpoint] = stamp
            elif not enabled[endpoint] and on:
                periods.append((endpoint, since[endpoint], stamp))
            enabled[endpoint] = bool(on)

        # every (event, endpoint) any file gives a delivery for
        delivered = set(db.execute("SELECT event_id, coalesce(endpoint_id, url_endpoint) FROM deliveries"))
        delivered |= set(db.execute("SELECT event_id, coalesce(endpoint_id, url_endpoint) FROM delivery_facts"))

        missed, totals = [], {}
        for endpoint, off, on in sorted(periods):
            lost = db.execute(
                "SELECT DISTINCT event, amount_minor, currency FROM api WHERE msg = 'event.accepted' AND merchant = ? "
                "AND ts_iso >= ? AND ts_iso < ? ORDER BY event",
                (merchant_of[endpoint], off, on),
            ).fetchall()
            lost = [row for row in lost if (row[0], endpoint) not in delivered]
            if not lost:
                continue
            missed.append({"endpoint_id": endpoint, "switched_off_at": off, "switched_on_at": on,
                           "event_ids": [row[0] for row in lost]})
            for _, amount, currency in lost:
                totals[currency] = totals.get(currency, 0) + amount
        skipped = dict(db.execute("SELECT file, corrupted_rows FROM skipped"))
        conflicts = db.execute(
            "SELECT (SELECT count(*) FROM events WHERE conflict) + (SELECT count(*) FROM deliveries WHERE conflict)"
        ).fetchone()[0]
        missed.sort(key=lambda entry: (entry["endpoint_id"], entry["switched_on_at"]))
        return {"missed": missed, "totals_minor": dict(sorted(totals.items())),
                "skipped_rows": sum(skipped.values())}, skipped, conflicts, len(periods)


def main():
    args = sys.argv[1:]
    write = None
    if "--write" in args:
        write = args[args.index("--write") + 1]
        del args[args.index("--write"):args.index("--write") + 2]
    folder = os.path.abspath(args[0] if args else os.path.join(HERE, "inc-2318"))
    incident = os.path.join(folder, "incident")
    truth = json.load(open(os.path.join(folder, "truth.json")))
    notes = json.load(open(os.path.join(HERE, "ground-truth-notes-2318.json")))
    ok = True

    counted = corrupted_by_the_contract(incident)
    said = notes["skipped_rows_by_file"]
    print("corrupted rows   contract rule / generator")
    for name in sorted(said):
        mark = "" if counted[name] == said[name] else "   <-- differ"
        ok = ok and counted[name] == said[name]
        print(f"  {name:<22} {counted[name]:>3} / {said[name]:<3}{mark}")
    print(f"  {'total':<22} {sum(counted.values()):>3} / {truth['skipped_rows']}")
    ok = ok and sum(counted.values()) == truth["skipped_rows"]

    derived, kit_skipped, conflicts, periods = report_from_the_kit(incident)
    print("kit loader: corrupted rows", sum(kit_skipped.values()),
          "(", ", ".join(f"{k} {v}" for k, v in sorted(kit_skipped.items())), "); conflicts", conflicts)
    pairs = lambda report: {(e["endpoint_id"], event) for e in report["missed"] for event in e["event_ids"]}  # noqa: E731
    print(f"derived through the kit: {periods} switch-ons, {len(derived['missed'])} with missed events, "
          f"{len(pairs(derived))} missed (endpoint, event) pairs; truth has {len(pairs(truth))}")
    for key in ("missed", "totals_minor", "skipped_rows"):
        same = derived[key] == truth[key]
        ok = ok and same
        print(f"  report.{key}: {'same as truth' if same else 'DIFFERS from truth'}")
    if derived["missed"] != truth["missed"]:
        want, got = pairs(truth), pairs(derived)
        print("   only in truth:", sorted(want - got)[:6], "\n   only from the kit:", sorted(got - want)[:6])
        print("   periods:", [(e["endpoint_id"], e["switched_off_at"], e["switched_on_at"]) for e in derived["missed"]])
    if write:
        os.makedirs(os.path.join(write, "out"), exist_ok=True)
        with open(os.path.join(write, "out", "impact.json"), "w", encoding="utf-8") as handle:
            json.dump(derived, handle, indent=2)
            handle.write("\n")
        print("wrote", os.path.join(write, "out", "impact.json"))
    print("OK" if ok else "MISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
