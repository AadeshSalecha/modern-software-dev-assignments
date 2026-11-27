Several engineers answered the report request of the ticket below independently, and their
files under `out/` differ. Work out what the right report is. Nobody will answer questions.

What you have:

- `out/`: report A, and `work/report.py`, the script that made it.
- `work/cross/*-b.*` and `work/cross/report-b.py`: report B and its script, if there is one.
  A and B were both made from `work/evidence.db`, a database loaded from the evidence packet
  by a tool (`kit/evidence.py`).
- `work/cross/*-c.*` and `work/cross/report-c.py`: report C and its script, if there is one.
  C was made straight from the raw files under `incident/`, without that database.
- `incident/` and `app/contracts/evidence.md`: the evidence itself and the rules for reading
  it. They are the ground truth here. The database is a convenience and can be wrong.
- The differences between the reports, below.

Method:

1. Read the scripts. For each sentence of the ticket's report request, write down how each
   script turns it into a condition. The reports differ where those conditions differ, or
   where the data they read differs.
2. Settle each difference by the ticket's wording, read literally, and by the raw files: for
   two or three concrete ids from each "only in" list, find the lines in `incident/` that
   mention them (`grep`) and decide from those lines whether the id belongs in the report.
   Do not pick the report that looks more plausible, and do not count votes: two reports
   that agree can share one mistake.
3. No report is presumed right, and where they all agree they can all be wrong. Check that
   each set is built from every file that can show a member: a script that takes a set from
   one file misses the members whose row was cut there.
4. Write the final file under `out/` with a script, `work/report-final.py`, in exactly the
   shape the ticket asks for, then run `kit/check.sh --only report`.

Do not edit anything under `app/`. Finish with one line per difference: what differed,
which reading is right, and the ticket sentence or raw line that decides it.

Differences between the reports:

