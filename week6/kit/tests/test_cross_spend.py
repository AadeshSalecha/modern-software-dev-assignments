"""Tests for kit/cross.py (the parts that run no services) and kit/spend.py."""

import json
import os
import sys
import tempfile
import time
import unittest

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KIT)
import cross  # noqa: E402
import spend  # noqa: E402


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


class Better(unittest.TestCase):
    def score(self, usable=True, changed=True, fails=()):
        return {"usable": usable, "changed": changed, "passed": 0,
                "fails": [{"author": author, "how": how} for author, how in fails]}

    def test_a_tie_goes_to_a(self):
        self.assertEqual(cross.better({"a": self.score(), "b": self.score()}), "a")

    def test_the_other_author_s_scenarios_decide_only_when_one_sided(self):
        a = self.score(fails=[("b", "as written")] * 5)
        self.assertEqual(cross.better({"a": a, "b": self.score()}), "b")
        both = self.score(fails=[("a", "as written")])
        self.assertEqual(cross.better({"a": a, "b": self.score(fails=[("a", "as written")])}), "a")
        variants = self.score(fails=[("b", "handed over before the last drain")] * 3)
        self.assertEqual(cross.better({"a": variants, "b": self.score()}), "a")

    def test_nor_do_the_variants(self):
        a = self.score(fails=[("a", "handed over before the last drain"), ("a", "every service restarted before the last drain")])
        self.assertEqual(cross.better({"a": a, "b": self.score()}), "a")

    def test_a_scenario_its_own_author_fails_and_the_other_passes_does(self):
        a = self.score(fails=[("a", "as written")])
        self.assertEqual(cross.better({"a": a, "b": self.score()}), "b")
        self.assertEqual(cross.better({"a": a, "b": self.score(fails=[("b", "as written")])}), "a")

    def test_breaking_a_shipped_scenario_loses(self):
        a = self.score(fails=[("shipped", "as written")])
        self.assertEqual(cross.better({"a": a, "b": self.score(fails=[("b", "as written")] * 3)}), "b")

    def test_unchanged_or_unbuildable_loses(self):
        self.assertEqual(cross.better({"a": self.score(changed=False), "b": self.score(fails=[("b", "as written")] * 4)}), "b")
        self.assertEqual(cross.better({"a": self.score(usable=False), "b": self.score(fails=[("b", "as written")] * 4)}), "b")


class Regressions(unittest.TestCase):
    """A scenario that passes on the shipped release says nothing about the defect, but it does
    say something about a repair that fails it while the other passes it."""

    def judge(self, failing):
        from unittest import mock
        scenario = {"name": "a neighbour that must keep working", "steps": [{"at": 0, "do": "drain"}], "expect": []}

        def run_all(specs, bins, deadline=None):
            out = []
            for label, _, release, app in specs:
                bad = release == "new" and any(app.startswith("/w/" + name + "/") for name in failing)
                out.append({"label": label, "name": "", "digest": "", "result": {"statuses": {}},
                            "problems": ["ep_a: 0 requests, expected 1"] if bad else []})
            return out

        with mock.patch.object(cross.rollout, "build", lambda apps: {}), \
                mock.patch.object(cross.rollout, "run_all", run_all), \
                mock.patch.object(cross, "changed", lambda root: True), \
                mock.patch.object(cross, "scenarios_of", lambda root: [("near.json", root + "/near.json", scenario)] if root == "/w/b" else []), \
                mock.patch.object(cross.glob, "glob", lambda pattern: []):
            return cross.judge_repairs({"a": "/w/a", "b": "/w/b"}, time.time() + 60)

    def test_it_counts_against_the_one_repair_that_breaks_it(self):
        scores, notes = self.judge(failing=["a"])
        self.assertEqual([(f["author"], f["how"]) for f in scores["a"]["fails"]], [("b", "as written")])
        self.assertEqual(scores["b"]["fails"], [])
        self.assertEqual(cross.written(scores["a"]), 1)
        self.assertEqual(cross.better(scores), "b")
        self.assertIn("worked as shipped no longer does", notes[0])

    def test_it_decides_nothing_when_no_repair_or_every_repair_fails_it(self):
        for failing in ([], ["a", "b"]):
            scores, notes = self.judge(failing=failing)
            self.assertEqual(scores["a"]["fails"], [])
            self.assertEqual(scores["b"]["fails"], [])
            self.assertIn("not used", notes[0])


class Reports(unittest.TestCase):
    def test_list_order_does_not_matter(self):
        a = {"affected": [{"id": 1}, {"id": 2}], "total": 3}
        b = {"total": 3, "affected": [{"id": 2}, {"id": 1}]}
        self.assertEqual(cross.canonical(a), cross.canonical(b))

    def test_differences_name_what_only_one_side_has(self):
        lines = cross.differences({"affected": [{"id": 1}], "n": 1}, {"affected": [{"id": 1}, {"id": 2}], "n": 2})
        text = "\n".join(lines)
        self.assertIn("1 identical", text)
        self.assertIn('only in b: {"id": 2}', text)
        self.assertIn("n: a has 1, b has 2", text)


class PrivateFormat(unittest.TestCase):
    SCENARIO = {"steps": [{"do": "event"}, {"do": "bus", "message": {"type": "cancel"}}, {"do": "drain"}]}

    def outcome(self, status):
        return {"problems": [], "result": {"statuses": {"_bus1": status}}}

    def test_refs_are_added_to_bus_steps_only_where_missing(self):
        scenario = {"steps": [{"do": "bus", "ref": "mine"}, {"do": "bus"}, {"do": "event"}]}
        changed = cross.with_bus_refs(scenario)
        self.assertEqual([step.get("ref") for step in changed["steps"]], ["mine", "_bus1", None])
        self.assertNotIn("ref", scenario["steps"][1])

    def test_a_message_only_the_repair_accepts_marks_the_scenario(self):
        found = cross.private_bus_step(self.SCENARIO, self.outcome(422), [self.outcome(200)])
        self.assertIn("step 2 cancel: 422 as shipped, 200 on the repair", found)

    def test_messages_the_shipped_release_accepts_or_both_refuse_do_not(self):
        self.assertEqual(cross.private_bus_step(self.SCENARIO, self.outcome(200), [self.outcome(200)]), "")
        self.assertEqual(cross.private_bus_step(self.SCENARIO, self.outcome(422), [self.outcome(422)]), "")
        self.assertEqual(cross.private_bus_step(self.SCENARIO, {"problems": ["x"], "result": None}, [self.outcome(200)]), "")


class ThreeReports(unittest.TestCase):
    """compare_reports: a and b use the kit's database, c is made from the raw files."""

    def roots(self, top, **reports):
        roots = {}
        for name, content in reports.items():
            root = os.path.join(top, name)
            os.makedirs(os.path.join(root, "out"))
            roots[name] = root
            if content is not None:
                write(os.path.join(root, "out", "impact.json"), json.dumps(content))
        return roots

    def state(self, **reports):
        with tempfile.TemporaryDirectory() as top:
            decided = os.path.join(top, "decided")
            state, lines = cross.compare_reports(self.roots(top, **reports), decided)
            taken = None
            if os.path.isfile(os.path.join(decided, "impact.json")):
                with open(os.path.join(decided, "impact.json"), encoding="utf-8") as handle:
                    taken = json.load(handle)
            return state, taken, "\n".join(lines)

    @staticmethod
    def report(entries, total=10, skipped=5):
        return {"affected": [{"id": n} for n in entries], "totals_minor": {"USD": total}, "skipped_rows": skipped}

    def test_all_the_same(self):
        x = self.report([1, 2])
        self.assertEqual(self.state(a=x, b=x, c=x)[:2], ("same", None))
        self.assertEqual(self.state(a=x, b=x)[:2], ("same", None))

    def test_the_raw_file_report_agreeing_with_a_keeps_a(self):
        self.assertEqual(self.state(a=self.report([1]), b=self.report([2]), c=self.report([1]))[:2], ("same", None))

    def test_the_raw_file_report_agreeing_with_b_takes_b_s_part(self):
        state, taken, _ = self.state(a=self.report([1], total=10), b=self.report([2], total=20), c=self.report([2], total=20))
        self.assertEqual(state, "settled")
        self.assertEqual(taken, self.report([2], total=20))

    def test_parts_are_settled_one_by_one(self):
        # c confirms b's entries and a's totals: the report handed in has each
        state, taken, _ = self.state(a=self.report([1], total=10), b=self.report([2], total=20), c=self.report([2], total=10))
        self.assertEqual(state, "settled")
        self.assertEqual(taken, self.report([2], total=10))

    def test_a_lone_figure_from_the_raw_files_does_not_call_for_a_decision(self):
        # the usual case: the raw-file parser has the entries and totals and miscounts corrupted rows
        state, taken, lines = self.state(a=self.report([1, 2]), b=self.report([1, 2]), c=self.report([1, 2], skipped=9))
        self.assertEqual((state, taken), ("same", None))
        self.assertIn("a's stands", lines)

    def test_the_two_database_reports_against_the_raw_file_one_on_the_entries_needs_deciding(self):
        state, taken, lines = self.state(a=self.report([1]), b=self.report([1]), c=self.report([2]))
        self.assertEqual((state, taken), ("decide", None))
        self.assertIn("affected: a=b, c (in dispute", lines)
        self.assertIn("a against c", lines)

    def test_three_different_or_two_without_the_third_need_deciding(self):
        self.assertEqual(self.state(a=self.report([1]), b=self.report([2]), c=self.report([3]))[0], "decide")
        self.assertEqual(self.state(a=self.report([1]), b=self.report([2]))[0], "decide")

    def test_without_a_report_from_a_another_is_taken(self):
        y, z = self.report([2]), self.report([3])
        self.assertEqual(self.state(a=None, b=y)[:2], ("settled", y))
        self.assertEqual(self.state(a=None, b=y, c=z)[:2], ("settled", z))
        self.assertEqual(self.state(a=None, b=None)[0], "none")


class OtherWork(unittest.TestCase):
    def test_the_other_repair_is_handed_over_as_a_diff_with_its_ledger_and_scenarios(self):
        with tempfile.TemporaryDirectory() as top:
            a_root, b_root = os.path.join(top, "a"), os.path.join(top, "b")
            shipped = os.path.join(a_root, ".pristine", "app", "services", "router", "main.py")
            write(shipped, "def run():\n    return 1\n")
            write(os.path.join(a_root, "app", "services", "router", "main.py"), "def run():\n    return 1\n")
            write(os.path.join(b_root, "app", "services", "router", "main.py"), "def run():\n    return 2\n")
            write(os.path.join(b_root, "app", "services", "router", "AGENTS.md"), "a map, not code\n")
            write(os.path.join(b_root, "app", "services", "router", "__pycache__", "x.pyc"), "junk")
            write(os.path.join(b_root, "work", "ledger.md"), "- [x] one\n")
            write(os.path.join(b_root, "work", "scenarios", "s.json"), json.dumps({"steps": []}))
            old_root, cross.A_ROOT = cross.A_ROOT, a_root
            try:
                self.assertFalse(cross.changed(a_root))
                self.assertTrue(cross.changed(b_root))
                cross.hand_over_material(a_root, b_root)
            finally:
                cross.A_ROOT = old_root
            target = os.path.join(a_root, "work", "cross")
            with open(os.path.join(target, "other.diff"), encoding="utf-8") as handle:
                diff = handle.read()
            self.assertIn("-    return 1", diff)
            self.assertIn("+    return 2", diff)
            self.assertNotIn("AGENTS.md", diff)
            self.assertNotIn("pyc", diff)
            self.assertTrue(os.path.isfile(os.path.join(target, "other-ledger.md")))
            self.assertTrue(os.path.isfile(os.path.join(target, "other-scenarios", "s.json")))


class Spend(unittest.TestCase):
    CARD = {"m": {"input": 1.0, "output": 10.0, "cache_read": 0.1, "cache_write": 2.0}}

    def result(self, session, output):
        return json.dumps({"type": "result", "session_id": session,
                           "modelUsage": {"m": {"inputTokens": 0, "outputTokens": output}}}) + "\n"

    def test_a_resumed_session_is_counted_once(self):
        with tempfile.TemporaryDirectory() as top:
            first, later = os.path.join(top, "a.claude.m.jsonl"), os.path.join(top, "fix.claude.m.jsonl")
            write(first, self.result("s1", 100000))   # 1 dollar
            write(later, self.result("s1", 150000))   # the whole session again: 1.5 dollars so far
            sessions = {}
            self.assertAlmostEqual(spend.cost_of(first, self.CARD, sessions), 1.0)
            self.assertAlmostEqual(spend.cost_of(later, self.CARD, sessions), 0.5)

    def test_a_session_that_was_cut_off_and_then_resumed_is_counted_once(self):
        # The main solver is stopped at its time limit (no result line), then resumed: the
        # resumed session reports the totals of both parts.
        with tempfile.TemporaryDirectory() as top:
            message = {"type": "assistant", "session_id": "s1", "message": {
                "id": "m1", "model": "m", "content": [{"type": "text", "text": "x" * 36000}],
                "usage": {"input_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}}}
            first = os.path.join(top, "a.claude.m.jsonl")
            write(first, json.dumps(message) + "\n")
            os.utime(first, (1000, 1000))
            second = os.path.join(top, "compare.claude.m.jsonl")
            write(second, self.result("s1", 15000))
            os.utime(second, (2000, 2000))
            sessions = {}
            costs = [spend.cost_of(path, self.CARD, sessions) for path in spend.in_order([second, first])]
        self.assertAlmostEqual(costs[0], 0.10, places=2)       # about 10,000 tokens estimated for the part cut off
        self.assertAlmostEqual(sum(costs), 0.15, places=6)     # the resumed session's exact total, once

    def test_a_session_that_was_cut_off_is_estimated_from_its_messages(self):
        with tempfile.TemporaryDirectory() as top:
            log = os.path.join(top, "a.claude.m.jsonl")
            message = {"type": "assistant", "message": {"id": "x", "model": "m", "content": [{"type": "text", "text": "y" * 250}],
                                                        "usage": {"input_tokens": 1000000, "cache_read_input_tokens": 0}}}
            write(log, json.dumps(message) + "\n")
            self.assertGreater(spend.cost_of(log, self.CARD), 1.0)

    def test_a_codex_session_that_was_cut_off_is_priced_by_its_steps(self):
        with tempfile.TemporaryDirectory() as top:
            log = os.path.join(top, "b.codex.m.jsonl")
            write(log, (json.dumps({"type": "item.completed", "item": {"type": "command_execution"}}) + "\n") * 40)
            cut = spend.cost_of(log, self.CARD)
            self.assertAlmostEqual(cut, 40 * spend.CODEX_DOLLARS_PER_ITEM * 10.0 / 5.0)
            with open(log, "a", encoding="utf-8") as handle:
                handle.write(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 100000, "cached_input_tokens": 0, "output_tokens": 0}}) + "\n")
            self.assertAlmostEqual(spend.cost_of(log, self.CARD), 0.1)

    def test_codex_turns_are_priced_with_cached_input_apart(self):
        with tempfile.TemporaryDirectory() as top:
            log = os.path.join(top, "b.codex.m.jsonl")
            write(log, json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1000000, "cached_input_tokens": 900000,
                                                                       "output_tokens": 0}}) + "\n")
            self.assertAlmostEqual(spend.cost_of(log, self.CARD), 0.1 + 0.09)



class Budget(unittest.TestCase):
    """kit/budget.py: what is left, and when a session is told to use it."""

    def setUp(self):
        import budget
        self.budget = budget
        self.top = tempfile.TemporaryDirectory()
        self.addCleanup(self.top.cleanup)
        self.saved = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(self.saved)))
        os.environ.update({"KIT_LOGS": self.top.name, "KIT_STARTED": str(time.time() - 100), "KIT_MONEY": "0.72",
                           "KIT_SESSION": "a", "KIT_SHARE": "0.36", "KIT_DEADLINE": "300"})
        self.rates = self.budget.spend.rates
        self.budget.spend.rates = lambda: {"m": {"input": 1.0, "output": 10.0, "cache_read": 0.1, "cache_write": 2.0}}
        self.addCleanup(lambda: setattr(self.budget.spend, "rates", self.rates))

    def log(self, name, session, output):
        write(os.path.join(self.top.name, name), json.dumps(
            {"type": "result", "session_id": session, "modelUsage": {"m": {"inputTokens": 0, "outputTokens": output}}}) + "\n")

    def test_it_separates_this_session_from_the_run(self):
        self.log("a.claude.m.jsonl", "s1", 20000)   # 0.20
        self.log("b.codex.m.jsonl", "s2", 10000)    # 0.10
        now = self.budget.state()
        self.assertAlmostEqual(now["spent"], 0.30)
        self.assertAlmostEqual(now["session_spent"], 0.20)
        self.assertAlmostEqual(now["money_left"], 0.42)
        self.assertTrue(195 <= now["seconds_left"] <= 201)
        self.assertIn("this session $0.20 of the $0.36", self.budget.line(now))

    def test_a_session_that_names_nothing_open_is_let_go_whatever_money_is_left(self):
        self.log("a.claude.m.jsonl", "s1", 20000)   # 0.20 of its 0.36, and the run has 0.52 left
        self.assertEqual(self.budget.nudge(self.budget.state()), "")
        self.assertEqual(self.budget.nudge(self.budget.state(), 0, "All of it is verified by scenarios."), "")

    def test_no_word_when_time_is_short_or_the_run_is_near_its_limit(self):
        said = "Not verified: a second copy of the api."
        self.log("a.claude.m.jsonl", "s1", 20000)
        self.assertIn("second copy", self.budget.nudge(self.budget.state(), 0, said))
        os.environ["KIT_DEADLINE"] = "150"          # 50 s left
        self.assertEqual(self.budget.nudge(self.budget.state(), 0, said), "")
        os.environ["KIT_DEADLINE"] = "300"
        self.log("b.codex.m.jsonl", "s2", 48000)    # the run is at 0.68 of 0.72
        self.assertEqual(self.budget.nudge(self.budget.state(), 0, said), "")

    def test_messages_name_what_the_agent_itself_left_open(self):
        self.log("a.claude.m.jsonl", "s1", 20000)
        now = self.budget.state()
        said = ("The fix is in and the gate is clear.\n- **Not covered:** two api copies racing on one key.\n"
                "- I have no scenario for an attempt already in flight.\n- Report: 53 entries.")
        text = self.budget.nudge(now, 1, said)
        self.assertIn("two api copies racing", text)
        self.assertIn("attempt already in flight", text)
        self.assertNotIn("53 entries", text)
        self.assertEqual(self.budget.open_items("Report: 53 entries."), [])
        self.assertEqual(len(self.budget.open_items(said)), 2)

    def test_a_gap_the_agent_admits_is_followed_up_while_the_run_has_money_whatever_its_share(self):
        self.log("a.claude.m.jsonl", "s1", 35000)   # 0.35 of its 0.36: no room of its own
        now = self.budget.state()
        said = "Fixed.\nI did not add a scenario for a repeat that is leased at the moment of upgrade; only the queued case has been run."
        self.assertEqual(self.budget.nudge(now, 0, "All verified."), "")
        text = self.budget.nudge(now, 0, said)
        self.assertIn("leased at the moment of upgrade", text)
        self.log("b.codex.m.jsonl", "s2", 30000)    # the run is at 0.65 of 0.72: under twelve cents left
        self.assertEqual(self.budget.nudge(self.budget.state(), 0, said), "")

    def test_the_last_message_is_read_from_what_the_harness_hands_the_hook(self):
        given = os.path.join(self.top.name, "stop.json")
        write(given, json.dumps({"last_assistant_message": "x is untested"}))
        self.assertEqual(self.budget.last_message(given), "x is untested")
        transcript = os.path.join(self.top.name, "t.jsonl")
        write(transcript, json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "first"}]}}) + "\n"
              + json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "y is not covered"}]}}) + "\n")
        write(given, json.dumps({"transcript_path": transcript}))
        self.assertEqual(self.budget.last_message(given), "y is not covered")
        self.assertEqual(self.budget.last_message(os.path.join(self.top.name, "missing.json")), "")

    def test_room(self):
        self.log("a.claude.m.jsonl", "s1", 50000)   # 0.50 of 0.72
        self.assertEqual(self.budget.main(["--room", "0.20"]), 0)
        self.assertEqual(self.budget.main(["--room", "0.30"]), 1)

    def test_without_run_sh_it_knows_nothing_and_fails_nothing(self):
        for name in ("KIT_LOGS", "KIT_STARTED"):
            os.environ.pop(name, None)
        self.assertIsNone(self.budget.state())
        self.assertEqual(self.budget.nudge(None), "")
        self.assertEqual(self.budget.main([]), 0)
        self.assertEqual(self.budget.main(["--room", "0.01"]), 1)

if __name__ == "__main__":
    unittest.main()
