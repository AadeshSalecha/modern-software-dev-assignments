"""Tests for kit/cross.py (the parts that run no services) and kit/spend.py."""

import json
import os
import sys
import tempfile
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
    def score(self, usable=True, changed=True, shipped=0, other=0):
        fails = [{"author": "shipped"}] * shipped + [{"author": "b"}] * other
        return {"usable": usable, "changed": changed, "fails": fails, "passed": 0}

    def test_a_tie_goes_to_a(self):
        self.assertEqual(cross.better({"a": self.score(), "b": self.score()}), "a")

    def test_fewer_failures_wins(self):
        self.assertEqual(cross.better({"a": self.score(other=2), "b": self.score(other=1)}), "b")

    def test_a_repair_that_breaks_a_shipped_scenario_loses_to_one_that_fails_more_new_ones(self):
        self.assertEqual(cross.better({"a": self.score(shipped=1), "b": self.score(other=3)}), "b")

    def test_unchanged_or_unbuildable_loses(self):
        self.assertEqual(cross.better({"a": self.score(changed=False), "b": self.score(other=4)}), "b")
        self.assertEqual(cross.better({"a": self.score(usable=False), "b": self.score(other=4)}), "b")


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

    def test_a_session_that_was_cut_off_is_estimated_from_its_messages(self):
        with tempfile.TemporaryDirectory() as top:
            log = os.path.join(top, "a.claude.m.jsonl")
            message = {"type": "assistant", "message": {"id": "x", "model": "m", "content": [{"type": "text", "text": "y" * 250}],
                                                        "usage": {"input_tokens": 1000000, "cache_read_input_tokens": 0}}}
            write(log, json.dumps(message) + "\n")
            self.assertGreater(spend.cost_of(log, self.CARD), 1.0)

    def test_codex_turns_are_priced_with_cached_input_apart(self):
        with tempfile.TemporaryDirectory() as top:
            log = os.path.join(top, "b.codex.m.jsonl")
            write(log, json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1000000, "cached_input_tokens": 900000,
                                                                       "output_tokens": 0}}) + "\n")
            self.assertAlmostEqual(spend.cost_of(log, self.CARD), 0.1 + 0.09)


if __name__ == "__main__":
    unittest.main()
