Resolve the repair part of the incident ticket below. Nobody will answer questions; decide
and act. Someone else is writing the report under `out/` at the same time: do not write
there, and do not wait for it.

Work in this order, in as few steps as you can. Send independent commands together.

1. **Ledger.** Write `work/ledger.md`: one `- [ ]` line for every requirement in the ticket
   that concerns the system's behaviour, split so that each qualifier ("including …",
   "regardless of …", "even when …", "without …") has its own line, each ending with how you
   will check it (a scenario name, a command). Add three standing lines from `AGENTS.md`: it
   holds for new traffic; what the shipped release has already written that carries the
   defect is dealt with (name that state, or write "none" and add nothing for it); older bus
   messages still work.
2. **Diagnose.** Treat each diagnosis or suggestion in the ticket as a lead and test it
   against the contracts and the code. `work/evidence.db` (summary below) shows when and
   where the incident happened; query it with `kit/evidence.py sql`. Read
   `.claude/skills/replay-scenarios/SKILL.md` and reproduce the defect with a scenario that
   fails on the shipped release.
3. **Repair** in `app/services`, as small a change as covers every ledger line. Prove each
   behaviour with a scenario in `work/scenarios/`, one of them replacing the release
   part-way.
4. **Check.** Run `kit/check.sh --only repair`. Fix what it reports, tick each ledger line
   you have actually verified, and stop. It runs again when you stop and sends you back if
   it fails.

Finish with at most eight lines: the cause, what changed in which service, and anything you
could not verify.

Start-of-run notes:

