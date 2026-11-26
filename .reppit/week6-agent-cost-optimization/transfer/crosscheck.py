#!/usr/bin/env python3
"""Check the INC-2231 packet, its truth and the kit's loader against each other.

    python3 crosscheck.py [inc-2231]

1. Counts corrupted rows with a small reading of contracts/evidence.md written here
   (not the kit's) and compares with what the generator says it cut.
2. Loads the packet with week6/kit/evidence.py and derives the report with a short
   query, then compares it with truth.json.
Exits 0 when everything agrees.
"""

import csv
import gzip
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))


def corrupted_by_the_contract(incident):
    counts = {}

    def lines(name):
        opener = gzip.open if name.endswith(".gz") else open
        with opener(os.path.join(incident, name), "rt", encoding="utf-8", newline="") as handle:
            return [line.rstrip("\r\n") for line in handle if line.strip()]

    for name in ("api.ndjson", "worker.jsonl.gz"):
        bad = 0
        for line in lines(name):
            try:
                json.loads(line)
            except ValueError:
                bad += 1
        counts[name] = bad
    for name in ("router.log", "egress.log"):
        bad = 0
        for line in lines(name):
            last = line.split(" ")[-1]
            if "=" not in last or last.endswith("="):  # "... attempt=" or "... att"
                bad += 1
        counts[name] = bad
    rows = lines("merchant_export.csv")
    counts["merchant_export.csv"] = sum(1 for line in rows[1:] if len(next(csv.reader([line]))) < 7)
    return counts


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
        state, switched = {}, {}
        for endpoint, enabled, stamp in db.execute(
            "SELECT endpoint, enabled, ts_iso FROM api WHERE msg IN ('endpoint.created', 'endpoint.updated') "
            "ORDER BY ts, line_no"
        ):
            if state.get(endpoint, 1) and not enabled:
                switched[endpoint] = stamp
            state[endpoint] = enabled
        entries, totals = {}, {}
        for endpoint, on in state.items():
            if on:
                continue
            for delivery, amount, currency in db.execute(
                "SELECT d.delivery_id, e.amount_minor, e.currency FROM deliveries d "
                "JOIN api a ON a.event = d.event_id AND a.msg = 'event.accepted' "
                "JOIN events e ON e.event_id = d.event_id "
                "WHERE d.endpoint_id = ? AND a.ts_iso > ? AND EXISTS (SELECT 1 FROM responses r "
                "  WHERE r.delivery_id = d.delivery_id AND r.status BETWEEN 200 AND 299)",
                (endpoint, switched[endpoint]),
            ):
                entries.setdefault(endpoint, []).append(delivery)
                totals[currency] = totals.get(currency, 0) + amount
        skipped = dict(db.execute("SELECT file, corrupted_rows FROM skipped"))
        conflicts = db.execute("SELECT (SELECT count(*) FROM events WHERE conflict) + (SELECT count(*) FROM deliveries WHERE conflict)").fetchone()[0]
        return {
            "endpoints": [
                {"endpoint_id": e, "switched_off_at": switched[e], "delivery_ids": sorted(ids)}
                for e, ids in sorted(entries.items())
            ],
            "totals_minor": dict(sorted(totals.items())),
            "skipped_rows": sum(skipped.values()),
        }, skipped, conflicts


def main():
    folder = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "inc-2231"))
    incident = os.path.join(folder, "incident")
    truth = json.load(open(os.path.join(folder, "truth.json")))
    notes = json.load(open(os.path.join(folder, "..", "ground-truth-notes.json")))
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

    derived, kit_skipped, conflicts = report_from_the_kit(incident)
    print("kit loader: corrupted rows", sum(kit_skipped.values()), "(", ", ".join(f"{k} {v}" for k, v in sorted(kit_skipped.items())), "); conflicts", conflicts)
    for key in ("endpoints", "totals_minor", "skipped_rows"):
        same = derived[key] == truth[key]
        ok = ok and same
        print(f"  report.{key}: {'same as truth' if same else 'DIFFERS from truth'}")
    if derived["endpoints"] != truth["endpoints"]:
        want = {(e["endpoint_id"], d) for e in truth["endpoints"] for d in e["delivery_ids"]}
        got = {(e["endpoint_id"], d) for e in derived["endpoints"] for d in e["delivery_ids"]}
        print("   only in truth:", sorted(want - got)[:6], "\n   only from the kit:", sorted(got - want)[:6])
        print("   switch-off times:", {e["endpoint_id"]: e["switched_off_at"] for e in derived["endpoints"]})
    print("OK" if ok else "MISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
