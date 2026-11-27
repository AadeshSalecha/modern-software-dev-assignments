Before your repair is handed in it gets one more pass, by you, on what it has not been tested
for. Nobody will answer questions. No second engineer's work is available in this run, so
this pass is the only check your repair gets beyond your own first one.

Work in this order.

1. **Failing runs**, listed at the end of this message (there may be none). Each is one of
   your own scenarios played another way, saved exactly as it was played
   (`work/cross/run-<n>.json`): run that file first and see it fail. "Handed over before the
   last drain" means the shipped release took every step up to the last drain and your
   change only finished: what the shipped release left behind has to be dealt with by your
   change. "Every service restarted before the last drain" means what your change kept only
   in a process's memory was lost: keep it in the service's store. If the run shows a
   requirement of the ticket or a rule in `app/contracts` that your repair misses, change
   your repair until it passes. If it asks for something neither requires (what the outcome
   needs is no longer in any store, or the harm was complete before your change started),
   leave the repair as it is and name the sentence you rely on.
2. **Stages.** List `work/scenarios/` and read step 3 of
   `.claude/skills/replay-scenarios/SKILL.md` again. For each stage of work the shipped
   release can hold at the moment it is replaced, name your scenario that replaces it in
   that stage. Write and run the ones that are missing, expecting what the merchant gets in
   total. One of them holds two or three affected objects and one that the shipped release
   handled correctly.
3. **Ticked on reasoning.** Go through `work/ledger.md`. For every line ticked without a
   scenario or a query that ran (the same code path, a restart or a crash point, an older
   bus version, a second copy of a service), write the scenario and run it, or point to the
   lines that make it hold whichever copy runs.
4. Run `bash kit/check.sh --only repair` and fix what it reports.

Change code only where a run fails: more code is not a better repair. Leave `out/` alone.
Finish in at most eight lines: what you ran, what failed, what you changed.

If you have no memory of this work: the ticket is in `task.md`, `AGENTS.md` describes the
workspace, your notes are in `work/ledger.md`, your scenarios in `work/scenarios/`, and your
change is in `app/services` (compare with `.pristine/app/services`).

Failing runs:
