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

## Status (end of 2026-11-26)

Steps 1 to 5 and 7 are done; step 6 is half done.

- Built as planned, with three changes found while testing with real models:
  - The comparison session runs after every cross-check, not only when a run fails, and it is
    always the main solver's session resumed. The better repair is chosen after it.
  - A failing run is handed over as the scenario that was played (`work/cross/run-<n>.json`).
    Named only in words, the author could not replay it and reported "cannot reproduce".
  - The cross-check also restarts every service before the last drain.
- Since submission 1: 14 of 14 starter runs and 7 of 7 runs on INC-2231 pass. Cost $0.24 to
  $0.62, time 113 to 463 s. `results.md` has every run.
- Step 6: Sonnet + `gpt-6.1-terra` ran twice on the Mac (pass, $0.33 and $0.39) before the
  comparison session was unconditional. It has not run since: the Mac went to sleep. Every
  step has run with real models, with a Claude model as the second solver.
- What the runs do not show: in 6 of 21 runs the main repair failed a cross-check run, each
  time a hand-over variant, and each of those runs passed its judge. On these two incidents
  the mechanical cross-check has not caught a real defect. The comparison session ran in 10
  runs and changed the main repair in 7, for reasons a judge might test (a message type
  outside the v3 schema, a clean-up that ran only at start-up, and on INC-2231 a disable from
  the archive that would have been lost, which is the case the one failing Sonnet run had
  missed).

## Status (2026-11-27): budget awareness and a wider test

Asked for after the Mac check: a harness that knows its budget and decides from it whether to
spend more effort and time, and an answer to where the held-out failures could be.

- **Mac check of the zip of 2026-11-26** (commit 51ef415, Sonnet + `gpt-6.1-terra`): starter
  2 of 2 ($0.43, $0.51), INC-2231 1 of 1 ($0.56).
- **What the first submission's gate says about the graded run.** Unticked ledger lines and the
  agent's own failing scenarios were blocking then. The session was let go after four blocks at
  158 s and $0.26; the rescue did nothing. Most likely the agent knew it was not finished.
- **Budget awareness** (commits 77a8706, 7bfe15c, 0e0854c): `kit/budget.py`; stop-hook
  messages that persist on failing checks and on the agent's own open items while money and
  time remain; follow-ups at effort high when affordable (resuming at another effort keeps the
  cache, measured); a finish session when the gate still fails; a budget stop for the second
  solver. Run estimate fixed for sessions still running and for Codex sessions cut off.
- **Cross-check, found with the real pairing:** the second solver's repair was installed twice
  on failure counts (a private bus message type; a cut-off session one failure ahead). Now the
  main repair stands unless the other is objectively better.
- **A wider test.** An audit of the release reproduced nine latent defects. Two became
  incidents: INC-2307 (a resend that is accepted and does nothing) and INC-2318 (events lost
  when an endpoint is off for more than a day), each with ticket, generated packet, judge (19
  incident scenarios) and reference repair. The first submission's setup passes 1 run in 4 on
  them; the zip of 2026-11-26 passes 2 in 4 with a stand-in second solver.
- **What the wider test found in the kit:** the report skill told the agent to leave out an id
  whose defining row was cut and never to rebuild it from another kind of record. On INC-2307
  that loses 7 of 35 entries every time (0 of 3 report-only runs right). Rewritten: 11 of 11
  right across four incidents.
- **Final commit 0e0854c, real pairing on the Mac:** starter $0.44, INC-2231 $0.65, INC-2307
  $0.54, INC-2318 $0.69, all passing, 314 to 385 s. The zip for submission 2 is built from it.
- **Not measured:** which of the budget rules earns its cost. They are measured for doing no
  harm and for price. Seven audit defects are not built into incidents (one needs a second
  worker, which the harness cannot start).

## Status after the second graded run (2026-11-27, later)

Submission 2: repair 0.71 (12 of 17), impact 0.11, $0.39, 177.5 s. The same scores as
submission 1, and no request to `gpt-6.1-terra`: the run was one Sonnet session.

- **Why the second solver did not run.** A graded run is another, unprivileged account with an
  emptied environment (`tools/runner.py`). `make_copy` gave up on the first file it could not
  read and `run.sh` went on alone. Reproduced with one unreadable folder under `app/`. Not
  proven to be what happened on the grader; the other candidate is Codex failing to start in
  the copy. Both are now handled (tolerant copy, checked; fallback sessions).
- **Why the same score twice.** Systematic for one Sonnet session with this kit on that
  incident. Ruled out by experiment: terse wording of the recovery requirement (6 of 6 pass),
  the Python version (3.8 to 3.13 identical), running unprivileged with no environment.
  Not reproduced locally.
- **Literature** (survey by a research agent, sources in the conversation, several 2026 items
  are preprints): selection is the bottleneck, different families cover more than resamples,
  execution beats voting and LLM judging, agent-written tests are weak evidence, judges are
  for triage. Consistent with: two or three different attempts, chosen by execution.
- **Built (commits 92c089b, e75500d, e0b42c6):** tolerant copy and fallbacks; a third session
  that derives the report from the raw files without the kit's database or skills; reports
  settled part by part; the second repair taken when it dominates in the cross matrix.
- **Measured:** the raw-file report with Sonnet has entries and totals right in 7 of 7 runs on
  four incidents and `skipped_rows` wrong in 3; Haiku rarely finishes it; `gpt-6-luna` is near
  but not exact. Full runs with Claude stand-ins: 7 of 7 pass, $0.37 to $0.71. Real pairing on
  the Mac at 92c089b: starter $0.66, INC-2307 $0.63, both pass.
- **Final validation (commit 9ec5cb1, the files of the zip for submission 3, nothing set),**
  each incident once in both places:

  | Incident | Mac: Sonnet, `gpt-6.1-terra` twice | Container: no Codex, fallbacks |
  | --- | --- | --- |
  | starter | pass, $0.58, 399 s | pass, $0.44, 246 s |
  | INC-2231 | pass, $0.70, 311 s | pass, $0.49, 130 s |
  | INC-2307 | pass, $0.73, 320 s | pass, $0.77, 314 s |
  | INC-2318 | pass, $0.81, 332 s | pass, $0.77, 318 s |

  8 of 8 pass. The fallback path ran with real models for the first time (`codex` exits 127,
  `run.sh` says so and starts Haiku and Sonnet low). Three runs are over $0.75 by 2 to 6
  cents (1 to 3 cost points). The main solver is the cost: 47 to 64 cents on the two larger
  incidents, so the comparison ($0.60 line) and a report decision ($0.70 line) do not start
  there, and the extra sessions count through selection alone. Left as it is: a money stop
  for the main solver would cut it while it is still working, and on the held-out incident
  the Sonnet session cost $0.24 and $0.39 in the two graded runs.
- **One Gradescope submission is left.** The zip is built and unchanged since e0b42c6.

## Out of scope

Anything that needs to know the held-out ticket. We only get category counts back.
