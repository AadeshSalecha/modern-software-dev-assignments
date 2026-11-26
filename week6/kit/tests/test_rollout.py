"""Tests for kit/rollout.py. Run: python3 -m unittest discover -s kit/tests"""

import os
import shutil
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rollout  # noqa: E402

SCENARIO = {
    "name": "made up",
    "steps": [
        {"at": 0, "do": "endpoint.create", "id": "ep_a", "merchant": "m_x"},
        {"at": 1, "do": "endpoint.create", "id": "ep_b", "merchant": "m_x", "path": "/in/b"},
        {"at": 2, "do": "crash_at", "service": "worker", "point": 4},
        {"at": 3, "do": "event", "ref": "e1", "merchant": "m_x", "type": "payment.captured", "amount_minor": 5, "currency": "USD"},
        {"at": 4, "do": "drain"},
    ],
}


def receipt(n, path, delivery, event, response=200, processed=True):
    return {
        "n": n,
        "now": rollout.replaylib.EPOCH + n,
        "path": path,
        "headers": {"webhook-id": delivery, "x-switchyard-event": event},
        "body": "{}",
        "response": response if isinstance(response, int) else None,
        "processed": processed,
        "accepted": response == "drop" or (isinstance(response, int) and 200 <= response < 300),
    }


def result(deliveries, received, crashes=(), down=()):
    state = {s: {} for s in ("api", "worker")}
    state["router"] = {"endpoints": [{"id": "ep_a", "enabled": True}, {"id": "ep_b", "enabled": True}], "deliveries": deliveries}
    for service in down:
        state[service] = None
    return {
        "name": "made up",
        "epoch": rollout.replaylib.EPOCH,
        "refs": {"e1": "evt_1"},
        "statuses": {},
        "secrets": {},
        "crashes": list(crashes),
        "received": received,
        "state": state,
    }


def delivery(id_, state="delivered", endpoint="ep_a", event="evt_1", resend_of=None, attempts=0):
    return {"id": id_, "event_id": event, "endpoint_id": endpoint, "resend_of": resend_of, "state": state, "attempts": attempts, "available_at": 0}


class ShapeTest(unittest.TestCase):
    def test_upgrade_positions_skip_the_end_and_armed_crash_points(self):
        self.assertEqual(rollout.upgrade_positions(SCENARIO), [1, 2, 4])
        self.assertEqual(rollout.upgrade_positions(rollout.with_upgrade(SCENARIO, 2)), [])

    def test_upgrade_positions_can_be_capped(self):
        long = {"steps": [{"do": "tick", "service": "api"}] * 30}
        self.assertEqual(len(rollout.upgrade_positions(long, limit=5)), 5)

    def test_with_upgrade_inserts_a_step_at_the_same_time(self):
        changed = rollout.with_upgrade(SCENARIO, 2)
        self.assertEqual(changed["steps"][2], {"do": "upgrade", "at": 1})
        self.assertEqual(len(SCENARIO["steps"]), 5)

    def test_endpoint_paths(self):
        self.assertEqual(rollout.endpoint_paths(SCENARIO), {"ep_a": {"/hooks/ep_a"}, "ep_b": {"/in/b"}})


class ExpectationTest(unittest.TestCase):
    def test_endpoint_counts(self):
        got = result(
            [delivery("dlv_1"), delivery("dlv_2", event="evt_2")],
            [
                receipt(1, "/hooks/ep_a", "dlv_1", "evt_1", 500),
                receipt(2, "/hooks/ep_a", "dlv_1", "evt_1", 200),
                receipt(3, "/hooks/ep_a", "dlv_2", "evt_2", "drop"),
                receipt(4, "/hooks/ep_a", "dlv_2", "evt_2", "refuse", processed=False),
                receipt(5, "/in/b", "dlv_3", "evt_1", 200),
            ],
        )
        scenario = dict(SCENARIO, expect=[{"endpoint": "ep_a", "requests": 3, "accepted": 2, "events": 2, "deliveries": 2}])
        self.assertEqual(rollout.expectations(got, scenario), [])
        scenario = dict(SCENARIO, expect=[{"endpoint": "ep_a", "events": 1, "max_requests": 2}, {"endpoint": "ep_b", "min_requests": 2}])
        self.assertEqual(
            sorted(rollout.expectations(got, scenario)),
            ["ep_a: 2 events, expected 1", "ep_a: 3 requests, expected at most 2", "ep_b: 1 requests, expected at least 2"],
        )

    def test_shipped_expectation_forms_still_work(self):
        got = result([delivery("dlv_1")], [receipt(1, "/hooks/ep_a", "dlv_1", "evt_1")])
        scenario = dict(SCENARIO, expect=[{"delivery": {"event": "e1", "endpoint": "ep_a"}, "state": "dead"}])
        self.assertEqual(rollout.expectations(got, scenario), ["e1 -> ep_a: state delivered, expected dead"])


class InvariantTest(unittest.TestCase):
    def problems(self, *args, **kwargs):
        return rollout.invariants(result(*args, **kwargs), SCENARIO)

    def test_a_clean_run_has_none(self):
        self.assertEqual(self.problems([delivery("dlv_1")], [receipt(1, "/hooks/ep_a", "dlv_1", "evt_1")]), [])

    def test_a_new_final_state_is_allowed(self):
        self.assertEqual(self.problems([delivery("dlv_1", state="withdrawn")], []), [])

    def test_left_in_the_queue(self):
        found = self.problems([delivery("dlv_1", state="queued")], [])
        self.assertEqual(len(found), 1)
        self.assertIn("still queued after the final drain", found[0])

    def test_delivered_without_a_2xx(self):
        found = self.problems([delivery("dlv_1")], [receipt(1, "/hooks/ep_a", "dlv_1", "evt_1", 500)])
        self.assertIn("no request for it got a 2xx", found[0])

    def test_two_first_deliveries(self):
        ok = [receipt(1, "/hooks/ep_a", "dlv_1", "evt_1"), receipt(2, "/hooks/ep_a", "dlv_2", "evt_1")]
        self.assertIn("2 first deliveries", self.problems([delivery("dlv_1"), delivery("dlv_2")], ok)[0])
        self.assertEqual(self.problems([delivery("dlv_1"), delivery("dlv_2", resend_of="dlv_1")], ok), [])

    def test_request_for_an_unknown_delivery_or_the_wrong_event(self):
        found = self.problems([delivery("dlv_1")], [receipt(1, "/hooks/ep_a", "dlv_1", "evt_1"), receipt(2, "/hooks/ep_a", "dlv_9", "evt_1")])
        self.assertIn("names a delivery the router does not have", found[0])
        found = self.problems([delivery("dlv_1")], [receipt(1, "/hooks/ep_a", "dlv_1", "evt_7")])
        self.assertIn("carries event evt_7", found[0])

    def test_services_and_exits(self):
        self.assertIn("worker is not running at the end", self.problems([], [], down=("worker",)))
        self.assertEqual(self.problems([], [], crashes=[{"service": "worker", "now": 1, "exit": 86}]), [])
        self.assertIn("exited with status 1", self.problems([], [], crashes=[{"service": "api", "now": 1, "exit": 1}])[0])


@unittest.skipUnless(shutil.which("go") and shutil.which("node"), "needs go and node")
class LiveTest(unittest.TestCase):
    def test_a_shipped_scenario_survives_an_upgrade_at_every_step(self):
        import glob

        paths = sorted(glob.glob(os.path.join(rollout.NEW_APP, "scenarios", "*.json")))[:1]
        self.assertTrue(paths)
        scenario = rollout.load(paths[0])
        specs = [("plain", scenario, "new")] + [(f"after {n}", rollout.with_upgrade(scenario, n), "new") for n in rollout.upgrade_positions(scenario)]
        outcomes = rollout.run_all(specs, rollout.build({rollout.OLD_APP, rollout.NEW_APP}), jobs=4, port_base=7900)
        self.assertEqual([o["problems"] for o in outcomes], [[] for _ in outcomes])


if __name__ == "__main__":
    unittest.main()
