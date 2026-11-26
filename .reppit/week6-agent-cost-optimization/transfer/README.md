# Transfer check: INC-2231

A second incident for Switchyard 2.3.1, made to see whether the Week 6 setup works on a
ticket it was not built around. Nothing here is inside `week6/`, so no practice or graded
run can read it.

## The incident

A version-2 `endpoint` bus message makes the router store the message's `seq` as the
endpoint's version (`services/router/bus.py`, `parse_v2`). Every later change from the api
carries a small version and is dropped as stale (`routing.apply_endpoint`). A merchant who
switches the endpoint off keeps receiving webhooks; a rotated secret or a new address never
takes effect. The shipped release reproduces it: `judge.py --shipped` fails all nine
incident scenarios and passes the rest.

The ticket describes symptoms only. It asks for a repair that also recovers changes already
lost, and for a report of deliveries to endpoints that are switched off as far as the api is
concerned.

## Files

| Path | What |
| --- | --- |
| `inc-2231/task.md` | The ticket. Goes into the workspace. |
| `inc-2231/incident/` | The evidence packet. Goes into the workspace. |
| `inc-2231/truth.json` | The expected `out/impact.json`. Stays out. |
| `inc-2231/scenarios.json` | The judge's scenarios: incident 9 (5 start on the shipped release), regressions 6 (plus the 3 shipped scenarios at run time), compat 4. Stays out. |
| `inc-2231/judge.py` | Scores a workspace. Stays out. |
| `gen_packet.py` | Builds the packet and the truth by running the shipped release. |
| `gen_scenarios.py` | Writes `scenarios.json`. |
| `crosscheck.py` | Checks packet, truth and `week6/kit/evidence.py` against each other. |
| `ground-truth-notes.json` | Counts from the last packet build. |
| `reference-fix.diff` | One repair that passes every scenario, to show the judge can be satisfied. Not the only valid design. |

## How the packet is made

`gen_packet.py` drives the unmodified release through three simulated days (2026-10-19 to
2026-10-21) with `app/bin/replaylib.py`: 8 merchants, 10 endpoints, 420 events accepted by
the api, 14 version-2 archive events, 525 deliveries, 599 requests, scripted failures and
retries. Service logs are the services' own. `egress.log` and the merchant export are written
from the merchant stand-in's records in the formats of `contracts/evidence.md`. Then, with a
fixed seed: clock skew per host, batches sent twice, batches delivered late, 88 rows cut
short. The build is deterministic; rebuilding gives the same bytes.

The truth comes from what the generator did (when it called the api, what the stand-in
answered, which rows it cut), not from the kit's loader. Three endpoints are in the report
(33, 25 and 28 deliveries). Each affected delivery loses at most one of its records, so every
fact the report needs is in at least one file, and 28 of the 86 need a second file.

Planted near misses: an endpoint switched off twice (the second change is not a switch-off),
one switched off and on again with catch-up deliveries, one switched off, on and off again,
two switched off normally, deliveries with no 2xx, one event accepted before a switch-off and
answered after it, and archive events the api never accepted.

## Running it

```bash
# 1. a workspace: week6/ without runs/, out/ and tools/starter/, with this ticket and packet
rsync -a --exclude runs --exclude out --exclude tools/starter week6/ "$WS"/
cp .reppit/week6-agent-cost-optimization/transfer/inc-2231/task.md "$WS"/task.md
rm -rf "$WS"/incident && cp -R .reppit/week6-agent-cost-optimization/transfer/inc-2231/incident "$WS"/incident

# 2. the setup, through the gateway, as practice.py runs it
(cd "$WS" && ./run.sh task.md)

# 3. the score
PATH=/opt/node24/bin:$PATH python3 .reppit/week6-agent-cost-optimization/transfer/inc-2231/judge.py "$WS" --out judge.json
```

`judge.py` puts the workspace's `services/{api,router,worker}` into a clean copy of the
release, plays the scenarios with `week6/kit/rollout.py`, and compares the report with the
truth. Scores use the assignment's formulas; an affected entry is one (endpoint, delivery)
pair, and the figures are each currency total, `skipped_rows` and each endpoint's
`switched_off_at`.

Rebuild and re-verify:

```bash
PATH=/opt/node24/bin:$PATH python3 gen_packet.py --app <scratch copy of week6/app>
python3 gen_scenarios.py
python3 crosscheck.py
PATH=/opt/node24/bin:$PATH python3 inc-2231/judge.py --shipped
```

## Limits

- The judge plays scenarios with the kit's own runner, so it shares that runner's contract
  checks with the setup it judges.
- Four expectations rest on the ticket's wording more than on a contract: an archive message
  must not undo an api change; changes the shipped release lost must come back without being
  repeated; an older api change arriving late must not undo a newer one; version-2 changes to
  an archive-only endpoint apply in order.
- The backfill story is invented context. The contracts say only that archived messages are
  replayed and older producers are still in service.
