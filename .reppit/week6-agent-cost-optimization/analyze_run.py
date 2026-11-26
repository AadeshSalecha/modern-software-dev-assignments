#!/usr/bin/env python3
"""Summarise practice runs from week6/runs/<stamp>/.

    python3 analyze_run.py week6/runs/<stamp> [...]        one block per run
    python3 analyze_run.py --table week6/runs/<a> <b> ...  one markdown row per run
    python3 analyze_run.py --steps week6/runs/<stamp>      every tool call, in order

Reads summary.json, usage.jsonl and agent.log (Claude Code stream-json). Prices come from
week6/rate_card.json, the same as tools/practice.py.
"""

import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RATES = json.load(open(os.path.join(HERE, "..", "..", "week6", "rate_card.json")))["models"]
KINDS = ("input", "output", "cache_read", "cache_write", "cache_write_1h")


def price(model, usage):
    rate = RATES.get(model) or next((r for name, r in RATES.items() if model.startswith(name)), {})
    return sum(usage.get(k, 0) * rate.get(k, rate.get("cache_write", 0)) for k in KINDS) / 1e6


def load(run):
    summary = json.load(open(os.path.join(run, "summary.json")))
    requests = []
    for line in open(os.path.join(run, "usage.jsonl")):
        row = json.loads(line)
        if row.get("metered"):
            requests.append(row)
    events = []
    try:
        for line in open(os.path.join(run, "agent.log"), errors="replace"):
            try:
                events.append(json.loads(line))
            except ValueError:
                events.append({"type": "text", "text": line.rstrip()})
    except OSError:
        pass
    return summary, requests, events


def tool_calls(events):
    calls, by_id = [], {}
    for event in events:
        if event.get("type") == "assistant":
            for block in event["message"].get("content", []):
                if block.get("type") == "tool_use":
                    call = {"name": block["name"], "input": block["input"], "result_chars": 0, "error": False}
                    by_id[block["id"]] = call
                    calls.append(call)
        elif event.get("type") == "user" and isinstance(event["message"].get("content"), list):
            for block in event["message"]["content"]:
                if block.get("type") == "tool_result" and block.get("tool_use_id") in by_id:
                    call = by_id[block["tool_use_id"]]
                    call["result_chars"] = len(json.dumps(block.get("content")))
                    call["error"] = bool(block.get("is_error"))
    return calls


def brief(call, width=150):
    data = call["input"]
    text = data.get("command") or data.get("file_path") or json.dumps(data)
    if call["name"] in ("Edit", "Write"):
        text = f"{data.get('file_path')} ({len(data.get('new_string') or data.get('content') or '')} chars)"
    return " ".join(str(text).split())[:width]


def totals(requests):
    by_model = collections.defaultdict(collections.Counter)
    for row in requests:
        by_model[row["model"]].update({k: row["usage"].get(k, 0) for k in KINDS})
        by_model[row["model"]]["requests"] += 1
    return by_model


def stop_blocks(events):
    blocks = 0
    for event in events:
        text = json.dumps(event)
        if ("Not finished: kit/check.sh reports" in text or "Before you stop, kit/check.sh reports" in text) and event.get("type") in ("user", "system"):
            blocks += 1
    return blocks


def block(run):
    summary, requests, events = load(run)
    score = summary.get("score") or {}
    cats = score.get("categories") or {}
    print(f"== {run}")
    print(
        f"{'PASS' if summary.get('passed') else 'FAIL'}  repair {score.get('repair')}  impact {score.get('impact')} "
        f"(P {score.get('precision')} R {score.get('recall')} figures {score.get('totals_right')}/{score.get('totals')})  "
        f"${summary.get('cost_usd'):.4f}  {summary.get('requests')} requests  {summary.get('seconds')} s"
    )
    print("   " + "  ".join(f"{name} {c['passed']}/{c['total']}" for name, c in cats.items()))
    for name, c in cats.items():
        for failed in c.get("failed", [])[:6]:
            print(f"   - [{name}] {failed['name']}: {'; '.join(failed.get('problems', [])[:2])[:160]}")
    for model, t in totals(requests).items():
        cost = price(model, t)
        parts = "  ".join(f"{k} {t[k]:,} (${price(model, {k: t[k]}):.3f})" for k in KINDS if t[k])
        print(f"   {model}: {t['requests']} requests, ${cost:.4f}: {parts}")
    if requests:
        sizes = [r["usage"].get("cache_read", 0) + r["usage"].get("cache_write", 0) + r["usage"].get("cache_write_1h", 0) + r["usage"].get("input", 0) for r in requests]
        print(f"   context per request: first {sizes[0]:,}, max {max(sizes):,}, last {sizes[-1]:,} tokens")
    calls = tool_calls(events)
    names = collections.Counter(c["name"] for c in calls)
    print(f"   tool calls: {sum(names.values())} ({', '.join(f'{k} {v}' for k, v in names.most_common())}); "
          f"results {sum(c['result_chars'] for c in calls):,} chars; errors {sum(c['error'] for c in calls)}; stop-hook blocks {stop_blocks(events)}")
    for event in events:
        if event.get("type") == "text" and event["text"].startswith("run.sh:"):
            print("   " + event["text"][:200])
    results = [e for e in events if e.get("type") == "result"]
    for result in results:
        print(f"   session result: {result.get('subtype')} turns {result.get('num_turns')} {int(result.get('duration_ms', 0) / 1000)} s")
    if results:
        print("   final message: " + " ".join(str(results[-1].get("result", "")).split())[:700])


def steps(run):
    _, requests, events = load(run)
    for number, call in enumerate(tool_calls(events), 1):
        flag = " ERR" if call["error"] else ""
        print(f"{number:3} {call['name']:<5} {call['result_chars']:>6}{flag}  {brief(call)}")


def table(runs):
    print("| Run | Result | Repair | Impact | Cost | Requests | Time | Incident | Regr. | Compat | In | Out | Cache read | Cache write |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    costs = []
    for run in runs:
        summary, requests, _ = load(run)
        score = summary.get("score") or {}
        cats = score.get("categories") or {}
        t = collections.Counter()
        for model_totals in totals(requests).values():
            t.update(model_totals)
        cell = lambda name: f"{cats[name]['passed']}/{cats[name]['total']}" if name in cats else "-"
        costs.append(summary.get("cost_usd") or 0)
        print(
            f"| {os.path.basename(run.rstrip('/'))} | {'PASS' if summary.get('passed') else 'FAIL'} | {score.get('repair')} | "
            f"{score.get('impact')} | ${summary.get('cost_usd'):.3f} | {summary.get('requests')} | {summary.get('seconds')} s | "
            f"{cell('incident')} | {cell('regressions')} | {cell('compat')} | {t['input']:,} | {t['output']:,} | "
            f"{t['cache_read']:,} | {t['cache_write'] + t['cache_write_1h']:,} |"
        )
    if costs:
        print(f"\nmean cost ${sum(costs) / len(costs):.3f}, worst ${max(costs):.3f}, {len(costs)} runs")


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    if argv[0] == "--table":
        table(argv[1:])
    elif argv[0] == "--steps":
        for run in argv[1:]:
            steps(run)
    else:
        for run in argv:
            block(run)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
