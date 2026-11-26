#!/usr/bin/env python3
"""Store results of runs made on the Mac (where Codex is installed) so make_results.py sees them.

Rows live in mac-runs.tsv, one finished run per line, copied from each run's summary.json there:

    kind label run passed repair impact cost requests seconds incident regressions compat
    input output cache_read cache_write model

kind is practice or transfer; incident/regressions/compat are passed/total. This script turns
each row into runs/<run>/summary.json (practice) or transfer/results/<run>/summary.json.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
index = []
for line in open(os.path.join(HERE, "mac-runs.tsv")):
    if not line.strip() or line.startswith("#"):
        continue
    (kind, label, run, passed, repair, impact, cost, requests, seconds, incident, regressions, compat,
     tokens_in, tokens_out, cache_read, cache_write, model) = line.split()
    cats = {}
    for name, cell in (("incident", incident), ("regressions", regressions), ("compat", compat)):
        done, total = cell.split("/")
        cats[name] = {"passed": int(done), "total": int(total), "failed": []}
    usage = {"requests": int(requests), "cost_usd": float(cost), "input": int(tokens_in), "output": int(tokens_out),
             "cache_read": int(cache_read), "cache_write": int(cache_write), "cache_write_1h": 0}
    score = {"categories": cats, "repair": float(repair)}
    score["impact"] = float(impact) if kind == "practice" else {"impact": float(impact)}
    summary = {"passed": passed == "PASS", "score": score, "seconds": float(seconds), "cost_usd": float(cost),
               "requests": int(requests), "by_model": {model: usage}, "machine": "mac"}
    if kind == "practice":
        folder = os.path.join(HERE, "runs", "mac-" + run)
        index.append(f"{label}\tmac-{run}")
    else:
        folder = os.path.join(HERE, "transfer", "results", f"{label}-{run}")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "summary.json"), "w") as handle:
        json.dump(summary, handle, indent=2)
with open(os.path.join(HERE, "runs", "index-mac.tsv"), "w") as handle:
    handle.write("\n".join(index) + ("\n" if index else ""))
print(f"{len(index)} practice runs from the Mac indexed")
