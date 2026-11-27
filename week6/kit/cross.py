#!/usr/bin/env python3
"""Check two independent answers to the same ticket against each other. No model is called.

    python3 kit/cross.py --b <second workspace> [--out work/cross]

The first workspace is the one this file lives in ("a"); the second ("b") is a clone in which
another agent did the whole job on its own. What happens:

  repairs   Every scenario either agent wrote that fails on the shipped release and passes on
            at least one of the two repairs counts as evidence. Each is run on both repairs,
            plainly, with the shipped release taking every step up to the last drain, and
            with every service restarted before the last drain. A scenario that posts a
            raw bus message the shipped release refuses is left out: it tests one repair's
            own message format. The shipped
            scenarios are run on both, alone and across a release replacement. Every
            failure is listed for the first workspace's author. Which repair is handed in
            is decided on less: "a" unless "b" is better on objective grounds (better()).
  reports   The files under out/ are compared value by value, ignoring the order of lists:
            those of the two workspaces and, with --c, one made from the raw files without
            the kit's database. See compare_reports for what settles a difference.

Written to <out>/:
  decision.env   BEST=a|b  A_FAILS=<n>  B_FAILS=<n>  A_USABLE=0|1  B_USABLE=0|1
                 A_CHANGED=0|1  B_CHANGED=0|1  REPORTS=same|settled|decide|none
  fix.txt        for the first workspace's author: the runs its repair fails
  reports.txt    how the reports differ
  decided/       with REPORTS=settled: the report files to hand in
  summary.txt    everything above, for the log
Copied to <first workspace>/work/cross/, for its author to compare with: the other repair as a
diff against the shipped release (other.diff), the other ledger, the other scenarios, and each
run its own repair fails as the scenario that was played (run-<n>.json). The other report and its script go to
<first workspace>/work/cross/.
"""

import argparse
import copy
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


def with_bus_refs(scenario):
    """A copy in which every raw bus step has a ref, so that the router's answer to it is in the
    result. Nothing else about the run changes."""
    changed = copy.deepcopy(scenario)
    for index, step in enumerate(changed["steps"]):
        if isinstance(step, dict) and step.get("do") == "bus" and "ref" not in step:
            step["ref"] = f"_bus{index}"
    return changed


def private_bus_step(scenario, old, passing):
    """A scenario that posts a raw bus message which the shipped release refuses and a repair it
    passes on accepts depends on that repair's own message format: api and router of one repair
    agree on it, another repair has no reason to. Returns a short description of the first such
    step, or "" if there is none."""
    def statuses(outcome):
        return ((outcome or {}).get("result") or {}).get("statuses") or {}
    before = statuses(old)
    for index, step in enumerate(scenario["steps"]):
        if not (isinstance(step, dict) and step.get("do") == "bus"):
            continue
        ref = step.get("ref", f"_bus{index}")
        refused = before.get(ref)
        if not isinstance(refused, int) or refused < 400:
            continue
        for outcome in passing:
            accepted = statuses(outcome).get(ref)
            if isinstance(accepted, int) and accepted < 300:
                message = step.get("message")
                kind = (message.get("type") or message.get("kind") or "") if isinstance(message, dict) else ""
                return f"step {index + 1}{' ' + str(kind) if kind else ''}: {refused} as shipped, {accepted} on the repair"
    return ""


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

    # 1. Every scenario either agent wrote, on the shipped release and on each repair. One counts
    #    if it fails on the shipped release and passes on at least one repair: then it shows
    #    something a repair of this ticket can do. That includes a scenario whose own author
    #    could not make it pass when the other repair does.
    authored = [(author, file_name, path, scenario) for author in roots for file_name, path, scenario in scenarios_of(roots[author])]
    specs = []
    for author, file_name, _, scenario in authored:
        probe = with_bus_refs(scenario)
        specs.append(((author, file_name, "old"), probe, "old", None))
        for name in usable:
            specs.append(((author, file_name, name), probe, "new", apps[name]))
    results = rollout.run_all([(str(i), s[1], s[2], s[3]) for i, s in enumerate(specs)], bins, deadline=deadline)
    outcomes = {spec[0]: outcome for spec, outcome in zip(specs, results)}
    valid = []
    for author, file_name, path, scenario in authored:
        old = outcomes.get((author, file_name, "old"))
        runs = {name: outcomes.get((author, file_name, name)) for name in usable}
        if old is None or rollout.not_run(old) or not runs or any(r is None or rollout.not_run(r) for r in runs.values()):
            continue
        if not old["problems"]:
            notes.append(f"{author}'s {file_name} passes on the shipped release too: not used")
            continue
        private = private_bus_step(scenario, old, [r for r in runs.values() if not r["problems"]])
        if private:
            notes.append(f"{author}'s {file_name} posts a bus message the shipped release refuses ({private}): "
                         "a format of one repair's own, so it says nothing about the other; not used")
            continue
        if all(r["problems"] for r in runs.values()):
            first = next(iter(runs.values()))["problems"][0][:120]
            notes.append(f"{author}'s {file_name} fails on every repair, so it decides nothing here ({first})")
            scores[author].setdefault("open", []).append({"scenario": file_name, "path": path, "problem": first})
            continue
        valid.append((author, file_name, path, scenario))
        for name, outcome in runs.items():
            if outcome["problems"]:
                scores[name]["fails"].append({"scenario": file_name, "author": author, "how": "as written", "path": path,
                                              "played": scenario, "problem": outcome["problems"][0][:200]})
            else:
                scores[name]["passed"] += 1

    # 2. The variants of every scenario that counts, on every usable repair; and the shipped
    #    scenarios, alone and across a replacement.
    specs = []
    for author, file_name, path, scenario in valid:
        late = rollout.handed_over(scenario)
        again = rollout.restarted(scenario)
        for name in usable:
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
    """The name of the repair to hand in: "a", the main solver's, unless "b" is better.

    "b" is better on objective grounds when "a" does not build or changed nothing, breaks more
    of the scenarios shipped with the release, or fails more scenarios that its own author
    wrote (and the other repair passes) than "b" fails of its own.

    Failing the other author's scenarios is weaker evidence: such a scenario is an opinion
    about the ticket, and counting them let whoever wrote more of them win. It decides only
    when it is one-sided: "b" passes every scenario "a" wrote and "a" fails some that "b"
    wrote. Then "b" does everything either author thought to test and "a" does not. The main
    author has been shown those runs first and has left them failing.

    The hand-over and restart variants never decide: they ask for more than a judge does
    about one run in three.
    """
    def count(name, author):
        return sum(1 for f in scores[name]["fails"] if f["how"] == "as written" and author(f["author"]))

    def rank(name):
        score = scores[name]
        shipped = sum(1 for f in score["fails"] if f["author"] == "shipped")
        own = count(name, lambda author: author == name)
        return (not score["usable"], not score["changed"], shipped, own, name)

    best = min(scores, key=rank)
    if best == "a" and "b" in scores and rank("a")[:4] == rank("b")[:4]:
        a_fails_theirs = count("a", lambda author: author == "b")
        b_fails_theirs = count("b", lambda author: author == "a")
        if a_fails_theirs > 0 and b_fails_theirs == 0:
            return "b"
    return best


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


def load_reports(roots):
    """{file name: {workspace name: (path, content)}} for the files under each workspace's out/.
    JSON is read into a canonical form; a file that cannot be read is left out."""
    found = {}
    for name, root in roots.items():
        for path in sorted(glob.glob(os.path.join(root, "out", "*"))):
            if not os.path.isfile(path):
                continue
            base = os.path.basename(path)
            try:
                with open(path, encoding="utf-8") as handle:
                    content = canonical(json.load(handle)) if base.endswith(".json") else handle.read()
            except (OSError, ValueError):
                continue
            found.setdefault(base, {})[name] = (path, content)
    return found


def agreeing(values):
    """[[names with equal values], ...] for {name: value}, in name order."""
    groups = []
    for name in sorted(values):
        for group in groups:
            if values[group[0]] == values[name]:
                group.append(name)
                break
        else:
            groups.append([name])
    return groups


def settle(values):
    """Which workspace's value to hand in for one thing that was reported, given {name: value}
    from "a" and "b" (both made with the kit's evidence database) and "c" (made from the raw
    files, without it). Returns (name, settled?, why).

    Two ways to the answer that share nothing settle it: where "c" agrees with "a" or with
    "b", that value stands. Agreement between "a" and "b" alone does not, because they read
    the same database; and nothing is ever decided by counting.
    """
    groups = agreeing(values)
    names = sorted(values)
    if len(groups) == 1:
        return names[0], True, "all the same"
    with_c = next((group for group in groups if "c" in group), None)
    if with_c and len(with_c) > 1:
        other = "a" if "a" in with_c else with_c[0]
        return other, True, f"c, made from the raw files, agrees with {other}"
    if "a" not in values:
        return ("c" if "c" in values else names[0]), True, "a has none"
    return "a", False, "they differ and nothing settles it"


def compare_reports(roots, decided_dir=None):
    """Compare the reports of up to three workspaces, part by part.

    A JSON report that is an object is compared key by key (its list of entries, its totals,
    its counts). For each key settle() says whose value stands. A key whose value is a list or
    an object and that nothing settles needs someone to work it out. A single number that
    nothing settles does not: there "a" stands, because the one such number in these reports
    is a count of corrupted rows, which the kit's loader takes from the evidence contract and
    a one-off parser tends to get slightly wrong, and one figure is not worth a session.

    Returns (state, lines):
      none     nobody wrote a report
      same     "a" has a report and nothing about it is to change
      settled  the report to hand in differs from "a"'s and is written to decided_dir
      decide   a list or an object in the report is in dispute
    """
    files = load_reports(roots)
    if not files:
        return "none", ["no workspace has a file under out/"]
    order = {"none": 0, "same": 1, "settled": 2, "decide": 3}
    worst, lines = "none", []
    for base, owners in sorted(files.items()):
        contents = {name: content for name, (_, content) in owners.items()}
        told = ", ".join("=".join(group) for group in agreeing(contents))
        whole, whole_settled, why = settle(contents)
        by_key = base.endswith(".json") and "a" in contents and all(isinstance(c, dict) for c in contents.values())
        state, merged = "same", None
        if len(agreeing(contents)) == 1:
            lines.append(f"out/{base}: {told} ({len(contents)} report(s), all the same)")
            state = "same" if "a" in contents else "settled"
            merged = None if "a" in contents else contents[whole]
        elif not by_key:
            lines.append(f"out/{base}: {told} ({why})")
            if whole_settled:
                state, merged = ("same", None) if whole == "a" else ("settled", contents[whole])
            else:
                state = "decide"
        else:
            lines.append(f"out/{base}: {told}; part by part:")
            merged = dict(contents["a"])
            for key in sorted(set().union(*contents.values())):
                values = {name: content[key] for name, content in contents.items() if key in content}
                name, settled, key_why = settle(values)
                plain = not any(isinstance(value, (list, dict)) for value in values.values())
                if len(agreeing(values)) == 1 and len(values) == len(contents):
                    continue
                if settled or plain:
                    keep = name if settled else ("a" if "a" in values else name)
                    if keep in values:
                        merged[key] = values[keep]
                    note = key_why if settled else "a single figure nothing settles: a's stands"
                    lines.append(f"  {key}: {', '.join('='.join(g) for g in agreeing(values))} ({note}; taking {keep}'s)")
                else:
                    state = "decide"
                    lines.append(f"  {key}: {', '.join('='.join(g) for g in agreeing(values))} (in dispute: {key_why})")
            if state != "decide":
                state = "same" if merged == contents["a"] else "settled"
                if state == "same":
                    merged = None
        if state == "settled" and decided_dir and merged is not None:
            os.makedirs(decided_dir, exist_ok=True)
            with open(os.path.join(decided_dir, base), "w", encoding="utf-8") as handle:
                if base.endswith(".json"):
                    json.dump(merged, handle, indent=2)
                else:
                    handle.write(merged)
        groups = agreeing(contents)
        if state == "decide" and base.endswith(".json"):
            for i, first in enumerate(groups):
                for second in groups[i + 1:]:
                    x, y = first[0], second[0]
                    lines.append(f"  {x} against {y} (in the lines below, \"a\" stands for {x} and \"b\" for {y}):")
                    lines += ["    " + line for line in differences(contents[x], contents[y])[:26]]
        if order[state] > order[worst]:
            worst = state
    return worst, lines


# --- main -----------------------------------------------------------------------------


def describe(scores, best, notes):
    lines = [f"repairs: better is {best}"]
    for name in sorted(scores):
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
    parser.add_argument("--c", help="a third folder that holds only a report (out/) and its script (report.py), made from the raw files")
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
    report_roots = dict(roots)
    if args.c and os.path.isdir(args.c):
        report_roots["c"] = os.path.abspath(args.c)
    decided = os.path.join(args.out, "decided")
    shutil.rmtree(decided, ignore_errors=True)
    state, report_lines = compare_reports(report_roots, decided)

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
    for item in scores["a"].get("open", [])[:4]:
        fix.append(f"- your own scenario work/scenarios/{item['scenario']} fails on your repair and on theirs: {item['problem']}\n"
                   "   either a requirement neither repair meets yet, or the scenario expects more than the ticket asks")
    with open(os.path.join(args.out, "fix.txt"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(fix) + ("\n" if fix else ""))

    # The other report and its script, next to ours, for whoever has to decide between them.
    mine = os.path.join(roots["a"], "work", "cross")
    os.makedirs(mine, exist_ok=True)
    for name, root in report_roots.items():
        if name == "a":
            continue
        for path in glob.glob(os.path.join(root, "out", "*")):
            if os.path.isfile(path):
                base, ext = os.path.splitext(os.path.basename(path))
                shutil.copy(path, os.path.join(mine, f"{base}-{name}{ext}"))
        for script in (os.path.join(root, "work", "report.py"), os.path.join(root, "report.py")):
            if os.path.isfile(script):
                shutil.copy(script, os.path.join(mine, f"report-{name}.py"))
                break
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
