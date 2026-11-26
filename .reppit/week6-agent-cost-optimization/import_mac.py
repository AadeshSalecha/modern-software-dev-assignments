#!/usr/bin/env python3
"""Store runs made on the Mac. Reads the JSON lines printed by /tmp/week6-collect.py there
(one run per line) from stdin and writes each summary where make_results.py looks:

    practice runs  -> runs/<run>/summary.json, and a line in runs/index-mac.tsv
    transfer runs  -> transfer/results/<run>/summary.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
index = []
for line in sys.stdin:
    line = line.strip()
    if not line.startswith("{"):
        continue
    row = json.loads(line)
    if row["kind"] == "practice":
        folder = os.path.join(HERE, "runs", row["run"])
        index.append(f"{row['label']}\t{row['run']}")
    else:
        folder = os.path.join(HERE, "transfer", "results", row["run"].replace("mac-", "", 1) + "-mac")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "summary.json"), "w") as handle:
        json.dump(row["summary"], handle, indent=2)
with open(os.path.join(HERE, "runs", "index-mac.tsv"), "w") as handle:
    handle.write("\n".join(index) + ("\n" if index else ""))
print(f"{len(index)} practice runs indexed")
