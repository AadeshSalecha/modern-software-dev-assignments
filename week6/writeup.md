# Assignment 6 (Writeup)

All numbers are from `python tools/practice.py --keep` on the starter incident, priced from
`rate_card.json`. Per-run summaries and gateway usage logs for every run below are in
`../.reppit/week6-agent-cost-optimization/runs/`, with a combined table in `results.md` there.

## Part I: Baseline

Run the provided `run.sh` on the starter incident (`python tools/practice.py`). Record the result below; add rows if you repeat it.

| Run | Repair | Impact | Cost  | Model requests | Time  |
| --- | ------ | ------ | ----- | -------------- | ----- |
| 1   | 0.44   | 0.57   | $1.26 | 38             | 303 s |
| 2   | 0.44   | 1.00   | $1.21 | 30             | 301 s |
| 3   | 1.00   | 1.00   | $2.02 | 39             | 570 s |

One pass in three, at a mean of $1.50. The pass was the most expensive run: it hit the $2.00 cap (the gateway refused its last requests) and used 570 of the 600 seconds.

**Tokens by kind**, averaged if you ran the baseline more than once:

| Model               | Input | Output | Cache read | Cache write       | Cost  |
| ------------------- | ----- | ------ | ---------- | ----------------- | ----- |
| `claude-sonnet-5-5` | 72    | 50,842 | 3,763,403  | 152,677 (1-hour)  | $1.50 |

**Where did the money go?** Which kind of token dominated, and what in the run produced it:

> Cache writes were the largest share, $0.61 of the $1.50 (41%). Every one was billed at the 1-hour rate ($4.00 per million, not $2.50), because that is the harness default for this login. The first request alone wrote 26,000 tokens of system prompt and tool definitions ($0.10) before any work.
>
> Output was $0.51 (34%): about 50,000 tokens per run at effort high, most of it reasoning and a 170-line log parser written from scratch.
>
> Cache reads were $0.38 (25%). The context grew from 26,000 to 135,000 to 200,000 tokens, and each of the 30 to 39 requests re-read all of it. What filled the context was whole-file `cat`s of the three services and the docs (170,000 to 250,000 characters of tool results per run).
>
> Fresh input was under $0.001. Cost here is context size times number of turns, plus output.

**What did the baseline get wrong?** Record scenarios passed per category and the impact report's precision and recall (averaged if you repeated the run). Then read the transcripts: what did the agent believe, and where did that belief come from?

| Category    | Passed (runs 1, 2, 3) | Mean       |
| ----------- | --------------------- | ---------- |
| incident    | 4/9, 4/9, 9/9         | 5.7 of 9   |
| regressions | 10/10, 10/10, 10/10   | 10 of 10   |
| compat      | 2/2, 2/2, 2/2         | 2 of 2     |

Impact precision and recall: 0.28, 1.00, 1.00 (mean 0.76 each). Totals and `skipped_rows` were exact in all three.

> **The repair.** All three runs found the cause (idempotency keys held only in the api's memory) and fixed it for new requests. Runs 1 and 2 failed the same five incident scenarios, all of which start on the shipped release, let it create repeats, and then replace it with the fix. The agent believed the job was done when new duplicates stopped. Run 1 said so in its summary: "Repeats already sitting in a router's queue at deploy time aren't cancelled, because the router never received their keys." The ticket asks for exactly that ("including those already queued for delivery") and says the release goes to every region.
>
> That belief came from the finish line it was given. `app/CLAUDE.md` and `app/AGENTS.md` are loaded automatically and say the work is done when `bin/evaluate` prints `3 of 3 scenarios pass`. Those three scenarios test none of this. The agent noticed that the two files contradict the contracts on other points and followed the contracts, but it still used `bin/evaluate` as its check. Run 1 added a fourth scenario and noted it "would also pass on the old code, because the harness can't tell a repeat from a new event".
>
> **The report.** Run 1 found the right 33 key groups but named the wrong event of the pair in 19 of them (all `m_maple`). Its first script followed the ticket (earliest accept is the original). Then it saw `event.repeated` lines in the api log pointing at the second event of each pair, and switched. Those lines are the defect itself: after a restart the api's key table is rebuilt from the later request. The agent let a service's log line override the ticket's definition. Totals still matched because both events of a pair carry the same amount.

## Part II: Experiments

One row per change you tried, including the ones you dropped. Try to run each change a few times to check its reliability; report how many runs you made.

| #   | Change | Why you expected it to help | Runs passed / attempted | Avg repair / impact | Avg cost | Kept? |
| --- | ------ | --------------------------- | ----------------------- | ------------------- | -------- | ----- |
| 1   | Harness flags only, same bare-ticket prompt: `--tools Bash,Read,Edit,Write`, `--strict-mcp-config`, `--setting-sources project`, `FORCE_PROMPT_CACHING_5M=1`, `--effort medium` | The first request was 26k tokens of prompt and tool definitions, re-read every turn, and every cache write paid the 1-hour rate | 2 / 3 | 0.81 / 1.00 | $0.53 | Yes |
| 2   | The kit, on top of 1: deterministic prep in `run.sh` (snapshot the release, move unused code to `app/_deprecated/`, replace the stale `app/AGENTS.md` and `CLAUDE.md`, per-service maps, load the evidence into SQLite), root `AGENTS.md`, two skills, a scenario runner that can replace the release mid-scenario, a gate, a stop hook, a workflow prompt | Baseline failures were a wrong finish line and a missed requirement, not missing ability; and most tokens went to exploring and to parsing logs | 6 / 6 | 1.00 / 1.00 | $0.22 | Yes |
| 3   | 2 with the stop hook and the resume switched off | To see whether the hook is doing anything | 3 / 3 | 1.00 / 1.00 | $0.19 | Hook kept (see below) |
| 4   | 2 with `--effort high` | More reasoning might be safer | 3 / 3 | 1.00 / 1.00 | $0.36 | No |
| 5   | 2 with `--effort low` | Cheaper output for mechanical steps | 1 / 3 | 1.00 / 0.82 | $0.16 | No |
| 6   | One sentence added to the report skill: add up each figure over exactly what its sentence names (entries, events and deliveries are different sets) | 5 failed by summing per event where the ticket says per entry | 3 / 3 at medium, 2 / 3 at low | 1.00 / 1.00 at medium, 1.00 / 0.91 at low | $0.22 at medium, $0.19 at low | Yes, at medium |
| 7   | 2 with `claude-haiku-5-5` for the whole session | Small tier is 20x cheaper per token; the kit might carry it | 3 / 3 | 1.00 / 1.00 | $0.07 | Not as the default (320 to 440 s) |
| 8   | 7 with `--effort low` | Make Haiku faster | 2 / 3 | 0.96 / 1.00 | $0.05 | No |
| 9   | 6 with `HOME` set to an empty directory | The grader has an empty home; check nothing leans on my user settings or a warm build cache | 1 / 1 | 1.00 / 1.00 | $0.21 | Check only |
| 10  | Fixes from an independent review of the kit by a second model: a deadline for every step of `run.sh`, a time limit per scenario run, a softer report-shape check, contract checks a scenario may skip, reworded skills | The reviewer found ways an unattended run could overrun or stall, and passages that leaned on the starter ticket | 4 / 5 | 1.00 / 0.91 | $0.21 | Yes, with 11 |
| 11  | Report rule: an id whose defining fact is in no file is left out, never rebuilt from another kind of record. Skipping a contract check is no longer advertised | The failure in 10 filled cut acceptance rows from `event.repeated` lines, the baseline's mistake again; and 4 of 5 agents skipped a contract check they did not need to skip | 5 / 5 | 1.00 / 1.00 | $0.20 | Yes |
| 12  | Split: Haiku writes the report in parallel while Sonnet only repairs | Small model for the mechanical half, and two agents at once | 3 / 3 | 1.00 / 1.00 | $0.20 | No: no saving |
| 13  | Haiku as the main agent, Sonnet only if the gate fails | Escalate only when checks fail | 3 / 3 | 1.00 / 1.00 | $0.09 | No: up to 458 s |
| 14  | Codex with `gpt-6.1-terra` for the whole session, same kit | Medium tier at half Sonnet's price and no charge for cache writes | 5 / 5 | 1.00 / 1.00 | $0.10 | Yes: as the rescue now, as the main agent next |
| 15  | Codex with `gpt-6-luna` for the whole session | 20x cheaper | 0 / 1, then 1 / 2 with row 16 | 0.63 / 1.00 | $0.01 to $0.03 | No |
| 16  | Gate: every scenario the agent writes is also played with the shipped release taking each step up to the last drain and the change only finishing; one prompt sentence that each case the ticket names needs its own scenario; random port choice | Row 15's first run fixed new traffic only, said so in its summary, and still cleared the gate because its own upgrade scenario was weak | 3 / 3 | 1.00 / 1.00 | $0.23 | Yes |
| 17  | Rescue: a failing gate goes to the other harness and family (`gpt-6.1-terra` through Codex) in a new session; if the first session left nothing, the rescue gets the whole job. Run on a second machine with another Claude Code version | One harness or model may not behave in the grader as it does here | 2 / 2, and 2 / 2 with the main model made invalid on purpose | 1.00 / 1.00 | $0.27; $0.10 when the rescue does the job | Yes |
| 18  | Rows 14 and 17 swapped: `gpt-6.1-terra` main, Sonnet rescue | Cheapest setup that has not failed | 2 / 2 | 1.00 / 1.00 | $0.10 | No: after submission 1 the spare money went to a second answer instead (row 21) |
| 19  | After submission 1. Gate that cannot do harm: it blocks only on the build, the services' tests, the shipped scenarios (alone and across a release replacement), the agent's own scenarios on its own tree, changed crash points, and a report that is missing or not JSON. The report's shape, reproduction on the shipped release, the hand-over variant and the ledger are shown once as notes. The rescue is removed | The graded run needed the rescue, which no local run had. Looking for what could block a correct answer, I found that the shape check read a report keyed by ids as a record with the ticket's placeholder key, so every real key was "unexpected" (now a unit test) | Measured with row 21 | | | Yes |
| 20  | Evidence: `attempts` and `leases` tables joined across files, and the clock gap between each pair of files | If the held-out report asks about attempts or about order across unsynchronised files, it should be a query, not parsing | Measured with row 21 | | | Yes |
| 21  | Two solvers at once, each doing the whole job: Sonnet here, a second agent in a copy of the workspace. Then `kit/cross.py`, no model: every scenario of either that fails on the shipped release and passes on its author's repair is run on both repairs, also with the shipped release taking every step up to the last drain; the reports are compared entry by entry. The better repair is installed; a failing run goes back to its author; two different reports go to a new Sonnet session at effort high. `run.sh` prices the sessions' logs and skips the follow-ups past a spending line | Cost had 49 cents of headroom and correctness was the problem. Two independent answers that agree are stronger than one, and where they differ there is something specific to look at | 2 / 2 with Sonnet at effort low as the second (container); 2 / 2 with `gpt-6.1-terra` through Codex as the second (Mac) | 1.00 / 1.00 | $0.42; $0.36 | Yes, with `gpt-6.1-terra` |
| 22  | Row 21 with a weak main solver on purpose (Haiku at effort low) and Sonnet as the second | To see the follow-up for a failing run fire with real models | 2 / 2 | 1.00 / 1.00 | $0.25 | Exercise only |
| 23  | Row 21 with a stand-in second solver that hands in the main solver's report minus three entries, with a script that says why | To make the report decision run with a real model | 1 / 1 | 1.00 / 1.00 | $0.36 | Exercise only |
| 24  | A comparison session after every cross-check, not only when a run fails: the main solver's session is resumed with the other repair as a diff, its ledger and scenarios, lists each case in which the two behave differently and settles each by the ticket and the contracts. `run.sh` keeps the result only if the repair still builds, the gate has not started failing and no more runs fail; otherwise it puts the repair back. The better of the two repairs is chosen after this session, not before. The cross-check also restarts every service before the last drain. One prompt sentence: look for every way into the defect before repairing | In rows 21 to 23, two repairs that passed each other's scenarios were never compared, and that is the usual case. A second repair is a list of decisions the first author did not make | 2 / 2 starter and 2 / 2 second incident with Haiku as the second; then from unpacked zips, 4 / 4 starter with Sonnet at effort low as the second and 4 / 4 second incident (container) | 1.00 / 1.00 | $0.39 and $0.41; from the zips $0.49 and $0.56 | Yes |

Counting every run of the kit on Sonnet at medium effort (rows 2, 3, 6, 9, 10, 11, 16 and 17, and two runs from unpacked copies of the submission zip), 29 of 30 passed on the starter incident. Rows 19 to 24 were made after the first graded run; all 14 starter runs and all 7 runs on the second incident passed.

What the follow-ups did when they ran with real models (rows 22 to 24):

- **Report decision (rows 23 and 24).** In one run of row 24 Haiku's report differed from Sonnet's in 38 of 53 entries: it had taken the original of each pair from the api's `event.repeated` lines, the trap that caught the baseline. The deciding session read both scripts, quoted the ticket's definition ("the first event accepted by the API"), followed one key through the evidence, and kept Sonnet's report. In row 23 it restored the three entries the stand-in had dropped. It cost 14 and 16 cents.
- **Comparison (row 24).** It ran in three of the four runs (in the fourth the second solver was stopped before it had changed anything). Each time it took three turns and 30 to 40 seconds, for 5 to 7 cents. In both starter runs Sonnet changed its own repair after reading Haiku's diff. In one, its message to the router used a type the v3 schema does not allow, and it refused to resend a repeated event, which `delivery.md` allows. In the other, its clean-up of repeats ran only when the api starts, which misses a repeat accepted by a copy of the api that has not been replaced yet; it now runs on every publish. No scenario of either agent had shown any of these, and the starter's judge passes the runs either way. This is the kind of miss a held-out scenario finds. On the second incident it listed three differences, decided each for its own repair by the ticket's wording ("stays in effect whatever older messages arrive afterwards") and changed nothing.
- **Failing run (row 22).** Both repairs failed the hand-over variant of one of Sonnet's scenarios, and Haiku was sent the run. It answered that it could not reproduce it and changed nothing. It could not, because the list named the variant in words and `kit/rollout.py` had no way to play it. The cross-check now saves each failing run as the scenario that was played, with the command that repeats it. In a later run from the zip the main session replayed such a file, saw that its own scenario drained once before the hand-over, so the merchant had already been sent the repeat, and corrected the scenario; the run then failed nothing. In 6 of the 21 runs since submission 1 the main repair failed a cross-check run. Every time it was a hand-over variant, on both repairs, and every one of those runs passed its judge in full: the variant asks for more than either judge does, which is why it is a note and never blocks. So on these two incidents the cross-check has not yet caught a real defect in the main repair. What the 21 runs show is that the added steps cost $0.10 to $0.30 and make nothing worse; whether they catch what one agent misses on a wider incident is what submission 2 tests.

**A second incident.** Every row above is the starter ticket, so before submitting I built a second one to test on: a different defect in the same release (endpoint changes made through the API are ignored after an old-format bus message), with its own ticket, an evidence packet generated by running the shipped release for three simulated days and then applying duplicated batches, late batches, clock skew and 88 cut rows, an expected report computed from what the generator did, and 22 judge scenarios (9 incident, 5 of which start on the shipped release). It is in `../.reppit/week6-agent-cost-optimization/transfer/`, outside `week6/`, so no run can read it. Scored with the assignment's formulas:

| Setup | Runs passed / attempted | Avg repair / impact | Avg cost | Time |
| ----- | ----------------------- | ------------------- | -------- | ---- |
| Baseline `run.sh` | 2 / 2 | 1.00 / 1.00 | $1.31 | 249 to 405 s |
| Kit, Sonnet, before row 16 | 2 / 3 | 0.97 / 1.00 | $0.30 | 136 to 187 s |
| Kit, Sonnet, with row 16 | 3 / 3 | 1.00 / 1.00 | $0.34 | 146 to 234 s |
| Kit, Sonnet with `gpt-6.1-terra` rescue (the submitted default), on the Mac | 1 / 1 | 1.00 / 1.00 | $0.41 | 250 s |
| Kit, `gpt-6.1-terra` (Codex) | 2 / 2 | 1.00 / 1.00 | $0.13 | 183 to 186 s |
| Kit, `gpt-6-luna` (Codex) | 1 / 1 | 1.00 / 1.00 | $0.03 | 481 s |
| Row 21: two solvers (Sonnet, Haiku second) | 1 / 1 | 1.00 / 1.00 | $0.42 | 342 s |
| Row 24: with the comparison session (Sonnet, Haiku second) | 2 / 2 | 1.00 / 1.00 | $0.41 | 252 to 388 s |
| Row 24 from an unpacked zip (Sonnet, Sonnet low second) | 2 / 2 | 1.00 / 1.00 | $0.61 | 230 to 272 s |
| The zip for submission 2, unpacked (Sonnet, Haiku second) | 2 / 2 | 1.00 / 1.00 | $0.50 | 396 to 463 s |

One of the first three Sonnet runs was judged twice: its live score was 0.89 because another run on the same machine held a port a service needed; judged again from its saved diff it passes. The run that did fail (repair 0.92) broke one case the ticket names, an old-format message switching off an endpoint that exists only in the archive: it had a scenario for archive-only endpoints, but not for that case. The baseline passes this ticket, which spells out its recovery requirement, so here the kit's gain is cost (about three quarters less), not correctness.

**The change that fixed the most failing categories**, and why it worked:

> The kit (row 2) took the incident category from 4 of 9 in most baseline runs to 9 of 9 in every run. I did not ablate its parts one by one, except the hook, so I can say what the transcripts show and not which single piece is responsible.
>
> The agent now starts from a root `AGENTS.md` that says how the system runs in production: one release replaces the running one in every region, each service keeps its store, and a repair has to be right for new traffic, for state the shipped release already wrote, and for older bus messages. The prompt asks for a scenario that fails on the shipped release and one that replaces the release part-way, and `kit/rollout.py` makes that a one-line step (`{"do": "upgrade"}`) with a few lines of output. In all 13 Sonnet runs the agent wrote such a scenario and ran it against the shipped release before repairing. In the transcripts I read in full it then added a step in the api, at start-up or at publish time, that finds repeats already in its store and tells the router to cancel their deliveries. That is the piece the baseline skipped.
>
> Two smaller things removed the baseline's wrong beliefs. `run.sh` moves the stale `app/AGENTS.md` and `app/CLAUDE.md` out before the agent starts, so nothing says "done at 3 of 3". And the runner adds an expectation that counts what an endpoint received in total, which the shipped harness cannot express; that was the limit the baseline agent ran into when it tried to test its own fix.
>
> Row 3 shows the stop hook is not what did it: with the hook off the result is the same, and with it on it never had to block. The agent runs the gate itself because the prompt tells it to.

**The change that saved the most money**, and why it worked:

> The harness flags (row 1): $1.50 to $0.53, about 65%, with the prompt unchanged. Restricting the tool list to four and loading no MCP servers cut the first request from 26,000 to 6,000 tokens, which is paid again as a cache read on every later turn. Forcing the 5-minute cache made every write $2.50 per million; the baseline paid $4.00. Medium effort cut output from about 51,000 to about 21,000 tokens.
>
> The kit then took $0.53 to $0.22. Requests fell from 27 to 12 and the largest context from about 78,000 to about 43,000 tokens, because the agent no longer explores (it has a map with line numbers), never reads raw logs (it queries `work/evidence.db`, and its report script is 20 lines), and gets a few lines back from each test run where `bin/evaluate` prints thousands.

**A change that did not work**, and what it showed you:

> Low effort (row 5). It saved five cents a run and broke the report in 3 of 6 runs across rows 5 and 6. The affected list was exact every time; the totals were wrong, because the agent summed each event once where the ticket says to sum over entries, and an event delivered to two endpoints is two entries. The repair was right in all six. So the cheap setting fails on careful reading of one sentence, which is the part of this task where being almost right scores worst. The sentence I added to the skill (row 6) may have helped, but 2 of 3 against 1 of 3 is not evidence, and I would not ship a setting that needs a hint to read the ticket.
>
> Haiku at low effort (row 8) failed differently: one run left a delivery that was mid-send during the release replacement to be retried. High effort (row 4) worked but cost 60% more for the same result.
>
> Splitting the report off to a small model (row 12) is the idea I most expected to pay and it saved nothing. Once the evidence is in a database the report costs Sonnet about two cents; a second session has to pay its own prompt and read its own context, which cancels that. Decomposition helps when the split-off part is expensive, and the kit had already made this one cheap.
>
> One fix from the review made things worse before it made them better (rows 10 and 11). The reviewer asked for a way to skip a contract check when a ticket overrides the contract. Four of five agents used it at once, on a check they were not failing. An escape hatch that is advertised gets used; it is now mentioned only in the failure message of the check it skips.

**Your final setup.** What `run.sh` does, step by step, and which model handles each step:

> This is the setup of submission 2. Submission 1 was steps 1, 2 (one solver), an older gate, and a rescue; what changed and why is in Part III.
>
> `./run.sh task.md`, with nothing in the environment, does this:
>
> 1. **Prep, no model** (`kit/prepare.sh`, a few seconds). Copies `app/services`, `app/bin` and `app/scenarios` to `.pristine/` as the release as shipped. Moves `sdk/`, `legacy/`, `services/router-next/` and `deploy/helm/` into `app/_deprecated/` with a short README, and checks the shipped scenarios still pass. Replaces `app/AGENTS.md` and `app/CLAUDE.md` with a short note and writes an `AGENTS.md` into each service with a line-numbered map made from the tree as it is. Loads `incident/` into `work/evidence.db` with `kit/evidence.py`, which applies `contracts/evidence.md` and nothing else: cut rows counted and skipped, resent lines collapsed, cut ids resolved, amounts in minor units; `events`, `deliveries`, `attempts`, `leases` and `responses` joined across files, and the clock gap between each pair of files.
> 2. **Two solvers at the same time, each doing the whole job on its own.** The main one is a Claude Code session on `claude-sonnet-5-5`, effort medium, in this folder. The second is a Codex session on `gpt-6.1-terra`, effort medium, in a copy of the workspace under `/tmp`. Same prompt, same `AGENTS.md`, same skills and tools; a different harness and a different model family on purpose. The Claude session has four tools, no MCP, project settings only and the 5-minute cache. The prompt is a fixed five-step workflow, then the prep notes and the evidence schema, then the ticket. Both are stopped at 300 seconds; the second gets at most two minutes after the first has finished.
> 3. **Gate, inside each session** (`kit/check.sh`, also run by a stop hook in the Claude session). It blocks only on what it can be sure of: the build, each service's tests, the shipped scenarios alone and with the release replaced after each step, the agent's own scenarios on its own tree, changed crash points, and a report that is missing or not JSON. Everything it cannot be sure of (a scenario that does not fail on the shipped release, the hand-over and restart variants, the report's shape against the ticket's example, the ledger) is shown once as a note and never blocks.
> 4. **Cross-check, no model** (`kit/cross.py`, about 10 to 30 seconds). Every scenario either solver wrote that fails on the shipped release and passes on its author's repair is run on both repairs: as written, with the shipped release taking every step up to the last drain, and with every service restarted before the last drain. The shipped scenarios are run on both, alone and across a release replacement. The repair with fewer failures is the better one (a tie goes to the main solver), and that is decided after step 5. The two reports are compared entry by entry.
> 5. **Comparison session: the main solver's Sonnet session, resumed.** It gets the other repair as a diff, the other ledger and scenarios, and the runs its own repair fails, each as a scenario file it can replay. It lists each case in which the two repairs behave differently and settles each by the ticket and the contracts, writing a scenario before it changes code. `run.sh` keeps the result only if the repair still builds, the gate has not started failing and it fails no more runs than before; otherwise the repair goes back to how it was. Then the cross-check picks the better of the two repairs again.
> 6. **Report decision: a new Claude Code session on `claude-sonnet-5-5`, effort high**, only if the two reports differ. It gets both reports, both scripts and the list of differences, and decides each difference by the ticket's wording, checking two or three ids in the evidence. If what it leaves is not valid JSON, the main solver's report is put back. Steps 5 and 6 run side by side.
> 7. **Install and restore, no model.** The better repair ends up in `app/services` (the second solver's is copied in if it won), the decided report in `out/`. The set-aside directories are moved back and the installed notes removed, so `app/` differs from the release only by the repair. This also runs if `run.sh` is stopped by a signal.
>
> After step 2 the folder already holds a complete answer, and every later step replaces a part of it only when the replacement checks out. `run.sh` adds up what the sessions have cost from their own logs and `rate_card.json` (`kit/spend.py`; it matched the gateway's figure to within half a cent in every run I compared) and skips step 5 above $0.64 and step 6 above $0.70. The lines differ because the stakes do: a comparison costs 5 to 7 cents and may find nothing, while two different reports mean one of them is wrong, and a wrong report costs more points than fifteen cents over the cost line. If a harness exits within 20 seconds with an error, it is run again with only the flags the assignment guarantees. Every step has a deadline counted from the start, and everything is finished by 570 seconds.

**Final setup on the starter incident.** Record your results; add rows for repeated runs. Briefly explain any variation you observed.

The setup of submission 1 (one Sonnet session, the first gate, a rescue):

| Run | Repair | Impact | Cost  |
| --- | ------ | ------ | ----- |
| 1   | 1.00   | 1.00   | $0.24 |
| 2   | 1.00   | 1.00   | $0.21 |
| 3   | 1.00   | 1.00   | $0.24 |
| 4   | 1.00   | 1.00   | $0.25 |
| 5   | 1.00   | 1.00   | $0.24 |
| 6   | 1.00   | 1.00   | $0.31 |
| 7   | 1.00   | 1.00   | $0.24 |

> Runs 1 to 3 are row 16 in the cloud container (Claude Code 2.1.332); run 4 was started from an unpacked copy of the submission zip; runs 5 and 6 are row 17 on my Mac (Claude Code 2.1.284); run 7 is the zip I uploaded first, unpacked and run on the Mac with nothing set. Time ranged from 95 to 173 seconds. The spread follows the number of requests (11 to 17): some runs read one more file or run the gate once more, and the older Claude Code on the Mac took a few more turns for the same work. No run needed the stop hook or the rescue. In the 13 transcripts of rows 2 to 9 that I checked, the ledger the prompt asks for first was written last in 8, so it works as a final checklist, not as a plan.

The final setup (submission 2: two solvers, cross-check, comparison, report decision):

| Run | Second solver | Follow-ups that ran | Repair | Impact | Cost  | Time  |
| --- | ------------- | ------------------- | ------ | ------ | ----- | ----- |
| 8   | `gpt-6.1-terra` (Mac) | none needed | 1.00 | 1.00 | $0.33 | 168 s |
| 9   | `gpt-6.1-terra` (Mac) | none needed | 1.00 | 1.00 | $0.39 | 191 s |
| 10  | Haiku (container) | comparison and report decision | 1.00 | 1.00 | $0.47 | 308 s |
| 11  | Haiku (container) | comparison | 1.00 | 1.00 | $0.31 | 290 s |
| 12  | none: a zip unpacked in the container, which has no Codex | none | 1.00 | 1.00 | $0.24 | 113 s |
| 13  | Sonnet at effort low: the zip for submission 2, unpacked (container) | comparison | 1.00 | 1.00 | $0.55 | 195 s |
| 14  | Sonnet at effort low: the same zip | comparison | 1.00 | 1.00 | $0.47 | 186 s |

> Runs 8 and 9 are the pairing that is submitted, at the commit before the comparison session became unconditional: the two repairs passed each other's scenarios and the reports were identical, so no follow-up ran. Runs 10, 11, 13 and 14 have every step, with a Claude model standing in for `gpt-6.1-terra` because the container has no Codex login. Run 12 is a zip with nothing set; Codex is missing there, the second solver exits at once, and the run goes on with the main solver alone. The submitted pairing has not run with the comparison session (the Mac that has the Codex login was asleep); from the parts I expect $0.35 to $0.60: Sonnet $0.21 to $0.29, terra $0.09 to $0.10, the comparison 4 to 7 cents, the report decision 14 to 16 cents when the reports differ.
>
> Cost now follows which follow-ups run and what the second solver costs: Sonnet at effort low costs $0.19 to $0.26 as the second, twice what terra does, which is why runs 13 and 14 are the dearest. Time follows the slower solver: Haiku needed all the time it was given, terra finishes about a minute after Sonnet. The second incident behaved the same way: $0.30 with no follow-up, $0.48 to $0.62 with the comparison, and up to 463 seconds when the second solver used all of its time.

**What will transfer?** The held-out task is a different incident in Switchyard. Which parts of your setup are about how to work in this repository and its evidence, and which might only have helped with duplicate events:

> **About the repository and its evidence, so I expect them to carry over.** The harness flags and their saving. The trust order, and moving the stale agent files out of the way. The evidence loader: it implements the evidence contract, keeps every field it finds, and knows nothing about any incident. The scenario runner, its contract checks (nothing left queued, delivered only with a 2xx, one first delivery per event and endpoint, valid signatures) and the shipped scenarios replayed across a release replacement, which would catch a fix that cannot open an old store whatever the defect. The gate's report check, which reads the shape from the ticket's own example.
>
> **Shaped by this incident, so they may help less.** Nothing in the setup names duplicate payments or idempotency keys, but I built it after watching the baseline fail here, and three choices follow from that. The weight on "state the shipped release left behind" pays off when a defect leaves bad records in a store; for a defect with no such state it adds a scenario to write and little else. The endpoint-level expectation was added because this incident's symptom could not be expressed per event. The rule that a service's log line never overrides the ticket's definition comes from the `event.repeated` trap; it is true in general, but I only know it mattered once.
>
> **What the second incident showed.** The report carried over completely: every kit run on it, 10 of 10 across three models, produced an exact report for a question of a different shape, including the corrupted-row count. The repair carried over mostly: Sonnet passed 6 of 7 and the miss was one named case without its own scenario, which is what row 16's prompt sentence is for. Cost carried over roughly as a ratio, not as a number: a sixth of the baseline here and a quarter there, $0.23 against $0.34, because the harder ticket takes more turns. Nothing in the kit had to change to run it.
>
> **What I still cannot know.** I wrote the second incident, with the same model family that runs the setup, so it shares my idea of what an incident in this repository looks like. The held-out one may not. One graded run will not tell me much either way: a setup that passes 29 of 30 can fail once.
>
> **After the first graded run** (Part III) I changed what I count on. The held-out incident has 17 incident scenarios where the starter has 9, and a setup that passed both of my incidents nearly every time got 12 of them and an impact score of 0.11. So "it passes locally" says little about a wider incident, and the parts added since are the ones that do not depend on having seen the incident: a second answer from another model family, a mechanical comparison of the two, and a gate that can no longer block a correct answer.

## Part III: Graded Submissions

Upload a zip of your `week6/` folder to the **Assignment 6 (Autograder)** assignment on Gradescope (up to 3 submissions, one run each) and report your autograder scores.

| Submission (up to 3, one run each) | Repair | Impact | Passed? | Cost | What you changed before it |
| ---------------------------------- | ------ | ------ | ------- | ---- | -------------------------- |
| 1                                  | 0.71 (incident 12/17, regressions 51/51, compat 8/8) | 0.11 | No | $0.2603 (Sonnet $0.2413, terra $0.0190; 24 requests, 158.5 s) | n/a |
| 2                                  | TODO   | TODO   | TODO    | TODO | Rows 19 to 24: a gate that blocks only on objective failures (and no rescue), attempt and lease tables in the evidence, two solvers at once (Sonnet, and `gpt-6.1-terra` through Codex in a copy of the workspace), a mechanical cross-check of the two repairs and the two reports, a comparison session for the better repair, a report decision when the reports differ, and a spending line in `run.sh` |
| 3                                  | TODO   | TODO   | TODO    | TODO | TODO                       |

**Starter incident versus held-out incident.** Did repair, impact and cost carry over? If not, give your best explanation, accounting for each submission having only one graded run:

> **Submission 1.** Cost carried over: $0.26 against $0.21 to $0.31 on the starter, full marks for cost. Correctness did not: repair 0.71 and impact 0.11, where 29 of 30 starter runs and 6 of 7 runs on my second incident passed in full. One run cannot give a rate, but it does show three things.
>
> The rescue ran (the second model made 3 requests), so the gate was still failing after the Sonnet session. That happened in no local run on either incident. Sonnet made 21 requests for a normal amount of output, about eight short turns more than usual, which is what being sent back by the stop hook looks like. The rescue then wrote 430 tokens and stopped.
>
> An impact of 0.11 is an F1 near zero. A definition read slightly wrong gives partial overlap (the baseline's wrong run still scored 0.28), so the entries were wrong as a set or the file's shape was. Looking for what in my setup could do that to a correct report, I found one thing and could reproduce it: the gate compared the report's keys with the ticket's example and blocked on any difference, and it read an object keyed by ids as a record with the example's placeholder key, so every real key was "unexpected". The starter's report has no object keyed by ids, so this never fired locally. I cannot see the held-out ticket, so I cannot show that this is what happened; it fits the extra turns, the failing gate and the score.
>
> The repair passed every regression and compatibility scenario and 12 of 17 incident scenarios: the cause was found and part of what the ticket asked for was missed. The starter has 9 incident scenarios, so the held-out incident covers more cases, and one agent's own scenarios did not reach five of them.
>
> What I took from it: the setup was tuned to pass where I could measure, at a quarter of the allowed cost, and its one blocking judgement about the report was a guess about tickets I had not seen. Submission 2 spends the unused budget on a second independent answer and on comparing the two, and nothing in it blocks on a guess.
>
> **Submission 2.** TODO after the run.

## Submission

1. `Command (⌘) + F` for `TODO`. No results means you're done. Delete rows you did not need.
2. Push all changes to your remote repository and submit the repository link to the **Assignment 6 (Writeup)** assignment on Gradescope. You can resubmit it as often as you like; your `week6/` folder goes to the separate **Assignment 6 (Autograder)** assignment (up to 3 submissions).
