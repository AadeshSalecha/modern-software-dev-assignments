# INC-2318: events missing after an endpoint was switched back on

A practice incident for Switchyard 2.3.1, built the way INC-2231 was (`../README.md`).
Nothing here is inside `week6/`. `task.md` and `incident/` go into the workspace; everything
else in this folder stays out.

## The defect

While an endpoint is switched off the router creates no deliveries for it. When it is
switched on again the router catches up (`services/router/routing.py`, `catch_up`), but only
as far back as 24 hours: `floor = max(since, now - CATCH_UP_SECONDS)`. Events routed for the
merchant earlier in the off period never get a delivery to that endpoint. A delivery that was
queued before the switch-off simply waits and is sent after the switch-on, so the two cases
are treated differently. `contracts/delivery.md` says "Accepted events get IDs and should not
be lost"; no contract mentions a catch-up window.

What the shipped release leaves behind: router `events` rows with no delivery for the
endpoint, and `endpoints.disabled_at` set back to null at the switch-on. After the fact the
router cannot tell which events were owed. The api's `endpoint_history` (and its `outbox`,
which holds every message in the order the router applied them) can. A manual resend does not
recover them either (`apply_resend` skips an endpoint that never had a delivery of the event);
that is a separate defect and nothing here depends on it.

Where the contracts are silent the ticket says what is wanted: which events are owed (accepted
while the endpoint was off, of the types subscribed to at the switch-on; an endpoint created
switched off is off from its creation), that each switch-on brings the off period that just
ended, that nothing is delivered twice, that events already skipped are recovered once without
anyone asking (and wait if the endpoint is off at that moment), and that the same holds for
version 1 and 2 messages. Recovery is limited to events the api accepted for endpoints managed
through the api, because that is all the stored state can reconstruct.

## Files

| Path | What |
| --- | --- |
| `task.md` | The ticket. |
| `incident/` | The evidence packet. |
| `truth.json` | The expected `out/impact.json`. |
| `scenarios.json` | The judge's scenarios, each with its `class` and `basis`. |
| `judge.py` | Scores a workspace; `--shipped` is the self-check, `--repair-only` skips the report. |
| `../gen_scenarios_2318.py` | Writes `scenarios.json`. |
| `../gen_packet_2318.py` | Builds the packet and the truth by running the shipped release (imports `gen_packet.py`'s machinery). |
| `../crosscheck_2318.py` | Derives the report from the packet through `week6/kit/evidence.py` and compares it with the truth. |
| `../ground-truth-notes-2318.json` | Counts from the last packet build. |
| `../reference-fix-2318.diff` | One repair that passes every scenario. Not the only valid design. |

## Scenarios

44 in `scenarios.json`, plus the 3 shipped scenarios added to `regressions` at run time.
Every expectation is about what a merchant's endpoint receives.

| Category | Count | Classes |
| --- | --- | --- |
| incident | 19 | plain case on new traffic 3, off and on several times 3, subscription changed meanwhile 2, restart or crash point 2, older bus versions 2, already skipped by the shipped release 7 (all start on the shipped release and replace it with an `upgrade` step) |
| regressions | 16 (+3 shipped) | off for less than a day 4, nothing twice 4, before the endpoint existed 2, stays off 3, types 3; 5 of them start on the shipped release |
| compat | 6 | version 1 1, version 2 4, both 1; 1 starts on the shipped release |

### Fairness: what requires each incident scenario

T-n is a sentence of the ticket, C-n a contract clause:

- T-owed: "an endpoint that is switched back on gets every event it is owed, however long it was off"
- T-start: "from the change that switched it off (for an endpoint that was created switched off, from its creation) ... A change made while it is off (a new secret, a new address, switching it off again) does not move that start."
- T-types: "whose type it is subscribed to at the moment it is switched back on"
- T-once: "Each is delivered once."
- T-not: "Events from before the endpoint existed, events accepted while it was on and not subscribed to their type, and events of types it is not subscribed to when it comes back on, are not owed. An endpoint that is still off gets nothing."
- T-several: "If an endpoint is switched off and on several times, each switch-on brings the events of the off period that just ended. Nothing is delivered a second time."
- T-recover: "Events that were owed in this way and that the running release has already failed to deliver must be delivered, once, when the release is out. Nobody should have to ask for them."
- T-wait: "If the endpoint is switched off at that moment, they wait and go out when it is switched on again."
- T-replace: "The release goes to every region and replaces the running one in place, on its existing state. An endpoint may be off at that moment."
- T-bus: "Version 1 and version 2 bus messages keep working. An endpoint that exists only in the archive and is switched off and on by version 2 messages is owed its events in the same way, and events that arrive as version 1 or version 2 messages while an endpoint is off are owed like any other."
- T-down: "Services are restarted and can go down at any point, as they do today; what an endpoint is owed does not depend on that."
- C-lost: delivery.md, "Accepted events get IDs and should not be lost."
- C-two: delivery.md, "Only manual resends can send an event under two delivery IDs to the same endpoint."

| # | Class | Scenario | Required by |
| --- | --- | --- | --- |
| 1 | plain | off for 25 h, one event, on: delivered once | T-owed, C-lost, T-once |
| 2 | plain | off for three days, four events of four types, on: each once; the merchant's other endpoint got them as they came | T-owed, C-lost, T-once |
| 3 | plain | created switched off, first switched on 25 h later: the events since its creation, none from before | T-start, T-owed, T-not |
| 4 | several times | off 1 h, on, off 25 h, on: each event once | T-several, T-owed, T-once |
| 5 | several times | off 25 h, on, off 1 min, on: each event once, at the switch-on that ended its off period | T-several, T-owed, T-once |
| 6 | several times | secret rotated and a second "off" while off: the start does not move; signed with the new secret | T-start, T-owed (signing with the current secret is today's behaviour) |
| 7 | types | subscription narrowed while off for 25 h: only the types subscribed to at the switch-on | T-types, T-not |
| 8 | types | subscription widened while off for 25 h: every type subscribed to at the switch-on | T-types, T-owed |
| 9 | restart or crash | api, router and worker restarted while the endpoint is off | T-down, T-owed, T-once |
| 10 | restart or crash | the router exits at crash point 1 right after applying the switch-on and is started again | T-down, T-owed, T-once |
| 11 | older bus versions | archive-only endpoint off and on by version 2 messages 25 h apart gets the version 2 event that arrived meanwhile | T-bus, T-owed |
| 12 | older bus versions | version 1 and version 2 events arrive while an api endpoint is off for 25 h | T-bus, T-owed, T-once |
| 13 | already skipped | an event the shipped release skipped is delivered once the release is replaced | T-recover, T-once |
| 14 | already skipped | of two owed events the shipped release delivered one: the other arrives, the first is not sent again, the other endpoint gets nothing more | T-recover, T-once, C-two |
| 15 | already skipped | only skipped events of a type subscribed to at that switch-on are recovered, whatever the endpoint subscribes to by then | T-recover, T-types, T-not |
| 16 | already skipped | starting the replaced release again (twice) delivers nothing more | T-recover, T-once, T-down |
| 17 | already skipped | a short off period the shipped release caught up and a long one it skipped: only the skipped event arrives | T-recover, T-several, T-once |
| 18 | already skipped | the endpoint is off again when the release is replaced: the skipped event waits and arrives once at the next switch-on | T-wait, T-recover, T-not, T-once |
| 19 | already skipped | off when the release is replaced, switched on later, 25 h after the switch-off: events from before and after the replacement | T-replace, T-owed, T-once |

No scenario was dropped. Two things rest on the ticket alone, not on a contract: the
subscription that counts is the one at the switch-on (it is what the shipped release does for
off periods under a day, so regressions and incident agree), and T-down (the contracts only
say crash points must stay where they are). No scenario checks recovery of version 1 or 2
events or of archive-only endpoints the shipped release skipped: the stored state cannot
reconstruct those, and the ticket says so.

## The packet

`gen_packet_2318.py` drives the unmodified release through six simulated days (2026-10-26 to
2026-10-31): 9 merchants, 11 endpoints, 632 events accepted by the api, 635 deliveries, 763
requests, scripted failures and retries, four service restarts. Then, with seed 2318: clock
skew per host (router +7 s, worker +41 s, egress -9 s), batches sent twice, batches delivered
late, 116 corrupted rows counting each appearance (api 11, router 53, worker 31, egress 18,
export 3). Rebuilding gives the same bytes.

The report: 7 items in `missed` (6 endpoints, `ep_juniper_1` twice), 71 (endpoint, event)
pairs, 5 events missed by two endpoints of one merchant and counted twice in the totals,
three currencies (USD, EUR, GBP). Ten figures: 3 totals, `skipped_rows`, 6 endpoints' off
periods.

| Endpoint | Off period | Hours | Accepted meanwhile | Missed |
| --- | --- | --- | --- | --- |
| `ep_harbor_1` | Mon 09:14:07 to Wed 10:02:41 | 48.8 | 32 | 14 |
| `ep_isle_1` | Tue 08:00:30 to Thu 09:00:12 | 49.0 | 28 | 14 |
| `ep_isle_2` | Tue 20:00:05 to Thu 02:00:44 | 30.0 | 18 | 5 |
| `ep_juniper_1` | Mon 06:00:19 to Tue 08:00:03 | 26.0 | 22 | 3 |
| `ep_juniper_1` | Wed 12:00:50 to Fri 15:00:20 | 51.0 | 31 | 19 |
| `ep_moss_1` | Mon 12:00:21 to Wed 00:30:02 | 36.5 | 22 | 4 |
| `ep_nettle_1` | created off Mon 07:30:00, on Wed 08:15:10 | 48.8 | 27 | 12 |

Truth comes from what the generator did (the time and order of every api call) and from the
router's own list of deliveries at the end, never from the kit's loader. The generator asserts
that the ticket's wording (api timestamps) and the order things really happened in give the
same missed events.

Each thing the report rests on loses at most one of its records, so no fact is missing from
every file: the api's record of an event of a merchant with an off period is never cut; of the
71 missed events' rows, 15 router `event.routed` rows are cut; of the 124 deliveries that show
an owed event was not missed, 9 lose their `delivery.created` row (the egress line still names
event and endpoint), 14 an egress line, 8 the worker's `attempt.started`. Event types are not
in any log, so every endpoint subscribes to all types and the ticket says so.

### Near misses planted

- Off for less than a day: `ep_kestrel_1` (20 h, secret rotated meanwhile), `ep_pine_1` (12 h),
  `ep_pine_2` (two seconds short of a day): 15 owed events, all caught up.
- Still off at the end: `ep_larch_1` (off from Wed, "off" again on Fri) and `ep_moss_1`'s second
  off period: 58 events accepted meanwhile, no switch-on, not in the report.
- Off, on, off again: `ep_moss_1`. Its first off period is in the report although it is off at
  the end.
- A repeated "off" and a secret rotation inside an off period (`ep_isle_1`, `ep_harbor_1`,
  `ep_nettle_1`): the api logs `enabled: false` again; the off period still starts at the
  first change.
- Same second as a change: accepted in the second of `ep_harbor_1`'s switch-off, after it
  (missed, in the report); in the second of `ep_isle_1`'s switch-off, before it (has a
  delivery that waited 49 h); in the second of `ep_juniper_1`'s switch-on, before it (caught
  up at once); in the second of `ep_moss_1`'s switch-on, after it (ordinary delivery).
- Either side of the 24 hours: `ep_harbor_1` events 24 h 1.5 min before the switch-on (missed)
  and 23 h 58.5 min before it (caught up).
- A delivery waiting for a retry when `ep_isle_1` was switched off, sent 49 h later.
- `m_nettle` events from before its endpoint existed; 14 deliveries to `ep_osier_1` that never
  got a 2xx (its server is down from Fri 20:00; the endpoint was never off).
- Records partly cut, as above.
- The Support note's lead (secret rotated while off) is true of `ep_harbor_1` and
  `ep_nettle_1`, and equally of `ep_kestrel_1`, which lost nothing.

What the traps cost (derived through the kit, scored by `judge.py`): as the ticket defines it
1.00; strictly after the switch-off 0.96; by arithmetic (accepted more than 24 h before the
switch-on) 0.96; only endpoints that are on at the end 0.90; deliveries from the router's
`delivery.created` rows only 0.80; every `enabled: false` row taken as a new switch-off 0.57.

## Verification

Run on 2026-11-27 with Node 24, port bases 26000 to 30000.

| Check | Result |
| --- | --- |
| `judge.py --shipped` | incident 0 of 19, regressions 19 of 19, compat 6 of 6 (exit 0) |
| `reference-fix-2318.diff` applied to a fresh copy of `week6/app` | incident 19 of 19, regressions 19 of 19, compat 6 of 6: repair 1.00 |
| incomplete repair: the 24-hour floor removed, nothing for events already skipped | incident 13 of 19 (already skipped 1 of 7), others 25 of 25: repair 0.68 |
| over-eager recovery: at start, every event of an enabled endpoint's merchant with no delivery | incident 17 of 19, others 23 of 25: repair 0.82 |
| `crosscheck_2318.py` | corrupted rows agree file by file (116); report derived through the kit equals `truth.json`; through `judge.py`: impact 1.00, 10 of 10 figures |

The reference repair: the router's catch-up loses its floor; the api, once at start, walks its
outbox in order, works out which events each endpoint was owed at each past switch-on, and
sends the router an `endpoint.changed` message for the endpoint's current version with an
extra `owed` list; the router makes a delivery for each listed event that has none to that
endpoint.

```bash
PATH=/opt/node24/bin:$PATH python3 gen_packet_2318.py
python3 gen_scenarios_2318.py
python3 crosscheck_2318.py
PATH=/opt/node24/bin:$PATH python3 inc-2318/judge.py --shipped
PATH=/opt/node24/bin:$PATH python3 inc-2318/judge.py "$WS" --out judge.json
```

## Limits

- The judge plays scenarios with the kit's own runner, so it shares that runner's contract
  checks with the setup it judges.
- `run_transfer.py` is fixed to `inc-2231` (`INCIDENT`) and was not changed; running the setup
  on this incident needs that path switched.
- Recovery scenarios keep api and router clocks together and drain after every step. A repair
  that matches api timestamps against the router's routing times passes them; a region whose
  outbox was stuck for hours is not played.
- Incident scenario 10 passes on any repair that does the catch-up in the transaction that
  applies the switch-on; it would catch one that does it afterwards.
