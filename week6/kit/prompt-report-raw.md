Answer only the report request in the ticket below (its second part): write the file it asks
for under `out/` in this folder. You are not asked to repair anything, and there is no code
here to repair. Nobody will answer questions.

What is in this folder:

- `incident/`: the evidence packet, exactly as it was collected. Nothing has been loaded,
  cleaned or summarised for you.
- `contracts/evidence.md`: how those files are written and what can be wrong with them.
  Read it first, all of it, and follow it to the letter: which rows are corrupted and how
  they are counted, lines that were shipped twice, ids that are cut short, clocks that
  differ between files, units of amounts.
- `contracts/`: what the system's terms mean (`delivery.md`, `api.yaml`, `messages/`).

How to work:

1. Turn each sentence of the report request into a condition on what the files record. The
   ticket's own definitions decide; where a service's log line states a conclusion about
   something, that is the service's opinion, not the definition.
2. Parse the files yourself with one script, `report.py` (python3, standard library only),
   and have it write the file under `out/` in exactly the shape of the ticket's example.
   No file is complete on its own: a fact can be recorded in one file and lost from another.
3. Before you finish, print how many entries the report has and its totals, and follow
   three entries by hand through the raw lines that support them.

Finish in three lines: the number of entries, the totals, and anything you could not settle.
