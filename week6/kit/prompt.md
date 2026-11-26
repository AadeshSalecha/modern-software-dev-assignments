Resolve the incident ticket below. Nobody will answer questions; decide and act.

Work in this order, in as few steps as you can. Send independent commands together.

1. **Ledger.** Write `work/ledger.md`: one `- [ ]` line for every requirement in the ticket,
   split so that each qualifier ("including …", "regardless of …", "even when …",
   "without …") has its own line, each ending with how you will check it (a scenario name, a
   query, a command). Add three standing lines from `AGENTS.md`: it holds for new traffic;
   what the shipped release has already written that carries the defect is dealt with (name
   that state, or write "none" and add nothing for it); older bus messages still work.
2. **Report.** Read `.claude/skills/evidence-report/SKILL.md`, then answer the ticket's
   report request from `work/evidence.db` with a script, and write the file under `out/`
   now. What you learn here about when and where the incident happened is your first lead.
3. **Diagnose.** Treat each diagnosis or suggestion in the ticket as a lead and test it
   against the contracts and the code. Read `.claude/skills/replay-scenarios/SKILL.md` and
   reproduce the defect with a scenario that fails on the shipped release. Then, before you
   repair anything, look for every other way into the same defect: the same decision is
   usually made in more than one place (in another service, once per bus message version,
   again on a retry, a resend, an expired lease or a restart). Add a ledger line for each
   way in that the ticket's wording covers; the first one you found is rarely the only one.
4. **Repair** in `app/services`, as small a change as covers every ledger line. Prove each
   behaviour with a scenario in `work/scenarios/`, one of them replacing the release
   part-way. `kit/check.sh` passing shows only what the shipped scenarios cover: every case
   the ticket names, each "including …" on its own, needs a scenario that exercises exactly
   that case. A requirement you could not meet is a failed job, not a note for the summary.
5. **Check.** Run `kit/check.sh`. Fix what it reports, tick each ledger line you have
   actually verified, and stop. It runs again when you stop and sends you back if it fails.

Finish with at most eight lines: the cause, what changed in which service, and anything you
could not verify.

Start-of-run notes:

