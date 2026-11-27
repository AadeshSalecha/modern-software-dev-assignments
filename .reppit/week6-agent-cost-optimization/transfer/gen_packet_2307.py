#!/usr/bin/env python3
"""Build the INC-2307 evidence packet by running the shipped release, and its truth.

    PATH=/opt/node24/bin:$PATH python3 gen_packet_2307.py [--app <clean app tree>] [--out inc-2307] [--port-base 24000]

Built the way gen_packet.py builds INC-2231's, and with its machinery (imported): the
unmodified release is driven through three simulated days with `app/bin/replaylib.py`, the
service logs are the services' own, `egress.log` and the merchant export are written from the
merchant stand-in's records, and then the log shipper's effects are applied with a fixed
seed (clock skew per host, batches sent twice, batches delivered late, rows cut short).
Without --app the release is copied to a temporary directory first; nothing runs in week6/app.

`truth.json` is computed from what this script did and saw: which resend requests it made
and what the api answered, and which resend deliveries the router holds at the end. It does
not use `week6/kit/evidence.py`.

What happens in the packet (2026-11-09 is a Monday):
  * m_juniper  registers ep_juniper_2 on Tuesday; 12 earlier events are resent to it, 3 of
               them again on Wednesday: all accepted, none delivered         -> in the report
  * m_kestrel  ep_kestrel_1 takes payment.captured only until Tuesday afternoon; 6 other
               events are resent to it afterwards                            -> in the report
  * m_larch    ep_larch_1 is off for 32 hours; events older than a day when it comes back
               are not caught up and are resent by hand                      -> in the report
               one event is asked for while the endpoint is off (lost), then caught up, then
               asked for again (works)                         -> in the report, one request
  * m_oak      registers ep_oak_2 on Wednesday; 5 earlier events are resent  -> in the report
  * m_pine     registers ep_pine_2 switched off; 3 events are resent to it   -> in the report
               a resend to ep_pine_1 while it is off creates a delivery that waits   -> works
  * m_myrtle   ep_myrtle_1's server is down for 12 hours, deliveries die and are resent
               (one of them twice)                                                   -> works
  * m_nettle   4 delivered events are resent                                         -> works
               3 of them are first asked for with m_oak's endpoint by mistake -> left out
  * m_juniper  one event is asked for with m_pine's endpoint by mistake       -> left out
"""

import argparse
import calendar
import csv
import gzip
import io
import json
import os
import random
import shutil
import sys
import tempfile
import time

import gen_packet as gp

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
EPOCH = calendar.timegm((2026, 11, 9, 0, 0, 0))
DAY = gp.DAY
END = 3 * DAY - 1800
SEED = 2307
SKEW = {"router": -12, "worker": 33, "egress": 5}
MERCHANTS = {
    "m_juniper": ("USD", ["ep_juniper_1", "ep_juniper_2"]),
    "m_kestrel": ("EUR", ["ep_kestrel_1"]),
    "m_larch": ("GBP", ["ep_larch_1"]),
    "m_myrtle": ("JPY", ["ep_myrtle_1"]),
    "m_nettle": ("KWD", ["ep_nettle_1"]),
    "m_oak": ("EUR", ["ep_oak_1", "ep_oak_2"]),
    "m_pine": ("USD", ["ep_pine_1", "ep_pine_2"]),
    "m_quill": ("GBP", ["ep_quill_1"]),
}
REPORTER = "m_juniper"
# gen_packet's helpers read these from their own module
gp.EPOCH, gp.SKEW, gp.MERCHANTS, gp.REPORTER, gp.EXPORT_OFFSET = EPOCH, SKEW, MERCHANTS, REPORTER, 1 * 3600
at, owner, secret_for, iso, HOST, TYPES = gp.at, gp.owner, gp.secret_for, gp.iso, gp.HOST, gp.TYPES

# endpoints registered later: (time, endpoint, extra)
LATER = {
    "ep_juniper_2": (at(2, 9, 30, 11), {}),
    "ep_pine_2": (at(2, 12, 0, 7), {"enabled": False}),
    "ep_oak_2": (at(3, 8, 0, 42), {}),
}
KESTREL_WIDER = at(2, 15, 0, 30)
LARCH_OFF, LARCH_ON = at(1, 6, 0, 20), at(2, 14, 10, 5)
PINE_OFF = at(3, 14, 0, 9)
MYRTLE_DOWN, MYRTLE_UP = at(1, 18, 0, 0), at(2, 6, 0, 0)
CHANGES = [
    (LARCH_OFF, "ep_larch_1", {"enabled": False}),
    (LARCH_ON, "ep_larch_1", {"enabled": True}),
    (KESTREL_WIDER, "ep_kestrel_1", {"event_types": ["*"]}),
    (PINE_OFF, "ep_pine_1", {"enabled": False}),
]
EXTRA_EVENTS = {
    "m_larch": [at(1, 7, 12, 40), at(1, 9, 3, 15), at(1, 11, 47, 2), at(1, 13, 20, 33)],
    "m_myrtle": [at(1, 18, 30, 5), at(1, 19, 45, 50), at(1, 20, 20, 20), at(1, 21, 10, 10), at(1, 22, 5, 45)],
}
SNAPSHOTS = [at(1, 23, 0, 0), at(2, 18, 0, 0), at(3, 12, 0, 0)]
RESTARTS = [(at(1, 10, 0, 0), "api"), (at(2, 5, 0, 0), "worker"), (at(3, 3, 0, 0), "router")]


def build_timeline(rng):
    """The ordered steps. A resend step's note says what the generator expects of it:
    lost (accepted, no delivery), works, or cross (another merchant's endpoint)."""
    steps = []
    order = 0

    def add(t, step, **note):
        nonlocal order
        order += 1
        steps.append((t, order, dict(step, at=t), note))

    t = 60
    for merchant, (_, endpoints) in MERCHANTS.items():
        for endpoint in endpoints:
            if endpoint in LATER:
                continue
            extra = {"event_types": ["payment.captured"]} if endpoint == "ep_kestrel_1" else {}
            add(t, dict({"do": "endpoint.create", "id": endpoint, "merchant": merchant, "secret": secret_for(endpoint)}, **extra))
            t += 11
    for endpoint, (when, extra) in LATER.items():
        add(when, dict({"do": "endpoint.create", "id": endpoint, "merchant": owner(endpoint),
                        "secret": secret_for(endpoint)}, **extra))
    for when, endpoint, change in CHANGES:
        add(when, dict({"do": "endpoint.update", "id": endpoint}, **change))
    for when, service in RESTARTS:
        add(when, {"do": "restart", "service": service})
    add(MYRTLE_DOWN, {"do": "receiver.script", "path": "/hooks/ep_myrtle_1", "responses": [], "default": 503})
    add(MYRTLE_UP, {"do": "receiver.script", "path": "/hooks/ep_myrtle_1", "responses": [], "default": 200})

    quiet = {m: [] for m in MERCHANTS}  # (from, to) windows with no ordinary events
    for when, endpoint, _ in CHANGES:
        quiet[owner(endpoint)].append((when - 600, when + 600))
    for endpoint, (when, _) in LATER.items():
        quiet[owner(endpoint)].append((when - 600, when + 600))
    for when, _ in RESTARTS:
        for merchant in MERCHANTS:
            quiet[merchant].append((when - 60, when + 60))
    events = {m: [] for m in MERCHANTS}  # merchant -> [(time, ref, type)]
    number = 0
    for merchant, (currency, endpoints) in MERCHANTS.items():
        count = 44 if merchant in ("m_juniper", "m_oak") else 36
        times = set(EXTRA_EVENTS.get(merchant, []))
        while len(times) < count + len(EXTRA_EVENTS.get(merchant, [])):
            when = rng.randint(700, END - 300)
            if any(a <= when <= b for a, b in quiet[merchant]):
                continue
            if any(abs(when - other) < 20 for other in times):
                continue
            times.add(when)
        for when in sorted(times):
            number += 1
            ref = f"e{number}"
            type_ = rng.choice(TYPES)
            if rng.random() < 0.09 and merchant != "m_myrtle":
                responses = rng.choice([[500], [503, 500], ["drop"], ["refuse"], [500, "drop"], [429]])
                add(when - 3, {"do": "receiver.script", "path": "/hooks/" + endpoints[0], "responses": responses})
            add(when, {"do": "event", "ref": ref, "merchant": merchant, "type": type_,
                       "amount_minor": gp.amount(rng, currency), "currency": currency}, event=ref)
            events[merchant].append((when, ref, type_))

    def before(merchant, limit, keep=lambda item: True):
        return [item for item in events[merchant] if item[0] < limit and keep(item)]

    def ask(when, ref, endpoint, kind):
        add(when, {"do": "resend", "event": ref, "endpoint": endpoint}, kind=kind)

    # m_juniper: the new endpoint, asked on Tuesday and again on Wednesday
    juniper = rng.sample(before("m_juniper", LATER["ep_juniper_2"][0] - 600), 12)
    for n, (_, ref, _) in enumerate(juniper):
        ask(at(2, 10, 5, 0) + n * 47, ref, "ep_juniper_2", "lost")
    for n, (_, ref, _) in enumerate(juniper[:3]):
        ask(at(3, 9, 2, 0) + n * 61, ref, "ep_juniper_2", "lost")
    ask(at(2, 10, 12, 30), juniper[0][1], "ep_pine_1", "cross")
    taken = {ref for _, ref, _ in juniper}
    others = [item for item in before("m_juniper", at(2, 9, 0, 0)) if item[1] not in taken]
    for n, (_, ref, _) in enumerate(rng.sample(others, 2)):
        ask(at(2, 10, 20, 0) + n * 37, ref, "ep_juniper_1", "works")
    # m_kestrel: types the endpoint did not take
    kestrel = before("m_kestrel", KESTREL_WIDER - 600, lambda item: item[2] != "payment.captured")
    for n, (_, ref, _) in enumerate(rng.sample(kestrel, 6)):
        ask(at(2, 15, 31, 0) + n * 53, ref, "ep_kestrel_1", "lost")
    # m_larch: off for 32 hours; what is older than a day when it comes back is not caught up
    larch = [item for item in events["m_larch"] if LARCH_OFF < item[0] < LARCH_ON - DAY]
    for n, (_, ref, _) in enumerate(larch):
        ask(at(2, 16, 0, 0) + n * 49, ref, "ep_larch_1", "lost")
    caught_up = next(item for item in events["m_larch"] if LARCH_ON - DAY + 600 < item[0] < at(2, 9, 0, 0) - 600)
    ask(at(2, 9, 0, 17), caught_up[1], "ep_larch_1", "lost")  # while it is off
    ask(at(2, 16, 20, 3), caught_up[1], "ep_larch_1", "works")  # after the catch-up
    # m_myrtle: deliveries that died while the server was down
    myrtle = [item for item in events["m_myrtle"] if MYRTLE_DOWN <= item[0] <= at(1, 22, 30, 0)]
    for n, (_, ref, _) in enumerate(myrtle):
        ask(at(2, 10, 30, 0) + n * 43, ref, "ep_myrtle_1", "works")
    ask(at(2, 10, 50, 0), myrtle[0][1], "ep_myrtle_1", "works")
    # m_nettle: replays the merchant asked for; three first typed with m_oak's endpoint
    nettle = rng.sample(before("m_nettle", at(3, 9, 0, 0)), 4)
    for n, (_, ref, _) in enumerate(nettle[:3]):
        ask(at(3, 9, 40, 0) + n * 31, ref, "ep_oak_1", "cross")
    for n, (_, ref, _) in enumerate(nettle):
        ask(at(3, 10, 0, 0) + n * 59, ref, "ep_nettle_1", "works")
    # m_oak: the new endpoint
    for n, (_, ref, _) in enumerate(rng.sample(before("m_oak", LATER["ep_oak_2"][0] - 600), 5)):
        ask(at(3, 8, 31, 0) + n * 45, ref, "ep_oak_2", "lost")
    # m_pine: an endpoint registered switched off; and a resend to the first one while it is off
    pine = rng.sample(before("m_pine", LATER["ep_pine_2"][0] - 600), 3)
    for n, (_, ref, _) in enumerate(pine):
        ask(at(2, 12, 31, 0) + n * 52, ref, "ep_pine_2", "lost")
    waiting = rng.choice(before("m_pine", at(3, 13, 0, 0)))
    ask(at(3, 15, 0, 20), waiting[1], "ep_pine_1", "works")

    for when in SNAPSHOTS:
        add(when, {"do": "snapshot"})
    steps.sort(key=lambda item: (item[0], item[1]))
    return steps


def run(app, port_base, steps):
    sys.path.insert(0, os.path.join(app, "bin"))
    import replaylib

    state_dir = tempfile.mkdtemp(prefix="inc2307-")
    dep = replaylib.Deployment(state_dir, port_base, app)
    known = {"events": {}, "snapshots": [], "requests": []}
    try:
        dep.set_clock(EPOCH)
        dep.start_all()
        runner = replaylib.Run(dep, {"steps": [], "epoch": EPOCH})
        for index, (when, _, step, note) in enumerate(steps):
            if step["do"] == "snapshot":
                dep.set_clock(EPOCH + when)
                known["snapshots"].append((when, dep.call("router", "GET", "/__admin/state")[1]))
            elif step["do"] == "resend":
                dep.set_clock(EPOCH + when)
                event_id = runner.refs[step["event"]]
                status, _ = dep.call("api", "POST", f"/v1/events/{event_id}/resend", {"endpoint_id": step["endpoint"]})
                known["requests"].append({"at": when, "event": event_id, "endpoint": step["endpoint"],
                                          "status": status, "expected": note["kind"]})
            else:
                runner.step(step)
                if "event" in note:
                    known["events"][runner.refs[note["event"]]] = {
                        "accepted": when, "merchant": step["merchant"], "type": step["type"],
                        "amount_minor": step["amount_minor"], "currency": step["currency"],
                    }
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


def truth_of(known):
    """The report the ticket asks for, from the requests this script made, what the api
    answered, and the resend deliveries the router holds at the end.

    Returns (report, pairs): pairs maps (event, endpoint) to its accepted requests, the
    resend deliveries the router made for it, and how many requests were lost."""
    pairs = {}
    for request in known["requests"]:
        if request["status"] != 202:
            continue
        pair = pairs.setdefault((request["event"], request["endpoint"]), {"requests": [], "made": [], "expected": []})
        pair["requests"].append(request["at"])
        pair["expected"].append(request["expected"])
    for delivery in known["router"]["deliveries"]:
        pair = pairs.get((delivery["event_id"], delivery["endpoint_id"]))
        if pair is not None and delivery["resend_of"] is not None:
            pair["made"].append(delivery["id"])
    merchants, totals = {}, {}
    for (event_id, endpoint), pair in sorted(pairs.items()):
        event = known["events"][event_id]
        pair["cross"] = owner(endpoint) != event["merchant"]
        pair["lost"] = 0 if pair["cross"] else len(pair["requests"]) - len(pair["made"])
        # the release did what this script expected of every request
        assert pair["lost"] == pair["expected"].count("lost"), (event_id, endpoint, pair)
        assert pair["cross"] == ("cross" in pair["expected"]) and (not pair["cross"] or not pair["made"]), pair
        if pair["lost"]:
            entry = merchants.setdefault(event["merchant"], {"merchant_id": event["merchant"], "lost_requests": 0, "resends": []})
            entry["lost_requests"] += pair["lost"]
            entry["resends"].append({"event_id": event_id, "endpoint_id": endpoint})
            totals[event["currency"]] = totals.get(event["currency"], 0) + event["amount_minor"]
    report = {"merchants": [merchants[m] for m in sorted(merchants)], "totals_minor": dict(sorted(totals.items()))}
    return report, pairs


# --- the packet -----------------------------------------------------------------------


def write_packet(out, known, logs, pairs):
    rng = random.Random(SEED)
    incident = os.path.join(out, "incident")
    shutil.rmtree(incident, ignore_errors=True)
    os.makedirs(os.path.join(incident, "snapshots"))
    receiver = known["receiver_url"]
    deliveries = known["router"]["deliveries"]
    all_deliveries = [d["id"] for d in deliveries]

    api = list(logs["api.ndjson"])
    router = [gp.shift_router(line.replace(receiver, HOST), SKEW["router"]) for line in logs["router.log"]]
    worker = []
    for line in logs["worker.jsonl"]:
        record = json.loads(line.replace(receiver, HOST))
        record["t"] += SKEW["worker"]
        worker.append(json.dumps(record, sort_keys=True, separators=(",", ":")))
    egress = [gp.egress_line(record) for record in known["received"]]
    export = gp.export_rows(rng, known, all_deliveries)

    # Everything about an event somebody asked to resend is kept whole, except one planned
    # cut per chosen request: no fact the report needs is missing from every file.
    asked = {event for event, _ in pairs}
    involved = asked | {d["id"] for d in deliveries if d["event_id"] in asked}
    answered = {r["headers"]["webhook-id"] for r in known["received"]
                if r["processed"] and isinstance(r["response"], int) and 200 <= r["response"] < 300}
    damage = {}
    for pair, facts in sorted(pairs.items()):
        if len(facts["requests"]) != 1 or facts["cross"] or rng.random() >= 0.3:
            continue
        if facts["lost"]:
            damage[pair] = rng.choice(["api", "router.skipped"])  # the other record still says it
        elif facts["made"][0] in answered:
            damage[pair] = rng.choice(["api", "router.created"])  # the delivery's other records still show it

    def names_involved(line):
        return any(name in line for name in involved)

    def api_protected(line):
        record = json.loads(line)
        return record["msg"].startswith("endpoint.") or record["msg"] == "resend.requested" or names_involved(line)

    def router_protected(line):
        return "msg=endpoint." in line or "msg=resend.skipped" in line or names_involved(line)

    def planned(name, line):
        """The pair whose record this line is, when that record is the one planned to be cut."""
        if name == "api.ndjson":
            record = json.loads(line)
            pair = (record.get("event"), record.get("endpoint"))
            return pair if record["msg"] == "resend.requested" and damage.get(pair) == "api" else None
        fields = dict(token.split("=", 1) for token in line.split(" ")[1:] if "=" in token)
        pair = (fields.get("event"), fields.get("endpoint"))
        if fields.get("msg") == "resend.skipped" and damage.get(pair) == "router.skipped":
            return pair
        if fields.get("msg") == "delivery.created" and "resend_of" in fields and damage.get(pair) == "router.created":
            return pair
        return None

    def twice(lines, marker):
        """The batch around the first line with this marker is sent a second time."""
        index = next(i for i, line in enumerate(lines) if marker in line and not line.startswith("\0CUT\0"))
        batch = lines[max(0, index - 12):index + 14]
        where = min(len(lines), index + 14 + rng.randint(120, 300))
        lines[where:where] = batch

    files, skipped, done = {}, {}, set()
    plans = [
        ("api.ndjson", api, gp.cut_json, 9, api_protected, (2, 1)),
        ("router.log", router, gp.cut_fields, 22, router_protected, (3, 2)),
        ("worker.jsonl", worker, gp.cut_json, 20, names_involved, (3, 1)),
        ("egress.log", egress, gp.cut_fields, 3, names_involved, (0, 0)),
    ]
    for name, lines, cutter, cuts, protected, batches in plans:
        lines = list(lines)
        if name in ("api.ndjson", "router.log"):
            for index, line in enumerate(lines):
                pair = planned(name, line)
                if pair is not None:
                    lines[index] = "\0CUT\0" + cutter(rng, line)
                    done.add(pair)
            twice(lines, '"msg":"resend.requested"' if name == "api.ndjson" else "msg=resend.skipped")
        shipped, cut_count = gp.ship(rng, lines, cutter, cuts,
                                     lambda l, p=protected: l.startswith("\0CUT\0") or p(l), batches)
        extra = sum(1 for l in shipped if l.startswith("\0CUT\0"))
        files[name] = [l.replace("\0CUT\0", "") for l in shipped]
        skipped[name] = cut_count + extra
    assert done == set(damage), sorted(set(damage) - done)

    harmless = [i for i, row in enumerate(export) if not any(d.startswith(row[1]) for d in involved)]
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


def clean_copy(tmp):
    app = os.path.join(tmp, "app")
    leave = shutil.ignore_patterns(".build", "__pycache__", "node_modules", "state", ".pytest_cache")
    for part in ("services", "bin", "contracts", "scenarios"):
        shutil.copytree(os.path.join(REPO, "week6", "app", part), os.path.join(app, part), ignore=leave)
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--app", help="a clean copy of week6/app to run (default: a temporary copy)")
    parser.add_argument("--out", default=os.path.join(HERE, "inc-2307"))
    parser.add_argument("--port-base", type=int, default=24000)
    args = parser.parse_args()

    steps = build_timeline(random.Random(SEED))
    tmp = tempfile.mkdtemp(prefix="inc2307-app-")
    try:
        app = os.path.abspath(args.app) if args.app else clean_copy(tmp)
        known, logs = run(app, args.port_base, steps)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    report, pairs = truth_of(known)
    skipped, damage = write_packet(args.out, known, logs, pairs)
    report["skipped_rows"] = sum(skipped.values())
    with open(os.path.join(args.out, "truth.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")

    deliveries = known["router"]["deliveries"]
    state_of = {d["id"]: d["state"] for d in deliveries}
    firsts = {(d["event_id"], d["endpoint_id"]) for d in deliveries if d["resend_of"] is None}
    accepted = [r for r in known["requests"] if r["status"] == 202]
    worked = {pair: facts for pair, facts in pairs.items() if facts["made"]}
    notes = {
        "period": [iso(0), iso(3 * DAY - 30)],
        "events_accepted_by_api": len(known["events"]),
        "deliveries": len(deliveries),
        "requests_to_merchants": len(known["received"]),
        "resend_requests_accepted": len(accepted),
        "resend_requests_lost": sum(facts["lost"] for facts in pairs.values()),
        "lost_by_merchant": {m["merchant_id"]: {"lost_requests": m["lost_requests"], "events_and_endpoints": len(m["resends"])}
                             for m in report["merchants"]},
        "totals_minor": report["totals_minor"],
        "skipped_rows_by_file": skipped,
        "near_misses": {
            "resend requests that worked (a resend delivery was made)": sum(len(f["made"]) for f in pairs.values()),
            "  of those, for a delivery that had died": sum(
                len(f["made"]) for (e, p), f in worked.items()
                if any(d["event_id"] == e and d["endpoint_id"] == p and d["resend_of"] is None and d["state"] == "dead" for d in deliveries)),
            "  of those, still waiting at the end because the endpoint is off": sum(
                1 for f in worked.values() for d in f["made"] if state_of[d] == "queued"),
            "requests naming another merchant's endpoint (accepted, nothing made, left out)": sum(
                len(f["requests"]) for f in pairs.values() if f["cross"]),
            "events with a lost request to their own merchant's endpoint and a request to another merchant's": sum(
                1 for (e, p), f in pairs.items() if f["cross"] and any(e == e2 and f2["lost"] for (e2, _), f2 in pairs.items())),
            "event and endpoint asked for twice, both lost": sum(1 for f in pairs.values() if f["lost"] == 2),
            "event and endpoint asked for twice, both worked": sum(1 for f in pairs.values() if len(f["made"]) == 2),
            "event and endpoint asked for twice, one lost and one worked (caught up in between)": sum(
                1 for f in pairs.values() if f["lost"] == 1 and len(f["made"]) == 1),
            "lost requests whose event and endpoint has a first delivery all the same (catch-up)": sum(
                f["lost"] for pair, f in pairs.items() if f["lost"] and pair in firsts),
            "lost requests to an endpoint that is switched off": sum(
                f["lost"] for (e, p), f in pairs.items() if p == "ep_pine_2"),
        },
        "records_cut_on_purpose": {
            "lost request, api record cut (router's resend.skipped is whole)": sum(
                1 for pair, kind in damage.items() if kind == "api" and pairs[pair]["lost"]),
            "lost request, router's resend.skipped cut (api record is whole)": sum(
                1 for kind in damage.values() if kind == "router.skipped"),
            "request that worked, api record cut": sum(
                1 for pair, kind in damage.items() if kind == "api" and not pairs[pair]["lost"]),
            "request that worked, router's delivery.created cut (egress, worker and later router records are whole)": sum(
                1 for kind in damage.values() if kind == "router.created"),
        },
    }
    with open(os.path.join(HERE, "ground-truth-notes-2307.json"), "w", encoding="utf-8") as handle:
        json.dump(notes, handle, indent=2)
        handle.write("\n")
    print(json.dumps(notes, indent=1))


if __name__ == "__main__":
    main()
