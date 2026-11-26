#!/usr/bin/env python3
"""Rebuild results.md from runs/index.tsv and the saved summary.json / usage.jsonl files.

    python3 make_results.py
"""

import collections
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RATES = json.load(open(os.path.join(HERE, "..", "..", "week6", "rate_card.json")))["models"]
KINDS = ("input", "output", "cache_read", "cache_write", "cache_write_1h")

DESCRIPTIONS = collections.OrderedDict(
    [
        ("baseline", "Unmodified `run.sh`: Sonnet, effort high, default tools, bare ticket."),
        ("flags", "Bare ticket, no kit. Only harness flags changed: 4 tools, no MCP, 5-minute cache, effort medium."),
        ("A-v1", "Option A (commit 1b556ac): prep + kit + one Sonnet session, effort medium, 4 tools, stop hook."),
        ("nohook", "A-v1 with the stop hook and the resume switched off."),
        ("effort-high", "A-v1 with `--effort high`."),
        ("effort-low", "A-v1 with `--effort low`."),
        ("haiku", "A-v1 with `claude-haiku-5-5` for the whole session (effort medium)."),
        ("A-v2", "A-v1 plus one sentence in the report skill about what each figure adds up over (commit 8a70799)."),
        ("A-v2-low", "A-v2 with `--effort low`."),
        ("haiku-low", "A-v2 with `claude-haiku-5-5` and `--effort low`."),
        ("A-v2-emptyhome", "A-v2 with HOME pointed at an empty directory, as in the grader."),
    ]
)


def load(run):
    folder = os.path.join(HERE, "runs", run)
    summary = json.load(open(os.path.join(folder, "summary.json")))
    usage = collections.Counter()
    for line in open(os.path.join(folder, "usage.jsonl")):
        row = json.loads(line)
        if row.get("metered"):
            usage.update({k: row["usage"].get(k, 0) for k in KINDS})
    return summary, usage


def main():
    groups = collections.OrderedDict()
    for line in open(os.path.join(HERE, "runs", "index.tsv")):
        if line.strip():
            label, run = line.split()
            groups.setdefault(label, []).append(run)
    order = [label for label in DESCRIPTIONS if label in groups] + [label for label in groups if label not in DESCRIPTIONS]

    out = [
        "# Results log: Week 6",
        "",
        "All runs: starter incident, `python3 tools/practice.py --keep`, Node 24, Claude Code 2.1.332 in the",
        "cloud container, cost from `rate_card.json`. `runs/<stamp>/` holds each run's `summary.json` and",
        "`usage.jsonl`; `runs/index.tsv` maps labels to runs. Full logs (`week6/runs/`) are gitignored.",
        "Rebuilt by `make_results.py`.",
        "",
        "## Summary",
        "",
        "| Setup | Passed | Mean repair | Mean impact | Mean cost | Cost range | Mean requests | Mean time | Longest |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    detail = []
    for label in order:
        loaded = [load(run) for run in groups[label]]
        summaries = [s for s, _ in loaded]
        n = len(summaries)
        mean = lambda pick: sum(pick(s) for s in summaries) / n
        costs = [s["cost_usd"] for s in summaries]
        out.append(
            f"| {label} | {sum(bool(s['passed']) for s in summaries)}/{n} | {mean(lambda s: s['score']['repair']):.2f} | "
            f"{mean(lambda s: s['score']['impact']):.2f} | ${mean(lambda s: s['cost_usd']):.3f} | "
            f"${min(costs):.2f} to ${max(costs):.2f} | {mean(lambda s: s['requests']):.0f} | "
            f"{mean(lambda s: s['seconds']):.0f} s | {max(s['seconds'] for s in summaries):.0f} s |"
        )
        detail += ["", f"## {label}", "", DESCRIPTIONS.get(label, ""), ""]
        detail += [
            "| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | Output | Cache read | Cache write |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for run, (summary, usage) in zip(groups[label], loaded):
            cats = summary["score"].get("categories", {})
            cell = lambda name: f"{cats[name]['passed']}/{cats[name]['total']}" if name in cats else "-"
            detail.append(
                f"| {run} | {'PASS' if summary['passed'] else 'FAIL'} | {summary['score']['repair']:.2f} | "
                f"{summary['score']['impact']:.2f} | ${summary['cost_usd']:.3f} | {summary['requests']} | "
                f"{summary['seconds']:.0f} s | {cell('incident')} | {cell('regressions')} | {cell('compat')} | "
                f"{usage['output']:,} | {usage['cache_read']:,} | {usage['cache_write'] + usage['cache_write_1h']:,} |"
            )
        failed = [
            f"- {run}: [{name}] {item['name']}"
            for run, (summary, _) in zip(groups[label], loaded)
            for name, cat in summary["score"].get("categories", {}).items()
            for item in cat.get("failed", [])
        ]
        notes = [
            f"- {run}: impact figures {summary['score'].get('totals_right')}/{summary['score'].get('totals')} right, "
            f"precision {summary['score'].get('precision')}, recall {summary['score'].get('recall')}"
            for run, (summary, _) in zip(groups[label], loaded)
            if summary["score"]["impact"] < 1
        ]
        if failed or notes:
            detail += ["", "Failures:"] + failed + notes
    notes_path = os.path.join(HERE, "results-notes.md")
    tail = ["", open(notes_path).read().rstrip()] if os.path.exists(notes_path) else []
    with open(os.path.join(HERE, "results.md"), "w") as handle:
        handle.write("\n".join(out + detail + tail) + "\n")
    print("\n".join(out[7:]))


if __name__ == "__main__":
    main()
