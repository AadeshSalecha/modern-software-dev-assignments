#!/usr/bin/env python3
"""Judge a run of the setup on INC-2318.

    python3 judge.py <workspace week6 dir> [--out judge.json] [--port-base 26000] [--port-span 4000]
    python3 judge.py --shipped            the shipped release as the candidate (self-check)

The workspace is a copy of week6/ in which `./run.sh task.md` has run with this folder's
task.md and incident/ in place. Scored the way the assignment scores a run:

  repair  api, router and worker from the workspace are put into a clean copy of the release
          and played through scenarios.json plus the three shipped scenarios.
          repair = share of incident scenarios passed x share of the others passed
  impact  <workspace>/out/impact.json against truth.json.
          impact = 0.6 x F1 on affected entries + 0.4 x share of figures exactly right
          An entry is one (endpoint_id, event_id) pair: an event in the `event_ids` of an
          item of `missed`. The figures are each currency in totals_minor (truth or report),
          skipped_rows, and for each endpoint (truth or report) its list of
          (switched_off_at, switched_on_at) pairs, one per item of `missed`.

The scenarios run with week6/kit/rollout.py from the repository, which also applies its
contract checks to every run.
"""

import argparse
import glob
import json
import os
import random
import shutil
import socket
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
WEEK6 = os.path.join(REPO, "week6")
SERVICES = ("api", "router", "worker")
LEAVE = shutil.ignore_patterns(".build", "__pycache__", "node_modules", "state", ".pytest_cache", "_deprecated",
                               "sdk", "legacy", "AGENTS.md", "CLAUDE.md")


def trees(workspace, tmp):
    """(clean release, release with the workspace's three services)"""
    clean = os.path.join(tmp, "clean-app")
    os.makedirs(clean)
    for part in ("services", "bin", "scenarios", "contracts"):
        shutil.copytree(os.path.join(WEEK6, "app", part), os.path.join(clean, part), ignore=LEAVE)
    if workspace is None:
        return clean, clean
    scored = os.path.join(tmp, "scored-app")
    shutil.copytree(clean, scored)
    for service in SERVICES:
        target = os.path.join(scored, "services", service)
        shutil.rmtree(target)
        source = os.path.join(workspace, "app", "services", service)
        if os.path.isdir(source):
            shutil.copytree(source, target, ignore=LEAVE)
    return clean, scored


def keep_ports_within(rollout, span):
    """The kit picks a port base anywhere in 20000 ports above --port-base. Keep it within `span`."""

    def free_port_base(start, taken):
        bases = list(range(start, start + span, 10))
        random.shuffle(bases)
        for base in bases:
            if base in taken:
                continue
            try:
                for offset in rollout.replaylib.OFFSET.values():
                    with socket.socket() as probe:
                        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        probe.bind(("127.0.0.1", base + offset))
            except OSError:
                continue
            return base
        raise RuntimeError("no free ports for a deployment")

    rollout.free_port_base = free_port_base


def repair_score(workspace, port_base, port_span, jobs=4):
    tmp = tempfile.mkdtemp(prefix="inc2318-judge-")
    try:
        clean, scored = trees(workspace, tmp)
        os.environ["KIT_OLD_APP"], os.environ["KIT_NEW_APP"] = clean, scored
        sys.path.insert(0, os.path.join(WEEK6, "kit"))
        import rollout

        keep_ports_within(rollout, port_span)
        with open(os.path.join(HERE, "scenarios.json"), encoding="utf-8") as handle:
            scenarios = [(category, scenario) for category, scenario in json.load(handle)]
        for path in sorted(glob.glob(os.path.join(clean, "scenarios", "*.json"))):
            scenarios.append(("regressions", rollout.load(path)))
        categories = {name: {"passed": 0, "total": 0, "failed": []} for name in ("incident", "regressions", "compat")}
        classes = {}
        try:
            bins = rollout.build({clean, scored})
        except RuntimeError as problem:
            for category, scenario in scenarios:
                categories[category]["total"] += 1
                categories[category]["failed"].append({"name": scenario["name"], "problems": ["does not build"]})
            return categories, 0.0, str(problem)[:400]
        outcomes = rollout.run_all([(s["name"], s, "new") for _, s in scenarios], bins, jobs=jobs, port_base=port_base)
        for (category, scenario), outcome in zip(scenarios, outcomes):
            categories[category]["total"] += 1
            if category == "incident":
                tally = classes.setdefault(scenario.get("class", "-"), {"passed": 0, "total": 0})
                tally["total"] += 1
                tally["passed"] += not outcome["problems"]
            if outcome["problems"]:
                categories[category]["failed"].append({"name": scenario["name"], "problems": outcome["problems"][:4]})
            else:
                categories[category]["passed"] += 1
        incident = categories["incident"]
        others = [categories["regressions"], categories["compat"]]
        share = incident["passed"] / incident["total"]
        rest = sum(c["passed"] for c in others) / sum(c["total"] for c in others)
        categories["incident"]["classes"] = classes
        return categories, round(share * rest, 4), None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def pairs(report):
    return {(e["endpoint_id"], event) for e in report["missed"] for event in e["event_ids"]}


def periods(report):
    out = {}
    for entry in report["missed"]:
        out.setdefault(entry["endpoint_id"], []).append((entry["switched_off_at"], entry["switched_on_at"]))
    return {endpoint: sorted(times) for endpoint, times in out.items()}


def impact_score(workspace):
    with open(os.path.join(HERE, "truth.json"), encoding="utf-8") as handle:
        truth = json.load(handle)
    result = {"impact": 0.0, "precision": 0.0, "recall": 0.0, "figures_right": 0, "figures": 0, "problem": None}
    try:
        with open(os.path.join(workspace, "out", "impact.json"), encoding="utf-8") as handle:
            report = json.load(handle)
        got, want = pairs(report), pairs(truth)
        totals = report["totals_minor"]
        times = periods(report)
        skipped = report["skipped_rows"]
        if not isinstance(totals, dict):
            raise TypeError("totals_minor is not an object")
    except (OSError, ValueError, KeyError, TypeError) as problem:
        result["problem"] = f"report missing or malformed: {problem!r}"
        return result
    hit = len(got & want)
    precision = hit / len(got) if got else 0.0
    recall = hit / len(want) if want else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    true_times = periods(truth)
    right = figures = 0
    for currency in sorted(set(totals) | set(truth["totals_minor"])):
        figures += 1
        value = totals.get(currency)
        right += isinstance(value, int) and not isinstance(value, bool) and value == truth["totals_minor"].get(currency)
    figures += 1
    right += isinstance(skipped, int) and not isinstance(skipped, bool) and skipped == truth["skipped_rows"]
    for endpoint in sorted(set(times) | set(true_times)):
        figures += 1
        right += times.get(endpoint) == true_times.get(endpoint)
    result.update(
        impact=round(0.6 * f1 + 0.4 * right / figures, 4), precision=round(precision, 3), recall=round(recall, 3),
        figures_right=right, figures=figures,
        reported={"endpoints": sorted(times), "entries": len(got), "skipped_rows": skipped},
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("workspace", nargs="?")
    parser.add_argument("--shipped", action="store_true")
    parser.add_argument("--out", default="judge.json")
    parser.add_argument("--port-base", type=int, default=26000)
    parser.add_argument("--port-span", type=int, default=4000)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--repair-only", action="store_true", help="skip the report (no packet needed)")
    args = parser.parse_args()
    if not args.shipped and not args.workspace:
        parser.error("give the workspace, or --shipped")
    workspace = None if args.shipped else os.path.abspath(args.workspace)

    categories, repair, build_problem = repair_score(workspace, args.port_base, args.port_span, args.jobs)
    scored = workspace is not None and not args.repair_only
    impact = impact_score(workspace) if scored else {"impact": None}
    passed = repair == 1.0 and (impact.get("impact") == 1.0 or not scored)
    if args.shipped:  # the self-check: every incident scenario fails, every other one passes
        passed = categories["incident"]["passed"] == 0 and all(
            categories[name]["passed"] == categories[name]["total"] for name in ("regressions", "compat"))
    summary = {"passed": passed, "repair": repair, "impact": impact, "categories": categories, "build_problem": build_problem}
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=1)
        handle.write("\n")

    print("PASS" if passed else "FAIL")
    line = f"  repair {repair:.2f}"
    if scored:
        line += (f"   impact {impact['impact']:.2f}  (precision {impact['precision']:.2f}, recall {impact['recall']:.2f}, "
                 f"figures {impact['figures_right']} of {impact['figures']} right)")
        if impact.get("problem"):
            line += "  " + impact["problem"]
    print(line)
    for name, category in categories.items():
        print(f"  {name:<12} {category['passed']:>2} of {category['total']}")
        for class_, tally in category.get("classes", {}).items():
            print(f"      {class_:<20} {tally['passed']} of {tally['total']}")
        for failed in category["failed"][:(3 if args.shipped and name == "incident" else 30)]:
            print(f"    - {failed['name']}: {'; '.join(failed['problems'][:2])[:170]}")
    if build_problem:
        print("  build: " + build_problem.splitlines()[0])
    print(f"  details: {args.out}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
