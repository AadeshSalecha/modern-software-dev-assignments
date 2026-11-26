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
        ("A-v3", "After the independent review (commit 94f7d88): bounded run.sh, skippable contract checks, reworded skills."),
        ("A-v4", "A-v3 plus the report rule on missing facts and no advertised check skipping (commit c39352d). The submitted default."),
        ("split-haiku-report", "A-v4 with the report written by `claude-haiku-5-5` in parallel while Sonnet only repairs."),
        ("haiku-main-sonnet-rescue", "A-v4 with `claude-haiku-5-5` as the main agent and Sonnet only if the gate fails."),
        ("codex-luna", "A-v4 with Codex and `gpt-6-luna` for the whole session (run on the Mac)."),
        ("codex-terra", "A-v4 with Codex and `gpt-6.1-terra` for the whole session (run on the Mac)."),
        ("A-v5", "A-v4 plus the hand-over check in the gate, random port choice and one prompt sentence (commit 4450fb7)."),
        ("codex-terra-v5", "A-v5 with Codex and `gpt-6.1-terra` for the whole session (Mac)."),
        ("codex-luna-v5", "A-v5 with Codex and `gpt-6-luna` for the whole session (Mac)."),
        ("luna-main-terra-rescue", "A-v5 with `gpt-6-luna` as the main agent and `gpt-6.1-terra` only if the gate fails (Mac)."),
        ("sonnet-main-terra-rescue", "Sonnet as the main agent and `gpt-6.1-terra` (Codex) only if the gate fails, on the Mac's Claude Code 2.1.284."),
        ("forced-rescue-terra", "Rescue path exercised on purpose: the main agent names a model that does not exist, so `gpt-6.1-terra` gets the whole job (Mac)."),
        ("terra-main-sonnet-rescue", "`gpt-6.1-terra` (Codex) as the main agent and Sonnet only if the gate fails (Mac)."),
        ("split-luna-report-terra", "Codex: `gpt-6-luna` writes the report in parallel while `gpt-6.1-terra` repairs (Mac)."),
        ("split-luna-report-sonnet", "`gpt-6-luna` (Codex) writes the report in parallel while Sonnet repairs (Mac)."),
        ("luna-main-sonnet-rescue", "`gpt-6-luna` (Codex) as the main agent and Sonnet only if the gate fails (Mac)."),
    ]
)


def load(run):
    folder = os.path.join(HERE, "runs", run)
    summary = json.load(open(os.path.join(folder, "summary.json")))
    usage = collections.Counter()
    log = os.path.join(folder, "usage.jsonl")
    if os.path.exists(log):
        for line in open(log):
            row = json.loads(line)
            if row.get("metered"):
                usage.update({k: row["usage"].get(k, 0) for k in KINDS})
    else:  # runs brought over from another machine carry only the summary
        for totals in (summary.get("by_model") or {}).values():
            usage.update({k: totals.get(k, 0) for k in KINDS})
    return summary, usage


def transfer_section():
    """Runs on the transfer incident, from transfer/results/<label>-<stamp>-<n>/summary.json."""
    folder = os.path.join(HERE, "transfer", "results")
    if not os.path.isdir(folder):
        return []
    groups = collections.OrderedDict()
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name, "summary.json")
        if os.path.exists(path):
            groups.setdefault(name.rsplit("-", 3)[0], []).append((name, json.load(open(path))))
    out = [
        "",
        "## Transfer incident (INC-2231, endpoint changes ignored)",
        "",
        "A second incident built to test the setup on a ticket it was not designed around; see",
        "`transfer/README.md`. Scored by `transfer/inc-2231/judge.py` with the assignment's formulas.",
        "",
        "| Setup | Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for label, runs in groups.items():
        for name, summary in runs:
            score = summary["score"]
            cats = score.get("categories", {})
            cell = lambda key: f"{cats[key]['passed']}/{cats[key]['total']}" if key in cats else "-"
            impact = (score.get("impact") or {}).get("impact")
            out.append(
                f"| {label} | {name[len(label) + 1:]} | {'PASS' if summary['passed'] else 'FAIL'} | {score.get('repair')} | "
                f"{impact} | ${summary['cost_usd']:.3f} | {summary['requests']} | {summary['seconds']:.0f} s | "
                f"{cell('incident')} | {cell('regressions')} | {cell('compat')} |"
            )
    return out


def main():
    groups = collections.OrderedDict()
    for index in ("index.tsv", "index-mac.tsv"):
        path = os.path.join(HERE, "runs", index)
        if not os.path.exists(path):
            continue
        for line in open(path):
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
    transfer = transfer_section()
    detail += transfer
    notes_path = os.path.join(HERE, "results-notes.md")
    tail = ["", open(notes_path).read().rstrip()] if os.path.exists(notes_path) else []
    with open(os.path.join(HERE, "results.md"), "w") as handle:
        handle.write("\n".join(out + detail + tail) + "\n")
    print("\n".join(out[7:]))


if __name__ == "__main__":
    main()
