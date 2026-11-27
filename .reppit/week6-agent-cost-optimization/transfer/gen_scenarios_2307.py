#!/usr/bin/env python3
"""Write inc-2307/scenarios.json: the judge's scenarios for INC-2307.

    python3 gen_scenarios_2307.py

A list of [category, scenario] in the format week6/kit/rollout.py plays (replaylib's, plus
the `upgrade` step and endpoint-level expectations). The three shipped scenarios in
app/scenarios are added to `regressions` by judge.py at run time.

Every expectation is about what a merchant's endpoint receives (requests, accepted requests,
distinct delivery ids, distinct events), never about how a fix stores a resend: no scenario
looks at `resend_of`, at the number of rows the router keeps, or at the API's answer to a
request the ticket leaves open.

  incident     a resend to an endpoint that never had a delivery of the event arrives:
               A  the plain cases on new traffic
               B  the variants the ticket names
               C  with a restart or a crash point in the path
               D  requests the shipped release had already accepted when it was replaced
  regressions  resends and routing that work today keep working; a resend never crosses
               merchants, on new traffic or when the release is replaced
  compat       version 1 and version 2 messages still do what they did

No step asks the candidate's API for a resend to another merchant's endpoint: the ticket
lets a repair answer that with 202 or 404, and replaylib's `resend` step fails on 404. Those
requests are made on the shipped release (before `upgrade`) or arrive as bus messages.
"""

import json
import os

from gen_scenarios import COMPAT as COMPAT_2231
from gen_scenarios import archive_endpoint, archive_event, create, drain, to, update, upgrade

HERE = os.path.dirname(os.path.abspath(__file__))
M = "m_acme"
OTHER = "m_bolt"
EPOCH = 1793577600  # replaylib's
HOURS = 3600


def event(at, ref, type_="payment.captured", merchant=M, amount=1250, currency="USD"):
    return {"at": at, "do": "event", "ref": ref, "merchant": merchant, "type": type_,
            "amount_minor": amount, "currency": currency}


def resend(at, ref, endpoint):
    return {"at": at, "do": "resend", "event": ref, "endpoint": endpoint}


def restart(at, *services):
    return [{"at": at + n, "do": "restart", "service": service} for n, service in enumerate(services)]


def script(at, endpoint, responses=(), default=200):
    return {"at": at, "do": "receiver.script", "path": "/hooks/" + endpoint, "responses": list(responses),
            "default": default}


def bus_event(at, seq, ref, event_id, merchant=M, amount=1250, currency="USD"):
    """An `event.accepted` message as the api publishes it, posted to the router as is."""
    return {"at": at, "do": "bus", "ref": ref, "message": {
        "v": 3, "producer": "api", "seq": seq, "type": "event.accepted", "at": EPOCH + at,
        "data": {"event": {"id": event_id, "merchant_id": merchant, "type": "payment.captured", "created": EPOCH + at,
                           "data": {"object": "payment", "payment_id": "pay_" + event_id[4:],
                                    "amount_minor": amount, "currency": currency}}}}}


def bus_resend(at, seq, ref, event_id, endpoint):
    """A `resend.requested` message as the api publishes it, posted to the router as is."""
    return {"at": at, "do": "bus", "ref": ref, "message": {
        "v": 3, "producer": "api", "seq": seq, "type": "resend.requested", "at": EPOCH + at,
        "data": {"event_id": event_id, "endpoint_id": endpoint}}}


def got(endpoint, requests=1, accepted=None, deliveries=None, events=1):
    """What the endpoint received in total."""
    return {"endpoint": endpoint, "requests": requests,
            "accepted": requests if accepted is None else accepted,
            "deliveries": requests if deliveries is None else deliveries, "events": events}


def nothing(endpoint):
    return {"endpoint": endpoint, "requests": 0}


V1_EVENT = {"id": "evt_legacy0000001", "merchant": M, "event_type": "payment.captured", "amount": "12.5",
            "currency": "USD", "payment": "pay_legacy0000001", "ts": "2026-11-02T00:00:00Z"}

# e1 goes to ep_a; ep_b is registered afterwards
LATER = [create(0), event(5, "e1"), drain(6), create(20, "ep_b"), drain(21)]
# ep_a takes payments only; e1 is a refund
NARROW = [create(0, event_types=["payment.captured"]), event(5, "e1", "refund.created", amount=300, currency="EUR"), drain(6)]
# ep_b is registered afterwards and is switched off
LATER_OFF = [create(0), event(5, "e1"), drain(6), create(20, "ep_b", enabled=False), drain(21)]

INCIDENT = [
    # A: the plain cases, on new traffic
    {"name": "a resend to an endpoint registered after the event arrives, once",
     "steps": LATER + [resend(30, "e1", "ep_b"), drain(31)],
     "expect": [got("ep_b"), got("ep_a")]},
    {"name": "a resend to an endpoint that did not take the event's type when it was accepted, and does now, arrives",
     "steps": NARROW + [update(20, event_types=["*"]), drain(21), resend(30, "e1", "ep_a"), drain(31)],
     "expect": [got("ep_a")]},
    {"name": "a resend to an endpoint that does not take the event's type arrives all the same; the next event of that type is not sent",
     "steps": NARROW + [resend(30, "e1", "ep_a"), drain(31),
                        event(40, "e2", "refund.created", amount=450, currency="EUR"), drain(41)],
     "expect": [got("ep_a"), {"delivery": to("ep_a", "e2"), "count": 0}]},
    {"name": "an event missed while the endpoint was switched off for more than a day can be resent",
     "steps": [create(0), drain(1), update(10, enabled=False), drain(11), event(100, "e1"), drain(101),
               update(100 + 25 * HOURS, enabled=True), drain(101 + 25 * HOURS),
               resend(200 + 25 * HOURS, "e1", "ep_a"), drain(201 + 25 * HOURS)],
     "expect": [got("ep_a")]},

    # B: the variants the ticket names
    {"name": "two resends of one event to one endpoint that never had it are two deliveries",
     "steps": LATER + [resend(30, "e1", "ep_b"), drain(31), resend(40, "e1", "ep_b"), drain(41)],
     "expect": [got("ep_b", requests=2), got("ep_a")]},
    {"name": "a resend to a switched-off endpoint that never had the event waits and goes out when the endpoint is switched on",
     "steps": LATER_OFF + [resend(30, "e1", "ep_b"), drain(31), update(200, "ep_b", enabled=True), drain(201)],
     "expect": [got("ep_b"), {"delivery": to("ep_b", "e1"), "first_receipt_at_least": 200}]},
    {"name": "a resend to an endpoint that never had the event is retried when the first attempt fails",
     "steps": LATER + [script(25, "ep_b", [500]), resend(30, "e1", "ep_b"), drain(31)],
     "expect": [got("ep_b", requests=2, accepted=1, deliveries=1)]},
    {"name": "an event that arrived as a version 1 message can be resent to an endpoint registered after it",
     "steps": [create(0), drain(1), {"at": 10, "do": "bus", "ref": "old1", "message": V1_EVENT}, drain(11),
               create(20, "ep_b"), drain(21), bus_resend(30, 9001, "ask", V1_EVENT["id"], "ep_b"), drain(31)],
     "expect": [{"status": "ask", "is": 200}, got("ep_b"),
                {"delivery": to("ep_b", "old1"), "amount_minor": 1250, "currency": "USD"}]},

    # C: a restart or a crash point in the path
    {"name": "the api restarts between accepting a resend and passing it on; it still arrives, once",
     "steps": LATER + [resend(30, "e1", "ep_b")] + restart(31, "api") + [drain(32)],
     "expect": [got("ep_b")]},
    {"name": "restarting every service after such a resend has arrived does not send it again",
     "steps": LATER + [resend(30, "e1", "ep_b"), drain(31)] + restart(40, "worker", "api", "router") + [drain(43)],
     "expect": [got("ep_b"), got("ep_a")]},
    {"name": "the router stops right after applying such a resend (crash point 1); it arrives once",
     "steps": LATER + [{"at": 29, "do": "crash_at", "service": "router", "point": 1}, resend(30, "e1", "ep_b"),
                       {"at": 31, "do": "drain", "restart": True}],
     "expect": [got("ep_b")]},
    {"name": "the api stops after the router took such a resend and before it noted that (crash point 3); it arrives once",
     "steps": LATER + [{"at": 29, "do": "crash_at", "service": "api", "point": 3}, resend(30, "e1", "ep_b"),
                       {"at": 31, "do": "drain", "restart": True}],
     "expect": [got("ep_b")]},

    # D: accepted by the shipped release before it was replaced
    {"name": "a resend the deployed release accepted and dropped arrives once the release is replaced",
     "start": "deployed",
     "steps": LATER + [resend(30, "e1", "ep_b"), drain(31), upgrade(60), drain(61)],
     "expect": [got("ep_b"), got("ep_a")]},
    {"name": "a resend the deployed release dropped because of the endpoint's event types arrives once the release is replaced",
     "start": "deployed",
     "steps": NARROW + [resend(30, "e1", "ep_a"), drain(31), upgrade(60), drain(61)],
     "expect": [got("ep_a")]},
    {"name": "a resend the deployed release accepted and had not passed on when it was replaced arrives, once",
     "start": "deployed",
     "steps": LATER + [resend(30, "e1", "ep_b"), upgrade(31), drain(32)],
     "expect": [got("ep_b")]},
    {"name": "two resends the deployed release dropped for one event and endpoint are two deliveries once it is replaced",
     "start": "deployed",
     "steps": LATER + [resend(30, "e1", "ep_b"), drain(31), resend(40, "e1", "ep_b"), drain(41), upgrade(60), drain(61)],
     "expect": [got("ep_b", requests=2)]},
    {"name": "starting the replaced release again does not send a recovered resend a second time",
     "start": "deployed",
     "steps": LATER + [resend(30, "e1", "ep_b"), drain(31), upgrade(60), drain(61)]
              + restart(70, "worker", "api", "router") + [drain(73)],
     "expect": [got("ep_b"), got("ep_a")]},
    {"name": "a dropped resend to a switched-off endpoint waits after the release is replaced and goes out when the endpoint is switched on",
     "start": "deployed",
     "steps": LATER_OFF + [resend(30, "e1", "ep_b"), drain(31), upgrade(60), drain(61),
                           update(200, "ep_b", enabled=True), drain(201)],
     "expect": [got("ep_b"), {"delivery": to("ep_b", "e1"), "first_receipt_at_least": 200}]},
    {"name": "once the release is replaced, a resend that had been dropped arrives and one that had worked is not repeated",
     "start": "deployed",
     "steps": LATER + [resend(30, "e1", "ep_a"), resend(35, "e1", "ep_b"), drain(36), upgrade(60), drain(61)],
     "expect": [got("ep_b"), got("ep_a", requests=2)]},
]

REGRESSIONS = [
    # resends that work today
    {"name": "a resend of a delivered event to the same endpoint is a second delivery",
     "steps": [create(0), event(5, "e1"), drain(6), resend(30, "e1", "ep_a"), drain(31)],
     "expect": [got("ep_a", requests=2), {"delivery": to("ep_a", "e1"), "state": "delivered", "count": 2}]},
    {"name": "a dead delivery can be resent once the endpoint answers again",
     "steps": [create(0), script(1, "ep_a", default=500), event(5, "e1"), drain(6),
               script(10 * HOURS, "ep_a"), resend(10 * HOURS + 5, "e1", "ep_a"), drain(10 * HOURS + 6)],
     "expect": [got("ep_a", requests=7, accepted=1, deliveries=2), {"delivery": to("ep_a", "e1"), "state": "dead"}]},
    {"name": "two resends of a delivered event are two more deliveries",
     "steps": [create(0), event(5, "e1"), drain(6), resend(30, "e1", "ep_a"), drain(31), resend(40, "e1", "ep_a"), drain(41)],
     "expect": [got("ep_a", requests=3)]},
    {"name": "a resend that keeps failing ends dead and leaves the first delivery delivered",
     "steps": [create(0), event(5, "e1"), drain(6), script(20, "ep_a", default=500), resend(30, "e1", "ep_a"), drain(31)],
     "expect": [got("ep_a", requests=7, accepted=1, deliveries=2), {"delivery": to("ep_a", "e1"), "state": "delivered"}]},
    {"name": "the same resend message arriving twice is one more delivery",
     "steps": [create(0), drain(1), bus_event(5, 9000, "b1", "evt_bus00000000001"), drain(6),
               bus_resend(30, 9001, "ask", "evt_bus00000000001", "ep_a"),
               bus_resend(31, 9001, "again", "evt_bus00000000001", "ep_a"), drain(32)],
     "expect": [{"status": "ask", "is": 200}, {"status": "again", "is": 200}, got("ep_a", requests=2)]},
    # switched-off endpoints
    {"name": "a resend to a switched-off endpoint is not sent while it is off",
     "steps": [create(0), event(5, "e1"), drain(6), update(20, enabled=False), drain(21), resend(30, "e1", "ep_a"), drain(31)],
     "expect": [got("ep_a")]},
    {"name": "a resend to a switched-off endpoint goes out when the endpoint is switched on again",
     "steps": [create(0), event(5, "e1"), drain(6), update(20, enabled=False), drain(21), resend(30, "e1", "ep_a"), drain(31),
               update(200, enabled=True), drain(201)],
     "expect": [got("ep_a", requests=2)]},
    {"name": "a switched-off endpoint that never had the event gets nothing from a resend while it is off",
     "steps": LATER_OFF + [resend(30, "e1", "ep_b"), drain(31)],
     "expect": [nothing("ep_b"), got("ep_a")]},
    # the near miss: a resend never crosses merchants
    {"name": "a resend message that names another merchant's endpoint is acknowledged and nothing is sent there",
     "steps": [create(0), create(1, "ep_x", OTHER), drain(2), bus_event(5, 9000, "b1", "evt_bus00000000001"), drain(6),
               bus_resend(30, 9001, "ask", "evt_bus00000000001", "ep_x"), drain(31)],
     "expect": [{"status": "ask", "is": 200}, nothing("ep_x"), got("ep_a")]},
    {"name": "a resend to another merchant's endpoint that the deployed release accepted and had not passed on is not delivered by the release that replaces it",
     "start": "deployed",
     "steps": [create(0), create(1, "ep_x", OTHER), event(5, "e1"), drain(6), resend(30, "e1", "ep_x"), upgrade(31), drain(32)],
     "expect": [nothing("ep_x"), got("ep_a")]},
    {"name": "a resend to another merchant's endpoint that the deployed release dropped stays dropped when the release is replaced",
     "start": "deployed",
     "steps": [create(0), create(1, "ep_x", OTHER), event(5, "e1"), drain(6), resend(30, "e1", "ep_x"), drain(31),
               upgrade(60), drain(61)] + restart(70, "api", "router") + [drain(72)],
     "expect": [nothing("ep_x"), got("ep_a")]},
    # replacing the release repeats nothing
    {"name": "a resend the deployed release delivered is not sent again when the release is replaced or restarted",
     "start": "deployed",
     "steps": [create(0), event(5, "e1"), drain(6), resend(30, "e1", "ep_a"), drain(31), upgrade(60), drain(61)]
              + restart(70, "api", "router") + [drain(72)],
     "expect": [got("ep_a", requests=2)]},
    # messages that name something the router does not have
    {"name": "a resend message that names an endpoint nobody registered is acknowledged and changes nothing",
     "steps": [create(0), drain(1), bus_event(5, 9000, "b1", "evt_bus00000000001"), drain(6),
               bus_resend(30, 9001, "ask", "evt_bus00000000001", "ep_ghost"), drain(31), event(40, "e2"), drain(41)],
     "expect": [{"status": "ask", "is": 200}, got("ep_a", requests=2, events=2)]},
    {"name": "a resend message that names an event the router does not have is acknowledged and changes nothing",
     "steps": [create(0), drain(1), bus_resend(30, 9001, "ask", "evt_nobody00000001", "ep_a"), drain(31),
               event(40, "e1"), drain(41)],
     "expect": [{"status": "ask", "is": 200}, got("ep_a")]},
    # routing as it is
    {"name": "an endpoint registered after an event does not get that event unless a resend asks for it",
     "steps": LATER + [event(30, "e2"), drain(31)],
     "expect": [got("ep_b"), {"delivery": to("ep_b", "e1"), "count": 0}, got("ep_a", requests=2, events=2)]},
    {"name": "an endpoint gets only the event types it takes",
     "steps": [create(0, event_types=["payment.captured"]), event(5, "e1", "refund.created", amount=300, currency="EUR"),
               event(6, "e2"), drain(7)],
     "expect": [got("ep_a"), {"delivery": to("ep_a", "e1"), "count": 0},
                {"delivery": to("ep_a", "e2"), "state": "delivered", "receipts": 1}]},
    {"name": "an endpoint switched on again within a day gets what it missed, once",
     "steps": [create(0), drain(1), update(20, enabled=False), drain(21), event(100, "e1"), drain(101),
               update(200, enabled=True), drain(201)],
     "expect": [{"delivery": to("ep_a", "e1"), "state": "delivered", "receipts": 1}, got("ep_a")]},
    {"name": "an event the endpoint caught up on can be resent: a second delivery",
     "steps": [create(0), drain(1), update(20, enabled=False), drain(21), event(100, "e1"), drain(101),
               update(200, enabled=True), drain(201), resend(300, "e1", "ep_a"), drain(301)],
     "expect": [got("ep_a", requests=2)]},
]

COMPAT = [
    COMPAT_2231[0],  # a version 1 event is delivered once, in minor units
    COMPAT_2231[1],  # an endpoint that exists only in the archive is created and gets its version 2 events
    {"name": "a version 2 event that was delivered can be resent, with the same amount",
     "steps": [archive_endpoint(0, 10, "ep_old", "m_old"), archive_event(5, 11, "a1", "m_old"), drain(6),
               bus_resend(30, 9001, "ask", "evt_archive0000011", "ep_old"), drain(31)],
     "expect": [{"status": "ask", "is": 200}, got("ep_old", requests=2),
                {"delivery": to("ep_old", "a1"), "amount_minor": 990, "currency": "EUR"}]},
    {"name": "a version 1 event that was delivered can be resent, still in minor units",
     "steps": [create(0), drain(1), {"at": 10, "do": "bus", "ref": "old1", "message": V1_EVENT}, drain(11),
               bus_resend(30, 9001, "ask", V1_EVENT["id"], "ep_a"), drain(31)],
     "expect": [{"status": "ask", "is": 200}, got("ep_a", requests=2),
                {"delivery": to("ep_a", "old1"), "amount_minor": 1250, "currency": "USD"}]},
    {"name": "a version 2 message of a kind that version does not have is refused and changes nothing",
     "steps": [archive_endpoint(0, 10, "ep_old", "m_old"), archive_event(5, 11, "a1", "m_old"), drain(6),
               {"at": 30, "do": "bus", "ref": "bad", "message": {
                   "v": 2, "seq": 50, "kind": "resend", "resend": {"event_id": "evt_archive0000011", "endpoint_id": "ep_old"}}},
               drain(31), archive_event(40, 50, "a2", "m_old", amount=1200), drain(41)],
     "expect": [{"status": "bad", "is": 422}, {"status": "a2", "is": 200},
                {"delivery": to("ep_old", "a2"), "state": "delivered", "receipts": 1, "amount_minor": 1200, "currency": "EUR"},
                got("ep_old", requests=2, events=2)]},
    COMPAT_2231[3],  # an archive-only endpoint the deployed release created gets version 2 events after the release is replaced
]


def main():
    scenarios = (
        [["incident", s] for s in INCIDENT] + [["regressions", s] for s in REGRESSIONS] + [["compat", s] for s in COMPAT]
    )
    names = [s["name"] for _, s in scenarios]
    assert len(names) == len(set(names)), "scenario names must be unique"
    path = os.path.join(HERE, "inc-2307", "scenarios.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(scenarios, handle, indent=1)
        handle.write("\n")
    print(f"{path}: " + ", ".join(f"{name} {len(group)}" for name, group in
                                  (("incident", INCIDENT), ("regressions", REGRESSIONS), ("compat", COMPAT))))


if __name__ == "__main__":
    main()
