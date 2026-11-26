#!/usr/bin/env python3
"""Write inc-2231/scenarios.json: the judge's scenarios for INC-2231.

    python3 gen_scenarios.py

A list of [category, scenario] in the format week6/kit/rollout.py plays (replaylib's, plus
the `upgrade` step and endpoint-level expectations). The three shipped scenarios in
app/scenarios are added to `regressions` by judge.py at run time.

Every expectation is about what a merchant's endpoint receives, never about how a fix
stores or numbers things:
  incident     a change made through the api holds, before or after an archive message for
               the endpoint, and when the shipped release has already lost it
  regressions  ordinary endpoint changes behave as they do today
  compat       version 1 and version 2 messages still do what they did
"""

import base64
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
M = "m_acme"
NEW_SECRET = "whsec_" + base64.b64encode(b"a-new-secret-for-acme-01").decode()


def secret_for(name):  # what replaylib gives an endpoint created without a secret
    return "whsec_" + base64.b64encode(hashlib.sha256(name.encode()).digest()[:24]).decode()


def create(at, endpoint="ep_a", merchant=M, **more):
    return dict({"at": at, "do": "endpoint.create", "id": endpoint, "merchant": merchant}, **more)


def update(at, endpoint="ep_a", **change):
    return dict({"at": at, "do": "endpoint.update", "id": endpoint}, **change)


def event(at, ref, merchant=M, amount=1250, currency="USD"):
    return {"at": at, "do": "event", "ref": ref, "merchant": merchant, "type": "payment.captured",
            "amount_minor": amount, "currency": currency}


def archive_endpoint(at, seq, endpoint="ep_a", merchant=M, active=True, ref=None):
    message = {"v": 2, "seq": seq, "kind": "endpoint",
               "endpoint": {"id": endpoint, "merchant": merchant, "url": "{receiver}/hooks/" + endpoint,
                            "secret": secret_for(endpoint), "types": ["*"], "active": active}}
    step = {"at": at, "do": "bus", "message": message}
    if ref:
        step["ref"] = ref
    return step


def archive_event(at, seq, ref, merchant, amount=990, currency="EUR"):
    return {"at": at, "do": "bus", "ref": ref, "message": {
        "v": 2, "seq": seq, "kind": "event",
        "event": {"id": f"evt_archive{seq:07d}", "merchant": merchant, "type": "payment.captured",
                  "created": 1790000000 + seq, "payment_id": f"pay_archive{seq:07d}",
                  "amount_minor": amount, "currency": currency}}}


def drain(at):
    return {"at": at, "do": "drain"}


def upgrade(at):
    return {"at": at, "do": "upgrade"}


def to(endpoint, ref):
    return {"event": ref, "endpoint": endpoint}


INCIDENT = [
    {"name": "an endpoint switched off through the api gets nothing more, after an archive message for it",
     "steps": [create(0), drain(1), archive_endpoint(10, 4100), update(20, enabled=False), drain(21),
               event(60, "e1"), drain(61)],
     "expect": [{"endpoint": "ep_a", "requests": 0}]},
    {"name": "a rotated secret signs the next delivery, after an archive message for the endpoint",
     "steps": [create(0), drain(1), archive_endpoint(10, 4100), update(20, secret=NEW_SECRET), drain(21),
               event(60, "e1"), drain(61)],
     "expect": [{"delivery": to("ep_a", "e1"), "state": "delivered", "secrets": [NEW_SECRET]}]},
    {"name": "a new address gets the next delivery, after an archive message for the endpoint",
     "steps": [create(0), drain(1), archive_endpoint(10, 4100), update(20, path="/hooks/ep_a/new"), drain(21),
               event(60, "e1"), drain(61)],
     "expect": [{"delivery": to("ep_a", "e1"), "state": "delivered", "path": ["/hooks/ep_a/new"]}]},
    {"name": "an archive message that arrives after a switch-off does not switch the endpoint back on",
     "steps": [create(0), drain(1), update(20, enabled=False), drain(21), archive_endpoint(40, 4100), drain(41),
               event(60, "e1"), drain(61)],
     "expect": [{"endpoint": "ep_a", "requests": 0}]},
    {"name": "a switch-off the deployed release lost takes effect once the release is replaced",
     "start": "deployed",
     "steps": [create(0), drain(1), archive_endpoint(10, 4100), update(20, enabled=False), drain(21),
               upgrade(40), drain(41), event(60, "e1"), drain(61)],
     "expect": [{"endpoint": "ep_a", "requests": 0}]},
    {"name": "a delivery queued for an endpoint whose switch-off was lost is not sent once the release is replaced",
     "start": "deployed",
     "steps": [create(0), drain(1), archive_endpoint(10, 4100), update(20, enabled=False), event(30, "e1"),
               {"at": 31, "do": "tick", "service": "api"}, upgrade(40), drain(41)],
     "expect": [{"endpoint": "ep_a", "requests": 0}]},
    {"name": "an endpoint the deployed release took an archive message for can be switched off after the release is replaced",
     "start": "deployed",
     "steps": [create(0), drain(1), archive_endpoint(10, 4100), drain(11), upgrade(40), drain(41),
               update(50, enabled=False), drain(51), event(60, "e1"), drain(61)],
     "expect": [{"endpoint": "ep_a", "requests": 0}]},
    {"name": "a rotated secret the deployed release lost signs deliveries once the release is replaced",
     "start": "deployed",
     "steps": [create(0), drain(1), archive_endpoint(10, 4100), update(20, secret=NEW_SECRET), drain(21),
               upgrade(40), drain(41), event(60, "e1"), drain(61)],
     "expect": [{"delivery": to("ep_a", "e1"), "state": "delivered", "secrets": [NEW_SECRET]}]},
    {"name": "starting the replaced release again changes nothing more",
     "start": "deployed",
     "steps": [create(0), create(1, "ep_b"), drain(2), archive_endpoint(10, 4100), update(20, enabled=False), drain(21),
               upgrade(40), drain(41), {"at": 45, "do": "restart", "service": "router"},
               {"at": 46, "do": "restart", "service": "api"}, {"at": 47, "do": "restart", "service": "worker"},
               drain(48), event(60, "e1"), drain(61)],
     "expect": [{"endpoint": "ep_a", "requests": 0}, {"endpoint": "ep_b", "requests": 1, "accepted": 1}]},
]

REGRESSIONS = [
    {"name": "an endpoint switched off through the api gets nothing more; the merchant's other endpoint does",
     "steps": [create(0), create(1, "ep_b"), drain(2), update(20, enabled=False), drain(21), event(60, "e1"), drain(61)],
     "expect": [{"endpoint": "ep_a", "requests": 0},
                {"delivery": to("ep_b", "e1"), "state": "delivered", "receipts": 1}]},
    {"name": "an endpoint switched on again gets what it missed, once",
     "steps": [create(0), drain(1), update(20, enabled=False), drain(21), event(100, "e1"), drain(101),
               update(200, enabled=True), drain(201)],
     "expect": [{"delivery": to("ep_a", "e1"), "state": "delivered", "receipts": 1},
                {"endpoint": "ep_a", "requests": 1}]},
    {"name": "a rotated secret signs the next delivery",
     "steps": [create(0), drain(1), update(20, secret=NEW_SECRET), drain(21), event(60, "e1"), drain(61)],
     "expect": [{"delivery": to("ep_a", "e1"), "state": "delivered", "secrets": [NEW_SECRET]}]},
    {"name": "a new address gets the next delivery",
     "steps": [create(0), drain(1), update(20, path="/hooks/ep_a/new"), drain(21), event(60, "e1"), drain(61)],
     "expect": [{"delivery": to("ep_a", "e1"), "state": "delivered", "path": ["/hooks/ep_a/new"]}]},
    {"name": "an older change that arrives late does not undo a newer one",
     "steps": [create(0), drain(1),
               {"at": 20, "do": "bus", "ref": "newer", "message": {
                   "v": 3, "producer": "api", "seq": 9001, "type": "endpoint.changed", "at": 1793577620,
                   "data": {"endpoint": {"id": "ep_a", "merchant_id": M, "url": "{receiver}/hooks/ep_a",
                                         "secret": secret_for("ep_a"), "event_types": ["*"], "enabled": False, "version": 5}}}},
               {"at": 21, "do": "bus", "ref": "older", "message": {
                   "v": 3, "producer": "api", "seq": 9000, "type": "endpoint.changed", "at": 1793577619,
                   "data": {"endpoint": {"id": "ep_a", "merchant_id": M, "url": "{receiver}/hooks/ep_a",
                                         "secret": secret_for("ep_a"), "event_types": ["*"], "enabled": True, "version": 4}}}},
               drain(22), event(60, "e1"), drain(61)],
     "expect": [{"status": "newer", "is": 200}, {"status": "older", "is": 200}, {"endpoint": "ep_a", "requests": 0}]},
    {"name": "a switch-off the deployed release applied still holds after the release is replaced, and can be undone",
     "start": "deployed",
     "steps": [create(0), drain(1), update(20, enabled=False), drain(21), event(100, "e1"), drain(101),
               upgrade(150), drain(151), event(160, "e2"), drain(161), update(300, enabled=True), drain(301)],
     "expect": [{"delivery": to("ep_a", "e1"), "state": "delivered", "receipts": 1, "first_receipt_at_least": 300},
                {"delivery": to("ep_a", "e2"), "state": "delivered", "receipts": 1, "first_receipt_at_least": 300},
                {"endpoint": "ep_a", "requests": 2}]},
]

COMPAT = [
    {"name": "a version 1 event is delivered once, in minor units",
     "steps": [create(0), drain(1),
               {"at": 10, "do": "bus", "ref": "old1", "message": {
                   "id": "evt_legacy0000001", "merchant": M, "event_type": "payment.captured", "amount": "12.5",
                   "currency": "USD", "payment": "pay_legacy0000001", "ts": "2026-11-02T00:00:00Z"}},
               {"at": 11, "do": "bus", "ref": "old1again", "message": {
                   "id": "evt_legacy0000001", "merchant": M, "event_type": "payment.captured", "amount": "12.5",
                   "currency": "USD", "payment": "pay_legacy0000001", "ts": "2026-11-02T00:00:00Z"}},
               drain(12)],
     "expect": [{"status": "old1", "is": 200}, {"status": "old1again", "is": 200},
                {"delivery": to("ep_a", "old1"), "state": "delivered", "receipts": 1, "amount_minor": 1250, "currency": "USD"}]},
    {"name": "an endpoint that exists only in the archive is created and gets its version 2 events",
     "steps": [archive_endpoint(0, 10, "ep_old", "m_old", ref="made"), archive_event(5, 11, "a1", "m_old"), drain(6)],
     "expect": [{"status": "made", "is": 200}, {"status": "a1", "is": 200},
                {"delivery": to("ep_old", "a1"), "state": "delivered", "receipts": 1, "amount_minor": 990, "currency": "EUR"}]},
    {"name": "version 2 changes to an archive-only endpoint apply in order",
     "steps": [archive_endpoint(0, 10, "ep_old", "m_old"), archive_endpoint(5, 11, "ep_old", "m_old", active=False, ref="off"),
               archive_event(10, 12, "a1", "m_old"), drain(11)],
     "expect": [{"status": "off", "is": 200}, {"endpoint": "ep_old", "requests": 0}]},
    {"name": "an archive-only endpoint the deployed release created gets version 2 events after the release is replaced",
     "start": "deployed",
     "steps": [archive_endpoint(0, 10, "ep_old", "m_old"), drain(1), upgrade(20), drain(21),
               archive_event(30, 11, "a1", "m_old"), drain(31)],
     "expect": [{"delivery": to("ep_old", "a1"), "state": "delivered", "receipts": 1}]},
]


def main():
    scenarios = (
        [["incident", s] for s in INCIDENT] + [["regressions", s] for s in REGRESSIONS] + [["compat", s] for s in COMPAT]
    )
    path = os.path.join(HERE, "inc-2231", "scenarios.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(scenarios, handle, indent=1)
        handle.write("\n")
    print(f"{path}: " + ", ".join(f"{name} {len(group)}" for name, group in
                                  (("incident", INCIDENT), ("regressions", REGRESSIONS), ("compat", COMPAT))))


if __name__ == "__main__":
    main()
