#!/usr/bin/env python3
"""Play scenarios against the release, the working tree, or one replaced by the other.

    python3 kit/rollout.py SCENARIO.json [...]            the working tree (app/)
    python3 kit/rollout.py SCENARIO.json --release old    the release as shipped, untouched
    python3 kit/rollout.py SCENARIO.json --upgrade-at 4   steps 1-4 on the release as shipped, then the
                                                          working tree takes over the same state
    python3 kit/rollout.py SCENARIO.json --upgrade-each   one run per upgrade position
    options: --jobs N  --port-base P  --full  --json

A scenario is what app/bin/replay takes (see app/bin/replaylib.py), plus:

  step         {"at": 40, "do": "upgrade"}
               api, router and worker stop and start again from the working tree, on the same
               state. A scenario with this step starts on the release as shipped. With
               --release old the step restarts the shipped release instead.
  expectation  {"endpoint": "ep_shop", "requests": 2, "accepted": 1, "events": 1, "deliveries": 1}
               what the endpoint received in total: requests it processed, requests it accepted,
               distinct events and distinct deliveries among those requests. Any of the four,
               each also as min_... / max_...

Besides the scenario's expectations, every run is checked against the contracts:
  running         api, router and worker are still up at the end
  exits           no service exited except at an armed crash point
  settled         nothing is left queued or leased after a final drain
  delivered       a delivery is delivered only with a recorded 2xx
  first_delivery  one first delivery per event and endpoint (a resend may add another)
  requests        every request names a known delivery and its event, with a valid signature
A scenario can leave checks out with "skip_checks": ["settled"]. Do that only where the
ticket itself overrides the contract, and say so in the scenario's name.

One run may take at most 45 s of wall-clock time.

Exits 0 when every run is clean, 1 otherwise, 2 when the worker does not build.
"""

import argparse
import concurrent.futures
import copy
import json
import os
import shutil
import signal
import socket
import sys
import tempfile
import threading
import time

KIT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(KIT)
NEW_APP = os.environ.get("KIT_NEW_APP") or os.path.join(ROOT, "app")
OLD_APP = os.environ.get("KIT_OLD_APP") or os.path.join(ROOT, ".pristine", "app")
if not os.path.isdir(os.path.join(OLD_APP, "services")):
    OLD_APP = NEW_APP  # no snapshot of the shipped release: "old" is the working tree

sys.path.insert(0, os.path.join(OLD_APP, "bin"))
import replaylib  # noqa: E402

SCORED = ("api", "router", "worker")
COUNTS = ("requests", "accepted", "events", "deliveries")
CHECKS = ("running", "exits", "settled", "delivered", "first_delivery", "requests")
RUN_SECONDS = int(os.environ.get("KIT_RUN_SECONDS", "45"))  # wall-clock limit for one run
LIVE = set()  # deployments with processes running, so a signal can stop them


class Deployment(replaylib.Deployment):
    """The merchant stand-in always comes from the shipped release."""

    def command(self, service):
        if service == "receiver":
            return [sys.executable, os.path.join(OLD_APP, "services", "receiver", "main.py")]
        return super().command(service)


def stop_everything(signum=None, frame=None):
    for dep in list(LIVE):
        try:
            dep.stop_all()
        except Exception:  # noqa: BLE001 - nothing useful to do while shutting down
            pass
    if signum is not None:
        os._exit(128 + signum)


def free_port_base(start, taken):
    for base in range(start, start + 2000, 10):
        if base in taken:
            continue
        try:
            for offset in replaylib.OFFSET.values():
                with socket.socket() as probe:
                    probe.bind(("127.0.0.1", base + offset))
        except OSError:
            continue
        return base
    raise RuntimeError("no free ports for a deployment")


def stderr_tail(state_dir, service, lines=6):
    try:
        with open(os.path.join(state_dir, "logs", service + ".stderr"), encoding="utf-8", errors="replace") as f:
            tail = [line.rstrip() for line in f.read().splitlines() if line.strip()][-lines:]
    except OSError:
        return []
    return [f"  {service} stderr: {line[:200]}" for line in tail]


def play(scenario, release, bins, port_base):
    """Run one scenario. Returns (result, errors)."""
    steps = scenario["steps"]
    upgrades = any(step.get("do") == "upgrade" for step in steps)
    app = OLD_APP if (release == "old" or upgrades) else NEW_APP
    target = OLD_APP if release == "old" else NEW_APP
    state_dir = tempfile.mkdtemp(prefix="switchyard-")
    dep = Deployment(state_dir, port_base, app, bins[app])
    errors, result = [], None
    overtime = threading.Event()

    def give_up():
        overtime.set()
        dep.stop_all()

    watchdog = threading.Timer(RUN_SECONDS, give_up)
    watchdog.daemon = True
    LIVE.add(dep)
    watchdog.start()
    try:
        dep.set_clock(scenario.get("epoch", replaylib.EPOCH))
        dep.start_all()
        run = replaylib.Run(dep, scenario)
        for number, step in enumerate(steps, 1):
            try:
                if step.get("do") == "upgrade":
                    if "at" in step:
                        dep.set_clock(run.epoch + step["at"])
                    for service in ("worker", "api", "router"):
                        dep.stop(service)
                    dep.app, dep.worker_bin = target, bins[target]
                    for service in ("router", "worker", "api"):
                        dep.start(service)
                else:
                    run.step(step)
            except (RuntimeError, replaylib.ServiceDown, KeyError, TypeError, ValueError) as problem:
                if overtime.is_set():
                    break
                errors.append(f"step {number} ({step.get('do')}) failed: {str(problem)[:300]}")
                for service in SCORED:
                    if not dep.running(service):
                        errors += stderr_tail(state_dir, service)
                break
            if overtime.is_set():
                break
        if overtime.is_set():
            return None, [f"timed out: the run did not finish in {RUN_SECONDS} s (a service stopped answering, or a drain never settles)"]
        result = run.result()
        for crash in dep.crashes:
            if crash.get("exit") != 86:
                errors += stderr_tail(state_dir, crash["service"])
    except (RuntimeError, replaylib.ServiceDown) as problem:
        if overtime.is_set():
            return None, [f"timed out: the run did not finish in {RUN_SECONDS} s (a service stopped answering, or a drain never settles)"]
        errors.append(f"could not start: {str(problem)[:300]}")
        for service in SCORED:
            errors += stderr_tail(state_dir, service)
    finally:
        watchdog.cancel()
        dep.stop_all()
        LIVE.discard(dep)
        shutil.rmtree(state_dir, ignore_errors=True)
    return result, errors


# --- checks ---------------------------------------------------------------------------


def endpoint_paths(scenario):
    paths = {}
    for step in scenario["steps"]:
        if step.get("do") in ("endpoint.create", "endpoint.update") and "id" in step:
            known = paths.setdefault(step["id"], set())
            if "path" in step or step["do"] == "endpoint.create":
                known.add(step.get("path", "/hooks/" + step["id"]))
    return paths


def event_of(receipt):
    named = (receipt.get("headers") or {}).get("x-switchyard-event")
    if named:
        return named
    try:
        return json.loads(receipt.get("body") or "{}").get("id")
    except ValueError:
        return None


def check_endpoint(result, expect, paths):
    name = expect["endpoint"]
    wanted = paths.get(name) or {"/hooks/" + name}
    receipts = [r for r in result["received"] if r["processed"] and r["path"] in wanted]
    accepted = [r for r in receipts if r["accepted"]]
    got = {
        "requests": len(receipts),
        "accepted": len(accepted),
        "events": len({event_of(r) for r in receipts}),
        "deliveries": len({r["headers"].get("webhook-id") for r in receipts}),
    }
    out = []
    for key in COUNTS:
        if key in expect and got[key] != expect[key]:
            out.append(f"{name}: {got[key]} {key}, expected {expect[key]}")
        if "min_" + key in expect and got[key] < expect["min_" + key]:
            out.append(f"{name}: {got[key]} {key}, expected at least {expect['min_' + key]}")
        if "max_" + key in expect and got[key] > expect["max_" + key]:
            out.append(f"{name}: {got[key]} {key}, expected at most {expect['max_' + key]}")
    return out


def expectations(result, scenario):
    paths, out = endpoint_paths(scenario), []
    for expect in scenario.get("expect", []):
        try:
            if "endpoint" in expect and "delivery" not in expect:
                out += check_endpoint(result, expect, paths)
            else:
                problem = replaylib.check(result, expect)
                if problem:
                    out.append(problem)
        except (KeyError, TypeError, ValueError) as problem:
            out.append(f"expectation {json.dumps(expect)[:120]} could not be checked: {problem!r}")
    return out


def invariants(result, scenario):
    """Contract checks. A scenario may leave some out with "skip_checks": [names from CHECKS]."""
    out = []
    skip = set(scenario.get("skip_checks") or [])
    steps = scenario["steps"]
    stopped = {}
    for step in steps:
        if step.get("do") == "stop":
            stopped[step["service"]] = True
        elif step.get("do") == "restart":
            stopped[step["service"]] = False
        elif step.get("do") == "upgrade":
            stopped.clear()
    for service in SCORED:
        if "running" not in skip and result["state"].get(service) is None and not stopped.get(service):
            out.append(f"{service} is not running at the end")
    for crash in result["crashes"]:
        if "exits" not in skip and crash.get("exit") != 86:
            out.append(f"{crash['service']} exited with status {crash.get('exit')} (not an armed crash point)")

    router = result["state"].get("router") or {}
    deliveries = router.get("deliveries", [])
    enabled = {e["id"]: e.get("enabled") for e in router.get("endpoints", [])}
    refs = {event_id: ref for ref, event_id in result["refs"].items()}
    by_id = {d["id"]: d for d in deliveries}

    def label(delivery):
        return f"{refs.get(delivery['event_id'], delivery['event_id'])} -> {delivery['endpoint_id']} ({delivery['id']})"

    final_drain = bool(steps) and steps[-1].get("do") == "drain" and "limit" not in steps[-1] and "settled" not in skip
    firsts = {}
    answered = {}
    for receipt in result["received"]:
        if receipt["processed"] and isinstance(receipt["response"], int) and 200 <= receipt["response"] < 300:
            answered[receipt["headers"].get("webhook-id")] = True
    for delivery in deliveries:
        if final_drain and delivery["state"] in ("queued", "leased") and enabled.get(delivery["endpoint_id"], True):
            out.append(f"{label(delivery)} is still {delivery['state']} after the final drain")
        if "delivered" not in skip and delivery["state"] == "delivered" and not answered.get(delivery["id"]):
            out.append(f"{label(delivery)} is delivered but no request for it got a 2xx")
        if delivery.get("resend_of") is None:
            firsts.setdefault((delivery["event_id"], delivery["endpoint_id"]), []).append(delivery)
    for same in firsts.values():
        if "first_delivery" not in skip and len(same) > 1:
            out.append(f"{label(same[0])} has {len(same)} first deliveries; only a resend may add one")

    secrets = result.get("secrets") or {}
    for receipt in result["received"]:
        if not receipt["processed"] or "requests" in skip:
            continue
        delivery = by_id.get(receipt["headers"].get("webhook-id"))
        where = f"request {receipt['n']} to {receipt['path']}"
        if deliveries and delivery is None:
            out.append(f"{where} names a delivery the router does not have: {receipt['headers'].get('webhook-id')}")
            continue
        if delivery is None:
            continue
        if event_of(receipt) != delivery["event_id"]:
            out.append(f"{where} carries event {event_of(receipt)}, but its delivery belongs to {delivery['event_id']}")
        known = secrets.get(delivery["endpoint_id"]) or []
        if known and not any(replaylib.signed_with(receipt, secret) for secret in known):
            out.append(f"{where} is not signed with a secret of {delivery['endpoint_id']}")
    return out


def digest(result):
    """A few lines that say what happened, for a failed run."""
    if result is None:
        return []
    refs = {event_id: ref for ref, event_id in result["refs"].items()}
    router = result["state"].get("router") or {}
    lines = []
    deliveries = router.get("deliveries", [])
    shown = [
        f"{refs.get(d['event_id'], d['event_id'])}>{d['endpoint_id']} {d['state']}"
        + (f" x{d['attempts']}" if d["attempts"] else "")
        + (" resend" if d.get("resend_of") else "")
        for d in deliveries[:12]
    ]
    if shown:
        more = f" (+{len(deliveries) - 12} more)" if len(deliveries) > 12 else ""
        lines.append("  deliveries: " + " | ".join(shown) + more)
    by_id = {d["id"]: d for d in deliveries}
    received = []
    for r in result["received"][:14]:
        delivery = by_id.get(r["headers"].get("webhook-id"))
        ref = refs.get(event_of(r), event_of(r))
        answer = r["response"] if r["response"] is not None else ("drop" if r["processed"] else "refuse")
        received.append(f"+{r['now'] - result['epoch']}s {ref}>{delivery['endpoint_id'] if delivery else r['path']} {answer}")
    if received:
        more = f" (+{len(result['received']) - 14} more)" if len(result["received"]) > 14 else ""
        lines.append("  received:   " + " | ".join(received) + more)
    if result["crashes"]:
        lines.append("  exits:      " + ", ".join(f"{c['service']}={c.get('exit')}" for c in result["crashes"]))
    return lines


# --- running --------------------------------------------------------------------------


def with_upgrade(scenario, after):
    """A copy of the scenario with an upgrade step after step number `after` (1-based)."""
    changed = copy.deepcopy(scenario)
    steps = changed["steps"]
    at = steps[after - 1].get("at") if after >= 1 else None
    step = {"do": "upgrade"}
    if at is not None:
        step["at"] = at
    steps.insert(after, step)
    return changed


def upgrade_positions(scenario, limit=None):
    """Positions where replacing the release keeps the scenario's meaning: not right after a
    crash point is armed (the arming would be lost), and not after the last step."""
    steps = scenario["steps"]
    if any(step.get("do") == "upgrade" for step in steps):
        return []
    positions = [n for n in range(1, len(steps)) if steps[n - 1].get("do") != "crash_at"]
    if limit and len(positions) > limit:
        stride = (len(positions) - 1) / float(limit - 1)
        positions = sorted({positions[int(round(i * stride))] for i in range(limit)})
    return positions


def build(apps):
    bins = {}
    for app in apps:
        if app not in bins:
            try:
                bins[app] = replaylib.build_worker(app)
            except OSError as problem:  # no go toolchain, or nowhere to write
                raise RuntimeError(f"the worker cannot be built: {problem}") from None
    return bins


def run_all(jobs_spec, bins, jobs=4, port_base=7400, deadline=None):
    """jobs_spec: list of (label, scenario, release). Returns list of dicts in the same order.
    Runs that have not started by `deadline` (a time.time() value) are reported as not run."""
    taken, choosing = set(), threading.Lock()

    def one(spec):
        label, scenario, release = spec
        if deadline is not None and time.time() > deadline:
            return {"label": label, "name": scenario.get("name", ""), "problems": ["not run: out of time"], "digest": [], "result": None}
        with choosing:
            base = free_port_base(port_base, taken)
            taken.add(base)
        try:
            result, errors = play(scenario, release, bins, base)
        finally:
            with choosing:
                taken.discard(base)
        problems = list(errors)
        if result is not None:
            problems += expectations(result, scenario) + invariants(result, scenario)
        return {"label": label, "name": scenario.get("name", ""), "problems": problems, "digest": digest(result), "result": result}

    if jobs <= 1 or len(jobs_spec) <= 1:
        return [one(spec) for spec in jobs_spec]
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(one, jobs_spec))


def load(path):
    with open(path, encoding="utf-8") as handle:
        scenario = json.load(handle)
    if not isinstance(scenario, dict) or not isinstance(scenario.get("steps"), list):
        raise ValueError("a scenario is an object with a list of steps")
    return scenario


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scenarios", nargs="+")
    parser.add_argument("--release", choices=("old", "new"), default="new")
    parser.add_argument("--upgrade-at", type=int)
    parser.add_argument("--upgrade-each", action="store_true")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--port-base", type=int, default=7400)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    specs = []
    for path in args.scenarios:
        short = os.path.relpath(path, ROOT)
        if short.startswith(".."):
            short = os.path.basename(path)
        try:
            scenario = load(path)
        except (OSError, ValueError) as problem:
            print(f"FAIL  {short}  cannot be read: {problem}")
            return 1
        if args.upgrade_each:
            for position in upgrade_positions(scenario):
                specs.append((f"{short} [upgrade after step {position}]", with_upgrade(scenario, position), args.release))
        elif args.upgrade_at:
            specs.append((f"{short} [upgrade after step {args.upgrade_at}]", with_upgrade(scenario, args.upgrade_at), args.release))
        else:
            upgrades = any(step.get("do") == "upgrade" for step in scenario["steps"])
            mode = "release as shipped" if args.release == "old" else ("shipped, then working tree" if upgrades else "working tree")
            specs.append((f"{short} [{mode}]", scenario, args.release))
    try:
        bins = build({OLD_APP, NEW_APP})
    except RuntimeError as problem:
        print("\n".join(str(problem).splitlines()[:20]))
        return 2
    signal.signal(signal.SIGTERM, stop_everything)
    outcomes = run_all(specs, bins, args.jobs, args.port_base)
    if args.json:
        print(json.dumps([{k: o[k] for k in ("label", "name", "problems")} for o in outcomes], indent=1))
    else:
        for outcome in outcomes:
            print(("FAIL  " if outcome["problems"] else "ok    ") + outcome["label"] + "  " + outcome["name"])
            for problem in outcome["problems"][:8]:
                print("  " + problem)
            if len(outcome["problems"]) > 8:
                print(f"  ... {len(outcome['problems']) - 8} more problems")
            if outcome["problems"] or args.full:
                print("\n".join(outcome["digest"]))
            if args.full:
                print(json.dumps(outcome["result"], indent=1))
    return 1 if any(o["problems"] for o in outcomes) else 0


if __name__ == "__main__":
    sys.exit(main())
