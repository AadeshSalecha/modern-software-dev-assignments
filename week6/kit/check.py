#!/usr/bin/env python3
"""The gate: is the work in a state that can be handed in?

    python3 kit/check.py            run every check, print what is wrong (at most ~40 lines)
    python3 kit/check.py --hook     the same, as the stop hook runs it

Checks, in order:
  build       the worker compiles
  tests       each service's own test command passes
  release     the shipped scenarios still pass, on the working tree alone and when the working
              tree replaces the shipped release after any step
  scenarios   every scenario in work/scenarios/ passes on the working tree
  reproduce   those scenarios fail on the shipped release, and one of them replaces the release
              part-way (asked for at most 3 times, then only noted)
  crash       each service has the same numbered crash points as the shipped release
  report      every out/ file the ticket names exists and has the keys and nesting of the
              ticket's example; a value of another kind than the example's (text for a number)
              is asked about like `reproduce`, since the example may only be a placeholder
  ledger      work/ledger.md has no unchecked line

Exit status 0: nothing blocks. 1: something does.
"""

import concurrent.futures
import glob
import json
import os
import re
import signal
import subprocess
import sys
import time

KIT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(KIT)
sys.path.insert(0, KIT)
import rollout  # noqa: E402

SERVICES = ("api", "router", "worker")
SOFT_LIMIT = 3
SOFT_COUNTER = os.path.join(ROOT, "work", ".soft_blocks")
NO_HARNESS = os.path.join(ROOT, "work", ".no_harness")
BUDGET_SECONDS = 150  # for all scenario runs together
CRASH = re.compile(r"\bcrash\((\d+)\)")


# --- tests ----------------------------------------------------------------------------


def test_command(directory):
    """The service's own test command, read from package.json or the Makefile."""
    package = os.path.join(directory, "package.json")
    if os.path.exists(package):
        try:
            with open(package, encoding="utf-8") as handle:
                script = json.load(handle).get("scripts", {}).get("test")
            if script:
                return script
        except (OSError, ValueError):
            pass
        return "npm test --silent"
    makefile = os.path.join(directory, "Makefile")
    if os.path.exists(makefile):
        try:
            with open(makefile, encoding="utf-8") as handle:
                lines = handle.read().splitlines()
            for index, line in enumerate(lines):
                if re.match(r"^test\s*:", line):
                    recipe = []
                    for following in lines[index + 1 :]:
                        if not following.startswith("\t"):
                            break
                        recipe.append(following.strip().lstrip("@"))
                    if recipe:
                        return " && ".join(recipe)
        except OSError:
            pass
        return "make test"
    return None


def interesting(output, limit=10):
    lines = [l.rstrip() for l in output.splitlines() if l.strip()]
    marked = [l for l in lines if re.search(r"FAIL|Error|error:|not ok|panic|Traceback|expected|AssertionError", l)]
    picked = marked[:limit] if marked else lines[-limit:]
    return [l[:220] for l in picked]


def run_tests(service):
    directory = os.path.join(rollout.NEW_APP, "services", service)
    command = test_command(directory)
    if not os.path.isdir(directory):
        return [f"{service}: the service directory is missing"]
    if command is None:
        return []
    try:
        done = subprocess.run(command, shell=True, cwd=directory, capture_output=True, text=True, timeout=240)
    except subprocess.TimeoutExpired:
        return [f"{service}: tests did not finish in 240 s ({command})"]
    if done.returncode == 0:
        return []
    return [f"{service}: tests fail ({command})"] + ["  " + l for l in interesting(done.stdout + "\n" + done.stderr)]


# --- crash points ---------------------------------------------------------------------


def crash_points(app, service):
    found = set()
    root = os.path.join(app, "services", service)
    for folder, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ("internal", "node_modules", "__pycache__", "tests", "test")]
        for name in files:
            if not name.endswith((".ts", ".js", ".py", ".go")) or name.endswith("_test.go") or ".test." in name:
                continue
            try:
                with open(os.path.join(folder, name), encoding="utf-8", errors="replace") as handle:
                    for line in handle:
                        if not re.search(r"(def|func|function)\s", line):
                            found.update(int(n) for n in CRASH.findall(line))
            except OSError:
                pass
    return found


def check_crash_points():
    if rollout.OLD_APP == rollout.NEW_APP:
        return []
    out = []
    for service in SERVICES:
        before, after = crash_points(rollout.OLD_APP, service), crash_points(rollout.NEW_APP, service)
        if before != after:
            out.append(
                f"{service}: crash points were {sorted(before)}, now {sorted(after)}; "
                "contracts/harness.md wants each at the same step under the same number"
            )
    return out


# --- the report -----------------------------------------------------------------------


def kind(value):
    if isinstance(value, bool):
        return "true/false"
    if isinstance(value, int):
        return "a whole number"
    if isinstance(value, float):
        return "a number"
    if isinstance(value, str):
        return "text"
    if isinstance(value, list):
        return "a list"
    if isinstance(value, dict):
        return "an object"
    return "null"


def is_map(example):
    return bool(example) and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in example.values())


def same_kind(example, actual):
    if isinstance(example, float) and isinstance(actual, int) and not isinstance(actual, bool):
        return True  # a whole number is a number
    return kind(example) == kind(actual)


def shape(example, actual, where="report", top=True):
    """Compare `actual` with the ticket's example. Returns (structure, values).

    structure: a missing or unexpected key, or a list/object/single value where another was shown.
    values:    a single value of another kind than the example's (text for a number, 1.0 for 1).
               The example may only be a placeholder there, so these are weaker evidence.
    """
    if example is None:
        return [], []  # the example does not say
    if isinstance(example, dict):
        if not isinstance(actual, dict):
            return [f"{where}: expected an object, found {kind(actual)}"], []
        if not top and is_map(example):
            sample = next(iter(example.values()))
            return [], [
                f"{where}.{key}: the ticket's example has {kind(sample)}, this is {kind(value)}"
                for key, value in actual.items()
                if not same_kind(sample, value)
            ][:3]
        structure = [f"{where}: missing \"{key}\"" for key in example if key not in actual]
        structure += [f"{where}: unexpected \"{key}\"" for key in actual if key not in example]
        values = []
        for key in example:
            if key in actual:
                found = shape(example[key], actual[key], f"{where}.{key}", False)
                structure += found[0]
                values += found[1]
        return structure, values
    if isinstance(example, list):
        if not isinstance(actual, list):
            return [f"{where}: expected a list, found {kind(actual)}"], []
        structure, values = [], []
        if example:
            for index, item in enumerate(actual):
                found = shape(example[0], item, f"{where}[{index}]", False)
                structure += found[0]
                values += found[1]
                if len(structure) + len(values) >= 3:
                    break
        return structure[:3], values[:3]
    if isinstance(actual, (dict, list)):
        return [f"{where}: expected {kind(example)}, found {kind(actual)}"], []
    if not same_kind(example, actual):
        return [], [f"{where}: the ticket's example has {kind(example)}, this is {kind(actual)}"]
    return [], []


def named_outputs(task_text):
    """(path, example or None) for each out/ file the ticket names."""
    blocks = []
    for found in re.finditer(r"```(?:json)?\s*\n(.*?)```", task_text, re.S):
        try:
            blocks.append((found.start(), json.loads(found.group(1))))
        except ValueError:
            continue
    seen, out = set(), []
    for found in re.finditer(r"\bout/[\w./-]*\w", task_text):
        path = found.group(0)
        if path in seen:
            continue
        seen.add(path)
        example = next((value for start, value in blocks if start > found.start()), None)
        if example is None and len(blocks) == 1:
            example = blocks[0][1]
        out.append((path, example if path.endswith(".json") else None))
    return out


def check_report(task_path):
    """Returns (hard, soft) problems with the out/ files the ticket names."""
    try:
        with open(task_path, encoding="utf-8") as handle:
            task_text = handle.read()
    except OSError:
        return [], []
    hard, soft = [], []
    for path, example in named_outputs(task_text):
        full = os.path.join(ROOT, path)
        if not os.path.isfile(full):
            hard.append(f"{path} does not exist yet")
            continue
        if not path.endswith(".json"):
            continue
        try:
            with open(full, encoding="utf-8") as handle:
                actual = json.load(handle)
        except ValueError as problem:
            hard.append(f"{path} is not valid JSON: {problem}")
            continue
        if example is not None:
            structure, values = shape(example, actual)
            hard += [p.replace("report", path, 1) for p in structure][:6]
            soft += [p.replace("report", path, 1) + " (change it only if the ticket's wording agrees)" for p in values][:3]
    return hard, soft


def check_ledger():
    path = os.path.join(ROOT, "work", "ledger.md")
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return ["work/ledger.md does not exist: list every requirement of the ticket there, one checkbox each"]
    open_lines = [l.strip() for l in lines if re.match(r"^\s*[-*]\s*\[ \]", l)]
    boxes = [l for l in lines if re.match(r"^\s*[-*]\s*\[[ xX]\]", l)]
    if not boxes:
        return ["work/ledger.md has no checkbox lines (`- [ ] requirement: how it is checked`)"]
    return [f"work/ledger.md: {len(open_lines)} requirement(s) not checked off, e.g. {open_lines[0][:140]}"] if open_lines else []


# --- scenarios ------------------------------------------------------------------------


def scenario_checks(bins):
    """Returns (hard, soft) problem lists."""
    hard, soft = [], []
    shipped_dir = os.path.join(rollout.OLD_APP, "scenarios")
    specs = []
    for path in sorted(glob.glob(os.path.join(shipped_dir, "*.json"))):
        name = "app/scenarios/" + os.path.basename(path)
        try:
            scenario = rollout.load(path)
        except (OSError, ValueError):
            continue
        specs.append(("release", f"{name} [working tree]", scenario, "new"))
        for position in rollout.upgrade_positions(scenario, limit=6):
            specs.append(("release", f"{name} [upgrade after step {position}]", rollout.with_upgrade(scenario, position), "new"))

    own = sorted(glob.glob(os.path.join(ROOT, "work", "scenarios", "*.json")))
    have_old = rollout.OLD_APP != rollout.NEW_APP
    replaces = False
    for path in own:
        name = "work/scenarios/" + os.path.basename(path)
        try:
            scenario = rollout.load(path)
        except (OSError, ValueError) as problem:
            hard.append(f"{name} cannot be read: {problem}")
            continue
        replaces = replaces or any(step.get("do") == "upgrade" for step in scenario["steps"])
        specs.append(("scenarios", name, scenario, "new"))
        if have_old:
            specs.append(("reproduce", name, scenario, "old"))

    # One run first: if the working tree does not start or stops answering, say so once
    # instead of waiting for every scenario to time out.
    canary = next((spec for spec in specs if spec[3] == "new"), None)
    if canary:
        first = rollout.run_all([canary[1:]], bins)[0]
        if any(p.startswith(("could not start", "timed out")) for p in first["problems"]):
            return ["the working tree does not run " + canary[1] + ": " + first["problems"][0]] + first["problems"][1:8], []
    outcomes = rollout.run_all(
        [(label, scenario, release) for _, label, scenario, release in specs], bins, deadline=time.time() + BUDGET_SECONDS
    )
    skipped = sum(1 for outcome in outcomes if outcome["problems"] == ["not run: out of time"])
    if skipped:
        hard.append(f"{skipped} scenario runs were not started: the others used up {BUDGET_SECONDS} s. Find what is slow.")
    for (group, label, _, _), outcome in zip(specs, outcomes):
        problems = outcome["problems"]
        if problems == ["not run: out of time"]:
            continue
        if group == "reproduce":
            if not problems:
                soft.append(f"{label} also passes on the shipped release, so it does not show the defect")
            continue
        if problems:
            hard.append(f"{label} fails: " + problems[0])
            hard += ["  " + p for p in problems[1:4]] + outcome["digest"]
    if not own:
        soft.append("work/scenarios/ is empty: add a scenario that fails on the shipped release and passes on your change")
    elif have_old and not replaces:
        soft.append(
            'no scenario in work/scenarios/ has an {"do": "upgrade"} step: show that state the shipped release '
            "left behind is handled when your change replaces it"
        )
    return hard, soft


def soft_count():
    try:
        with open(SOFT_COUNTER, encoding="utf-8") as handle:
            return int(handle.read().strip() or 0)
    except (OSError, ValueError):
        return 0


def main(argv):
    hook = "--hook" in argv
    task = os.path.join(ROOT, "task.md")
    for index, arg in enumerate(argv):
        if arg == "--task" and index + 1 < len(argv):
            task = argv[index + 1]

    hard, soft, notes = [], [], []
    signal.signal(signal.SIGTERM, rollout.stop_everything)
    if os.path.exists(NO_HARNESS):
        # prepare.sh found that the shipped release cannot be run here (see work/start.txt).
        # Nothing the agent does can change that, so only the files it writes are checked.
        notes.append("the services cannot be run in this environment (work/start.txt); only the report and ledger are checked")
    else:
        try:
            bins = rollout.build({rollout.OLD_APP, rollout.NEW_APP})
        except RuntimeError as problem:
            print("BLOCKING\nbuild: " + "\n  ".join(str(problem).splitlines()[:16]))
            return 1
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            tests = pool.map(run_tests, SERVICES)
            try:
                scenario_hard, soft = scenario_checks(bins)
            except RuntimeError as problem:
                scenario_hard, soft = [f"scenarios could not run: {problem}"], []
            for found in tests:
                hard += found
        hard += scenario_hard
        hard += check_crash_points()
    report_hard, report_soft = check_report(task)
    hard += report_hard
    soft += report_soft
    hard += check_ledger()

    asked = soft_count()
    soft_blocks = bool(soft) and asked < SOFT_LIMIT
    if hook and soft_blocks:
        try:
            os.makedirs(os.path.dirname(SOFT_COUNTER), exist_ok=True)
            with open(SOFT_COUNTER, "w", encoding="utf-8") as handle:
                handle.write(str(asked + 1))
        except OSError:
            pass
    lines = []
    if hard or soft_blocks:
        lines.append("BLOCKING")
        lines += hard
        if soft_blocks:
            lines += soft
    if soft and not soft_blocks:
        lines += ["NOTED (no longer blocking)"] + soft
    if notes:
        lines += ["NOTED"] + notes
    if not (hard or soft_blocks):
        lines.insert(0, "check: all clear" if not (soft or notes) else "check: nothing blocking")
    if len(lines) > 40:
        lines = lines[:39] + [f"... {len(lines) - 39} more lines"]
    print("\n".join(lines))
    return 1 if (hard or soft_blocks) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
