# Review: Week 6 Option A kit

Reviewer: a fresh-context agent on a different model (Opus), given `plan.md`, the `week6/` diff
against `bf1e62e`, the unit-test output and `results.md`, and no reasoning from the implementer.
It ran `kit/prepare.sh`, `kit/check.sh` and the unit tests in a scratch copy. Reviewed at commit
`a5ad0d3`; fixes below are in the commit that adds this file.

Status key: **Fixed**, **Partly** (with what remains), **Open** (for the user).

## Must-fix

| # | Where | Finding | Status |
|---|---|---|---|
| 1 | packaging | `week6/runs/` (44 MB of practice logs with earlier `out/impact.json` files and `app.diff`s) would ship in a plain `zip -r` of the folder: starter answers and copies of `app/` code inside the graded workspace. `practice.py` drops `runs/`, so practice never showed it. | **Fixed.** `make_submission.sh` builds the zip without `runs/`, `out/`, `tools/starter/`, caches and `writeup.md`, and fails if any of them is in it. `AGENTS.md` also lists `runs/` as not to be opened. |

## Should-fix

| # | Where | Finding | Status |
|---|---|---|---|
| 2 | `run.sh` | The gate after the session had no time limit, and GNU `timeout` put the harness in its own process group, out of reach of the grader's group kill; replay services detach and would outlive a killed gate. | **Fixed.** No `timeout`; children stay in `run.sh`'s group under a watchdog; every step has a deadline counted from the start; a TERM/INT trap stops the child and the services and restores `app/`. Tested with a stand-in harness: group TERM leaves 0 processes and a restored `app/`; deadlines end the run at 91 s of an allowed 100. |
| 3 | `kit/rollout.py` | A service that stops answering made a run wait on 30 s HTTP timeouts with no overall bound. | **Fixed.** 45 s per run, 150 s for all runs in the gate; the gate's first run reports "does not run" at once. Tested with a router that sleeps in `tick`. |
| 4 | `kit/check.py` `shape` | Report-shape check blocked on harmless differences (`null` in the example, `0.0` against `1`) and could push the agent to bend a correct report to a placeholder's type. | **Fixed.** Keys and nesting block; a single value of another kind is asked about at most 3 times, then noted; `null` in the example matches anything; a whole number satisfies a decimal. |
| 5 | `kit/rollout.py` `invariants` | Contract checks always blocked, though the trust order puts the ticket above the contracts. | **Fixed.** Checks are named; a scenario can skip one with `"skip_checks"`. The shipped scenarios still get all of them. |
| 6 | `kit/evidence.py` `discover` | Two files mapping to one table name overwrote each other; a file named `events.*` crashed the build; subdirectories and rotated names were not loaded. | **Fixed**, with tests. |
| 7 | `kit/evidence.py` request lines | `endpoint` for a request line was read from the address, which no contract defines, and could override the router's endpoint for a delivery. | **Fixed.** It is `url_endpoint`, kept apart from `endpoint_id`; the summary counts deliveries where the two differ. |
| 8 | toolchain | With `go` or `node` missing, the gate would block on a build failure the agent cannot fix, through every stop and the resume. | **Fixed.** `prepare.sh` records what is missing and sets `work/.no_harness`; the gate then checks only the report and the ledger. Tested with `go` off `PATH`. `run.sh` also sets `HOME` and `PATH` when the caller passes neither. |
| 9 | `plan.md` | Drift not recorded (hook cap, resume condition, gate order, missing load check). | **Fixed** in "Changes during implementation". |

## Overfitting and rule compliance

| # | Where | Finding | Status |
|---|---|---|---|
| 10 | `replay-scenarios/SKILL.md`, near misses | "another merchant … another endpoint, optional fields left out, an explicit resend" maps onto the starter's hidden regression scenarios. | **Fixed.** Now "inputs next to the defect's trigger … take them from the contract clauses your change touches". |
| 11 | `evidence-report/SKILL.md` | Two examples restated starter report clauses (a 2xx in the egress log; leaving out keys; entries/events/deliveries). | **Fixed.** Examples are neutral; the sentence about each figure stays in general form. |
| 12 | `kit/overlay/app.AGENTS.md` | Asserted that the shipped `app/AGENTS.md`, `CLAUDE.md` and README describe release 2.0 and are wrong on five points; false if the held-out `app/` ships different notes. | **Fixed.** Says they were moved and may describe an earlier release. |
| 13 | `kit/prompt.md`, `AGENTS.md` | "State the shipped release left behind" was a required ledger line every time, which pushes toward start-up sweeps a different defect does not need. | **Fixed.** The line is now a question: name that state, or write "none" and add nothing. |
| 14 | `AGENTS.md` trust order, endpoint-level expectation | Shaped by this incident but true in general. | **Open**, judged acceptable by the reviewer; listed in the write-up under what may not transfer. |

## Nice-to-have

| # | Where | Finding | Status |
|---|---|---|---|
| 15 | `kit/evidence.py` `finish_export` | Prefix matching was quadratic. | **Fixed** (bisect). |
| 16 | `kit/check.py` `is_map` | A nested object with fixed numeric keys is treated as an open map, so a missing key there is not caught. | **Open.** Accepted limit of a shape check. |
| 17 | `kit/check.py` crash points | Compares sets of numbers, so a removed second call site of the same number goes unnoticed. | **Open.** A stricter check would flag honest refactors. |
| 18 | dev checkout | Running `rollout.py` or `check.py` there writes `app/.build/worker` (gitignored). | **Open.** Harmless. |

## Checked and found sound by the reviewer

Unit tests pass; prep in a bare environment takes about 15 s with a cold build cache and finds 97
corrupted rows and no cross-file conflicts; the gate takes about 7 s; `--restore` returns the
shipped layout exactly; corrupted rows are counted before duplicates are collapsed; the `upgrade`
step restarts the three services on the same state; shipped scenarios are read from the snapshot,
so the agent cannot weaken them; the development-checkout guard works; no keys, and every model
call goes through the `claude` CLI.

## After the fixes

- Unit tests: 40 pass.
- Scratch workspace: prep, gate, hung-router, missing-Go, signal and deadline tests as noted above.
- Practice runs on the revised setup: see `results.md`, label `A-v3`.

## For the user

- Every measurement is still the starter incident. Items 10 to 13 were the reviewer's main
  concern for a different defect; they are reworded but untested on one.
- Build the Gradescope zip with `make_submission.sh`, not a plain `zip -r`.
