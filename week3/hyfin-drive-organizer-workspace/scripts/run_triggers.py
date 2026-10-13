#!/usr/bin/env python3
"""Trigger eval runner: does a fresh Claude Code session load the skill for each query?

Each run is a brand-new `claude -p` process with its own config directory that holds the
team's other installed skills (the near-miss competitors: google-workspace, make-it-hyfin,
gaia-capital-providers, docs, ...) plus exactly ONE copy of hyfin-drive-organizer: the
directory passed with --skill, with its description optionally overridden by --description.

"Triggered" = the transcript contains a Skill tool call whose skill name contains
"hyfin-drive-organizer". The run is stopped as soon as any Skill call appears.

Safety: tools that could change anything outside the sandbox are disallowed, no MCP
connectors are loaded (so no Drive access at all), and a system-prompt line forbids moving,
trashing, creating, renaming or sharing anything.

Usage:
  python3 run_triggers.py --skill <skill dir> --others <dir with other skills> \
      --queries trigger_queries.json --runs 3 --label iter-1 --out results.json \
      [--description-file desc.txt] [--split train|validation|all] [--model claude-opus-5-5]
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

TARGET = "hyfin-drive-organizer"
DISALLOWED = ["RemoteTrigger", "CronCreate", "CronDelete", "ScheduleWakeup", "PushNotification",
              "SendUserFile", "SendMessage", "Artifact", "ArtifactData", "ArtifactComments",
              "Workflow", "Write", "Edit", "NotebookEdit", "DesignSync", "ShareOnboardingGuide",
              "Task", "Monitor", "EnterWorktree"]
SAFETY = ("This is a skill-triggering test. You must not move, trash, create, rename or share any "
          "file, folder, task or schedule. Respond to the user's message as you normally would.")
STRIP_ENV = ["CLAUDECODE", "CLAUDE_CODE_SYNC_SKILLS", "CLAUDE_CODE_REMOTE", "CLAUDE_CODE_SESSION_ID",
             "CLAUDE_CODE_REMOTE_SESSION_ID", "SESSION_INGRESS_URL", "CLAUDE_CODE_MESSAGING_SOCKET",
             "CLAUDE_CODE_MESSAGING_TOKEN", "CLAUDE_SESSION_INGRESS_TOKEN_FILE", "CLAUDE_CODE_CHILD_SESSION"]


def set_description(skill_md: Path, desc: str):
    text = skill_md.read_text()
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    fm = m.group(1)
    # drop the existing description (single-line or folded block) and insert the new one
    fm = re.sub(r"^description:.*?(?=^\S)", "", fm + "\n", flags=re.S | re.M).rstrip("\n")
    folded = "description: >-\n" + "\n".join("  " + line for line in desc.strip().splitlines())
    fm = fm.replace("name: " + TARGET, "name: " + TARGET + "\n" + folded, 1)
    skill_md.write_text("---\n" + fm + "\n---\n" + text[m.end():])


def build_config(skill_dir: Path, others: Path, desc: str | None) -> Path:
    cfg = Path(tempfile.mkdtemp(prefix="trigcfg-"))
    (cfg / "skills").mkdir()
    for d in others.iterdir():
        if d.is_dir() and d.name != TARGET:
            shutil.copytree(d, cfg / "skills" / d.name)
    shutil.copytree(skill_dir, cfg / "skills" / TARGET, ignore=shutil.ignore_patterns("evals"))
    if desc:
        set_description(cfg / "skills" / TARGET / "SKILL.md", desc)
    return cfg


def run_one(query: str, cfg: Path, model: str, timeout: int, cwd: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in STRIP_ENV}
    env["CLAUDE_CONFIG_DIR"] = str(cfg)
    cmd = ["claude", "-p", query, "--output-format", "stream-json", "--verbose", "--max-turns", "3",
           "--model", model, "--append-system-prompt", SAFETY, "--disallowedTools", *DISALLOWED]
    t0 = time.time()
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=cwd, env=env, text=True)
    rec = {"triggered": False, "skill_called": None, "tools": [], "text": "", "skills_listed": None}
    try:
        for line in p.stdout:
            if time.time() - t0 > timeout:
                rec["timeout"] = True
                break
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("type") == "system" and e.get("subtype") == "init":
                rec["skills_listed"] = [s for s in e.get("skills", []) if TARGET in s]
            if e.get("type") == "assistant":
                for c in e["message"]["content"]:
                    if c["type"] == "tool_use":
                        rec["tools"].append(c["name"] + " " + json.dumps(c["input"])[:120])
                        if c["name"] == "Skill":
                            rec["skill_called"] = c["input"].get("skill")
                            rec["triggered"] = TARGET in (rec["skill_called"] or "")
                    elif c["type"] == "text" and len(rec["text"]) < 400:
                        rec["text"] += c["text"][:400 - len(rec["text"])]
                if rec["skill_called"]:
                    break
            if e.get("type") == "result":
                break
    finally:
        if p.poll() is None:
            p.kill()
        p.wait()
    rec["seconds"] = round(time.time() - t0, 1)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill", required=True)
    ap.add_argument("--others", required=True)
    ap.add_argument("--queries", required=True)
    ap.add_argument("--description-file")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--split", default="all")
    ap.add_argument("--only", help="comma-separated query ids")
    ap.add_argument("--label", required=True)
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--timeout", type=int, default=150)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    desc = Path(a.description_file).read_text() if a.description_file else None
    qs = json.loads(Path(a.queries).read_text())
    if a.split != "all":
        qs = [q for q in qs if q["split"] == a.split]
    if a.only:
        ids = set(a.only.split(","))
        qs = [q for q in qs if q["id"] in ids]
    cfg = build_config(Path(a.skill), Path(a.others), desc)
    cwd = Path(tempfile.mkdtemp(prefix="trigcwd-"))
    jobs = [(q, r) for q in qs for r in range(1, a.runs + 1)]
    with ThreadPoolExecutor(a.workers) as ex:
        outs = list(ex.map(lambda j: run_one(j[0]["query"], cfg, a.model, a.timeout, cwd), jobs))
    results = []
    for q in qs:
        runs = [dict(run=r, **o) for (qq, r), o in zip(jobs, outs) if qq is q]
        rate = sum(x["triggered"] for x in runs) / len(runs)
        results.append({"id": q["id"], "split": q["split"], "should_trigger": q["should_trigger"],
                        "query": q["query"], "trigger_rate": round(rate, 2),
                        "triggered": rate > 0.5, "pass": (rate > 0.5) == q["should_trigger"], "runs": runs})
    summary = {}
    for split in ("train", "validation"):
        sub = [r for r in results if r["split"] == split]
        if sub:
            summary[split] = {"passed": sum(r["pass"] for r in sub), "total": len(sub),
                              "pass_rate": round(sum(r["pass"] for r in sub) / len(sub), 2)}
    out = {"label": a.label, "model": a.model, "runs_per_query": a.runs, "threshold": 0.5,
           "skill_dir": str(a.skill), "description": desc or "(as in SKILL.md)", "summary": summary,
           "results": results}
    Path(a.out).write_text(json.dumps(out, indent=2))
    shutil.rmtree(cfg, ignore_errors=True)
    print(json.dumps(summary))
    for r in results:
        flag = "PASS" if r["pass"] else "FAIL"
        others = sorted({x["skill_called"] for x in r["runs"] if x["skill_called"] and TARGET not in x["skill_called"]})
        print(f"{flag} {r['id']:<4} {r['split']:<10} want={str(r['should_trigger']):<5} rate={r['trigger_rate']:.2f} other={others} :: {r['query'][:70]}")


if __name__ == "__main__":
    main()
