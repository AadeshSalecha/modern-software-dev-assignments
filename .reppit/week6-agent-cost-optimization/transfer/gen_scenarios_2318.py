#!/usr/bin/env python3
"""Write inc-2318/scenarios.json: the judge's scenarios for INC-2318.

    python3 gen_scenarios_2318.py

A list of [category, scenario] in the format week6/kit/rollout.py plays (replaylib's, plus
the `upgrade` step and endpoint-level expectations). The three shipped scenarios in
app/scenarios are added to `regressions` by judge.py at run time. A scenario with an
`upgrade` step starts on the shipped release ("start": "deployed" marks those).

Every expectation is about what a merchant's endpoint receives, never about how a fix
stores things or tells the router:
  incident     an endpoint that is switched back on gets what it is owed however long it
               was off: on new traffic, over several off periods, with its subscription
               changed meanwhile, across restarts and crash points, through older bus
               versions, and for events the shipped release has already skipped
  regressions  everything about switching off and on that works today
  compat       version 1 and version 2 messages still do what they did

Each scenario carries "class" (which kind of case it is) and "basis" (the ticket sentence
or contract clause that requires what it checks). Neither is read by the runner.
"""

import base64
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
M = "m_acme"
DAY = 86400
LONG = 90000  # 25 hours
NEW_SECRET = "whsec_" + base64.b64encode(b"a-new-secret-for-acme-01").decode()

# what the ticket and the contracts say, by a short name (the "basis" of a scenario)
BASIS = {
    "owed": 'ticket, fix: "an endpoint that is switched back on gets every event it is owed, however long it was off"; '
            'delivery.md: "Accepted events get IDs and should not be lost."',
    "created-off": 'ticket, fix: "for an endpoint that was created switched off, from its creation"',
    "before": 'ticket, fix: "Events from before the endpoint existed ... are not owed."',
    "several": 'ticket, fix: "If an endpoint is switched off and on several times, each switch-on brings the events of '
               'the off period that just ended. Nothing is delivered a second time."',
    "off-start": 'ticket, fix: "from the change that switched it off ... A change made while it is off (a new secret, '
                 'a new address, switching it off again) does not move that start."',
    "types": 'ticket, fix: "whose type it is subscribed to at the moment it is switched back on"',
    "not-subscribed": 'ticket, fix: "events accepted while it was on and not subscribed to their type, and events of '
                      'types it is not subscribed to when it comes back on, are not owed"',
    "once": 'ticket, fix: "Each is delivered once."; delivery.md: "Only manual resends can send an event under two '
            'delivery IDs to the same endpoint."',
    "restart": 'ticket, deployment: "Services are restarted and can go down at any point, as they do today; what an '
               'endpoint is owed does not depend on that."',
    "bus": 'ticket, deployment: "Version 1 and version 2 bus messages keep working. An endpoint that exists only in '
           'the archive and is switched off and on by version 2 messages is owed its events in the same way, and '
           'events that arrive as version 1 or version 2 messages while an endpoint is off are owed like any other."',
    "recover": 'ticket, fix: "Events that were owed in this way and that the running release has already failed to '
               'deliver must be delivered, once, when the release is out. Nobody should have to ask for them."',
    "recover-off": 'ticket, fix: "If the endpoint is switched off at that moment, they wait and go out when it is '
                   'switched on again."',
    "replace": 'ticket, deployment: "The release goes to every region and replaces the running one in place, on its '
               'existing state", including an endpoint that is off at that moment.',
    "still-off": 'ticket, fix: "An endpoint that is still off gets nothing."',
    "waits": "delivery.md: \"Unless an endpoint is disabled, a delivery ends as `delivered` or `dead`.\" A delivery "
             "queued before the switch-off waits and is sent after the switch-on (today's behaviour).",
    "today": "today's behaviour, which the ticket does not change",
    "messages": "contracts/messages/README.md",
}


def secret_for(name):  # what replaylib gives an endpoint created without a secret
    return "whsec_" + base64.b64encode(hashlib.sha256(name.encode()).digest()[:24]).decode()


def create(at, endpoint="ep_a", merchant=M, **more):
    return dict({"at": at, "do": "endpoint.create", "id": endpoint, "merchant": merchant}, **more)


def update(at, endpoint="ep_a", **change):
    return dict({"at": at, "do": "endpoint.update", "id": endpoint}, **change)


def off(at, endpoint="ep_a"):
    return update(at, endpoint, enabled=False)


def on(at, endpoint="ep_a", **more):
    return update(at, endpoint, enabled=True, **more)


def event(at, ref, type_="payment.captured", merchant=M, amount=1250, currency="USD"):
    return {"at": at, "do": "event", "ref": ref, "merchant": merchant, "type": type_,
            "amount_minor": amount, "currency": currency}


def archive_endpoint(at, seq, endpoint="ep_old", merchant="m_old", active=True, ref=None):
    message = {"v": 2, "seq": seq, "kind": "endpoint",
               "endpoint": {"id": endpoint, "merchant": merchant, "url": "{receiver}/hooks/" + endpoint,
                            "secret": secret_for(endpoint), "types": ["*"], "active": active}}
    step = {"at": at, "do": "bus", "message": message}
    if ref:
        step["ref"] = ref
    return step


def archive_event(at, seq, ref, merchant="m_old", amount=990, currency="EUR"):
    return {"at": at, "do": "bus", "ref": ref, "message": {
        "v": 2, "seq": seq, "kind": "event",
        "event": {"id": f"evt_archive{seq:07d}", "merchant": merchant, "type": "payment.captured",
                  "created": 1790000000 + seq, "payment_id": f"pay_archive{seq:07d}",
                  "amount_minor": amount, "currency": currency}}}


def v1_event(at, ref, number, merchant=M):
    return {"at": at, "do": "bus", "ref": ref, "message": {
        "id": f"evt_legacy{number:07d}", "merchant": merchant, "event_type": "payment.captured", "amount": "12.5",
        "currency": "USD", "payment": f"pay_legacy{number:07d}", "ts": "2026-11-02T00:00:00Z"}}


def drain(at, **more):
    return dict({"at": at, "do": "drain"}, **more)


def upgrade(at):
    return {"at": at, "do": "upgrade"}


def restart_all(at):
    return [{"at": at + n, "do": "restart", "service": service} for n, service in enumerate(("router", "api", "worker"))]


def to(endpoint, ref):
    return {"event": ref, "endpoint": endpoint}


def once(endpoint, ref, **more):
    return dict({"delivery": to(endpoint, ref), "state": "delivered", "count": 1, "receipts": 1}, **more)


def never(endpoint, ref):
    return {"delivery": to(endpoint, ref), "count": 0}


def got(endpoint, requests):
    return {"endpoint": endpoint, "requests": requests, "accepted": requests, "events": requests, "deliveries": requests}


def scenario(name, class_, basis, steps, expect, deployed=False):
    flat = []
    for step in steps:
        flat.extend(step if isinstance(step, list) else [step])
    out = {"name": name, "class": class_, "basis": [BASIS[b] for b in basis]}
    if deployed:
        out["start"] = "deployed"
        assert any(s["do"] == "upgrade" for s in flat)
    else:
        assert not any(s["do"] == "upgrade" for s in flat)
    out["steps"], out["expect"] = flat, expect
    return out


INCIDENT = [
    # --- the plain case, on new traffic -------------------------------------------------
    scenario("an endpoint switched off for more than a day gets the event accepted meanwhile when it is switched on",
             "plain", ["owed", "once"],
             [create(0), drain(1), off(10), drain(11), event(20, "e1"), drain(21), on(LONG), drain(LONG + 1)],
             [once("ep_a", "e1", first_receipt_at_least=LONG), got("ep_a", 1)]),
    scenario("an endpoint switched off for three days gets the events of every one of those days, each once; "
             "the merchant's other endpoint got them as they came",
             "plain", ["owed", "once"],
             [create(0), create(1, "ep_b"), drain(2), off(10), drain(11),
              event(100, "e1"), drain(101), event(DAY + 100, "e2", "refund.created", amount=300), drain(DAY + 101),
              event(2 * DAY + 100, "e3", "payout.paid", amount=88000), drain(2 * DAY + 101),
              event(3 * DAY - 100, "e4", "payment.failed"), drain(3 * DAY - 99),
              on(3 * DAY + 10), drain(3 * DAY + 11)],
             [once("ep_a", "e1"), once("ep_a", "e2", amount_minor=300), once("ep_a", "e3"), once("ep_a", "e4"),
              got("ep_a", 4), got("ep_b", 4), once("ep_b", "e1", first_receipt_at_most=200)]),
    scenario("an endpoint created switched off gets the events accepted since its creation when it is first "
             "switched on more than a day later, and none from before it existed",
             "plain", ["created-off", "owed", "before"],
             [event(0, "e0"), drain(1), create(10, enabled=False), drain(11), event(20, "e1"), drain(21),
              event(40000, "e2"), drain(40001), on(LONG), drain(LONG + 1)],
             [once("ep_a", "e1"), once("ep_a", "e2"), never("ep_a", "e0"), got("ep_a", 2)]),
    # --- switched off and on several times ----------------------------------------------
    scenario("switched off for an hour, on, then off for more than a day and on: each event arrives once",
             "several times", ["several", "owed", "once"],
             [create(0), drain(1), off(10), drain(11), event(20, "e1"), drain(21), on(3600), drain(3601),
              off(7200), drain(7201), event(7210, "e2"), drain(7211), on(7200 + LONG), drain(7201 + LONG)],
             [once("ep_a", "e1", first_receipt_at_most=3700), once("ep_a", "e2", first_receipt_at_least=7200 + LONG),
              got("ep_a", 2)]),
    scenario("switched off for more than a day, on, then off for a minute and on: each event arrives once, "
             "at the switch-on that ended its off period",
             "several times", ["several", "owed", "once"],
             [create(0), drain(1), off(10), drain(11), event(20, "e1"), drain(21), on(LONG), drain(LONG + 1),
              off(LONG + 100), drain(LONG + 101), event(LONG + 110, "e2"), drain(LONG + 111),
              on(LONG + 200), drain(LONG + 201)],
             [once("ep_a", "e1", first_receipt_at_most=LONG + 50), once("ep_a", "e2", first_receipt_at_least=LONG + 200),
              got("ep_a", 2)]),
    scenario("a secret rotated and a second switch-off while the endpoint is off do not move the start of the "
             "off period; the event arrives signed with the new secret",
             "several times", ["off-start", "owed"],
             [create(0), drain(1), off(10), drain(11), event(20, "e1"), drain(21),
              update(50000, secret=NEW_SECRET), drain(50001), off(60000), drain(60001),
              on(LONG), drain(LONG + 1)],
             [once("ep_a", "e1", secrets=[NEW_SECRET]), got("ep_a", 1)]),
    # --- subscription changed meanwhile ---------------------------------------------------
    scenario("subscription narrowed while off for more than a day: only the types subscribed to at the switch-on "
             "are delivered",
             "types", ["types", "not-subscribed", "owed"],
             [create(0), drain(1), off(10), drain(11), event(20, "e1"), event(30, "e2", "refund.created", amount=300),
              drain(31), update(40000, event_types=["refund.created"]), drain(40001), on(LONG), drain(LONG + 1)],
             [once("ep_a", "e2"), never("ep_a", "e1"), got("ep_a", 1)]),
    scenario("subscription widened while off for more than a day: every type subscribed to at the switch-on is "
             "delivered",
             "types", ["types", "owed"],
             [create(0, event_types=["payment.captured"]), drain(1), off(10), drain(11), event(20, "e1"),
              event(30, "e2", "refund.created", amount=300), drain(31), update(40000, event_types=["*"]), drain(40001),
              on(LONG), drain(LONG + 1)],
             [once("ep_a", "e1"), once("ep_a", "e2"), got("ep_a", 2)]),
    # --- restarts and crash points --------------------------------------------------------
    scenario("api, router and worker are restarted while the endpoint is off for more than a day",
             "restart or crash", ["restart", "owed", "once"],
             [create(0), drain(1), off(10), drain(11), event(20, "e1"), drain(21), restart_all(30000), drain(30010),
              event(30020, "e2"), drain(30021), on(LONG + 30000), drain(LONG + 30001)],
             [once("ep_a", "e1"), once("ep_a", "e2"), got("ep_a", 2)]),
    scenario("the router goes down right after it applies the switch-on and is started again",
             "restart or crash", ["restart", "owed", "once"],
             [create(0), drain(1), off(10), drain(11), event(20, "e1"), event(30, "e2"), drain(31),
              {"at": LONG - 1, "do": "crash_at", "service": "router", "point": 1}, on(LONG),
              drain(LONG + 1, restart=True), drain(LONG + 2)],
             [once("ep_a", "e1"), once("ep_a", "e2"), got("ep_a", 2)]),
    # --- older bus versions ---------------------------------------------------------------
    scenario("an endpoint that exists only in the archive, switched off and on by version 2 messages more than "
             "a day apart, gets the version 2 event that arrived meanwhile",
             "older bus versions", ["bus", "owed"],
             [archive_endpoint(0, 10), drain(1), archive_endpoint(10, 11, active=False, ref="off"), drain(11),
              archive_event(20, 12, "a1"), drain(21), archive_endpoint(LONG, 13, active=True, ref="on"),
              drain(LONG + 1)],
             [{"status": "off", "is": 200}, {"status": "on", "is": 200},
              once("ep_old", "a1", amount_minor=990, currency="EUR"), got("ep_old", 1)]),
    scenario("version 1 and version 2 events that arrive while an endpoint is off for more than a day are "
             "delivered when it is switched on, with the api's own",
             "older bus versions", ["bus", "owed", "once"],
             [create(0), drain(1), off(10), drain(11), v1_event(20, "old1", 1), archive_event(30, 4100, "a1", M),
              event(40, "e1"), drain(41), on(LONG), drain(LONG + 1)],
             [{"status": "old1", "is": 200}, {"status": "a1", "is": 200},
              once("ep_a", "old1", amount_minor=1250, currency="USD"), once("ep_a", "a1", amount_minor=990),
              once("ep_a", "e1"), got("ep_a", 3)]),
    # --- events the shipped release has already skipped -----------------------------------
    scenario("an event the deployed release skipped at a switch-on is delivered once the release is replaced",
             "already skipped", ["recover", "once"],
             [create(0), drain(1), off(10), drain(11), event(20, "e1"), drain(21), on(LONG), drain(LONG + 1),
              upgrade(LONG + 100), drain(LONG + 101)],
             [once("ep_a", "e1", first_receipt_at_least=LONG + 100), got("ep_a", 1)], deployed=True),
    scenario("of two events owed at a switch-on the deployed release delivered one; the other arrives once the "
             "release is replaced, the first is not sent again, the merchant's other endpoint gets nothing more",
             "already skipped", ["recover", "once"],
             [create(0), create(1, "ep_b"), drain(2), off(10), drain(11), event(20, "e1"), drain(21),
              event(80000, "e2"), drain(80001), on(LONG), drain(LONG + 1), upgrade(LONG + 100), drain(LONG + 101)],
             [once("ep_a", "e1", first_receipt_at_least=LONG + 100), once("ep_a", "e2", first_receipt_at_most=LONG + 50),
              got("ep_a", 2), got("ep_b", 2)], deployed=True),
    scenario("only the skipped events of a type the endpoint was subscribed to at that switch-on are delivered "
             "once the release is replaced, whatever it subscribes to by then",
             "already skipped", ["recover", "types", "not-subscribed"],
             [create(0), drain(1), off(10), drain(11), event(20, "e1"), event(30, "e2", "refund.created", amount=300),
              drain(31), on(LONG, event_types=["payment.captured"]), drain(LONG + 1),
              update(LONG + 50, event_types=["*"]), drain(LONG + 51), upgrade(LONG + 100), drain(LONG + 101)],
             [once("ep_a", "e1"), never("ep_a", "e2"), got("ep_a", 1)], deployed=True),
    scenario("starting the replaced release again delivers nothing more",
             "already skipped", ["recover", "once", "restart"],
             [create(0), drain(1), off(10), drain(11), event(20, "e1"), drain(21), on(LONG), drain(LONG + 1),
              upgrade(LONG + 100), drain(LONG + 101), restart_all(LONG + 200), drain(LONG + 210),
              event(LONG + 300, "e2"), drain(LONG + 301), restart_all(LONG + 400), drain(LONG + 410)],
             [once("ep_a", "e1"), once("ep_a", "e2"), got("ep_a", 2)], deployed=True),
    scenario("two off periods under the deployed release, a short one it caught up and a long one it skipped: "
             "once the release is replaced the skipped event arrives and the other is not sent again",
             "already skipped", ["recover", "several", "once"],
             [create(0), drain(1), off(10), drain(11), event(20, "e1"), drain(21), on(3600), drain(3601),
              off(7200), drain(7201), event(7210, "e2"), drain(7211), on(7200 + LONG), drain(7201 + LONG),
              upgrade(7300 + LONG), drain(7301 + LONG)],
             [once("ep_a", "e1", first_receipt_at_most=3700), once("ep_a", "e2", first_receipt_at_least=7300 + LONG),
              got("ep_a", 2)], deployed=True),
    scenario("an endpoint with a skipped event is switched off again when the release is replaced: the event "
             "waits and arrives once, with the newer one, when the endpoint is switched on",
             "already skipped", ["recover-off", "recover", "once", "still-off"],
             [create(0), drain(1), off(10), drain(11), event(20, "e1"), drain(21), on(LONG), drain(LONG + 1),
              off(LONG + 50), drain(LONG + 51), event(LONG + 60, "e2"), drain(LONG + 61),
              upgrade(LONG + 100), drain(LONG + 101), on(LONG + 500), drain(LONG + 501)],
             [once("ep_a", "e1", first_receipt_at_least=LONG + 500), once("ep_a", "e2", first_receipt_at_least=LONG + 500),
              got("ep_a", 2)], deployed=True),
    scenario("an endpoint is off when the release is replaced and is switched on later, more than a day after "
             "it was switched off: it gets the events from before and after the replacement",
             "already skipped", ["replace", "owed", "once"],
             [create(0), drain(1), off(10), drain(11), event(20, "e1"), drain(21), upgrade(50000), drain(50001),
              event(50010, "e2"), drain(50011), on(LONG), drain(LONG + 1)],
             [once("ep_a", "e1", first_receipt_at_least=LONG), once("ep_a", "e2", first_receipt_at_least=LONG),
              got("ep_a", 2)], deployed=True),
]

REGRESSIONS = [
    scenario("an endpoint switched off for less than a day gets what it missed when it is switched on, once",
             "less than a day", ["today"],
             [create(0), drain(1), off(10), drain(11), event(20, "e1"), event(5000, "e2", "refund.created", amount=300),
              drain(5001), on(80000), drain(80001)],
             [once("ep_a", "e1", first_receipt_at_least=80000), once("ep_a", "e2"), got("ep_a", 2)]),
    scenario("switched off and on twice within a day: each event arrives once",
             "less than a day", ["today", "once"],
             [create(0), drain(1), off(10), drain(11), event(20, "e1"), drain(21), on(1000), drain(1001),
              event(1500, "e2"), drain(1501), off(2000), drain(2001), event(2010, "e3"), drain(2011), on(3000),
              drain(3001)],
             [once("ep_a", "e1"), once("ep_a", "e2"), once("ep_a", "e3"), got("ep_a", 3)]),
    scenario("a delivery that was waiting for a retry when the endpoint was switched off is sent after the "
             "switch-on, more than a day later, under the same delivery",
             "nothing twice", ["waits", "once"],
             [create(0), {"at": 0, "do": "receiver.script", "path": "/hooks/ep_a", "responses": [500]},
              event(5, "e1"), drain(6, limit=3), off(10), drain(11), on(LONG), drain(LONG + 1)],
             [{"delivery": to("ep_a", "e1"), "state": "delivered", "count": 1, "receipts": 2, "accepted": 1, "counted": 1},
              {"endpoint": "ep_a", "requests": 2, "deliveries": 1}]),
    scenario("events from before the endpoint existed are not delivered, also not after it has been off and on",
             "before the endpoint existed", ["before", "today"],
             [event(0, "e0"), drain(1), create(10), drain(11), off(20), drain(21), event(30, "e1"), drain(31),
              on(1000), drain(1001)],
             [never("ep_a", "e0"), once("ep_a", "e1"), got("ep_a", 1)]),
    scenario("an endpoint that stays off gets nothing; the merchant's other endpoint gets everything",
             "stays off", ["still-off", "today"],
             [create(0), create(1, "ep_b"), drain(2), off(10), drain(11), event(20, "e1"), drain(21),
              event(2 * DAY, "e2"), drain(2 * DAY + 1)],
             [{"endpoint": "ep_a", "requests": 0}, once("ep_b", "e1"), once("ep_b", "e2"), got("ep_b", 2)]),
    scenario("an endpoint created switched off and never switched on gets nothing",
             "stays off", ["still-off", "today"],
             [create(0, enabled=False), drain(1), event(20, "e1"), drain(21), event(2 * DAY, "e2"), drain(2 * DAY + 1)],
             [{"endpoint": "ep_a", "requests": 0}]),
    scenario("off for less than a day with the subscription narrowed meanwhile: only the types subscribed to at "
             "the switch-on are delivered",
             "types", ["types", "today"],
             [create(0), drain(1), off(10), drain(11), event(20, "e1"), event(30, "e2", "refund.created", amount=300),
              drain(31), update(500, event_types=["refund.created"]), drain(501), on(1000), drain(1001)],
             [once("ep_a", "e2"), never("ep_a", "e1"), got("ep_a", 1)]),
    scenario("an event that passed while the endpoint was on and not subscribed to its type is not delivered "
             "after an off period, even if the endpoint subscribes to everything by then",
             "types", ["not-subscribed", "today"],
             [create(0, event_types=["payment.captured"]), drain(1), event(10, "e1", "refund.created", amount=300),
              drain(11), off(20), drain(21), event(30, "e2", "refund.created", amount=300), drain(31),
              update(40, event_types=["*"]), drain(41), on(1000), drain(1001)],
             [never("ep_a", "e1"), once("ep_a", "e2"), got("ep_a", 1)]),
    scenario("a secret rotated while the endpoint is off for less than a day signs what it gets at the switch-on",
             "less than a day", ["today"],
             [create(0), drain(1), off(10), drain(11), event(20, "e1"), drain(21), update(500, secret=NEW_SECRET),
              drain(501), on(1000), drain(1001)],
             [once("ep_a", "e1", secrets=[NEW_SECRET]), got("ep_a", 1)]),
    scenario("what an endpoint gets at the switch-on is retried like any delivery",
             "less than a day", ["today"],
             [create(0), drain(1), off(10), drain(11), event(20, "e1"), drain(21),
              {"at": 900, "do": "receiver.script", "path": "/hooks/ep_a", "responses": [500, 503]},
              on(1000), drain(1001)],
             [{"delivery": to("ep_a", "e1"), "state": "delivered", "count": 1, "receipts": 3, "accepted": 1, "counted": 2},
              {"endpoint": "ep_a", "requests": 3, "deliveries": 1}]),
    scenario("a manual resend of a delivered event still sends it again under a second delivery",
             "nothing twice", ["today"],
             [create(0), drain(1), event(10, "e1"), drain(11), {"at": 100, "do": "resend", "event": "e1", "endpoint": "ep_a"},
              drain(101)],
             [{"delivery": to("ep_a", "e1"), "count": 2, "receipts": 2, "accepted": 2},
              {"endpoint": "ep_a", "requests": 2, "deliveries": 2, "events": 1}]),
    scenario("an off period the deployed release caught up is not delivered again when the release is replaced "
             "and started again",
             "nothing twice", ["once", "recover"],
             [create(0), drain(1), off(10), drain(11), event(20, "e1"), drain(21), on(1000), drain(1001),
              upgrade(2000), drain(2001), restart_all(2100), drain(2110), event(2200, "e2"), drain(2201)],
             [once("ep_a", "e1", first_receipt_at_most=1100), once("ep_a", "e2"), got("ep_a", 2)], deployed=True),
    scenario("an endpoint that is off when the release is replaced and stays off gets nothing; the merchant's "
             "other endpoint gets everything",
             "stays off", ["still-off", "replace"],
             [create(0), create(1, "ep_b"), drain(2), off(10), drain(11), event(20, "e1"), drain(21),
              upgrade(LONG), drain(LONG + 1), event(LONG + 10, "e2"), drain(LONG + 11)],
             [{"endpoint": "ep_a", "requests": 0}, got("ep_b", 2)], deployed=True),
    scenario("replacing the release delivers nothing from before an endpoint existed and nothing of a type it "
             "was not subscribed to",
             "before the endpoint existed", ["before", "not-subscribed"],
             [event(0, "e0"), drain(1), create(10, event_types=["payment.captured"]), drain(11),
              event(20, "e1", "refund.created", amount=300), event(30, "e2"), drain(31),
              update(40, event_types=["*"]), drain(41), upgrade(LONG), drain(LONG + 1)],
             [never("ep_a", "e0"), never("ep_a", "e1"), once("ep_a", "e2"), got("ep_a", 1)], deployed=True),
    scenario("an event that was not owed at a switch-on under the deployed release (its type was not subscribed "
             "to then) is not delivered when the release is replaced",
             "types", ["types", "not-subscribed"],
             [create(0), drain(1), off(10), drain(11), event(20, "e1", "refund.created", amount=300), event(30, "e2"),
              drain(31), on(1000, event_types=["payment.captured"]), drain(1001), update(2000, event_types=["*"]),
              drain(2001), upgrade(3000), drain(3001)],
             [never("ep_a", "e1"), once("ep_a", "e2"), got("ep_a", 1)], deployed=True),
    scenario("a delivery that was waiting for a retry when the endpoint was switched off waits through the "
             "replacement of the release and is sent once after the switch-on",
             "nothing twice", ["waits", "once", "replace"],
             [create(0), {"at": 0, "do": "receiver.script", "path": "/hooks/ep_a", "responses": [500]},
              event(5, "e1"), drain(6, limit=3), off(10), drain(11), upgrade(LONG), drain(LONG + 1),
              on(LONG + 10), drain(LONG + 11)],
             [{"delivery": to("ep_a", "e1"), "state": "delivered", "count": 1, "receipts": 2, "accepted": 1, "counted": 1},
              {"endpoint": "ep_a", "requests": 2, "deliveries": 1}], deployed=True),
]

COMPAT = [
    scenario("a version 1 event is delivered once, in minor units",
             "version 1", ["messages"],
             [create(0), drain(1), v1_event(10, "old1", 1), v1_event(11, "old1again", 1), drain(12)],
             [{"status": "old1", "is": 200}, {"status": "old1again", "is": 200},
              once("ep_a", "old1", amount_minor=1250, currency="USD")]),
    scenario("an endpoint that exists only in the archive is created and gets its version 2 events",
             "version 2", ["messages"],
             [archive_endpoint(0, 10, ref="made"), archive_event(5, 11, "a1"), drain(6)],
             [{"status": "made", "is": 200}, {"status": "a1", "is": 200},
              once("ep_old", "a1", amount_minor=990, currency="EUR")]),
    scenario("an archive-only endpoint switched off by a version 2 message gets nothing",
             "version 2", ["messages", "still-off"],
             [archive_endpoint(0, 10), archive_endpoint(5, 11, active=False, ref="off"), archive_event(10, 12, "a1"),
              drain(11)],
             [{"status": "off", "is": 200}, {"endpoint": "ep_old", "requests": 0}]),
    scenario("an archive-only endpoint switched off and on by version 2 messages within a day gets the version 2 "
             "event that arrived meanwhile, once; a repeated message changes nothing",
             "version 2", ["messages", "today"],
             [archive_endpoint(0, 10), drain(1), archive_endpoint(10, 11, active=False), drain(11),
              archive_event(20, 12, "a1"), drain(21), archive_endpoint(1000, 13, active=True, ref="on"), drain(1001),
              archive_endpoint(1100, 13, active=True, ref="again"), archive_event(1101, 12, "a1again"), drain(1102)],
             [{"status": "on", "is": 200}, {"status": "again", "is": 200}, {"status": "a1again", "is": 200},
              once("ep_old", "a1"), got("ep_old", 1)]),
    scenario("version 1 and version 2 events that arrive while an endpoint is off for less than a day are "
             "delivered once when it is switched on",
             "version 1 and 2", ["messages", "today"],
             [create(0), drain(1), off(10), drain(11), v1_event(20, "old1", 1), archive_event(30, 4100, "a1", M),
              drain(31), on(1000), drain(1001)],
             [once("ep_a", "old1", amount_minor=1250, currency="USD"), once("ep_a", "a1", amount_minor=990),
              got("ep_a", 2)]),
    scenario("an archive-only endpoint the deployed release created gets version 2 events after the release is "
             "replaced, and nothing it already got",
             "version 2", ["messages", "replace"],
             [archive_endpoint(0, 10), archive_event(5, 11, "a0"), drain(6), upgrade(LONG), drain(LONG + 1),
              archive_event(LONG + 10, 12, "a1"), drain(LONG + 11)],
             [once("ep_old", "a0", first_receipt_at_most=100), once("ep_old", "a1"), got("ep_old", 2)], deployed=True),
]


def main():
    groups = (("incident", INCIDENT), ("regressions", REGRESSIONS), ("compat", COMPAT))
    names = [s["name"] for _, group in groups for s in group]
    assert len(names) == len(set(names)), "scenario names must be unique"
    scenarios = [[name, s] for name, group in groups for s in group]
    path = os.path.join(HERE, "inc-2318", "scenarios.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(scenarios, handle, indent=1)
        handle.write("\n")
    print(f"{path}: " + ", ".join(f"{name} {len(group)}" for name, group in groups))
    for name, group in groups:
        classes = {}
        for s in group:
            classes[s["class"]] = classes.get(s["class"], 0) + 1
        print(f"  {name}: " + ", ".join(f"{k} {v}" for k, v in classes.items()))


if __name__ == "__main__":
    main()
