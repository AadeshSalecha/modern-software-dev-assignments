# Plan v2: spend more, be right (after graded submission 1)

Written 2026-11-26 after the first graded run. Two submissions remain.

## What the graded run told us

| | Starter (ours, 7 runs) | Held-out, submission 1 |
|---|---|---|
| Repair | 1.00 | 0.71 (incident 12/17, regressions 51/51, compat 8/8) |
| Impact | 1.00 | 0.11 |
| Cost | $0.21 to $0.31 | $0.2603 (Sonnet $0.2413, terra $0.0190) |
| Requests | 11 to 17 | 24 (Sonnet 21, terra 3) |
| Time | 95 to 173 s | 158.5 s |
| Points | | correctness 17.12/35, cost 35/35 |

Facts:
- The rescue ran, so `kit/check.sh` was still failing after the Sonnet session. That never
  happened in any local run on either incident.
- Sonnet made 21 requests with a normal amount of output (9.3k tokens) and normal cache writes
  (39k): about eight extra short turns, which is what stop-hook blocks look like.
- terra made 3 requests and wrote 430 output tokens: two quick tool calls, then it stopped.
- Impact 0.11 means an F1 near zero. A slightly wrong definition gives partial overlap (the
  baseline's 0.28); near zero means the entries were systematically wrong or the report was
  overwritten.

Suspects, none verifiable from here:
1. **The gate did harm.** The report-shape check blocks on keys and nesting against the
   ticket's example. A report keyed by ids (a map of records or lists) is read as a record with
   the example's placeholder key, so every real key is "unexpected". That would block the stop
   hook four times on a correct report, and hand the rescue a "fix" that destroys it.
2. **The rescue took an easy exit.** Soft checks say "if …, say so in the ledger"; a rescue
   can clear the gate with one line and no repair.
3. **The repair was incomplete** in the way the starter baseline was (a class of incident
   scenarios, 5 of 17).
4. A report question the evidence views do not make easy (attempt-level or time-across-files).

## Direction (user): spend more, run longer, do a better job

Budget: full cost credit up to $0.75 (we used $0.26); 600 s (we used 158 s).

## Design

1. **Gate that cannot do harm.** Only objective failures block: build, a service's own tests,
   shipped scenarios (alone and across a replacement), the agent's own scenarios on its own
   tree, report file missing or not JSON. Report shape is a note, shown once, never a block,
   and placeholder-keyed objects are treated as maps. Soft checks (reproduce, hand-over) are
   asked once and offer no "write a line in the ledger" exit.
2. **Evidence at the level of attempts and leases, with clock offsets.** New joined tables so
   that attempt-level and time-across-files questions are queries, not parsing.
3. **Two independent solvers, different families, in separate workspaces.** A: Sonnet in the
   main workspace. B: `gpt-6.1-terra` (Codex) in a clone (`.b/`). Each does the whole job.
4. **Cross-validation, no model.** Every validated scenario from either solver (fails on the
   shipped release, passes on its author's repair), plus the hand-over variants, is run on both
   repairs. Reports are compared entry by entry.
5. **Adjudication.** Repairs: the candidate that passes more of the union is chosen; its author
   gets the scenarios it fails ("make it pass, or quote the ticket sentence that says it need
   not"). Reports: if they differ, a fresh high-effort session gets both scripts and the list
   of differences and decides sentence by sentence.
6. **Fail-safe.** The main workspace is a complete answer after step 3. Later steps replace an
   artifact only when the replacement checks out; candidates are kept.
7. **Spend governor.** `run.sh` adds up tokens from the harness logs with `rate_card.json` and
   skips optional steps past a spend or time line.

## Steps

| # | Step | Done when |
|---|---|---|
| 1 | Gate v2 | Unit tests; a map-of-records example no longer blocks |
| 2 | Evidence: attempts, leases, clock offsets | Tests on synthetic packet; starter and INC-2231 reports still derivable |
| 3 | Clone workspace, second solver, cross-validation tool | Dry run with stand-in harnesses |
| 4 | Adjudication prompts, spend governor | Dry run; governor skips when over |
| 5 | Local runs with two Claude solvers | Starter and INC-2231 pass 3 of 3 each |
| 6 | Mac runs with Sonnet + terra | Same, with cost under $0.75 |
| 7 | Zip, hand to user for submission 2 | |

## Out of scope

Anything that needs to know the held-out ticket. We only get category counts back.
