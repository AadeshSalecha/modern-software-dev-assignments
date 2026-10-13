#!/usr/bin/env python3
"""Extract tool calls, token usage and wall time from a subagent JSONL transcript.

Usage: python3 parse_transcript.py transcript.jsonl > tool_calls.json
Prints {"tool_calls": [{"name", "input"}...], "usage": {...}, "seconds": n}.
"""
import json, sys
from datetime import datetime

calls, usage, times = [], {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}, []
seen = set()
for line in open(sys.argv[1]):
    try:
        e = json.loads(line)
    except json.JSONDecodeError:
        continue
    if e.get("timestamp"):
        times.append(datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00")))
    msg = e.get("message") or {}
    if e.get("type") == "assistant" and isinstance(msg.get("content"), list):
        mid = msg.get("id")
        if mid and mid not in seen and msg.get("usage"):
            seen.add(mid)
            for k in usage:
                usage[k] += msg["usage"].get(k, 0) or 0
        for c in msg["content"]:
            if c.get("type") == "tool_use":
                calls.append({"name": c["name"], "input": c["input"]})
print(json.dumps({"tool_calls": calls, "usage": usage,
                  "seconds": round((max(times) - min(times)).total_seconds(), 1) if times else None}, indent=1))
