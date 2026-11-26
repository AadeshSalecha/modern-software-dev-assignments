#!/usr/bin/env python3
"""Run the Week 6 setup on the transfer incident (INC-2231), the way practice.py runs it on the
starter: a copy of week6/ in a temporary workspace, this folder's ticket and packet in place of
the starter's, `./run.sh task.md` through the metering gateway, then the judge.

    python3 run_transfer.py [--runs N] [--label NAME] [--port 8797] [--timeout 600]

KIT_* variables in the environment reach run.sh, as with practice.py. Logs for each run go to
transfer/runs/<label>-<stamp>-<n>/: agent.log, usage.jsonl, summary.json, judge.json,
app.diff and out/.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
WEEK = REPO / "week6"
INCIDENT = HERE / "inc-2231"
sys.path.insert(0, str(WEEK / "tools"))
import costs  # noqa: E402
import harness  # noqa: E402
import runner  # noqa: E402

# What practice.py leaves out, plus what the submission zip leaves out.
SKIP = shutil.ignore_patterns(
    ".git", "runs", "out", "__pycache__", ".pytest_cache", ".venv", "node_modules", ".build", "state", "starter",
    "writeup.md", "work", ".pristine",
)
CODEX_LOGIN = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "auth.json"
REAL_KEYS = {"anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"), "openai": ("OPENAI_API_KEY",)}


def one_run(index, args, stamp):
    out_dir = HERE / "runs" / f"{args.label}-{stamp}-{index}"
    out_dir.mkdir(parents=True)
    usage_log, agent_log = out_dir / "usage.jsonl", out_dir / "agent.log"
    with tempfile.TemporaryDirectory(prefix="cs146s-transfer-") as temp:
        temp = Path(temp)
        workspace = temp / "week6"
        shutil.copytree(WEEK, workspace, ignore=SKIP, symlinks=True)
        shutil.rmtree(workspace / "incident")
        shutil.copytree(INCIDENT / "incident", workspace / "incident")
        shutil.copy(INCIDENT / "task.md", workspace / "task.md")
        clean = temp / "clean-app"
        shutil.copytree(WEEK / "app", clean, ignore=SKIP)
        home = temp / "home"
        gateway_url = f"http://127.0.0.1:{args.port}"

        give_keys = {p: bool(os.environ.get(names[0])) for p, names in REAL_KEYS.items()}
        env = dict(os.environ)
        for provider, names in REAL_KEYS.items():
            if give_keys[provider]:
                for name in names:
                    env.pop(name, None)
        env.update(harness.gateway_env(gateway_url, home, give_keys))
        codex_login = CODEX_LOGIN if not give_keys["openai"] and CODEX_LOGIN.is_file() else None
        harness.write_codex_config(home, gateway_url, login=codex_login)

        gateway = runner.start_gateway(args.port, WEEK / "rate_card.json", usage_log, max_cost=2.0,
                                       allow_login=codex_login is not None)  # fmt: skip
        print(f"run {index}: running ./run.sh task.md on INC-2231 ...", flush=True)
        try:
            result = runner.run_entry(workspace, "task.md", env, args.timeout, agent_log)
        finally:
            runner.stop_gateway(gateway)
            subprocess.run(["pkill", "-f", str(workspace)], check=False)

        judged = subprocess.run(
            [sys.executable, str(INCIDENT / "judge.py"), str(workspace), "--out", str(out_dir / "judge.json")],
            capture_output=True, text=True, timeout=900,
        )  # fmt: skip
        (out_dir / "judge.log").write_text(judged.stdout + judged.stderr)
        diff = subprocess.run(["diff", "-ruN", "-x", ".build", "-x", "state", "-x", "__pycache__",
                               str(clean), str(workspace / "app")], capture_output=True, text=True)  # fmt: skip
        (out_dir / "app.diff").write_text(diff.stdout.replace(str(temp) + "/", ""))
        for name in ("out", "work"):
            if (workspace / name).is_dir():
                shutil.copytree(workspace / name, out_dir / name, ignore=shutil.ignore_patterns("*.db", "home"))

    try:
        judge = json.loads((out_dir / "judge.json").read_text())
    except (OSError, ValueError):
        judge = {"error": (judged.stdout + judged.stderr)[-600:]}
    summary = costs.summarize(usage_log)
    impact = judge.get("impact") if isinstance(judge.get("impact"), dict) else {}
    passed = bool(judge.get("passed"))
    record = {"passed": passed, "score": judge, **result, **summary}
    (out_dir / "summary.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"run {index}: {'PASS' if passed else 'FAIL'}  repair {judge.get('repair')}  impact {impact.get('impact')}  "
          f"${summary['cost_usd']:.4f}  {summary['requests']} requests  {result['seconds']} s")  # fmt: skip
    print("  " + (judged.stdout.strip().replace("\n", "\n  ")[:1800] or judged.stderr.strip()[-600:]))
    print(f"  logs: {out_dir.relative_to(REPO)}/", flush=True)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--label", default="default")
    parser.add_argument("--port", type=int, default=8797)
    parser.add_argument("--timeout", type=float, default=600)
    args = parser.parse_args()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    records = [one_run(index, args, stamp) for index in range(1, args.runs + 1)]
    print(f"{sum(r['passed'] for r in records)} of {len(records)} passed; "
          f"mean cost ${sum(r['cost_usd'] for r in records) / len(records):.4f}")  # fmt: skip
    return 0 if all(r["passed"] for r in records) else 1


if __name__ == "__main__":
    sys.exit(main())
