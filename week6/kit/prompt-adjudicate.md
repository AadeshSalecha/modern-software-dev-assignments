Two engineers answered the report request of the ticket below independently, and their
files under `out/` differ. Decide what the right report is. Nobody will answer questions.

What you have:

- `out/`: report A, and `work/report.py`, the script that made it.
- `work/cross/*-b.*`: report B, and `work/cross/report-b.py`, the script that made it. It was
  written in another copy of this workspace and reads the same database.
- `work/evidence.db`: the evidence, loaded. Read `.claude/skills/evidence-report/SKILL.md`
  before anything else.
- The differences between the two reports, below.

Method:

1. Read both scripts. For each sentence of the ticket's report request, write down how each
   script turns it into a condition. The reports differ where those conditions differ.
2. Decide each such difference by the ticket's wording, read literally. Check the decision
   on two or three concrete ids from the "only in" lists by following them through the
   per-file tables.
3. Neither report is presumed right, and where they agree they can both be wrong. If you
   find a sentence both scripts mishandle, fix that too.
4. Write the final file under `out/` with a script, `work/report-final.py`, in exactly the
   shape the ticket asks for, then run `kit/check.sh --only report`.

Do not edit anything under `app/`. Finish with one line per difference: what differed,
which reading is right, and the ticket sentence that decides it.

Differences between the two reports:

