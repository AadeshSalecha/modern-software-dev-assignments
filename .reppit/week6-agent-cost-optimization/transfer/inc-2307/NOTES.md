# INC-2307: a resend that is accepted and never arrives

A third practice incident for Switchyard 2.3.1, built like INC-2231 (see `../README.md`).
Nothing here is inside `week6/`.

## The defect

`POST /v1/events/{id}/resend` answers 202 whenever the event and the endpoint exist
(`services/api/src/main.ts`, `resend`). The router then looks for the first delivery of that
event to that endpoint and, when there is none, logs `resend.skipped`, keeps the bus message
as applied and creates nothing (`services/router/routing.py`, `apply_resend`). So a resend
is lost whenever the endpoint never had the event: it was registered later, did not take the
event's type, or was switched off for more than the 24 hours catch-up covers.
`contracts/api.yaml` says of a resend: "Creates a new delivery." `docs/runbooks/dead-letters.md`
describes the skip as intended; the contract and the ticket say otherwise.

What the shipped release leaves behind: api outbox rows of type `resend.requested` marked
`published`, and router `bus_seen` rows holding those messages as applied. The router keeps
no record of what a skipped request asked for. A repair of new requests alone never sees the
old ones again.

The near miss: the api does not check that the endpoint belongs to the event's merchant.
Today only the router's skip stops a cross-merchant resend. A repair that simply removes the
skip starts delivering one merchant's events to another's endpoint.

## Files

| Path | What |
| --- | --- |
| `inc-2307/task.md` | The ticket. Goes into the workspace. |
| `inc-2307/incident/` | The evidence packet. Goes into the workspace. |
| `inc-2307/truth.json` | The expected `out/impact.json`. Stays out. |
| `inc-2307/scenarios.json` | The judge's scenarios. Stays out. |
| `inc-2307/judge.py` | Scores a workspace; `--shipped` is the self-check. Stays out. |
| `gen_scenarios_2307.py` | Writes `scenarios.json`. |
| `gen_packet_2307.py` | Builds the packet and the truth by running the shipped release (imports `gen_packet.py`'s shipper, cutters, egress and export writers). |
| `crosscheck_2307.py` | Derives the report through `week6/kit/evidence.py` and compares it with the truth and through the judge. |
| `ground-truth-notes-2307.json` | Counts from the last packet build. |
| `reference-fix-2307.diff` | One complete repair. Not the only valid design. |

`run_transfer.py --incident inc-2307` runs the setup on it.

## What a correct release does

Decided from the contracts; where they are silent the ticket says it in plain words.

| Case | Wanted | Source |
| --- | --- | --- |
| endpoint registered after the event | one new delivery | `api.yaml` "Creates a new delivery"; ticket 1, first bullet |
| endpoint not subscribed to the type, then or now | one new delivery; routing of later events unchanged | ticket 1, first bullet; `messages/README.md` "Event types" |
| endpoint switched off | the delivery is created, waits, goes out when switched on | `delivery.md` "Unless an endpoint is disabled…"; ticket 1, third bullet |
| another merchant's endpoint | no delivery, ever; the API may answer 202 or 404 | ticket 1, fourth bullet |
| unknown endpoint or event at the API | 404, as today | `api.yaml` (not judged: replaylib's `resend` step cannot expect a 404) |
| unknown endpoint or event in a bus message | 200, nothing created | `messages/README.md` "answers 200 when a message is applied" |
| asked twice | two deliveries, two ids | `api.yaml`; ticket 1, second bullet |
| same bus message twice | applied once | `messages/README.md` |
| older bus versions | versions 1 and 2 carry no resends (a version 2 `kind` other than `event`/`endpoint` is malformed, 422); events that arrived in them can be resent | `bus.v2.schema.json`; ticket, deployment, first bullet |
| already accepted and dropped | one delivery per such request once the release is out, not repeated by restarts; requests that worked are not repeated | ticket 1, fifth bullet |

## Scenarios

`scenarios.json` holds 43; the judge adds the 3 shipped scenarios to regressions.

| Category | Count | Classes |
| --- | --- | --- |
| incident | 19 | A plain cases on new traffic 4 · B variants the ticket names 4 · C restart or crash point in the path 4 · D accepted by the shipped release before it was replaced 7 (these start on the shipped release and use the `upgrade` step) |
| regressions | 18 (+3 shipped = 21) | resends that work today 5 · switched-off endpoints 3 · cross-merchant near miss 3 (one bus message, two that start on the shipped release) · replacing the release repeats nothing 1 · bus messages naming an unknown endpoint or event 2 · routing as it is 4 |
| compat | 6 | version 1 event; archive-only endpoint with version 2 events; resend of a version 2 event; resend of a version 1 event; version 2 message of an unknown kind is refused; archive-only endpoint across a release replacement |

Every expectation counts what an endpoint received (requests, accepted, distinct delivery ids,
distinct events). None looks at `resend_of`, at how many rows the router keeps, or at the
API's answer to a cross-merchant request, so a repair is free in how it stores a resend that
has no original. No step asks the candidate's API for a cross-merchant resend: replaylib's
`resend` step fails on a 404, and the ticket allows a 404. The audit's
`near_miss/resend_cross_merchant.json` does ask, and fails the reference repair for that reason.

### Fairness review, incident scenarios

Ticket bullets are numbered within "1. A fix"; D1/D2 are the two deployment bullets.

| # | Scenario | What requires it |
| --- | --- | --- |
| A1 | resend to an endpoint registered after the event arrives, once | bullet 1 "registered"; `api.yaml` "Creates a new delivery" |
| A2 | endpoint did not take the type then, does now | bullet 1 "subscribed to the event's type when the event was accepted" |
| A3 | endpoint does not take the type; next event of that type is not sent | bullet 1 "the endpoint's event types now"; `messages/README.md` "An endpoint subscribes to a list of types" |
| A4 | event missed while switched off for more than a day | bullet 1 "switched on … when the event was accepted" |
| B1 | two resends to an endpoint that never had the event are two deliveries | bullet 2 "Two requests … are two deliveries" |
| B2 | switched-off endpoint: waits, goes out when switched on | bullet 3 |
| B3 | first attempt fails, the resend is retried | `delivery.md` "a delivery ends as `delivered` or `dead`" |
| B4 | version 1 event resent to an endpoint registered after it | D1 "An event that reached the router in one of them can be resent like any other" |
| C1 | api restarts between accepting and passing on | bullet 2 "also when a service stops or restarts" |
| C2 | every service restarted afterwards, not sent again | bullet 2 "exactly one new delivery" |
| C3 | router crash point 1 while applying | bullet 2; `harness.md` crash points |
| C4 | api crash point 3 while publishing | bullet 2; `harness.md` crash points |
| D1 | dropped by the deployed release, arrives after replacement | bullet 5 |
| D2 | dropped because of event types, arrives after replacement | bullet 5 with bullet 1 |
| D3 | accepted, not yet passed on at replacement | D2 "with requests in flight"; bullet 2 |
| D4 | two dropped requests for one event and endpoint are two deliveries | bullet 5 "one delivery for each such request" |
| D5 | replaced release started again, nothing sent twice | bullet 5 "however often the services are restarted afterwards" |
| D6 | dropped resend to a switched-off endpoint waits, then goes out | bullet 5 with bullet 3 |
| D7 | dropped one arrives, one that worked is not repeated | bullet 5 "A request that did get its delivery must not get another" |

Left out on purpose because the ticket would not settle them beyond argument: a request
dropped while the endpoint was off, whose event the endpoint later got through catch-up
(does recovery add a delivery?); a request the shipped router applied and the api had not yet
marked published when the release was replaced; a resend to a switched-off endpoint for an
event that catch-up will also cover (one delivery or two).

## The packet

`gen_packet_2307.py` drives the unmodified release through 2026-11-09 (a Monday) to
2026-11-11: 8 merchants, 11 endpoints (3 registered during the period, one of them switched
off), 313 events, 341 deliveries, 448 requests to merchants, three service restarts, three
router snapshots. Support makes 60 resend requests; the api accepts all of them.

| | Requests | Events and endpoints |
| --- | --- | --- |
| lost, in the report | 38 | 35 (m_juniper 12, m_larch 9, m_kestrel 6, m_oak 5, m_pine 3) |
| worked | 18 | 17 (one of them also has a lost request) |
| another merchant's endpoint, left out | 4 | 4 |

Totals: EUR 778017, GBP 787367, USD 2382041. JPY and KWD have none. Shipper effects with
seed 2307: skew per host (router -12 s, worker +33 s, egress +5 s; the export is local time),
batches sent twice and late, 82 cut rows (api 22, router 32, worker 22, egress 3, export 3).
The build is deterministic: a second build gave the same bytes.

The truth comes from the requests the generator made, the api's answers and the resend
deliveries in the router's final state. It does not use the kit's loader.

Planted near misses:

- 18 requests that worked: 10 for deliveries that had died during m_myrtle's outage, 4 replays
  for m_nettle, 2 for m_juniper's first endpoint, one after a catch-up, one to a switched-off
  endpoint whose delivery is still waiting at the end (accepted, nothing arrived, not lost).
- 4 requests naming another merchant's endpoint, also logged as `resend.skipped`. One of those
  events has a lost request to its own merchant's endpoint as well.
- Asked twice: 3 events lost both times (count twice, listed once), 1 worked both times, and
  1 lost while the endpoint was off, caught up, then asked again and worked (one lost
  request, although the endpoint has the event under two delivery ids).
- 3 lost requests to an endpoint that is switched off.
- Records cut on purpose, one per request at most: 7 lost requests whose api record is cut
  (the router's `resend.skipped` is whole), 5 whose `resend.skipped` is cut (the api record is
  whole), 2 worked requests whose api record is cut, 3 whose `delivery.created` is cut (the
  delivery's egress, worker and later router records are whole). Events and endpoints asked
  for more than once lose nothing.
- The batch around the first `resend.requested` and the first `resend.skipped` is sent twice.

Shortcuts and what they score against the truth (impact): every `resend.skipped` record 0.67;
api requests less `delivery.created` records with `resend_of` 0.57; requests for an event and
endpoint with no delivery at all 0.90; raw `resend.skipped` lines without de-duplication 0.64.

## Verification (2026-11-27)

| Check | Result |
| --- | --- |
| `judge.py --shipped` | repair 0.00: incident 0 of 19, regressions 21 of 21, compat 6 of 6 |
| `reference-fix-2307.diff` on a fresh copy, report derived by `crosscheck_2307.py` | PASS: repair 1.00 (19, 21, 6), impact 1.00 |
| incomplete repair: router creates the delivery for new requests (with the merchant check), nothing for requests already dropped | repair 0.68: incident 13 of 19 (fails D1, D2, D4, D5, D6, D7), regressions 21 of 21, compat 6 of 6 |
| `crosscheck_2307.py` | cut rows by the contract rule equal the generator's per file (82); report from the kit's tables equals `truth.json`; impact 1.00 through `judge.py` (9 of 9 figures) |
| repair that drops the skip with no merchant check | repair 0.61: fails the cross-merchant and unknown-event regressions |
| repair that asks again for every published resend on each start | repair 0.81: fails C2, D5, D7 and "a resend the deployed release delivered is not sent again" |

```bash
PATH=/opt/node24/bin:$PATH python3 gen_packet_2307.py
python3 gen_scenarios_2307.py
python3 crosscheck_2307.py
PATH=/opt/node24/bin:$PATH python3 inc-2307/judge.py --shipped
```

The reference repair: the router creates the delivery whenever it has the event and the
endpoint and both belong to one merchant, and records which request each resend delivery
answers (`resend_requests`). On its first start the api puts every earlier `resend.requested`
outbox row on the bus again with `request` set to the original sequence number; the router
gives such a request a delivery only when no unaccounted resend delivery exists for it. The
api also answers a cross-merchant request with 404.

## Limits

- The judge shares `week6/kit/rollout.py` and its contract checks with the setup it judges.
- B4 rests on one ticket sentence. The api cannot resend a version 1 or 2 event (it does not
  have it), so the scenario posts the `resend.requested` message itself.
- "One delivery for each dropped request" (D4) is the ticket's choice, taken from the
  contract's wording. One per event and endpoint would also be a defensible product decision;
  the ticket rules it out explicitly.
- The API's 404 answers and its answer to a cross-merchant request are not judged.
- Only the reference design and three wrong ones were run. A different complete design (for
  example the api comparing its outbox with the router's state) was reasoned through, not run.
