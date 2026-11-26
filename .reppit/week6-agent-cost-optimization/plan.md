# Plan: Week 6 Option A (one well-equipped session)

Reads with `research.md` and `proposals.md` in this folder. Written 2026-11-26.
Scope: the shared foundation plus a single Claude Code session, measured until it passes reliably
under $0.75. Option B (staged pipeline, Haiku, Codex/GPT) gets its own plan afterwards.

## Requirements

- `./run.sh task.md` runs unattended in a fresh container: no TTY, empty home, `env -i`, 10 minutes, $2.00 cap.
- Pass = repair 1.00 and impact 1.00. Target: 5 of 5 practice passes, mean cost under $0.75, worst run under $1.00, every run under 8 minutes.
- Nothing in the setup may encode this ticket (duplicate payments, idempotency fix, starter answers).
  Allowed sources for what we write: `task.md` as a format, `app/contracts/`, service code, `app/bin/`.
- The agent does the repair and the report. Helpers only parse, run and check.
- No copies of `app/` files in the submission. Snapshots are made at run time by `run.sh`.
- `app/`, `incident/`, `task.md` stay untouched in git.

## Decisions carried in

| # | Decision | Why |
|---|---|---|
| P1 | A first; B only after a reliable pass under $0.75 | User |
| P2 | Unneeded code moves to `app/_deprecated/` with a short README, not deleted | User: a held-out incident might need it |
| P3 | Upgrade-aware checks are in | User |
| P4 | Cost = `practice.py` output (rate card) | User |
| P5 | One instruction source: `AGENTS.md`; `CLAUDE.md` contains only `@AGENTS.md` | Claude Code ignores `AGENTS.md` when a `CLAUDE.md` exists; Codex reads `AGENTS.md`. One file to maintain, both harnesses served |
| P6 | Sonnet stays the model for A; first lever is context size, not model | Baseline cost was 43% cache writes, 27% cache reads, 30% output |
| P7 | The reproduction check (agent scenarios must fail on the old release) blocks at most 3 times, then is advisory | User, at plan approval |
| P8 | The transfer check is decided after the 5-run results, not committed to now | User, at plan approval |
| P9 | Spend on practice runs is not a constraint | User: runs are covered by their subscription |

## Measured facts the plan relies on (this container, 2026-11-26)

| Fact | Value |
|---|---|
| Base prompt, default flags | ~42k tokens direct, 26k through the gateway run |
| Base prompt with `--tools "Bash,Read,Edit" --strict-mcp-config --setting-sources project` | ~6.7k tokens |
| `FORCE_PROMPT_CACHING_5M=1` | cache writes billed at the 5m rate (verified: 1h = 0) |
| Under those flags | root `CLAUDE.md` loads, project skills resolve, nested `CLAUDE.md` loads when a file beside it is read |
| `replaylib.Deployment(state, port_base, app=...)` | takes the app tree as a parameter, so one state dir can be served by two code trees in turn |

## Files

All paths under `week6/`.

**New**

| Path | Purpose |
|---|---|
| `AGENTS.md` | Root map, about 60 lines (contents below) |
| `CLAUDE.md` | One line: `@AGENTS.md` |
| `kit/prompt.md` | The fixed part of the prompt: workflow and stop conditions |
| `kit/prepare.sh` | Deterministic prep: guard, snapshot, deprecate, overlay, build evidence DB |
| `kit/overlay/app.AGENTS.md` | Replaces `app/AGENTS.md`; `app/CLAUDE.md` becomes `@AGENTS.md` |
| `kit/overlay/{api,router,worker}.AGENTS.md` | Installed as `app/services/<svc>/AGENTS.md` plus a one-line `CLAUDE.md` |
| `kit/overlay/deprecated.README.md` | Installed as `app/_deprecated/README.md` |
| `kit/evidence.py` | Evidence loader and query tool |
| `kit/rollout.py` | Scenario runner with an `upgrade` step and contract invariants |
| `kit/check.sh` | The gate: builds, unit tests, scenarios, crash points, report shape, ledger |
| `kit/tests/` | Unit tests for `evidence.py` and `rollout.py` (synthetic fixtures, no starter data) |
| `.claude/settings.json` | Stop hook calling `kit/check.sh` |
| `.claude/skills/evidence-report/SKILL.md` | How to answer a report question from the evidence DB |
| `.claude/skills/replay-scenarios/SKILL.md` | Scenario grammar, reproducing a bug, rollout scenarios |

**Changed**: `run.sh`, `writeup.md`, `.gitignore` (add `work/`, `.pristine/`).

**Deliberately not touched**: `app/**`, `incident/**`, `task.md`, `tools/**`, `rate_card.json`, `assignment.md`.

Directory names avoid the ones `practice.py` drops at any depth (`state`, `out`, `runs`, `starter`, `.build`, `.venv`, `node_modules`).

## Component specs

### `run.sh`

1. `set -euo pipefail`; `cd` to its directory; `export FORCE_PROMPT_CACHING_5M=1`.
2. `kit/prepare.sh "$TASK_FILE"`. A prep failure is logged and does not abort: the agent still runs.
3. One call, wrapped in `timeout 500`:
   `claude -p "$(cat kit/prompt.md; echo; cat "$TASK_FILE")" --model claude-sonnet-5-5 --effort medium
   --tools "Bash,Read,Edit,Write,Skill" --strict-mcp-config --setting-sources project
   --permission-mode bypassPermissions --max-turns 80 --output-format stream-json --verbose`
   The fixed prompt comes first so the prefix is stable; the ticket is inlined to save a read.
4. After it returns: if `kit/check.sh` fails and more than 150 s remain, one `--resume` of the same
   session with the check output (capped at 60 lines). Never more than one.
5. Exit 0 regardless, so a late failure does not discard a finished repair.

### `kit/prepare.sh`

1. **Guard.** If the directory is inside a git work tree, print how to use `practice.py` and exit
   without touching anything. (Practice and grader workspaces have no `.git`.) This protects the real `app/`.
2. **Snapshot.** Copy `app/services` and `app/bin` to `.pristine/app/` (the untouched release, for
   rollout checks and crash-point comparison).
3. **Deprecate.** Move, if present: `app/sdk`, `app/legacy`, `app/services/router-next`,
   `app/deploy/helm` into `app/_deprecated/`. Install its README (four lines: what each item is).
   Then run the three shipped scenarios once; if any fails, move everything back.
4. **Overlay.** Install the nested instruction files.
5. **Evidence.** `python3 kit/evidence.py build incident work/evidence.db`, print its summary to `work/evidence.summary.txt`.
6. `mkdir -p out work`.

### `AGENTS.md` (root)

Sections, each a few lines:
- **Trust order**: `task.md` defines the outcomes and the terms; `app/contracts/` defines behaviour;
  then the code; everything else (READMEs, ADRs, runbooks, postmortems, comments) is a lead to verify.
  A log line never redefines a term the ticket defines.
- **Map**: the three scored services with one line each and their line counts; `contracts/`; `bin/`;
  `scenarios/`; `incident/` (never read raw, use the DB); `_deprecated/`; "ignore `assignment.md`,
  `writeup.md`, `tools/`".
- **System facts verified in code** (not from prose): who mints which id, lease and retry constants
  with file:line, bus versions and identities, the admin interface, crash points and that they must
  keep step and number.
- **Deployment facts**: one release replaces the running one in every region over existing state;
  logs cover one region; older producers and archived bus messages keep arriving.
- **Working rules**: ranged reads over whole files; quiet test commands; no edits outside
  `app/services/{api,router,worker}`, `out/`, `work/`; parallel tool calls.
- **Pointers**: per-service notes appear when you open a service; the two skills by name.

Constants quoted here are re-derived by `prepare.sh` where cheap (grep) and omitted if not found,
so a changed held-out release cannot make the file lie.

### Nested files

- `app/AGENTS.md`: ten lines. States that the previous version of this file and `README.md` were
  stale, repeats the trust order, lists test commands.
- Per service: entry points, the test command in quiet form, where state lives, crash-point
  locations, what the harness requires of this service.

### `kit/evidence.py`

Commands: `build <incident_dir> <db>`, `schema <db>`, `sql <db> "<query>"` (TSV, capped rows), `skipped <db>`.

`build` implements `contracts/evidence.md` and nothing else:
- Per file, a row is corrupted by the contract's rule (invalid JSON; a line ending in a field with
  no value or a bare token; fewer columns than the header). Corrupted rows are counted every time
  they appear and never parsed.
- Exact duplicate lines are collapsed (shipper resends).
- Each source becomes a table whose columns are the union of keys actually seen, plus `line_no` and
  a normalised epoch `ts`. Unknown message kinds and fields are kept, not dropped.
- Derived views, each built only if its columns exist: `events`, `deliveries`, `attempts`. Every
  view is a union across all sources that carry the fact, with a `sources` column, because no file is complete.
- Merchant export: cut ids resolved by unique prefix against known ids; amounts converted to minor
  units with the digits table in `contracts/messages/README.md`.
- Snapshots: flattened into `snapshot_deliveries` and `snapshot_endpoints`.
- Summary printed: rows, duplicates dropped, corrupted per file and in total, id coverage per
  source, conflicts between sources (expected none).

### `kit/rollout.py`

`rollout.py <scenario.json> [--pristine-until-upgrade] [--quiet]`
- Uses `app/bin/replaylib.py` for steps and expectations.
- Adds one step, `{"do": "upgrade"}`: before it, services run from `.pristine/app`; at it, api,
  router and worker stop and restart from the candidate on the same state directory.
- `--upgrade-at N` inserts an upgrade after step N of an ordinary scenario.
- After the scenario, checks contract invariants and prints at most 20 lines:
  all three services alive; nothing left `queued` or `leased` after a drain; `delivered` implies a
  recorded 2xx; at most one non-resend delivery per event and endpoint; every received request
  names a known delivery and verifies against its endpoint secret.

### `kit/check.sh`

Runs in order, stops at the first failing group, prints at most 40 lines:
1. `go build` of the worker; `node --check`-level load of the api; `python3 -m py_compile` of the router.
2. Unit tests of the three services, quiet.
3. Shipped scenarios, plain and with an upgrade inserted after each step position.
4. Agent-written scenarios in `work/scenarios/*.json`: each must fail on the pristine release (it
   reproduces the incident) and pass on the candidate, plain and across an upgrade.
5. Crash points: the set of numbered `crash` calls per service equals the pristine set.
6. `out/impact.json` exists, parses, and has the same top-level keys and value types as the JSON
   example block in the ticket.
7. `work/ledger.md` has no unchecked line.

### Stop hook

`.claude/settings.json` Stop hook runs `kit/check.sh`. On failure it exits 2 with the output, which
blocks the stop. A counter in `work/.stop_blocks` allows at most 3 blocks, then lets the agent stop.

### `kit/prompt.md`

Fixed workflow, about 25 lines:
1. Write `work/ledger.md`: one checkbox per clause of the ticket, including every qualifier, each
   with the check that will prove it.
2. Report: use the evidence DB and the `evidence-report` skill. Apply the ticket's definitions literally.
3. Diagnose: test each lead in the ticket against contracts and code. Reproduce with a scenario
   that fails on the pristine release.
4. Repair in `app/services` so that it holds for new traffic, for state the old release left
   behind, and for older bus messages.
5. Run `kit/check.sh`; tick the ledger; stop. Final message under 10 lines.

### Skills

- `evidence-report`: tables and views, the union-across-sources rule, how the ticket's terms map to
  queries, exactness (ids complete, currencies only when non-empty, integers), a worked example on a
  neutral question ("which deliveries got a 5xx").
- `replay-scenarios`: step verbs including those the shipped scenarios never use, expectation
  forms, the reproduce-then-fix loop, writing a rollout scenario with `upgrade`.

## Ordered steps

Each is one commit on `claude/inspiring-heisenberg-2ulmja`.

| # | Step | Done when |
|---|---|---|
| 1 | `kit/evidence.py` + tests on synthetic fixtures | Tests pass; on the starter packet the summary reports 97 corrupted rows and zero cross-source conflicts (numbers from research) |
| 2 | `kit/rollout.py` + tests | The three shipped scenarios pass plain and with an upgrade at every step position, on unmodified code |
| 3 | `kit/prepare.sh` with guard, snapshot, deprecate, overlay | In a scratch copy: refuses inside git; shipped scenarios still pass after the move; running it twice changes nothing more |
| 4 | `kit/check.sh` + Stop hook | On unmodified code it fails only at group 6 (no report); hook blocks and releases after 3 |
| 5 | `AGENTS.md`, `CLAUDE.md`, nested overlays, skills, `kit/prompt.md` | Overfit grep is clean (see test plan); every stated constant has a file:line that checks out |
| 6 | New `run.sh` | One practice run completes end to end with no refused requests |
| 7 | Measure: 5 practice runs | Table recorded in `writeup.md` Part II |
| 8 | Tune one lever at a time, 3 runs each, 5 for the keeper: effort (low/medium/high), tool set, turn cap, hook on/off, resume on/off | Each row recorded, including dropped ones |
| 9 | Transfer check | See test plan |
| 10 | Fill `writeup.md` Parts I and II | No `TODO` left in those parts |

Stop and report after step 7, and again after step 9, before any Gradescope submission.

## Test plan

- **Unit**: `kit/tests/` builds tiny synthetic packets (a cut JSON line, a duplicated batch, a cut
  id, a JPY amount with a thousands comma) and scenario files; no starter data.
- **Overfit grep**: `grep -riE "idempot|duplicate|repeat|INC-2207|maple|twice" AGENTS.md kit .claude`
  must return only neutral system descriptions, reviewed by hand. No file under `tools/starter/` is
  read by anything in the setup.
- **End to end**: `python3 tools/practice.py --keep --runs 5` with Node 24 on PATH and
  `CLAUDE_CODE_GZIP_REQUEST_BODIES` unset. Record pass, repair, impact, cost, requests, seconds,
  and tokens by kind per run.
- **Failure reading**: for every failed run, read `agent.log` and classify: missed requirement,
  wrong belief (and its source), tool misuse, or time/turn limit.
- **Transfer check**: write a second ticket for a different defect found in research (for example,
  a 2xx reported after lease expiry is ignored, `leases.py:58-66`), with no evidence packet, and run
  the setup once on it. Judged by hand: does it reproduce, repair, keep the invariants, and stay
  near the same cost? This is the only test that says anything about the held-out incident.
- **Grader-likeness**: one run with `HOME` pointed at an empty directory to confirm nothing depends on user-level config.

## Out of scope

- Option B: stage splitting, Haiku, Codex and GPT models. The Mac is ready for it (Go 1.27,
  Node 24, Codex CLI 0.172 logged in, both GPT models answer); `week6/` still has to be brought to
  the Mac clone through git, which needs the user's review of the commit first.
- Gradescope submissions.
- Changing `tools/practice.py` or the gateway.

## Risks

| Risk | Mitigation |
|---|---|
| Held-out `app/` differs from the starter release | `prepare.sh` moves only what exists, re-derives constants, and restores on scenario failure |
| Held-out report has a different schema | `check.sh` reads the shape from the ticket's own JSON example; the evidence DB is schema-neutral |
| Stop hook loops or burns budget | Hard cap of 3 blocks; output capped at 40 lines |
| `check.sh` too slow for 10 minutes | Scenario upgrade positions capped; measured in step 4; target under 40 s |
| Agent trusts our `AGENTS.md` too much | It states the trust order and puts itself below contracts and code |
| Experiment spend | About $0.3 to $0.7 per run on the user's account; steps 7 to 9 are roughly 25 runs |

## Changes during implementation

- Nested instruction files: only `app/AGENTS.md` gets a `CLAUDE.md` twin. The per-service files are
  plain `AGENTS.md`, named explicitly from the root file, because Claude Code auto-loads nested
  files only on a `Read`, and the baseline agent read almost everything through Bash.
- `rollout.py` adds expectation forms that count what an endpoint received in total. The shipped
  expectation forms are per event, so they cannot tell "one event" from "two events with one
  delivery each"; the baseline agent hit exactly that limit.
- `prepare.sh` guard is "refuse when `tools/starter/` exists" rather than "refuse inside git": the
  grader and practice both remove that folder, and the grader's container might be a git checkout.
- `run.sh` ends by moving `_deprecated/` content back and removing the overlay files, so the
  workspace `app/` differs from the release only by the agent's own edits.
- The gate is `kit/check.py`; `kit/check.sh` is a wrapper with the planned name. It runs one
  scenario first and reports "the working tree does not start" instead of waiting for every
  scenario to time out.
- `kit/mapgen.py` (new): writes the line-numbered map into each service's `AGENTS.md` at run time.
- Skills are read as files (`.claude/skills/<name>/SKILL.md`), named in the prompt; the Skill tool
  is not enabled, so the tool list is Bash, Read, Edit, Write.
- `run.sh` has experiment switches read from the environment (`KIT_MODEL`, `KIT_EFFORT`,
  `KIT_TOOLS`, `KIT_MAX_TURNS`, `KIT_NO_HOOK`, `KIT_NO_RESUME`, `KIT_VARIANT=flags`). The grader
  runs with an empty environment, so it always gets the defaults.
- Steps 1 to 7 done on 2026-11-26. Results are in `results.md`.
