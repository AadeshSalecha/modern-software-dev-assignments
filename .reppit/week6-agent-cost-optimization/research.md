# Research: Week 6 agent cost-optimization (Switchyard)

Researched 2026-11-26 against `week6/` at branch `claude/inspiring-heisenberg-2ulmja`. Descriptive only.
Paths are relative to `week6/` unless noted. This file lives outside `week6/` on purpose: anything
inside `week6/` is copied into the agent's workspace and into the submission zip.

## 1. The assignment in one page

- Deliverable: a `week6/` folder whose `./run.sh task.md` runs unattended (no TTY, empty home, 10 min,
  $2.00 gateway cap) and leaves (a) a repair in `app/services/{api,router,worker}` and (b) `out/impact.json`.
- Graded once per submission on a **held-out incident in the same repo**; 3 submissions max.
- Before the run the grader replaces `app/`, `incident/`, `task.md`; drops `tools/starter/` and `out/`.
  Everything else in `week6/` is ours (run.sh, prompts, root `CLAUDE.md`/`AGENTS.md`, `.claude/`, scripts).
  `run.sh` may rewrite or delete files in `app/` before the agent starts.
- Scores: repair = (incident scenarios passed share) x (other scenarios passed share);
  impact = 0.6 x F1(affected) + 0.4 x share of figures exactly right. Pass = both 1.00.
- Points: correctness 35; cost 35, linear from $1.50 (0 pts) to $0.75 or less (35 pts); write-up 30.
  Leaderboard bonus for lowest passing cost.
- Rate card ($/M tokens: in / out / cache read / cache write):
  sonnet-5-5 2.00/10.00/0.10/2.50 (1h write 4.00); haiku-5-5 0.10/0.50/0.01/0.125 (1h 0.20);
  gpt-6.1-terra 1.00/5.00/0.05/1.25; gpt-6-luna 0.10/0.50/0.01/0.125. Small tier is 20x cheaper than Sonnet.
- Rules: every model call via the gateway; `run.sh` must get to the repair/report by running an agent;
  zero-model-call passes are flagged; submissions carrying copies of `app/` files are reviewed; do not
  show `tools/starter/` to the agent; "tune for the system, not the ticket".
- Baseline `run.sh`: one `claude -p "$(cat task.md)" --model claude-sonnet-5-5 --effort high
  --permission-mode bypassPermissions --output-format stream-json --verbose` (`run.sh:18-22`).

## 2. Repository layout (`app/`, release 2.3.1; 219 files, 1.9 MB)

| Path | ~Tokens | What | Scored / needed |
|---|---|---|---|
| `contracts/` | 5.8k | delivery.md, evidence.md, harness.md, api.yaml, bus v1/v2/v3 schemas + README | Authoritative |
| `services/api` | 6.7k | TypeScript, run raw by node, `node:sqlite`, no deps | Scored |
| `services/router` | 9.8k | Python stdlib | Scored |
| `services/worker` | 13.5k | Go stdlib + vendored `internal/standardwebhooks` | Scored |
| `services/receiver` | 6.4k | scripted merchant stand-in (harness only) | No |
| `services/router-next` | 6.8k | unfinished 2.5 rewrite, not started by anything | No |
| `bin/` | 7k | `up`, `down`, `replay`, `evaluate`, `attempt-id`, `replaylib.py` | Tooling |
| `scenarios/` | 0.8k | 3 happy-path scenarios (delivery, retry, restart) | Regression only |
| `docs/` | 9.9k | 9 ADRs, 5 runbooks, 2 postmortems | Leads and decoys |
| `deploy/`, `legacy/` | 13k | k8s (live), Helm (stale), release-1 dispatcher | No |
| `sdk/` | 173k | upstream Standard Webhooks libs in 9 languages | No |
| root | 1.7k | `CLAUDE.md`, `AGENTS.md`, `README.md`, `CHANGELOG.md` | CHANGELOG accurate, others stale |

## 3. Services and event flow

- **api** `services/api/src/main.ts` (344 lines), `store.ts` (237), `keys.ts` (37). Port base+1.
  `acceptEvent` main.ts:142; idempotency lookup main.ts:163 uses only in-memory `RecentKeys`
  (24h window, keys.ts:4); `store.eventByKey` store.ts:164 exists but only the Support GET uses it
  (main.ts:265-273, :300). Outbox published on tick as bus **v3** (main.ts:225-232).
  Crash points 1-4 at :202, :105/:138, :255, :258. Tests: `npm test` (12 tests, none cover main.ts).
- **router** `main.py` (190), `bus.py` (182), `routing.py` (157), `leases.py` (147), `store.py` (130).
  Port base+2. `bus.parse` dispatches v1/v2/v3 (bus.py:172); dedup via `bus_seen` (main.py:47-55);
  `route_event` dedups by event id only (routing.py:64-86); router mints `dlv_` (routing.py:20-33).
  `LEASE_SECONDS=120`, `MAX_ATTEMPTS=6`, `RETRY_AFTER=[30,120,600,3600,21600]` (leases.py:7-9).
  `SWITCHYARD_INC2188_WORKAROUND` default on (routing.py:13, :137). Tests: `make test` (15).
- **worker** `main.go` (240), `queue.go` (80), `journal.go` (176), `recovery.go` (36), `deliver.go` (73).
  Port base+3. Mints `att_` from worker id + journal counter (main.go:60-63); journal at
  `state/worker/journal.jsonl`; `settle()` replays held attempts on restart (recovery.go:7-35);
  outcome: unfinished=unknown, 2xx=delivered, else failed (deliver.go:58-69). Crash points 1-9. Tests: `make test` (14).
- Ids: `prefix_` + 14 hex of sha256 over a per-prefix counter in each service's own `meta` table.
- No service has a cancel path, cancelled state, or cancel bus message type today.
- All three unit suites pass offline; nothing needs a network install. Go 1.21 module, no requires.
- Harness (`contracts/harness.md`): env `SWITCHYARD_STATE`, `SWITCHYARD_PORT_BASE`, `SWITCHYARD_CLOCK`;
  `/__admin/{health,clock,tick,crash_at,state}`; no background work outside handlers and tick;
  crash points must keep step and number. `bin/replay <file>` runs one scenario; `bin/evaluate` runs
  `scenarios/*.json`, traces verbosely by default (`--quiet` exists, bin/evaluate:91).
  Scenario step verbs supported by `replaylib.py:12-22` include `event` with `idempotency_key`, `bus`,
  `crash_at`, `restart`, `resend`, `drain`, though the three shipped scenarios use none of those.

## 4. Contracts vs everything else

Contract rules (authoritative): delivered only after a recorded 2xx; ends `delivered` or `dead` unless
endpoint disabled; a delivery may arrive more than once under the same id; only manual resends give an
event two delivery ids at one endpoint; Standard Webhooks signing; a repeated idempotency key "returns
the first event with 200 and accepts nothing new" (api.yaml:75, no window); router accepts bus v1/v2/v3,
200 if applied or already applied, 422 if malformed.

`app/CLAUDE.md` and `app/AGENTS.md` are auto-loaded by Claude Code / Codex when working under `app/`,
never mention `contracts/`, and state:

| Claim (AGENTS.md / CLAUDE.md) | Contract or code |
|---|---|
| Done when `bin/evaluate` prints `3 of 3 scenarios pass` | Those scenarios cover nothing incident-specific |
| At most once; unrecorded attempt settled as delivered | delivery.md:5,9; harness.md:38 (at least once, `unknown` counted) |
| `api` assigns delivery ids; router/worker never mint ids | router mints `dlv_`, worker mints `att_` |
| Bus messages are version 2 | api emits v3; all three accepted |
| 5 attempts, 30s/2m/10m/1h; lease 60s | 6 attempts incl. 6h; lease 120s |
| Keep a change inside one service | no such contract rule |
| `legacy/README.md` documents guarantees best | release-1 semantics |

Also stale: `app/README.md`, api and worker READMEs, `docs/runbooks/worker-restart.md`, Helm chart,
`docs/README.md` index. ADR chain: 0003 superseded by 0009, 0006 by 0008, 0001 by 0004; current are
0008, 0009, 0010, 0011; 0013 (in-memory idempotency keys) is "accepted" but in tension with api.yaml:75.
Postmortems: INC-1907 (lease/clock skew, same delivery id) and INC-2188 (endpoint change creates second
delivery id; suppressed by a default-on flag, real fix not done).

Code divergences from contracts found by reading (not all exercised):
1. Idempotency lookup is in-memory only: lost on restart, per process, 24h (verified).
2. `follow_version` creates a second non-resend delivery when the INC-2188 flag is off (verified; inactive by default).
3. v3 identity `producer`+`seq`: every api process sends `producer:"api"` with its own seq (mechanism verified).
4. Attempts keyed by `attempt_id` alone; reused id inherits earlier outcome (leases.py:68-77; occurrence suspected).
5. 2xx reported after lease expiry is `report.ignored` (leases.py:58-66).
6. v2/v3 parsers are laxer than the schemas; v1 regex/strptime edge cases (suspected).

## 5. Evidence packet (`incident/`, 10.5 MB, ~2.6M tokens raw)

| File | Rows | Shape | Notes |
|---|---|---|---|
| `api.ndjson` | 8,961 | NDJSON keyed on `msg` (6 kinds) | only source of acceptance order and `idempotency_key` |
| `router.log` | 24,372 | logfmt (8 kinds) | event amount/currency, delivery->event/endpoint |
| `worker.jsonl.gz` | 25,345 | gzip JSONL keyed on `op` | attempt status; epoch-second `t` |
| `egress.log` | 5,015 | positional + k=v | status the merchant answered |
| `merchant_export.csv` | 784 | CSV, CRLF | one merchant only; local time; major units; cut ids |
| `snapshots/router-*.json` x3 | 1 line each | router state | third source for delivery->event/endpoint |

Properties measured on the starter packet (all described generically in `contracts/evidence.md:92-99`):
- 97 truncated rows across the five files (13/36/37/7/4); the contract's cut-row rule identifies all of them.
- Shipper duplicates: exact repeated lines in api (67), router (323), worker (262).
- Late batches (backward timestamp jumps); clock skew of tens of seconds between hosts.
- No file is complete: 6 events are api-only and 6 router-only; router lacks 9 `delivery.created`,
  egress lacks 7 deliveries; 7 attempts have no worker status but a 200 at egress; 15 deliveries lack
  2xx evidence in one of worker/egress/router. Cross-file facts never conflict where both exist.
- `evidence.md` examples are incomplete relative to real rows (extra fields such as `idempotency_key`,
  `version=`, undocumented message kinds; `err=` position; snapshot fields).
- CSV: amounts in four textual forms, JPY 0 / KWD 3 minor digits, 23 cut `webhook_id` prefixes, UTC-5.
- `event.repeated.event` names the event the key currently maps to, not always the first one.

## 6. Grading and practice tooling (`tools/`)

- `practice.py [--runs N] [--timeout 600] [--port 8787] [--keep]`: copies `week6/` to a temp workspace,
  dropping at any depth `.git, runs, out, __pycache__, .pytest_cache, .venv, node_modules, .build,
  state, starter` (practice.py:51-53); starts the gateway with `--max-cost 2.0`; runs `./run.sh task.md`
  with stdin `/dev/null`; scores; writes `runs/<stamp>-<i>/{usage.jsonl, agent.log, score.log,
  summary.json}` plus `app.diff` and `out/` with `--keep`.
- Env given to the harness: `ANTHROPIC_BASE_URL`, `OPENAI_BASE_URL`, `CODEX_HOME`,
  `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`, `DISABLE_AUTOUPDATER=1`. Practice keeps the real
  `HOME` and full env; grading uses `env -i` and an empty home (runner.py:73-75).
- Gateway: meters `/v1/messages` and OpenAI responses/chat; `count_tokens` is free; unlisted model
  gets 403 and is logged; budget check happens before forwarding; aborted streams are still fully
  charged; upstream errors count as requests; gzip request bodies get 415; 1h cache writes priced higher.
- Scoring: 21 scenarios in three categories: incident 9, regressions 10, compat 2 (bus v1, v2).
  11 start from the *deployed* release and then `upgrade` to the candidate on the same state dir.
  Every scenario also checks: services still running, one first delivery per (event, endpoint),
  delivered implies a 2xx, nothing left queued or leased, requests signed and naming known deliveries.
  Impact F1 key is `(event_id, endpoint_id, sorted delivery_ids)`; figures are each currency in the
  union of truth and report plus `skipped_rows`, exact match (an extra currency counts as wrong).
- Only `services/{api,router,worker}` are taken from the workspace; a build failure fails everything.
- Workspace has no `.git`; `out/` is not pre-created; root `.claude/`, `CLAUDE.md`, `AGENTS.md` are copied.

Held back from the agent setup (known to us only because research read `tools/starter/`): starter
scenario contents and `truth.json` (53 affected entries, 5 currencies).

## 7. This machine

| Item | State |
|---|---|
| Node | default v22.23.5; v24.22.3 at `/opt/node24/bin` (used for practice) |
| Go / Python | 1.24.7 / 3.13 |
| claude | 2.1.332, logged in via host-managed session OAuth token |
| codex | not installed; no OpenAI key or login |
| API keys | none set |

## 8. Baseline run (2026-11-26, unmodified `run.sh`, starter incident)

Command: `env -u CLAUDE_CODE_GZIP_REQUEST_BODIES PATH=/opt/node24/bin:$PATH python3 tools/practice.py --keep`
(Node 24.22.3 from `/opt/node24`; the gzip variable must be unset or the gateway answers 415).
Logs: `week6/runs/20261126-101810-1/`. One run only.

| Repair | Impact | Cost | Requests | Time | Result |
|---|---|---|---|---|---|
| 0.44 | 0.57 (P 0.28, R 0.28, figures 6/6) | $1.2602 | 38 | 303 s | FAIL |

| Model | Input | Output | Cache read | Cache write (5m) | Cache write (1h) |
|---|---|---|---|---|---|
| claude-sonnet-5-5 | 78 | 37,711 | 3,419,684 | 0 | 135,234 |

Cost split: 1h cache writes $0.54 (43%), output $0.38 (30%), cache reads $0.34 (27%), input ~$0.
- Every cache write was billed at the 1h rate ($4.00/M, not $2.50/M). At the 5m rate the run would be $1.06.
  Whether the grader's pinned harness also writes 1h cache is unknown.
- The first request alone wrote 26k tokens (system prompt and tool definitions) = $0.10 before any work.
- Context grew from 26k to 133k tokens over 38 requests; every request re-reads the whole prefix,
  which is where the 3.4M cache-read tokens come from.
- Tool use: 39 Bash, 1 Read, 1 Edit; 171k chars of tool results. Largest results were whole-file `cat`s
  of the services (17-20k chars each) and of `CLAUDE.md`/`AGENTS.md`/contracts. It also read
  `assignment.md`, `writeup.md` and `run.sh` from the workspace root.
- No background Haiku requests appeared. One unmetered refusal (`endpoint_not_available`, an
  agent-proxy CA-cert path specific to this hosted container).

Scenarios: incident 4/9, regressions 10/10, compat 2/2.
- All five failures are scenarios where repeats already exist when the old release is replaced
  (queued for retry, in flight, already-delivered original, several payments, double restart). Problem
  reported each time: "a payment reaches an endpoint as a second event".
- The agent's own summary states this limit: "Repeats already sitting in a router's queue at deploy
  time aren't cancelled, because the router never received their keys."
- What it did build: idempotency lookup moved into the api's SQLite `events` table; optional
  `idempotency_key` on v3 `event.accepted`; router `cancelled` state for later same-key events.
- It noticed that `AGENTS.md`/`CLAUDE.md` contradict the contracts and followed the contracts, but still
  ran `bin/evaluate` as its finish line and added a fourth scenario it admitted could not detect the bug.

Impact: 53 entries reported against 53 expected, all totals and `skipped_rows` exact, but only 15
entries match. Both sides name 33 events and only 14 coincide; endpoint distribution is identical.
So for 19 key groups the report names a different event of the pair than the expected one. Why it
chose that event has not been traced in the transcript.

## Gaps / unknowns

1. Practice runs here for Claude Code (section 8). Only one baseline run exists, so variance is unknown.
   This container's harness (hosted session, real `HOME`, 1h cache TTL, ~26k-token base prompt) may
   differ from the grader's pinned one; staff measured $1.50 on the held-out incident versus $1.26 here.
2. **Codex side** cannot be exercised in this container (not installed, no OpenAI credentials). The
   user has Codex locally.
3. **Grader environment**: pinned harness versions unknown; whether `PATH`, `python3`, `go`, `node`
   are available to `run.sh` and the agent inside the container is implied (scoring needs them) but not shown.
4. **Shape of the held-out incident**: unknown. Same repo and evidence format; whether it has the same
   report schema (`affected` / `totals_minor` / `skipped_rows`) is not stated.
5. Why the baseline report named the wrong event in 19 of 33 key groups is untraced.
6. **Five starter events have no recoverable idempotency key** in any file, despite evidence.md:99;
   whether they matter to the report is unverified.
7. **How far `run.sh` preprocessing may go** before it counts as "writing the repair or report
   yourself": deleting/rewriting misleading `app/` docs is explicitly allowed; generic evidence-parsing
   scripts are listed as a lever; ticket-specific logic is not.
8. Whether Small-tier models can do the repair reliably is unmeasured.
