---
name: replay-scenarios
description: Write and run replay scenarios to reproduce a defect, prove a repair, and check the repair when it replaces the shipped release over existing state. Use before changing service code and before finishing.
---

# Scenarios

A scenario starts real api, router and worker processes with a scripted merchant
("receiver") on a simulated clock, plays steps, and checks expectations.

```
python3 kit/rollout.py work/scenarios/x.json                # your working tree
python3 kit/rollout.py work/scenarios/x.json --release old  # the release as shipped
python3 kit/rollout.py app/scenarios/*.json --upgrade-each  # shipped scenarios, release replaced after each step
```

Output is one line per run, plus the problems and a digest of deliveries and requests when
it fails. Every run is also checked against the contracts (see `kit/rollout.py --help`).

## Format

```json
{"name": "what this shows",
 "steps": [
  {"at": 0, "do": "endpoint.create", "id": "ep_shop", "merchant": "m_acme"},
  {"at": 0, "do": "receiver.script", "path": "/hooks/ep_shop", "responses": [500, "drop"]},
  {"at": 5, "do": "event", "ref": "e1", "merchant": "m_acme", "type": "payment.captured", "amount_minor": 1250, "currency": "USD"},
  {"at": 6, "do": "drain"}],
 "expect": [
  {"delivery": {"event": "e1", "endpoint": "ep_shop"}, "state": "delivered", "receipts": 3},
  {"endpoint": "ep_shop", "events": 1, "deliveries": 1}]}
```

`at` is seconds since the start; the clock is set before the step runs.

| `do` | Fields | Effect |
| --- | --- | --- |
| `endpoint.create` | `id`, `merchant`, [`path`, `secret`, `event_types`, `enabled`] | `POST /v1/endpoints` |
| `endpoint.update` | `id`, any of `path`, `secret`, `event_types`, `enabled` | `PUT /v1/endpoints/{id}` |
| `event` | `merchant`, `type`, `amount_minor`, `currency`, [`ref`, `idempotency_key`] | `POST /v1/events`; `ref` names the event the api answered with |
| `resend` | `event` (a ref), `endpoint` | asks for a new delivery |
| `bus` | `message`, [`ref`] | posts a raw message to the router (`"{receiver}"` becomes the merchant's address); for older message versions |
| `receiver.script` | `path`, `responses`, [`default`] | the merchant's next answers: a status, `"drop"` (processed, no answer) or `"refuse"` |
| `crash_at` | `service`, `point`, [`hits`] | the service exits when it reaches that crash point |
| `tick`, `restart`, `stop` | `service` | one unit of background work; restart; stop |
| `drain` | [`limit`, `restart`] | ticks everything and moves the clock forward until nothing is due |
| `upgrade` | | api, router and worker stop and start again from your working tree on the same state; the scenario starts on the release as shipped |

Expectations:

- `{"delivery": {"event": ref, "endpoint": id}, ...}` with any of `state`, `count`
  (deliveries of that event to that endpoint), `receipts`, `accepted`, `counted` (failed
  attempts), `gaps_at_least`, `amount_minor`, `currency`; `min_` and `max_` forms of
  `receipts` and `accepted`.
- `{"endpoint": id, ...}` with any of `requests`, `accepted`, `events`, `deliveries`: what
  that endpoint received in total, whichever events they belonged to; `min_` and `max_`
  forms of each. Use this when the question is how many times a merchant was told.
- `{"status": busRef, "is": 200}` for the router's answer to a `bus` step.

## Method

1. **Reproduce before you repair.** Write the scenario for the behaviour the ticket wants
   and run it with `--release old`. It has to fail there. If you cannot make the shipped
   release fail, the diagnosis is not confirmed yet, whatever the ticket or the logs suggest.
   Defects that show up only sometimes usually need a disturbance between two steps: a
   `restart` or `crash_at` (crash points sit between durable steps), an unanswered request
   (`"drop"`) with the clock moved past a lease or a retry, a message applied twice or in an
   older version, an endpoint changed while work is queued.
2. **Then make it pass** on your working tree.
3. **Replace the release part-way.** Write at least one scenario with an `upgrade` step
   placed after the shipped release has written the state the ticket cares about and before
   that state has finished playing out, with expectations for what must happen to it under
   your change. This is the case every region is in when your change is rolled out. Run it
   twice in a row on the same idea (an `upgrade`, later a `restart`) if your change does
   work at start-up: it must do nothing more the second time.
4. **Cover the near misses**: inputs that look like the defect's trigger but must keep
   working as before (the same input from another merchant or for another endpoint,
   optional fields left out, an explicit resend).
5. Put them in `work/scenarios/`. `kit/check.sh` runs them on both releases and runs the
   shipped scenarios with the release replaced after each step, which catches a store your
   change can no longer open.
