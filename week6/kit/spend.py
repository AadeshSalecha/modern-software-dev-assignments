#!/usr/bin/env python3
"""What the sessions so far have cost, from the harnesses' own logs and the rate card.

    python3 kit/spend.py work/logs              total and per log, in dollars
    python3 kit/spend.py --under 0.55 work/logs exit status 0 if the total is below 0.55

run.sh uses this to decide whether an optional step is still affordable. It is an estimate:
the grader's gateway is what counts, and a session that is cut off may not have logged its
last request. Logs are named <step>.<harness>.<model>.jsonl.

  claude  --output-format stream-json: every assistant message carries the usage of its request
  codex   --json: every finished turn carries the turn's usage
"""

import glob
import json
import os
import sys

KIT = os.path.dirname(os.path.abspath(__file__))
FALLBACK = {  # dollars per million tokens, if rate_card.json is not there
    "claude-sonnet-5-5": {"input": 2.0, "output": 10.0, "cache_read": 0.1, "cache_write": 2.5, "cache_write_1h": 4.0},
    "claude-haiku-5-5": {"input": 0.1, "output": 0.5, "cache_read": 0.01, "cache_write": 0.125, "cache_write_1h": 0.2},
    "gpt-6.1-terra": {"input": 1.0, "output": 5.0, "cache_read": 0.05, "cache_write": 1.25},
    "gpt-6-luna": {"input": 0.1, "output": 0.5, "cache_read": 0.01, "cache_write": 0.125},
}


def rates():
    try:
        with open(os.path.join(os.path.dirname(KIT), "rate_card.json"), encoding="utf-8") as handle:
            return json.load(handle)["models"]
    except (OSError, ValueError, KeyError):
        return FALLBACK


def rate_for(card, model):
    if model in card:
        return card[model]
    for name in card:
        if model and model.startswith(name):
            return card[name]
    return max(card.values(), key=lambda r: r.get("output", 0))  # unknown: assume the dearest


def price(card, model, usage):
    rate = rate_for(card, model)
    return sum(usage.get(kind, 0) * rate.get(kind, rate.get("cache_write", 0)) for kind in usage) / 1e6


def cost_of(path, card, sessions=None):
    """Dollars for one log file. `sessions` carries what has been counted per Claude session
    across files: a resumed session reports the totals of the whole session again, so only
    the increase belongs to the later file."""
    sessions = {} if sessions is None else sessions
    name = os.path.basename(path).split(".")
    file_model = ".".join(name[2:-1]) if len(name) > 3 else ""
    total = 0.0
    pending = {}  # claude messages since the last session result: id -> (model, usage, characters written)
    try:
        handle = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return 0.0
    with handle:
        for line in handle:
            if not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            kind = event.get("type")
            if kind == "assistant" and isinstance(event.get("message"), dict):
                # The usage on a message is taken when the request starts: input and cache counts
                # are right, the output count is not. Output is estimated from what was written.
                message = event["message"]
                usage = message.get("usage") or {}
                hour = (usage.get("cache_creation") or {}).get("ephemeral_1h_input_tokens", 0)
                written = sum(len(json.dumps(block)) for block in message.get("content") or [])
                key = message.get("id") or len(pending)
                before = pending.get(key, (None, None, 0))[2]
                pending[key] = (message.get("model") or file_model, {
                    "input": usage.get("input_tokens", 0),
                    "cache_read": usage.get("cache_read_input_tokens", 0),
                    "cache_write": usage.get("cache_creation_input_tokens", 0) - hour,
                    "cache_write_1h": hour,
                }, before + written)
            elif kind == "result" and isinstance(event.get("modelUsage"), dict):
                # The end of an invocation: exact totals per model for the session so far, in
                # place of the estimates.
                whole = 0.0
                for model, used in event["modelUsage"].items():
                    hour = used.get("cacheCreationEphemeral1hInputTokens", 0)
                    whole += price(card, model, {
                        "input": used.get("inputTokens", 0),
                        "output": used.get("outputTokens", 0),
                        "cache_read": used.get("cacheReadInputTokens", 0),
                        "cache_write": used.get("cacheCreationInputTokens", 0) - hour,
                        "cache_write_1h": hour,
                    })
                key = event.get("session_id") or f"{path}#{len(sessions)}"
                total += max(whole - sessions.get(key, 0.0), 0.0)
                sessions[key] = max(whole, sessions.get(key, 0.0))
                pending = {}
            elif kind == "turn.completed" and isinstance(event.get("usage"), dict):
                usage = event["usage"]
                cached = usage.get("cached_input_tokens", 0)
                total += price(card, file_model, {
                    "input": max(usage.get("input_tokens", 0) - cached, 0),
                    "output": usage.get("output_tokens", 0),
                    "cache_read": cached,
                })
    for model, usage, written in pending.values():  # a session that was cut off
        total += price(card, model, dict(usage, output=int(written / 2.5)))
    return total


def main(argv):
    limit, paths = None, []
    index = 0
    while index < len(argv):
        if argv[index] == "--under":
            limit, index = float(argv[index + 1]), index + 2
        else:
            paths.append(argv[index])
            index += 1
    files = []
    for path in paths:
        files += sorted(glob.glob(os.path.join(path, "*.jsonl"))) if os.path.isdir(path) else [path]
    card = rates()
    sessions = {}
    costs = [(path, cost_of(path, card, sessions)) for path in files]
    total = sum(cost for _, cost in costs)
    if limit is not None:
        return 0 if total < limit else 1
    for path, cost in costs:
        print(f"{cost:8.4f}  {os.path.basename(path)}")
    print(f"{total:8.4f}  total")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
