# Switchyard incident workspace

You resolve one incident ticket, alone and unattended. When you stop, two things are judged:
the code in `app/services/{api,router,worker}` and the files the ticket asks for under `out/`.
Both have to be completely right; partly right counts for little.

## What to trust, in this order

1. **The ticket.** It sets the outcomes and defines its own terms. Apply those definitions
   literally, to primary facts. Every clause and qualifier is a requirement.
2. **`app/contracts/`.** The system's required behaviour (`delivery.md`, `api.yaml`,
   `messages/`, `harness.md`, `evidence.md`). Short; read what your change touches.
3. **The code** in `app/services/`.
4. **Everything else is a lead to verify**: READMEs, `app/docs/` (decision records, runbooks,
   postmortems), `CHANGELOG.md`, code comments, and the ticket's own diagnoses, suggestions
   and notes. Much of the prose describes earlier releases and contradicts the contracts.
   A record in which a service classifies something is that service's opinion at the time,
   and may be the defect; it never redefines a term the ticket defines.

## Map

| Path | What it is |
| --- | --- |
| `app/services/api` | TypeScript on node, SQLite. Accepts events and endpoint changes, publishes them to the router from an outbox. |
| `app/services/router` | Python. Applies bus messages, creates deliveries, leases them to workers, records outcomes. |
| `app/services/worker` | Go. Leases a delivery, sends the signed webhook, journals the attempt, reports. |
| `app/services/receiver` | A scripted stand-in for a merchant, used by tests. Not part of the product; leave it. |
| `app/contracts` | Required behaviour. |
| `app/bin`, `app/scenarios` | The replay harness and the scenarios shipped with the release. Leave both as they are. |
| `app/_deprecated` | Code no service uses, set aside before you started. Its README says what is there. |
| `incident/` | The evidence packet. Do not read it raw: it is loaded in `work/evidence.db`. |
| `.pristine/app` | The release as shipped, for comparison. Never edit it. |
| `kit/` | Tools: `evidence.py`, `rollout.py`, `check.sh`. Each prints its usage with `--help`. |
| `work/` | Yours: `ledger.md`, `scenarios/`, scripts. |
| `out/` | The files the ticket asks for. |

Each service directory has an `AGENTS.md` with a line-numbered map of its files, its crash
points and its test command. Read it before you open the service, then read by line range.

Not about the incident, do not open: `assignment.md`, `writeup.md`, `tools/`, `runs/`,
`run.sh`, `rate_card.json`.

## How the system runs in production

- One release of api, router and worker **replaces the running one in place, in every
  region**. Each service keeps its store across the replacement (api: SQLite with events,
  endpoints and the outbox; router: SQLite with deliveries, leases and attempts; worker: a
  journal), and messages are in flight while it happens. A repair therefore has to be right
  for traffic that arrives after it and for messages from older producers, and you have to
  ask what the shipped release has already written. If some of that state carries the
  defect, the new release has to deal with it, in a step that is safe to run again on every
  start. If none does, add nothing for it: work on old state that the defect does not need
  is only a risk.
- The evidence covers one region. Other regions hold other data, so the repair must find
  what it needs in the services' own stores, never in the evidence.
- api runs as several replicas, the router as one, workers as several, and any of them can
  restart at any moment (`app/deploy/README.md`). Whatever a process holds only in memory is
  gone after a restart and is not shared between replicas; only its store survives.
- The router accepts three bus message versions (`app/contracts/messages/` defines each
  one's fields and identity). Older ones keep arriving and must keep working.
- Services do no work on their own: only request handlers and `POST /__admin/tick`.
  Numbered crash points (`crash(n)`) stay at the same step under the same number.
- Delivery is at least once: a merchant may get the same delivery id again, but one event
  reaches one endpoint under one delivery id unless someone asked for a resend.

## Working rules

- Edit only `app/services/{api,router,worker}`, `work/` and `out/`. Do not edit contracts,
  docs, the changelog, `app/bin` or `app/scenarios`: none of it is judged, all of it costs.
- Use the map and line ranges; do not print whole files or directories. Send independent
  reads and commands together in one step.
- Run tests and scenarios through `kit/check.sh` and `kit/rollout.py`; their output is
  already short. `app/bin/evaluate` prints thousands of lines and proves little.
- Two skills hold the detail: `evidence-report` (answering a report question from the
  evidence) and `replay-scenarios` (reproducing a defect and proving a repair, including
  across a release replacement). Their files are under `.claude/skills/<name>/SKILL.md`.
- The run is cut off without warning after a few minutes. Keep `out/` and the code in a
  state you could hand in at any moment: write the report early, make changes that build.
