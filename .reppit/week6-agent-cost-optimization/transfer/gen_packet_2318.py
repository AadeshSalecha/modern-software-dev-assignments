#!/usr/bin/env python3
"""Build the INC-2318 evidence packet by running the shipped release, and its truth.

    PATH=/opt/node24/bin:$PATH python3 gen_packet_2318.py [--app <scratch copy of week6/app>] [--out inc-2318] [--port-base 26600]

Built the way gen_packet.py builds INC-2231's, and with its machinery (imported): the
shipped release is driven through six simulated days (2026-10-26 to 2026-10-31) with the
repository's own harness, the service logs are taken as the services wrote them,
`egress.log` and the merchant export are written from the merchant stand-in's records, and
then the log shipper's effects are applied with a fixed seed (clock skew per host, batches
sent twice, batches delivered late, rows cut short). Without --app the release is copied to
a temporary directory first; nothing runs in week6/app.

`truth.json` is computed from what this script did (when it called the api, in which order)
and from the router's own list of deliveries at the end. It does not use
`week6/kit/evidence.py`.

What happens in the packet:
  ep_harbor_1   off Mon 09:14 -> on Wed 10:02 (49 h), secret rotated meanwhile    -> in the report
  ep_isle_1     off Tue 08:00 -> on Thu 09:00 (49 h), "off" again meanwhile       -> in the report
  ep_isle_2     off Tue 20:00 -> on Thu 02:00 (30 h); same merchant as ep_isle_1  -> in the report
  ep_juniper_1  off Mon 06:00 -> on Tue 08:00 (26 h), off Wed 12:00 -> on Fri 15:00 (51 h)
                                                                                 -> in the report, twice
  ep_moss_1     off Mon 12:00 -> on Wed 00:30 (36.5 h), off again Thu 18:00 to the end
                                                                                 -> in the report (first period)
  ep_nettle_1   created switched off Mon 07:30 -> on Wed 08:15 (49 h)            -> in the report
  ep_kestrel_1  off Tue 10:00 -> on Wed 06:00 (20 h), secret rotated meanwhile    -> everything caught up
  ep_pine_1     off Thu 09:00 -> on Thu 21:00 (12 h)                              -> everything caught up
  ep_pine_2     off Mon 22:00 -> on Tue 21:59:58 (two seconds short of a day)     -> everything caught up
  ep_larch_1    off Wed 09:00 to the end ("off" again on Fri)                     -> not switched on
  ep_osier_1    never off; secret rotated; its server answers 503 from Fri 20:00  -> deliveries that die
"""

import argparse
import base64
import calendar
import csv
import gzip
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
sys.path.insert(0, HERE)
import gen_packet as gp  # noqa: E402  the INC-2231 generator: shipper effects, formats, helpers

REPO = gp.REPO
DAY = 86400
DAYS = 6
EPOCH = calendar.timegm((2026, 10, 26, 0, 0, 0))
END = DAYS * DAY - 1800
SEED = 2318
TYPES = gp.TYPES

MERCHANTS = {
    "m_harbor": ("USD", ["ep_harbor_1"]),
    "m_isle": ("EUR", ["ep_isle_1", "ep_isle_2"]),
    "m_juniper": ("GBP", ["ep_juniper_1"]),
    "m_kestrel": ("JPY", ["ep_kestrel_1"]),
    "m_larch": ("KWD", ["ep_larch_1"]),
    "m_moss": ("USD", ["ep_moss_1"]),
    "m_nettle": ("EUR", ["ep_nettle_1"]),
    "m_osier": ("USD", ["ep_osier_1"]),
    "m_pine": ("GBP", ["ep_pine_1", "ep_pine_2"]),
}
REPORTER = "m_harbor"
BUSY = ("m_harbor", "m_isle", "m_juniper", "m_moss", "m_nettle")  # more traffic: the merchants in the report

# gen_packet's helpers read these from their own module
gp.EPOCH, gp.MERCHANTS, gp.REPORTER = EPOCH, MERCHANTS, REPORTER
at, owner, iso = gp.at, gp.owner, gp.iso

OFF, ON = {"enabled": False}, {"enabled": True}


def rotated(name):
    return {"secret": "whsec_" + base64.b64encode(f"{name:-<6}-rotated-secret-01".encode()[:24]).decode()}


CREATED_OFF = {"ep_nettle_1": at(1, 7, 30, 0)}
# (time, endpoint, change) through the api
CHANGES = [
    (at(1, 6, 0, 19), "ep_juniper_1", OFF),
    (at(1, 9, 14, 7), "ep_harbor_1", OFF),
    (at(1, 12, 0, 21), "ep_moss_1", OFF),
    (at(1, 22, 0, 0), "ep_pine_2", OFF),
    (at(2, 8, 0, 3), "ep_juniper_1", ON),       # 26 h
    (at(2, 8, 0, 30), "ep_isle_1", OFF),
    (at(2, 10, 0, 7), "ep_kestrel_1", OFF),
    (at(2, 11, 0, 0), "ep_nettle_1", rotated("nettle")),
    (at(2, 15, 0, 0), "ep_harbor_1", rotated("harbor")),
    (at(2, 16, 30, 0), "ep_kestrel_1", rotated("kestrl")),
    (at(2, 20, 0, 5), "ep_isle_2", OFF),
    (at(2, 21, 59, 58), "ep_pine_2", ON),       # two seconds short of a day
    (at(3, 0, 30, 2), "ep_moss_1", ON),         # 36.5 h
    (at(3, 6, 0, 9), "ep_kestrel_1", ON),       # 20 h
    (at(3, 8, 0, 0), "ep_isle_1", OFF),         # "switched it off again": already off
    (at(3, 8, 15, 10), "ep_nettle_1", ON),      # 48.75 h after it was created switched off
    (at(3, 9, 0, 13), "ep_larch_1", OFF),       # stays off
    (at(3, 10, 2, 41), "ep_harbor_1", ON),      # 48.8 h
    (at(3, 12, 0, 50), "ep_juniper_1", OFF),
    (at(3, 14, 0, 0), "ep_osier_1", rotated("osier")),
    (at(4, 2, 0, 44), "ep_isle_2", ON),         # 30 h
    (at(4, 9, 0, 4), "ep_pine_1", OFF),
    (at(4, 9, 0, 12), "ep_isle_1", ON),         # 49 h
    (at(4, 18, 0, 33), "ep_moss_1", OFF),       # off again, to the end
    (at(4, 21, 0, 6), "ep_pine_1", ON),         # 12 h
    (at(5, 9, 0, 0), "ep_larch_1", OFF),        # already off
    (at(5, 15, 0, 20), "ep_juniper_1", ON),     # 51 h
]
# (time, merchant, ref, before (-1) or after (+1) a change in the same second, or 0)
CRAFTED = [
    (at(1, 9, 14, 7), "m_harbor", "same_second_after_off", 1),      # no delivery: missed
    (at(2, 8, 0, 30), "m_isle", "same_second_before_off", -1),      # has a delivery that waits
    (at(5, 15, 0, 20), "m_juniper", "same_second_before_on", -1),   # caught up at once
    (at(3, 0, 30, 2), "m_moss", "same_second_after_on", 1),         # ordinary delivery
    (at(2, 10, 1, 11), "m_harbor", "day_and_90s_before_on", 0),     # 24 h 1.5 min before the switch-on: missed
    (at(2, 10, 4, 11), "m_harbor", "day_less_90s_before_on", 0),    # 23 h 58.5 min before: caught up
    (at(1, 6, 20, 11), "m_juniper", "juniper_first_a", 0),          # the two hours of the 26 h that were missed
    (at(1, 7, 31, 40), "m_juniper", "juniper_first_b", 0),
]
WAITING = (at(2, 7, 35, 30), "m_isle", "retry_waiting_at_off")  # ep_isle_1 answers 500 until after the switch-off
OSIER_DOWN = at(5, 20, 0, 0)
SNAPSHOTS = [at(2, 23, 0, 0), at(4, 18, 30, 0), at(6, 12, 0, 0)]
RESTARTS = [(at(1, 10, 0, 0), "api"), (at(2, 5, 0, 0), "worker"), (at(3, 3, 0, 0), "router"), (at(5, 3, 0, 0), "api")]


def build_timeline(rng):
    """The ordered steps. Each is (time, order within the second, sequence, step, note)."""
    steps = []
    sequence = 0

    def add(t, step, within=0, **note):
        nonlocal sequence
        sequence += 1
        steps.append((t, within, sequence, dict(step, at=t), note))

    def event(t, merchant, ref, within=0, amount=None):
        currency = MERCHANTS[merchant][0]
        add(t, {"do": "event", "ref": ref, "merchant": merchant, "type": rng.choice(TYPES),
                "amount_minor": gp.amount(rng, currency) if amount is None else amount, "currency": currency},
            within, event=ref)

    t = 60
    for merchant, (_, endpoints) in MERCHANTS.items():
        for endpoint in endpoints:
            step = {"do": "endpoint.create", "id": endpoint, "merchant": merchant, "secret": gp.secret_for(endpoint)}
            if endpoint in CREATED_OFF:
                add(CREATED_OFF[endpoint], dict(step, enabled=False))
            else:
                add(t, step)
            t += 11
    for when, endpoint, change in CHANGES:
        add(when, dict({"do": "endpoint.update", "id": endpoint}, **change), change=(endpoint, change))
    for when, service in RESTARTS:
        add(when, {"do": "restart", "service": service})
    add(OSIER_DOWN, {"do": "receiver.script", "path": "/hooks/ep_osier_1", "responses": [], "default": 503})
    for when, merchant, ref, within in CRAFTED:
        event(when, merchant, ref, within)
    waiting, merchant, ref = WAITING
    add(waiting - 5, {"do": "receiver.script", "path": "/hooks/ep_isle_1", "responses": [500, 500, 503, 500]})
    event(waiting, merchant, ref, amount=86420)

    quiet = {m: [] for m in MERCHANTS}  # (from, to) windows with no ordinary events
    for when, endpoint, _ in CHANGES:
        quiet[owner(endpoint)].append((when - 600, when + 600))
    for endpoint, when in CREATED_OFF.items():
        quiet[owner(endpoint)].append((when - 600, when + 600))  # its merchant has events before it exists
    for when, merchant, _, _ in CRAFTED:
        quiet[merchant].append((when - 200, when + 200))
    quiet["m_isle"].append((waiting - 200, waiting + 4600))
    for when, _ in RESTARTS:
        for merchant in MERCHANTS:
            quiet[merchant].append((when - 60, when + 60))
    number = 0
    for merchant, (currency, endpoints) in MERCHANTS.items():
        count = 84 if merchant in BUSY else 50
        times = set()
        while len(times) < count:
            when = rng.randint(700, END - 300)
            if any(a <= when <= b for a, b in quiet[merchant]):
                continue
            if any(abs(when - other) < 20 for other in times):
                continue
            times.add(when)
        if merchant == "m_osier":  # a few while its server is down
            times |= {OSIER_DOWN + 1200, OSIER_DOWN + 3900, OSIER_DOWN + 7400}
        for when in sorted(times):
            number += 1
            if rng.random() < 0.09 and not (merchant == "m_osier" and when > OSIER_DOWN - 30000):
                responses = rng.choice([[500], [503, 500], ["drop"], ["refuse"], [500, "drop"], [429]])
                add(when - 3, {"do": "receiver.script", "path": "/hooks/" + rng.choice(endpoints), "responses": responses})
            event(when, merchant, f"e{number}")
    for when in SNAPSHOTS:
        add(when, {"do": "snapshot"})
    steps.sort(key=lambda item: item[:3])
    return steps


def run(app, port_base, steps):
    sys.path.insert(0, os.path.join(app, "bin"))
    import replaylib

    state_dir = tempfile.mkdtemp(prefix="inc2318-")
    dep = replaylib.Deployment(state_dir, port_base, app)
    known = {"events": {}, "snapshots": [], "changes": [], "created": {}}
    try:
        dep.set_clock(EPOCH)
        dep.start_all()
        runner = replaylib.Run(dep, {"steps": [], "epoch": EPOCH})
        for index, (when, _, _, step, note) in enumerate(steps):
            if step["do"] == "snapshot":
                dep.set_clock(EPOCH + when)
                known["snapshots"].append((when, dep.call("router", "GET", "/__admin/state")[1]))
            else:
                runner.step(step)
                if "event" in note:
                    known["events"][runner.refs[note["event"]]] = {
                        "accepted": when, "order": index, "ref": note["event"], "merchant": step["merchant"],
                        "type": step["type"], "amount_minor": step["amount_minor"], "currency": step["currency"],
                    }
                if "change" in note:
                    known["changes"].append((when, index) + note["change"])
                if step["do"] == "endpoint.create":
                    known["created"][step["id"]] = (when, index, step.get("enabled", True))
            following = steps[index + 1][0] if index + 1 < len(steps) else DAYS * DAY - 60
            if following - when > 1:
                dep.drain(limit=following - when - 1)
        dep.set_clock(EPOCH + DAYS * DAY - 30)
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


def off_periods(known):
    """Per endpoint: the off periods that ended in a switch-on, as (off time, off step, on time, on
    step), and the start of the one still open at the end, if any."""
    state = {endpoint: (enabled, when, index) for endpoint, (when, index, enabled) in known["created"].items()}
    closed = {endpoint: [] for endpoint in state}
    for when, index, endpoint, change in sorted(known["changes"]):
        if "enabled" not in change:
            continue
        enabled, since, since_index = state[endpoint]
        if enabled and not change["enabled"]:
            state[endpoint] = (False, when, index)
        elif not enabled and change["enabled"]:
            closed[endpoint].append((since, since_index, when, index))
            state[endpoint] = (True, None, None)
    still_off = {endpoint: since for endpoint, (enabled, since, _) in state.items() if not enabled}
    return closed, still_off


def truth_of(known):
    """The report the ticket asks for. Also returns the (event, endpoint) pairs that were owed and
    do have a delivery, and what is known about the near misses."""
    closed, still_off = off_periods(known)
    have = {}
    for delivery in known["router"]["deliveries"]:
        have.setdefault((delivery["event_id"], delivery["endpoint_id"]), []).append(delivery["id"])
    missed, totals, caught, per_period = [], {}, {}, []
    for endpoint in sorted(closed):
        merchant = owner(endpoint)
        mine = {e: info for e, info in known["events"].items() if info["merchant"] == merchant}
        for off, off_index, on, on_index in closed[endpoint]:
            by_time = {e for e, info in mine.items() if off <= info["accepted"] < on}
            by_order = {e for e, info in mine.items() if off_index < info["order"] < on_index}
            lost = sorted(e for e in by_time if (e, endpoint) not in have)
            # the ticket's wording (the api's timestamps) and the order things really happened in agree
            assert lost == sorted(e for e in by_order if (e, endpoint) not in have), (endpoint, off, on)
            for e in by_time:
                if (e, endpoint) in have:
                    caught[(e, endpoint)] = have[(e, endpoint)]
            per_period.append({"endpoint_id": endpoint, "switched_off_at": iso(off), "switched_on_at": iso(on),
                               "seconds_off": on - off, "hours_off": round((on - off) / 3600, 2),
                               "accepted_meanwhile": len(by_time),
                               "missed": len(lost), "caught_up_or_waiting": len(by_time) - len(lost)})
            if not lost:
                continue
            missed.append({"endpoint_id": endpoint, "switched_off_at": iso(off), "switched_on_at": iso(on),
                           "event_ids": lost})
            for e in lost:
                currency = mine[e]["currency"]
                totals[currency] = totals.get(currency, 0) + mine[e]["amount_minor"]
    missed.sort(key=lambda entry: (entry["endpoint_id"], entry["switched_on_at"]))
    report = {"missed": missed, "totals_minor": dict(sorted(totals.items()))}
    return report, caught, per_period, still_off, have


# --- the packet -----------------------------------------------------------------------


def write_packet(out, known, logs, report, caught):
    rng = random.Random(SEED)
    incident = os.path.join(out, "incident")
    shutil.rmtree(incident, ignore_errors=True)
    os.makedirs(os.path.join(incident, "snapshots"))
    receiver = known["receiver_url"]
    all_deliveries = [d["id"] for d in known["router"]["deliveries"]]
    missed_events = {e for entry in report["missed"] for e in entry["event_ids"]}
    caught_deliveries = {d for ids in caught.values() for d in ids}
    requested = {record["headers"]["webhook-id"] for record in known["received"]}

    api = logs["api.ndjson"]
    router = [gp.shift_router(line.replace(receiver, gp.HOST), gp.SKEW["router"]) for line in logs["router.log"]]
    worker = []
    for line in logs["worker.jsonl"]:
        record = json.loads(line.replace(receiver, gp.HOST))
        record["t"] += gp.SKEW["worker"]
        worker.append(json.dumps(record, sort_keys=True, separators=(",", ":")))
    egress = [gp.egress_line(record) for record in known["received"]]
    export = gp.export_rows(rng, known, all_deliveries)

    # What the report rests on may lose one of its records, never more: no fact is missing everywhere.
    #   a missed event: the api's record of it is kept; the router's `event.routed` may be cut
    #   a delivery of an owed event (it shows the event was not missed): one of the router's
    #   `delivery.created`, an egress line, the worker's `attempt.started` may be cut
    damage = {}
    for event_id in sorted(missed_events):
        if rng.random() < 0.3:
            damage[event_id] = "router.routed"
    for delivery in sorted(caught_deliveries):
        if delivery in requested and rng.random() < 0.3:
            damage[delivery] = rng.choice(["router.created", "router.created", "egress", "worker.started"])
    planned = dict(damage)
    careful = {m for m in MERCHANTS if m != "m_osier"}  # every merchant with an off period

    def api_protected(line):
        record = json.loads(line)
        if record["msg"].startswith("endpoint."):
            return True
        return record["msg"] in ("event.accepted", "event.repeated") and record.get("merchant") in careful

    def names(line):
        """The missed event or the delivery of an owed event this line is about, if any."""
        found = re.findall(r"(?:evt|dlv)_[0-9a-f]{14}", line)
        return next((i for i in found if i in caught_deliveries), None) or next((i for i in found if i in missed_events), None)

    files, skipped = {}, {}
    plan = [
        ("api.ndjson", api, gp.cut_json, 9, api_protected, (2, 1), []),
        ("router.log", router, gp.cut_fields, 26, lambda l: names(l) is not None or "msg=endpoint." in l, (3, 2),
         [("router.routed", lambda l: "msg=event.routed" in l), ("router.created", lambda l: "msg=delivery.created" in l)]),
        ("worker.jsonl", worker, gp.cut_json, 22, lambda l: names(l) is not None, (3, 1),
         [("worker.started", lambda l: '"op":"attempt.started"' in l)]),
        ("egress.log", egress, gp.cut_fields, 4, lambda l: names(l) is not None, (0, 0),
         [("egress", lambda l: True)]),
    ]
    for name, lines, cutter, cuts, protected, batches, kinds in plan:
        lines = list(lines)
        for kind, marker in kinds:
            for index, line in enumerate(lines):
                if line.startswith("\0CUT\0"):
                    continue
                for ident in re.findall(r"(?:evt|dlv)_[0-9a-f]{14}", line):
                    if damage.get(ident) == kind and marker(line):
                        lines[index] = "\0CUT\0" + cutter(rng, line)
                        damage[ident] = kind + " (done)"  # one record only
                        break
        shipped, cut_count = gp.ship(rng, lines, cutter, cuts,
                                     lambda l, p=protected: l.startswith("\0CUT\0") or p(l), batches)
        extra = sum(1 for l in shipped if l.startswith("\0CUT\0"))
        files[name] = [l.replace("\0CUT\0", "") for l in shipped]
        skipped[name] = cut_count + extra

    harmless = [i for i, row in enumerate(export) if not any(d.startswith(row[1]) for d in caught_deliveries)]
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
            "now": state["now"] + gp.SKEW["router"],
            "endpoints": [{k: e[k] for k in ("id", "merchant_id", "enabled", "version")} for e in state["endpoints"]],
            "deliveries": [
                dict({k: d[k] for k in ("id", "event_id", "endpoint_id", "resend_of", "state", "attempts")},
                     available_at=d["available_at"] + gp.SKEW["router"])
                for d in state["deliveries"]
            ],
        }
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(EPOCH + when))
        with open(os.path.join(incident, "snapshots", f"router-{stamp}.json"), "w", encoding="utf-8") as handle:
            json.dump(snapshot, handle)
    return skipped, planned, damage


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--app", help="a scratch copy of week6/app to run (default: a temporary copy)")
    parser.add_argument("--out", default=os.path.join(HERE, "inc-2318"))
    parser.add_argument("--port-base", type=int, default=26600)
    args = parser.parse_args()

    temporary = None
    if args.app:
        app = os.path.abspath(args.app)
    else:
        temporary = tempfile.mkdtemp(prefix="inc2318-app-")
        app = os.path.join(temporary, "app")
        for part in ("services", "bin", "contracts"):
            shutil.copytree(os.path.join(REPO, "week6", "app", part), os.path.join(app, part),
                            ignore=shutil.ignore_patterns(".build", "__pycache__", "node_modules", "state"))
    try:
        steps = build_timeline(random.Random(SEED))
        known, logs = run(app, args.port_base, steps)
    finally:
        if temporary:
            shutil.rmtree(temporary, ignore_errors=True)
    report, caught, per_period, still_off, have = truth_of(known)
    skipped, planned, damage = write_packet(args.out, known, logs, report, caught)
    report["skipped_rows"] = sum(skipped.values())
    with open(os.path.join(args.out, "truth.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")

    deliveries = known["router"]["deliveries"]
    events = known["events"]
    answered = {r["headers"]["webhook-id"] for r in known["received"]
                if r["processed"] and isinstance(r["response"], int) and 200 <= r["response"] < 300}
    by_ref = {info["ref"]: event_id for event_id, info in events.items()}
    missed_pairs = {(e, entry["endpoint_id"]) for entry in report["missed"] for e in entry["event_ids"]}
    events_missed = [e for e, _ in missed_pairs]

    def crafted(ref, endpoint):
        event_id = by_ref[ref]
        ids = have.get((event_id, endpoint), [])
        return {"event_id": event_id, "endpoint_id": endpoint, "accepted_at": iso(events[event_id]["accepted"]),
                "deliveries": len(ids), "got_a_2xx": any(d in answered for d in ids),
                "in_the_report": (event_id, endpoint) in missed_pairs}

    notes = {
        "period": [iso(0), iso(DAYS * DAY)],
        "events_accepted_by_api": len(events),
        "deliveries": len(deliveries),
        "requests": len(known["received"]),
        "missed_entries": len(missed_pairs),
        "missed_by_item": [{"endpoint_id": m["endpoint_id"], "switched_off_at": m["switched_off_at"],
                            "switched_on_at": m["switched_on_at"], "events": len(m["event_ids"])} for m in report["missed"]],
        "events_missed_by_two_endpoints": len(events_missed) - len(set(events_missed)),
        "off_periods_that_ended": per_period,
        "still_off_at_the_end": {e: iso(t) for e, t in sorted(still_off.items())},
        "skipped_rows_by_file": skipped,
        "cut_on_purpose": {
            "router event.routed of a missed event": sum(1 for v in damage.values() if v == "router.routed (done)"),
            "router delivery.created of a delivery of an owed event": sum(1 for v in damage.values() if v == "router.created (done)"),
            "egress line of a delivery of an owed event": sum(1 for v in damage.values() if v == "egress (done)"),
            "worker attempt.started of a delivery of an owed event": sum(1 for v in damage.values() if v == "worker.started (done)"),
        },
        "near_misses": {
            "owed at a switch-on and delivered or waiting (not missed)": len(caught),
            "of those, in an off period of less than a day": sum(
                p["caught_up_or_waiting"] for p in per_period if p["seconds_off"] < DAY),
            "accepted while an endpoint was off that is still off at the end (no switch-on, no delivery)": sum(
                1 for endpoint, since in still_off.items() for e, info in events.items()
                if info["merchant"] == owner(endpoint) and info["accepted"] >= since and (e, endpoint) not in have),
            "deliveries that never got a 2xx, by endpoint (endpoint not off at the end)": {
                endpoint: sum(1 for d in deliveries if d["endpoint_id"] == endpoint and d["id"] not in answered)
                for endpoint in sorted({d["endpoint_id"] for d in deliveries if d["id"] not in answered} - set(still_off))},
            "events of m_nettle from before its endpoint existed": sum(
                1 for info in events.values()
                if info["merchant"] == "m_nettle" and info["accepted"] < CREATED_OFF["ep_nettle_1"]),
            "same second as a change": {ref: crafted(ref, endpoint) for ref, endpoint in (
                ("same_second_after_off", "ep_harbor_1"), ("same_second_before_off", "ep_isle_1"),
                ("same_second_before_on", "ep_juniper_1"), ("same_second_after_on", "ep_moss_1"))},
            "a day and 90 s before the switch-on": crafted("day_and_90s_before_on", "ep_harbor_1"),
            "90 s less than a day before the switch-on": crafted("day_less_90s_before_on", "ep_harbor_1"),
            "accepted before the switch-off, delivery waiting for a retry, sent after the switch-on":
                crafted("retry_waiting_at_off", "ep_isle_1"),
        },
    }
    assert all(v.endswith("(done)") for v in damage.values()), {k: v for k, v in damage.items() if not v.endswith("(done)")}
    with open(os.path.join(HERE, "ground-truth-notes-2318.json"), "w", encoding="utf-8") as handle:
        json.dump(notes, handle, indent=2)
        handle.write("\n")
    print(json.dumps(notes, indent=1))


if __name__ == "__main__":
    main()
