A second engineer worked on the same ticket on their own, without seeing your work. Their
scenarios were then run on your repair and yours on theirs. Before anything is handed in,
use their work to find what your repair still misses. Nobody will answer questions.

In `work/cross/` you now have:

- `other.diff`: their change to `app/services`, as a diff against the shipped release.
- `other-ledger.md`: their list of the ticket's requirements.
- `other-scenarios/`: their scenarios. Each fails on the shipped release and passes on
  their repair.

Work in this order.

1. **Failing runs**, listed at the end of this message. Each comes with the scenario
   exactly as it was played (`work/cross/run-<n>.json`): run that file first and see it
   fail. For each failing run: if it shows a
   requirement of the ticket or a rule in `app/contracts` that your repair misses, change
   your repair until it passes. "Handed over before the last drain" means the shipped
   release took every step up to the last drain and your change only finished: what the
   shipped release left behind has to be dealt with by your change. "Every service restarted
   before the last drain" means what your change kept only in a process's memory was lost:
   keep it in the service's store. If a run asks for something that neither the ticket nor
   a contract requires, leave your repair as it is and name the sentence you rely on.
2. **Differences.** Read `other.diff` next to your own change. Under a heading
   `## Compared` in `work/ledger.md`, write one line for each case in which the two repairs
   behave differently: a case one of them handles and the other does not (an older message
   version, state the shipped release left behind, a restart or a second copy of a service,
   a retry or a resend, an endpoint or an event in another state, another way into the same
   defect), or a different outcome for the same case. Add any requirement that is in
   `other-ledger.md` and not in your ledger. Where the two agree, write nothing.
3. **Decide each line** by the ticket and `app/contracts`, read literally, and quote the
   sentence that decides it. Where their behaviour is what the text requires, first write a
   scenario in `work/scenarios/` that shows it (it fails on your repair as it is now), then
   change your repair until it passes. Where yours is what the text requires, or the text
   requires neither, change nothing. More code is not a better repair: every added line can
   break something that works today, so never take over their change wholesale.
4. Run `bash kit/check.sh --only repair` and fix what it reports.

Do not edit their scenarios, and leave `out/` alone: the reports are compared separately.
Finish in at most eight lines: each difference, which behaviour is right, and the sentence
that decides it.

If you have no memory of this work: the ticket is in `task.md`, `AGENTS.md` describes the
workspace, your notes are in `work/ledger.md`, your scenarios in `work/scenarios/`, and your
change is in `app/services` (compare with `.pristine/app/services`).

Failing runs:

