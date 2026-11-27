#!/usr/bin/env python3
"""Check the INC-2307 packet, its truth, the kit's loader and the judge against each other.

    python3 crosscheck_2307.py [inc-2307] [--write FILE]     --write saves the derived report

1. Counts corrupted rows with crosscheck.py's own small reading of contracts/evidence.md
   (not the kit's) and compares with what the generator says it cut.
2. Loads the packet with week6/kit/evidence.py and derives the report from its tables with
   the query below, which knows nothing of how the packet was made, then compares it with
   truth.json.
3. Puts the derived report where a workspace would have it and scores it with
   inc-2307/judge.py's impact formula.
Exits 0 when everything agrees and the impact is 1.0.

The derivation, for each event and endpoint of the same merchant:
  R  distinct `resend.requested` records of the api (a batch sent twice is one record)
  S  distinct `resend.skipped` records of the router
  C  delivery ids known for the event and endpoint in any file, less the first one
     (delivery.md: only a manual resend puts an event on an endpoint under a second id)
  lost = max(R - C, S, 0)
R - C and S are both lower bounds, and a request has lost at most one of its records.
"""

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile

from crosscheck import corrupted_by_the_contract

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))


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
        owner = dict(db.execute("SELECT endpoint, merchant FROM router WHERE msg = 'endpoint.changed' AND merchant IS NOT NULL"))
        owner.update(db.execute("SELECT endpoint, merchant FROM api WHERE msg = 'endpoint.created'"))
        events = {e: (m, a, c) for e, m, a, c in db.execute("SELECT event_id, merchant_id, amount_minor, currency FROM events")}
        asked = dict(((e, p), n) for e, p, n in db.execute(
            "SELECT event, endpoint, count(*) FROM api WHERE msg = 'resend.requested' GROUP BY 1, 2"))
        dropped = dict(((e, p), n) for e, p, n in db.execute(
            "SELECT event, endpoint, count(*) FROM router WHERE msg = 'resend.skipped' GROUP BY 1, 2"))
        ids = dict(((e, p), n) for e, p, n in db.execute(
            "SELECT event_id, coalesce(endpoint_id, url_endpoint), count(*) FROM deliveries GROUP BY 1, 2"))
        merchants, totals = {}, {}
        for event, endpoint in sorted(set(asked) | set(dropped)):
            merchant, amount, currency = events[event]
            if owner[endpoint] != merchant:
                continue
            made = max(ids.get((event, endpoint), 0) - 1, 0)
            lost = max(asked.get((event, endpoint), 0) - made, dropped.get((event, endpoint), 0), 0)
            if not lost:
                continue
            entry = merchants.setdefault(merchant, {"merchant_id": merchant, "lost_requests": 0, "resends": []})
            entry["lost_requests"] += lost
            entry["resends"].append({"event_id": event, "endpoint_id": endpoint})
            totals[currency] = totals.get(currency, 0) + amount
        skipped = dict(db.execute("SELECT file, corrupted_rows FROM skipped"))
        conflicts = db.execute(
            "SELECT (SELECT count(*) FROM events WHERE conflict) + (SELECT count(*) FROM deliveries WHERE conflict)").fetchone()[0]
        return {
            "merchants": [merchants[m] for m in sorted(merchants)],
            "totals_minor": dict(sorted(totals.items())),
            "skipped_rows": sum(skipped.values()),
        }, skipped, conflicts


def impact_through_the_judge(folder, report):
    spec = importlib.util.spec_from_file_location("judge_2307", os.path.join(folder, "judge.py"))
    judge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(judge)
    with tempfile.TemporaryDirectory() as workspace:
        os.makedirs(os.path.join(workspace, "out"))
        with open(os.path.join(workspace, "out", "impact.json"), "w", encoding="utf-8") as handle:
            json.dump(report, handle)
        return judge.impact_score(workspace)


def main():
    args = sys.argv[1:]
    write = args.pop(args.index("--write") + 1) if "--write" in args else None
    args = [a for a in args if a != "--write"]
    folder = os.path.abspath(args[0] if args else os.path.join(HERE, "inc-2307"))
    incident = os.path.join(folder, "incident")
    truth = json.load(open(os.path.join(folder, "truth.json")))
    notes = json.load(open(os.path.join(HERE, "ground-truth-notes-2307.json")))
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
    for key in ("merchants", "totals_minor", "skipped_rows"):
        same = derived[key] == truth[key]
        ok = ok and same
        print(f"  report.{key}: {'same as truth' if same else 'DIFFERS from truth'}")
    if derived["merchants"] != truth["merchants"]:
        def flat(report):
            return {(m["merchant_id"], r["event_id"], r["endpoint_id"]) for m in report["merchants"] for r in m["resends"]}
        print("   only in truth:", sorted(flat(truth) - flat(derived))[:6], "\n   only from the kit:", sorted(flat(derived) - flat(truth))[:6])
        print("   lost_requests:", {m["merchant_id"]: m["lost_requests"] for m in derived["merchants"]},
              "truth:", {m["merchant_id"]: m["lost_requests"] for m in truth["merchants"]})
    if write:
        os.makedirs(os.path.dirname(os.path.abspath(write)), exist_ok=True)
        with open(write, "w", encoding="utf-8") as handle:
            json.dump(derived, handle, indent=2)
    score = impact_through_the_judge(folder, derived)
    print(f"judge.py on the derived report: impact {score['impact']:.2f} (precision {score['precision']:.2f}, "
          f"recall {score['recall']:.2f}, figures {score['figures_right']} of {score['figures']} right)")
    ok = ok and score["impact"] == 1.0
    print("OK" if ok else "MISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
