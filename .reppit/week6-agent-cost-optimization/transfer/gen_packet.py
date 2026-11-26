#!/usr/bin/env python3
"""Build the INC-2231 evidence packet by running the shipped release, and its truth.

    PATH=/opt/node24/bin:$PATH python3 gen_packet.py [--app <clean app tree>] [--out inc-2231] [--port-base 7600]

The shipped release (unmodified `week6/app`) is driven through three simulated days of
traffic with the repository's own harness (`app/bin/replaylib.py`). Service logs are taken
from the state directory as the services wrote them. `egress.log` and the merchant export
are written from what the merchant stand-in recorded, in the formats of
`contracts/evidence.md`. Then the log shipper's effects are applied with a fixed seed:
clock skew per host, batches sent twice, batches delivered late, rows cut short.

`truth.json` is computed from what this script knows it did (when it called the api, what
the stand-in answered, which rows it cut). It does not use `week6/kit/evidence.py`.

What happens in the packet (seconds are from 2026-10-19T00:00:00Z):
  * the archive backfill posts version-2 messages on day 1 (endpoints of orchid, poplar,
    quince, tulip, and some old events) and on day 2 (violet's endpoint, old tulip events)
  * ep_orchid_1, ep_quince_1: switched off through the api after the backfill; the router
    drops the change; deliveries continue                                   -> in the report
  * ep_violet_1: switched off (applied), then the day-2 backfill switches it on again
                                                                            -> in the report
  * ep_quince_2, ep_sorrel_1: switched off and it worked                    -> no deliveries
  * ep_rowan_1: switched off, then on again (catch-up deliveries)           -> not switched off
  * ep_poplar_1 (secret), ep_tulip_1 (address): changes dropped, not switch-offs
"""

import argparse
import base64
import calendar
import csv
import gzip
import hashlib
import io
import json
import os
import random
import re
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
EPOCH = calendar.timegm((2026, 10, 19, 0, 0, 0))
DAY = 86400
END = 3 * DAY - 1800
SKEW = {"router": 7, "worker": 41, "egress": -9}
EXPORT_OFFSET = -4 * 3600  # the reporting merchant's local time
HOST = "https://hooks.merchant.example"
SEED = 2231
TYPES = ["payment.captured", "payment.captured", "payment.captured", "payment.failed", "refund.created", "payout.paid"]

MERCHANTS = {
    "m_orchid": ("USD", ["ep_orchid_1", "ep_orchid_2"]),
    "m_poplar": ("EUR", ["ep_poplar_1"]),
    "m_quince": ("GBP", ["ep_quince_1", "ep_quince_2"]),
    "m_rowan": ("JPY", ["ep_rowan_1"]),
    "m_sorrel": ("KWD", ["ep_sorrel_1"]),
    "m_tulip": ("USD", ["ep_tulip_1"]),
    "m_umber": ("EUR", ["ep_umber_1"]),
    "m_violet": ("EUR", ["ep_violet_1"]),
}
REPORTER = "m_orchid"


def at(day, hh, mm, ss=0):
    return (day - 1) * DAY + hh * 3600 + mm * 60 + ss


# (time, endpoint, change) through the api
CHANGES = [
    (at(1, 20, 0, 12), "ep_sorrel_1", {"enabled": False}),
    (at(2, 2, 0, 40), "ep_sorrel_1", {"enabled": True}),
    (at(2, 8, 0, 5), "ep_rowan_1", {"enabled": False}),
    (at(2, 9, 12, 44), "ep_orchid_1", {"enabled": False}),
    (at(2, 9, 40, 10), "ep_violet_1", {"enabled": False}),
    (at(2, 10, 30, 5), "ep_poplar_1", {"secret": "whsec_" + base64.b64encode(b"poplar-rotated-secret-01").decode()}),
    (at(2, 11, 0, 20), "ep_tulip_1", {"path": "/hooks/ep_tulip_1/v2"}),
    (at(2, 11, 20, 0), "ep_umber_1", {"path": "/in/umber-webhooks"}),
    (at(2, 13, 0, 30), "ep_rowan_1", {"enabled": True}),
    (at(2, 16, 40, 31), "ep_quince_1", {"enabled": False}),
    (at(2, 16, 41, 2), "ep_quince_2", {"enabled": False}),
    (at(3, 6, 0, 15), "ep_sorrel_1", {"enabled": False}),
    (at(3, 8, 3, 27), "ep_orchid_1", {"enabled": False}),  # "switched it off again": already off
]
# archive backfill: (time, [(seq, endpoint)], number of old events, merchants the old events belong to)
BACKFILL = [
    (at(1, 14, 0, 0), [(4117, "ep_orchid_1"), (4131, "ep_poplar_1"), (4160, "ep_quince_1"), (4188, "ep_tulip_1")],
     10, ["m_orchid", "m_poplar", "m_quince", "m_tulip"]),
    (at(2, 14, 5, 0), [(5302, "ep_violet_1")], 4, ["m_tulip"]),
]
ORCHID_DOWN = at(3, 20, 0, 0)  # ep_orchid_1's server answers 503 from here to the end
SNAPSHOTS = [at(1, 23, 0, 0), at(2, 18, 0, 0), at(3, 12, 0, 0)]
RESTARTS = [(at(1, 10, 0, 0), "api"), (at(2, 5, 0, 0), "worker"), (at(3, 3, 0, 0), "api")]


def owner(endpoint):
    return next(m for m, (_, eps) in MERCHANTS.items() if endpoint in eps)


def secret_for(name):
    return "whsec_" + base64.b64encode(hashlib.sha256(name.encode()).digest()[:24]).decode()


def hex14(text):
    return hashlib.sha256(text.encode()).hexdigest()[:14]


def amount(rng, currency):
    if currency == "JPY":
        return rng.randint(300, 900000)
    if currency == "KWD":
        return rng.randint(500, 400000)
    return rng.choice([rng.randint(150, 9999), rng.randint(10000, 480000), rng.randint(1, 60) * 500])


def build_timeline(rng):
    """Returns the ordered steps and what the generator knows about them."""
    steps = []
    order = 0

    def add(t, step, **note):
        nonlocal order
        order += 1
        steps.append((t, order, dict(step, at=t), note))

    t = 60
    for merchant, (_, endpoints) in MERCHANTS.items():
        for endpoint in endpoints:
            add(t, {"do": "endpoint.create", "id": endpoint, "merchant": merchant, "secret": secret_for(endpoint)})
            t += 11
    for when, endpoint, change in CHANGES:
        add(when, dict({"do": "endpoint.update", "id": endpoint}, **change), change=(endpoint, change))
    for when, endpoints, old_events, merchants in BACKFILL:
        seq_rng = random.Random(when)
        used = {seq for seq, _ in endpoints}
        offset = 0
        for seq, endpoint in endpoints:
            message = {
                "v": 2, "seq": seq, "kind": "endpoint",
                "endpoint": {"id": endpoint, "merchant": owner(endpoint), "url": "{receiver}/hooks/" + endpoint,
                             "secret": secret_for(endpoint), "types": ["*"], "active": True},
            }
            add(when + offset, {"do": "bus", "message": message}, backfill=endpoint)
            offset += 2
        low = min(used)
        for n in range(old_events):
            seq = low + 1 + n
            while seq in used:
                seq += 1
            used.add(seq)
            merchant = merchants[n % len(merchants)]
            currency = MERCHANTS[merchant][0]
            message = {
                "v": 2, "seq": seq, "kind": "event",
                "event": {"id": "evt_" + hex14(f"archive:{seq}"), "merchant": merchant,
                          "type": seq_rng.choice(TYPES), "created": EPOCH - 40 * DAY + seq * 37,
                          "payment_id": "pay_" + hex14(f"archive-pay:{seq}"),
                          "amount_minor": amount(seq_rng, currency), "currency": currency},
            }
            add(when + offset, {"do": "bus", "message": message}, archive_event=message["event"]["id"])
            offset += 3
    for when, service in RESTARTS:
        add(when, {"do": "restart", "service": service})
    add(ORCHID_DOWN, {"do": "receiver.script", "path": "/hooks/ep_orchid_1", "responses": [], "default": 503})

    # one event accepted before ep_quince_1 is switched off whose 2xx comes after it
    quince_off = at(2, 16, 40, 31)
    crafted = quince_off - 1500
    add(crafted - 5, {"do": "receiver.script", "path": "/hooks/ep_quince_1", "responses": [500, 500, 503, 500]})
    add(crafted, {"do": "event", "ref": "crafted_quince", "merchant": "m_quince", "type": "payment.captured",
                  "amount_minor": 86420, "currency": "GBP"}, event="crafted_quince")

    quiet = {m: [] for m in MERCHANTS}  # (from, to) windows with no ordinary events
    for when, endpoint, _ in CHANGES:
        quiet[owner(endpoint)].append((when - 900, when + 900))
    for when, _, _, merchants in BACKFILL:
        for merchant in MERCHANTS:
            quiet[merchant].append((when - 120, when + 240))
    quiet["m_quince"].append((crafted - 200, crafted + 4600))
    for when, _ in RESTARTS:
        for merchant in MERCHANTS:
            quiet[merchant].append((when - 60, when + 60))
    number = 0
    for merchant, (currency, endpoints) in MERCHANTS.items():
        count = 62 if merchant in ("m_orchid", "m_quince", "m_violet") else 46
        times = set()
        while len(times) < count:
            when = rng.randint(700, END - 300)
            if any(a <= when <= b for a, b in quiet[merchant]):
                continue
            if any(abs(when - other) < 20 for other in times):
                continue
            times.add(when)
        if merchant == "m_orchid":  # a few while ep_orchid_1's server is down
            times |= {ORCHID_DOWN + 1200, ORCHID_DOWN + 3900, ORCHID_DOWN + 7400}
        for when in sorted(times):
            number += 1
            ref = f"e{number}"
            if rng.random() < 0.09 and not (merchant == "m_orchid" and when > ORCHID_DOWN - 30000):
                responses = rng.choice([[500], [503, 500], ["drop"], ["refuse"], [500, "drop"], [429]])
                add(when - 3, {"do": "receiver.script", "path": "/hooks/" + rng.choice(endpoints), "responses": responses})
            add(when, {"do": "event", "ref": ref, "merchant": merchant, "type": rng.choice(TYPES),
                       "amount_minor": amount(rng, currency), "currency": currency}, event=ref)
    for when in SNAPSHOTS:
        add(when, {"do": "snapshot"})
    steps.sort(key=lambda item: (item[0], item[1]))
    return steps


def run(app, port_base, steps):
    sys.path.insert(0, os.path.join(app, "bin"))
    import replaylib

    state_dir = tempfile.mkdtemp(prefix="inc2231-")
    dep = replaylib.Deployment(state_dir, port_base, app)
    known = {"events": {}, "snapshots": [], "changes": []}
    try:
        dep.set_clock(EPOCH)
        dep.start_all()
        runner = replaylib.Run(dep, {"steps": [], "epoch": EPOCH})
        for index, (when, _, step, note) in enumerate(steps):
            if step["do"] == "snapshot":
                dep.set_clock(EPOCH + when)
                known["snapshots"].append((when, dep.call("router", "GET", "/__admin/state")[1]))
            else:
                runner.step(step)
                if "event" in note:
                    known["events"][runner.refs[note["event"]]] = {
                        "accepted": when, "merchant": step["merchant"], "type": step["type"],
                        "amount_minor": step["amount_minor"], "currency": step["currency"],
                    }
                if "change" in note:
                    known["changes"].append((when,) + note["change"])
            following = steps[index + 1][0] if index + 1 < len(steps) else 3 * DAY - 60
            if following - when > 1:
                dep.drain(limit=following - when - 1)
        dep.set_clock(EPOCH + 3 * DAY - 30)
        known["router"] = dep.call("router", "GET", "/__admin/state")[1]
        known["received"] = dep.call("receiver", "GET", "/__admin/state")[1]["received"]
        known["receiver_url"] = runner.receiver_url
    finally:
        dep.stop_all()
    logs = {}
    for name in ("api.ndjson", "router.log", "worker.jsonl"):
        with open(os.path.join(state_dir, "logs", name), encoding="utf-8") as handle:
            logs[name] = handle.read().splitlines()
    shutil.rmtree(state_dir, ignore_errors=True)
    return known, logs


# --- what really happened -------------------------------------------------------------


def iso(seconds):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(EPOCH + seconds))


def truth_of(known):
    """The report the ticket asks for, from what the generator did and what the merchant answered."""
    enabled, switched_off = {}, {}
    for when, endpoint, change in sorted(known["changes"]):
        if "enabled" not in change:
            continue
        was = enabled.get(endpoint, True)
        if was and not change["enabled"]:
            switched_off[endpoint] = when
        enabled[endpoint] = change["enabled"]
    population = {e: switched_off[e] for e, on in enabled.items() if not on}
    answered = set()
    for record in known["received"]:
        if record["processed"] and isinstance(record["response"], int) and 200 <= record["response"] < 300:
            answered.add(record["headers"]["webhook-id"])
    entries, totals, affected = {}, {}, []
    for delivery in known["router"]["deliveries"]:
        endpoint = delivery["endpoint_id"]
        event = known["events"].get(delivery["event_id"])
        if endpoint not in population or event is None or delivery["id"] not in answered:
            continue
        if event["accepted"] <= population[endpoint]:
            continue
        entries.setdefault(endpoint, []).append(delivery["id"])
        totals[event["currency"]] = totals.get(event["currency"], 0) + event["amount_minor"]
        affected.append(delivery["id"])
    report = {
        "endpoints": [
            {"endpoint_id": e, "switched_off_at": iso(population[e]), "delivery_ids": sorted(ids)}
            for e, ids in sorted(entries.items())
        ],
        "totals_minor": dict(sorted(totals.items())),
    }
    return report, population, set(affected), answered


# --- the packet -----------------------------------------------------------------------


def shift_router(line, by):
    stamp, rest = line.split(" ", 1)
    seconds = calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")) + by
    rest = re.sub(r"\b(expires|retry_at)=(\d+)", lambda m: f"{m.group(1)}={int(m.group(2)) + by}", rest)
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(seconds)) + " " + rest


def egress_line(record):
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record["now"] + SKEW["egress"]))
    headers = record["headers"]
    if isinstance(record["response"], int):
        status, error = f"{record['response']:03d}", ""
    else:
        status = "000"
        error = " err=upstream_reset" if record["processed"] else " err=connect_refused"
    return (
        f"{stamp} egress POST {HOST}{record['path']} {status} webhook-id={headers['webhook-id']} "
        f"attempt={headers['x-switchyard-attempt']} event={headers['x-switchyard-event']} "
        f"bytes={len(record['body'].encode())}{error}"
    )


def major(rng, minor, currency):
    digits = {"JPY": 0, "KWD": 3}.get(currency, 2)
    text = f"{minor / 10 ** digits:.{digits}f}" if digits else str(minor)
    if digits and text.endswith("0") and rng.random() < 0.5:
        text = text.rstrip("0").rstrip(".")
    whole, dot, fraction = text.partition(".")
    if len(whole) > 3 and rng.random() < 0.6:
        whole = f"{int(whole):,}"
    return whole + dot + fraction


def export_rows(rng, known, all_deliveries):
    paths = {"/hooks/" + e for e in MERCHANTS[REPORTER][1]}
    rows = []
    ordered = sorted(all_deliveries)
    for record in known["received"]:
        if record["path"] not in paths or not record["processed"]:
            continue
        body = json.loads(record["body"])
        local = time.strftime("%m/%d/%Y %H:%M", time.gmtime(record["now"] + EXPORT_OFFSET))
        webhook = record["headers"]["webhook-id"]
        if rng.random() < 0.04:  # the spreadsheet cut the id; keep it unique as a prefix
            length = 9
            while sum(1 for d in ordered if d.startswith(webhook[:length])) > 1:
                length += 1
            webhook = webhook[: max(length, rng.randint(9, 12))]
        status = "" if record["response"] is None else str(record["response"])
        rows.append([local, webhook, body["id"], body["type"],
                     major(rng, body["data"]["amount_minor"], body["data"]["currency"]), body["data"]["currency"], status])
    return rows


def cut_json(rng, line):
    return line[: rng.randint(12, len(line) - 2)]


def cut_fields(rng, line):
    tokens = line.split(" ")
    fields = [i for i, token in enumerate(tokens) if re.match(r"^[A-Za-z_][\w.\-]*=", token)]
    index = rng.choice(fields[1:] if len(fields) > 1 else fields)
    key = tokens[index].split("=", 1)[0]
    tail = key + "=" if rng.random() < 0.35 else key[: rng.randint(1, len(key) - 1)]
    return " ".join(tokens[:index] + [tail])


def ship(rng, lines, cutter, cuts, protected, batches=(2, 1)):
    """Apply cuts, then send some batches twice and some late. Returns (lines, cut rows as they appear)."""
    rows = [[line, False] for line in lines]
    free = [i for i, (line, _) in enumerate(rows) if not protected(line)]
    for index in rng.sample(free, min(cuts, len(free))):
        rows[index] = [cutter(rng, rows[index][0]), True]
    twice, late = batches
    for _ in range(late):
        size = rng.randint(15, 40)
        start = rng.randint(50, max(51, len(rows) - size - 400))
        batch = rows[start:start + size]
        del rows[start:start + size]
        where = min(len(rows), start + rng.randint(150, 350))
        rows[where:where] = batch
    for n in range(twice):
        size = rng.randint(20, 45)
        if n == 0 and any(cut for _, cut in rows):  # one batch that is sent twice holds a cut row
            anchor = rng.choice([i for i, (_, cut) in enumerate(rows) if cut])
            start = max(0, anchor - size // 2)
        else:
            start = rng.randint(50, max(51, len(rows) - size - 300))
        batch = [list(row) for row in rows[start:start + size]]
        where = min(len(rows), start + size + rng.randint(120, 300))
        rows[where:where] = batch
    return [line for line, _ in rows], sum(1 for _, cut in rows if cut)


def write_packet(out, known, logs, report, affected, answered):
    rng = random.Random(SEED)
    incident = os.path.join(out, "incident")
    shutil.rmtree(incident, ignore_errors=True)
    os.makedirs(os.path.join(incident, "snapshots"))
    receiver = known["receiver_url"]
    all_deliveries = [d["id"] for d in known["router"]["deliveries"]]

    api = logs["api.ndjson"]
    router = [shift_router(line.replace(receiver, HOST), SKEW["router"]) for line in logs["router.log"]]
    worker = []
    for line in logs["worker.jsonl"]:
        record = json.loads(line.replace(receiver, HOST))
        record["t"] += SKEW["worker"]
        worker.append(json.dumps(record, sort_keys=True, separators=(",", ":")))
    egress = [egress_line(record) for record in known["received"]]
    export = export_rows(rng, known, all_deliveries)

    # Each affected delivery may lose one of its records, never more: no fact is missing everywhere.
    damage = {}
    for delivery in sorted(affected):
        if rng.random() < 0.3:
            damage[delivery] = rng.choice(["router.created", "router.delivered", "worker.finished", "egress"])
    careful = {"m_orchid", "m_quince", "m_violet", "m_sorrel"}

    def api_protected(line):
        record = json.loads(line)
        if record["msg"].startswith("endpoint."):
            return True
        return record["msg"] in ("event.accepted", "event.repeated") and record.get("merchant") in careful

    def names_affected(line):
        return next((d for d in affected if d in line), None)

    def router_protected(line):
        delivery = names_affected(line)
        if delivery is None:
            return "msg=endpoint." in line
        return True

    def worker_protected(line):
        return names_affected(line) is not None

    files, skipped = {}, {}
    planned = [
        ("api.ndjson", api, cut_json, 9, api_protected, (2, 1), None, None),
        ("router.log", router, cut_fields, 22, router_protected, (3, 2),
         ("router.created", lambda l: "msg=delivery.created" in l), ("router.delivered", lambda l: "msg=delivery.delivered" in l)),
        ("worker.jsonl", worker, cut_json, 20, worker_protected, (3, 1),
         ("worker.finished", lambda l: '"op":"attempt.finished"' in l and '"status":2' in l), None),
        ("egress.log", egress, cut_fields, 3, lambda l: names_affected(l) is not None, (0, 0),
         ("egress", lambda l: re.search(r" 2\d\d webhook-id=", l) is not None), None),
    ]
    for name, lines, cutter, cuts, protected, batches, first, second in planned:
        lines = list(lines)
        for spec in (first, second):
            if spec is None:
                continue
            kind, marker = spec
            for index, line in enumerate(lines):
                delivery = names_affected(line)
                if delivery and damage.get(delivery) == kind and marker(line):
                    lines[index] = "\0CUT\0" + cutter(rng, line)
                    damage[delivery] = kind + " (done)"  # one record only, even if it has several 2xx
        shipped, cut_count = ship(rng, [l for l in lines], cutter, cuts,
                                  lambda l, p=protected: l.startswith("\0CUT\0") or p(l), batches)
        extra = sum(1 for l in shipped if l.startswith("\0CUT\0"))
        files[name] = [l.replace("\0CUT\0", "") for l in shipped]
        skipped[name] = cut_count + extra

    harmless = [i for i, row in enumerate(export) if not any(d.startswith(row[1]) for d in affected)]
    cut_rows = set(rng.sample(harmless, 3))
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(["received_at", "webhook_id", "event_id", "type", "amount", "currency", "http_status"])
    for index, row in enumerate(export):
        if index in cut_rows:
            keep = rng.randint(1, 3)
            buffer.write(",".join(row[:keep]) + "," + row[keep][: rng.randint(0, 3)] + "\r\n")
        else:
            writer.writerow(row)
    skipped["merchant_export.csv"] = len(cut_rows)

    for name in ("api.ndjson", "router.log", "egress.log"):
        with open(os.path.join(incident, name), "w", encoding="utf-8") as handle:
            handle.write("\n".join(files[name]) + "\n")
    with open(os.path.join(incident, "worker.jsonl.gz"), "wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as handle:
            handle.write(("\n".join(files["worker.jsonl"]) + "\n").encode())
    skipped["worker.jsonl.gz"] = skipped.pop("worker.jsonl")
    with open(os.path.join(incident, "merchant_export.csv"), "w", encoding="utf-8", newline="") as handle:
        handle.write(buffer.getvalue())
    for when, state in known["snapshots"]:
        snapshot = {
            "service": "router",
            "now": state["now"] + SKEW["router"],
            "endpoints": [{k: e[k] for k in ("id", "merchant_id", "enabled", "version")} for e in state["endpoints"]],
            "deliveries": [
                dict({k: d[k] for k in ("id", "event_id", "endpoint_id", "resend_of", "state", "attempts")},
                     available_at=d["available_at"] + SKEW["router"])
                for d in state["deliveries"]
            ],
        }
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(EPOCH + when))
        with open(os.path.join(incident, "snapshots", f"router-{stamp}.json"), "w", encoding="utf-8") as handle:
            json.dump(snapshot, handle)
    return skipped, damage


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--app", default=os.path.join(REPO, "week6", "app"))
    parser.add_argument("--out", default=os.path.join(HERE, "inc-2231"))
    parser.add_argument("--port-base", type=int, default=7600)
    args = parser.parse_args()

    steps = build_timeline(random.Random(SEED))
    known, logs = run(os.path.abspath(args.app), args.port_base, steps)
    report, population, affected, answered = truth_of(known)
    skipped, damage = write_packet(args.out, known, logs, report, affected, answered)
    report["skipped_rows"] = sum(skipped.values())
    with open(os.path.join(args.out, "truth.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")

    deliveries = known["router"]["deliveries"]
    by_endpoint = {}
    for delivery in deliveries:
        by_endpoint.setdefault(delivery["endpoint_id"], []).append(delivery)
    notes = {
        "events_accepted_by_api": len(known["events"]),
        "deliveries": len(deliveries),
        "requests": len(known["received"]),
        "switched_off_at_the_end": {e: iso(t) for e, t in sorted(population.items())},
        "affected_deliveries": {e["endpoint_id"]: len(e["delivery_ids"]) for e in report["endpoints"]},
        "skipped_rows_by_file": skipped,
        "affected_deliveries_with_one_cut_record": sum(1 for v in damage.values() if v.endswith("(done)")),
        "states_at_the_end": {
            e: {s: sum(1 for d in ds if d["state"] == s) for s in sorted({d["state"] for d in ds})}
            for e, ds in sorted(by_endpoint.items())
        },
        "near_misses": {
            "to a switched-off endpoint, event accepted after, no 2xx": sum(
                1 for d in deliveries
                if d["endpoint_id"] in population and d["event_id"] in known["events"]
                and known["events"][d["event_id"]]["accepted"] > population[d["endpoint_id"]] and d["id"] not in answered),
            "to a switched-off endpoint, 2xx, event accepted before the switch-off": sum(
                1 for d in deliveries
                if d["endpoint_id"] in population and d["event_id"] in known["events"]
                and known["events"][d["event_id"]]["accepted"] <= population[d["endpoint_id"]] and d["id"] in answered),
            "to a switched-off endpoint, 2xx, event from the archive (never accepted by the api)": sum(
                1 for d in deliveries
                if d["endpoint_id"] in population and d["event_id"] not in known["events"] and d["id"] in answered),
        },
    }
    with open(os.path.join(args.out, "..", "ground-truth-notes.json"), "w", encoding="utf-8") as handle:
        json.dump(notes, handle, indent=2)
        handle.write("\n")
    print(json.dumps(notes, indent=1))


if __name__ == "__main__":
    main()
