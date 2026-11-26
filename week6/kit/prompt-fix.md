A second engineer worked on the same ticket on their own. Their scenarios were then run on
your repair, and yours on theirs. The runs listed below fail on your repair. Every one of
these scenarios fails on the shipped release and passes on its author's repair, so each
shows something a repair of this ticket can do.

Files named `work/cross/…` are the other engineer's scenarios, copied into your workspace.
For each failing run:

- If it shows a requirement of the ticket or a rule in `app/contracts` that your repair
  misses, change your repair until it passes. "Handed over before the last drain" means the
  shipped release took every step up to the last drain and your change only finished: what
  the shipped release left behind has to be dealt with by your change. "Every service
  restarted before the last drain" means what your change kept only in a process's memory
  was lost: keep it in the service's store.
- If it asks for something that neither the ticket nor a contract requires, leave your
  repair as it is and say which sentence you rely on.

Do not edit the scenarios. Keep the code building and your own scenarios passing, and run
`kit/check.sh --only repair` before you stop. Finish in five lines.

If you have no memory of this work: the ticket is in `task.md`, `AGENTS.md` describes the
workspace, your notes are in `work/ledger.md`, your scenarios in `work/scenarios/`, and your
changes are in `app/services` (compare with `.pristine/app/services`).

Failing runs:

