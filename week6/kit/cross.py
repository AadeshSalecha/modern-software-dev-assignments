#!/usr/bin/env python3
"""Check two independent answers to the same ticket against each other. No model is called.

    python3 kit/cross.py --b <second workspace> [--out work/cross]

The first workspace is the one this file lives in ("a"); the second ("b") is a clone in which
another agent did the whole job on its own. What happens:

  repairs   Every scenario either agent wrote that fails on the shipped release and passes on
            its author's repair counts as evidence. Each is run on both repairs, plainly and
            with the shipped release taking every step up to the last drain. The shipped
            scenarios are run on both, alone and across a release replacement. The repair
            with fewer failures is the better one; a tie goes to "a".
  reports   The files under out/ are compared value by value, ignoring the order of lists.

Written to <out>/:
  decision.env   BEST=a|b  A_FAILS=<n>  B_FAILS=<n>  A_USABLE=0|1  B_USABLE=0|1
                 A_CHANGED=0|1  B_CHANGED=0|1  REPORTS=same|differ|only_a|only_b|none
  fix.txt        for the first workspace's author: the runs its repair fails
  reports.txt    how the two reports differ
  summary.txt    everything above, for the log
Copied to <first workspace>/work/cross/, for its author to compare with: the other repair as a
diff against the shipped release (other.diff), the other ledger, the other scenarios, and each
run its own repair fails as the scenario that was played (run-<n>.json). The other report and its script go to
<first workspace>/work/cross/.
"""

import argparse
import difflib
import glob
import json
import os
import shutil
import sys
import time

KIT = os.path.dirname(os.path.abspath(__file__))
A_ROOT = os.path.dirname(KIT)
sys.path.insert(0, KIT)
import rollout  # noqa: E402

BUDGET_SECONDS = 100


def scenarios_of(root):
    found = []
    for path in sorted(glob.glob(os.path.join(root, "work", "scenarios", "*.json"))):
        try:
            found.append((os.path.basename(path), path, rollout.load(path)))
        except (OSError, ValueError):
            continue
    return found


SKIP_DIRS = ("__pycache__", ".build", "node_modules", "dist", "build")
SKIP_FILES = ("AGENTS.md", "CLAUDE.md")
DIFF_LIMIT = 60000  # characters of other.diff


def service_files(base):
    """Relative paths of the files under base/{api,router,worker}."""
    found = set()
    for service in ("api", "router", "worker"):
        for folder, dirs, files in os.walk(os.path.join(base, service)):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for name in files:
                if name not in SKIP_FILES and not name.endswith((".pyc", ".db", ".sqlite")):
                    found.add(os.path.relpath(os.path.join(folder, name), base))
    return found


def read_bytes(path):
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError:
        return None


def changed_files(root):
    """Files under the workspace's services that differ from the shipped release: [(path, old, new)],
    old or new None for a file that only one side has."""
    old_base = os.path.join(A_ROOT, ".pristine", "app", "services")
    new_base = os.path.join(root, "app", "services")
    out = []
    for path in sorted(service_files(old_base) | service_files(new_base)):
        old, new = read_bytes(os.path.join(old_base, path)), read_bytes(os.path.join(new_base, path))
        if old != new:
            out.append((path, old, new))
    return out


def changed(root):
    """True if the workspace's services differ from the shipped release."""
    return bool(changed_files(root))


def diff_text(root):
    """The workspace's change to the services as a unified diff against the shipped release."""
    parts = []
    for path, old, new in changed_files(root):
        try:
            before = (old or b"").decode("utf-8").splitlines(keepends=True)
            after = (new or b"").decode("utf-8").splitlines(keepends=True)
        except UnicodeDecodeError:
            parts.append(f"(binary file {path} differs)\n")
            continue
        parts.append("".join(difflib.unified_diff(
            before, after, f"shipped/app/services/{path}", f"theirs/app/services/{path}", n=4)))
    text = "".join(part if part.endswith("\n") or not part else part + "\n" for part in parts)
    if len(text) > DIFF_LIMIT:
        text = text[:DIFF_LIMIT] + "\n(cut here: the diff is longer)\n"
    return text


def hand_over_material(best_root, other_root):
    """Put the other engineer's work where the better repair's author can read it."""
    target = os.path.join(best_root, "work", "cross")
    os.makedirs(os.path.join(target, "other-scenarios"), exist_ok=True)
    with open(os.path.join(target, "other.diff"), "w", encoding="utf-8") as handle:
        handle.write(diff_text(other_root) or "(the other engineer changed nothing under app/services)\n")
    ledger = os.path.join(other_root, "work", "ledger.md")
    if os.path.isfile(ledger):
        shutil.copy(ledger, os.path.join(target, "other-ledger.md"))
    for name, path, _ in scenarios_of(other_root):
        shutil.copy(path, os.path.join(target, "other-scenarios", name))


def judge_repairs(roots, deadline):
    """Returns (scores, notes). scores[name] = {"usable", "fails": [...], "passed": n}."""
    notes = []
    apps = {name: os.path.join(root, "app") for name, root in roots.items()}
    scores = {name: {"usable": True, "changed": changed(roots[name]), "fails": [], "passed": 0} for name in roots}
    bins = {}
    try:
        bins.update(rollout.build({rollout.OLD_APP}))
    except RuntimeError as problem:
        return scores, [f"the shipped release does not build here, so the repairs cannot be compared: {str(problem)[:200]}"]
    for name, app in apps.items():
        try:
            bins.update(rollout.build({app}))
        except RuntimeError as problem:
            scores[name]["usable"] = False
            scores[name]["fails"].append({"scenario": "(build)", "author": "-", "how": "build", "problem": str(problem).splitlines()[0][:200]})
    usable = [name for name in roots if scores[name]["usable"]]

    # 1. Which scenarios count: fail on the shipped release, pass on their author's repair.
    authored = [(author, file_name, path, scenario) for author in roots for file_name, path, scenario in scenarios_of(roots[author])]
    specs = []
    for author, file_name, _, scenario in authored:
        specs.append((f"{author}:{file_name}:old", scenario, "old"))
        if scores[author]["usable"]:
            specs.append((f"{author}:{file_name}:own", scenario, "new", apps[author]))
    outcomes = {o["label"]: o for o in rollout.run_all(specs, bins, deadline=deadline)}
    valid = []
    for author, file_name, path, scenario in authored:
        old = outcomes.get(f"{author}:{file_name}:old")
        own = outcomes.get(f"{author}:{file_name}:own")
        if old is None or own is None or rollout.not_run(old) or rollout.not_run(own):
            continue
        if not old["problems"]:
            notes.append(f"{author}'s {file_name} passes on the shipped release too: not used")
        elif own["problems"]:
            notes.append(f"{author}'s {file_name} fails on its author's own repair: not used")
        else:
            valid.append((author, file_name, path, scenario))

    # 2. Every valid scenario, and its hand-over variant, on every usable repair; and the
    #    shipped scenarios, alone and across a replacement.
    specs = []
    for author, file_name, path, scenario in valid:
        late = rollout.handed_over(scenario)
        again = rollout.restarted(scenario)
        for name in usable:
            if name != author:
                specs.append(((name, author, file_name, "as written", path), scenario, "new", apps[name]))
            if late is not None:
                specs.append(((name, author, file_name, "handed over before the last drain", path), late, "new", apps[name]))
            if again is not None:
                specs.append(((name, author, file_name, "every service restarted before the last drain", path), again, "new", apps[name]))
    for path in sorted(glob.glob(os.path.join(rollout.OLD_APP, "scenarios", "*.json"))):
        scenario = rollout.load(path)
        for name in usable:
            specs.append(((name, "shipped", os.path.basename(path), "as written", path), scenario, "new", apps[name]))
            for position in rollout.upgrade_positions(scenario, limit=3):
                specs.append(((name, "shipped", os.path.basename(path), f"release replaced after step {position}", path),
                              rollout.with_upgrade(scenario, position), "new", apps[name]))
    results = rollout.run_all([(str(i), s[1], s[2], s[3]) for i, s in enumerate(specs)], bins, deadline=deadline)
    for spec, outcome in zip(specs, results):
        name, author, file_name, how, path = spec[0]
        if rollout.not_run(outcome):
            continue
        if outcome["problems"]:
            scores[name]["fails"].append({"scenario": file_name, "author": author, "how": how, "path": path,
                                          "played": spec[1], "problem": outcome["problems"][0][:200]})
        else:
            scores[name]["passed"] += 1
    return scores, notes


def better(scores):
    """The name of the better repair. Unusable or unchanged loses; then fewer failures; then "a"."""
    def rank(name):
        score = scores[name]
        shipped = sum(1 for f in score["fails"] if f["author"] == "shipped")
        return (not score["usable"], not score["changed"], shipped, len(score["fails"]), name)
    return min(scores, key=rank)


# --- reports --------------------------------------------------------------------------


def canonical(value):
    """The value with lists in a fixed order, so that two reports differ only if they say different things."""
    if isinstance(value, dict):
        return {key: canonical(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return sorted((canonical(item) for item in value), key=lambda item: json.dumps(item, sort_keys=True))
    return value


def differences(a, b, where="", limit=6):
    """Lines that say how two JSON values differ."""
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            path = f"{where}.{key}" if where else str(key)
            if key not in a:
                out.append(f"{path}: only in b ({json.dumps(b[key])[:80]})")
            elif key not in b:
                out.append(f"{path}: only in a ({json.dumps(a[key])[:80]})")
            else:
                out += differences(a[key], b[key], path, limit)
        return out
    if isinstance(a, list) and isinstance(b, list):
        text_a = {json.dumps(item, sort_keys=True): item for item in a}
        text_b = {json.dumps(item, sort_keys=True): item for item in b}
        only_a = [text_a[k] for k in text_a if k not in text_b]
        only_b = [text_b[k] for k in text_b if k not in text_a]
        if only_a or only_b:
            out.append(f"{where or 'list'}: {len(a)} entries in a, {len(b)} in b; {len(set(text_a) & set(text_b))} identical, "
                       f"{len(only_a)} only in a, {len(only_b)} only in b")
            for label, items in (("only in a", only_a), ("only in b", only_b)):
                for item in items[:limit]:
                    out.append(f"  {label}: {json.dumps(item, sort_keys=True)[:230]}")
                if len(items) > limit:
                    out.append(f"  ... and {len(items) - limit} more {label}")
        return out
    if a != b:
        out.append(f"{where or 'value'}: a has {json.dumps(a)[:80]}, b has {json.dumps(b)[:80]}")
    return out


def compare_reports(roots):
    """Returns (state, lines). state: same, differ, only_a, only_b or none."""
    files = {}
    for name, root in roots.items():
        for path in sorted(glob.glob(os.path.join(root, "out", "*"))):
            if os.path.isfile(path):
                files.setdefault(os.path.basename(path), {})[name] = path
    if not files:
        return "none", ["neither workspace has a file under out/"]
    lines, states = [], set()
    for base, owners in sorted(files.items()):
        loaded = {}
        for name, path in owners.items():
            try:
                with open(path, encoding="utf-8") as handle:
                    loaded[name] = canonical(json.load(handle)) if base.endswith(".json") else handle.read()
            except (OSError, ValueError):
                lines.append(f"out/{base} in {name} cannot be read")
        if set(loaded) == {"a", "b"}:
            if loaded["a"] == loaded["b"]:
                states.add("same")
                lines.append(f"out/{base}: the two reports are identical")
            else:
                states.add("differ")
                found = differences(loaded["a"], loaded["b"]) if base.endswith(".json") else ["the text differs"]
                lines += [f"out/{base}: the two reports differ"] + ["  " + line for line in found[:40]]
        elif "a" in loaded:
            states.add("only_a")
            lines.append(f"out/{base}: only a has it")
        elif "b" in loaded:
            states.add("only_b")
            lines.append(f"out/{base}: only b has it")
    for state in ("differ", "only_b", "only_a", "same"):
        if state in states:
            return state, lines
    return "none", lines


# --- main -----------------------------------------------------------------------------


def describe(scores, best, notes):
    lines = [f"repairs: better is {best}"]
    for name in ("a", "b"):
        score = scores[name]
        lines.append(f"  {name}: {'usable' if score['usable'] else 'does not build'}, "
                     f"{'changed' if score['changed'] else 'unchanged from the shipped release'}, "
                     f"{score['passed']} runs passed, {len(score['fails'])} failed")
        for fail in score["fails"][:6]:
            lines.append(f"    - {fail['author']}'s {fail['scenario']} ({fail['how']}): {fail['problem'][:150]}")
    return lines + ["  note: " + note for note in notes[:6]]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--b", required=True)
    parser.add_argument("--out", default=os.path.join(A_ROOT, "work", "cross"))
    parser.add_argument("--repairs-only", action="store_true",
                        help="score the repairs again and write decision.env and summary.txt; copy nothing")
    args = parser.parse_args(argv)
    roots = {"a": A_ROOT, "b": os.path.abspath(args.b)}
    os.makedirs(args.out, exist_ok=True)

    try:
        scores, notes = judge_repairs(roots, time.time() + BUDGET_SECONDS)
    except Exception as problem:  # noqa: BLE001 - whatever happens, run.sh needs a decision and the reports compared
        scores = {name: {"usable": True, "changed": changed(roots[name]), "fails": [], "passed": 0} for name in roots}
        notes = [f"the repairs could not be compared ({type(problem).__name__}: {str(problem)[:160]}); a is kept unless it changed nothing"]
    best = better(scores)
    other = "b" if best == "a" else "a"
    if args.repairs_only:
        with open(os.path.join(args.out, "decision.env"), "w", encoding="utf-8") as handle:
            handle.write(f"BEST={best}\nA_FAILS={len(scores['a']['fails'])}\nB_FAILS={len(scores['b']['fails'])}\n"
                         f"A_USABLE={int(scores['a']['usable'])}\nB_USABLE={int(scores['b']['usable'])}\n")
        summary = describe(scores, best, notes)
        with open(os.path.join(args.out, "summary.txt"), "w", encoding="utf-8") as handle:
            handle.write("\n".join(summary) + "\n")
        print("\n".join(summary))
        return 0
    state, report_lines = compare_reports(roots)

    # For the main solver, whose session is resumed to compare the two repairs: the runs its
    # own repair fails, each as the scenario that was played.
    fails = scores["a"]["fails"]
    target = os.path.join(roots["a"], "work", "cross")
    os.makedirs(target, exist_ok=True)
    fix = []
    for index, fail in enumerate(fails[:8], 1):
        if fail["author"] == "-":
            fix.append(f"{index}. your repair does not build: {fail['problem']}")
            continue
        whose = {"shipped": "a scenario shipped with the release", "a": "your own scenario"}.get(
            fail["author"], "the other engineer's scenario")
        line = f"{index}. {whose} {fail['scenario']}, {fail['how']}: {fail['problem']}"
        if fail.get("played"):
            # The scenario exactly as it was played, variant included, so the run can be repeated.
            name = f"run-{index}.json"
            with open(os.path.join(target, name), "w", encoding="utf-8") as handle:
                json.dump(fail["played"], handle, indent=1)
            line += f"\n   the scenario as it was played is work/cross/{name}; repeat the run with: python3 kit/rollout.py work/cross/{name}"
        fix.append(line)
    with open(os.path.join(args.out, "fix.txt"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(fix) + ("\n" if fix else ""))

    # The other report and its script, next to ours, for whoever has to decide between them.
    mine = os.path.join(roots["a"], "work", "cross")
    os.makedirs(mine, exist_ok=True)
    for path in glob.glob(os.path.join(roots["b"], "out", "*")):
        if os.path.isfile(path):
            base, ext = os.path.splitext(os.path.basename(path))
            shutil.copy(path, os.path.join(mine, f"{base}-b{ext}"))
    script = os.path.join(roots["b"], "work", "report.py")
    if os.path.isfile(script):
        shutil.copy(script, os.path.join(mine, "report-b.py"))
    with open(os.path.join(args.out, "reports.txt"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(report_lines) + "\n")

    try:
        hand_over_material(roots["a"], roots["b"])
    except OSError as problem:
        notes.append(f"the other engineer's work could not be copied over: {problem}")

    with open(os.path.join(args.out, "decision.env"), "w", encoding="utf-8") as handle:
        handle.write(f"BEST={best}\n"
                     f"A_FAILS={len(scores['a']['fails'])}\nB_FAILS={len(scores['b']['fails'])}\n"
                     f"A_USABLE={int(scores['a']['usable'])}\nB_USABLE={int(scores['b']['usable'])}\n"
                     f"A_CHANGED={int(scores['a']['changed'])}\nB_CHANGED={int(scores['b']['changed'])}\n"
                     f"REPORTS={state}\n")
    summary = describe(scores, best, notes)
    summary += [f"reports: {state}"] + ["  " + line for line in report_lines[:14]]
    with open(os.path.join(args.out, "summary.txt"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(summary) + "\n")
    print("\n".join(summary))
    return 0


if __name__ == "__main__":
    import signal

    signal.signal(signal.SIGTERM, rollout.stop_everything)
    sys.exit(main())
