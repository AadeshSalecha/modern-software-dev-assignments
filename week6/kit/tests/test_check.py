"""Tests for the pure parts of kit/check.py. Run: python3 -m unittest discover -s kit/tests"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import check  # noqa: E402

TICKET = """# A ticket

Write the result to `out/summary.json`:

```json
{
  "items": [ { "id": "x_…", "parts": ["p_…"] } ],
  "sums": { "AAA": 0, "BBB": 0 },
  "count": 0
}
```

Also leave notes in out/notes.txt.
"""
EXAMPLE = {"items": [{"id": "x_…", "parts": ["p_…"]}], "sums": {"AAA": 0, "BBB": 0}, "count": 0}


class ShapeTest(unittest.TestCase):
    def test_a_matching_report(self):
        report = {"items": [{"id": "x_1", "parts": ["p_1", "p_2"]}], "sums": {"CCC": 12}, "count": 4}
        self.assertEqual(check.shape(EXAMPLE, report), ([], []))
        self.assertEqual(check.shape(EXAMPLE, {"items": [], "sums": {}, "count": 0}), ([], []))

    def test_keys_of_a_record_must_match_but_keys_of_a_map_are_free(self):
        structure, values = check.shape(EXAMPLE, {"items": [], "sums": {"ZZZ": 1}, "total": 0})
        self.assertEqual(structure, ['report: missing "count"', 'report: unexpected "total"'])
        self.assertEqual(values, [])

    def test_wrong_nesting_is_structure(self):
        structure, values = check.shape(EXAMPLE, {"items": {"id": "x"}, "sums": [1], "count": [0]})
        self.assertEqual(
            structure,
            [
                "report.items: expected a list, found an object",
                "report.sums: expected an object, found a list",
                "report.count: expected a whole number, found a list",
            ],
        )
        self.assertEqual(values, [])

    def test_a_value_of_another_kind_is_only_a_question(self):
        report = {"items": [{"id": 5, "parts": ["p_1"]}], "sums": {"AAA": 1.5}, "count": True}
        structure, values = check.shape(EXAMPLE, report)
        self.assertEqual(structure, [])
        self.assertEqual(
            values,
            [
                "report.items[0].id: the ticket's example has text, this is a whole number",
                "report.sums.AAA: the ticket's example has a whole number, this is a number",
                "report.count: the ticket's example has a whole number, this is true/false",
            ],
        )

    def test_null_in_the_example_and_whole_numbers_for_decimals_are_fine(self):
        example = {"note": None, "rate": 0.0}
        self.assertEqual(check.shape(example, {"note": "anything", "rate": 1}), ([], []))
        self.assertEqual(check.shape(example, {"note": None, "rate": 0.5}), ([], []))

    def test_keys_that_are_placeholders_are_free(self):
        # a report keyed by ids: the example's "ep_…" stands for any endpoint id
        example = {"by_endpoint": {"ep_…": {"deliveries": ["dlv_…"], "amount_minor": 0}}, "skipped_rows": 0}
        report = {"by_endpoint": {"ep_a_1": {"deliveries": ["dlv_1"], "amount_minor": 5},
                                  "ep_b_2": {"deliveries": [], "amount_minor": 0}}, "skipped_rows": 3}
        self.assertEqual(check.shape(example, report), ([], []))
        # the same at the top level, and a map from ids to lists
        self.assertEqual(check.shape({"m_…": ["dlv_…"]}, {"m_one": ["dlv_1"], "m_two": []}), ([], []))
        self.assertEqual(check.shape({"<merchant id>": 0}, {"m_one": 4}), ([], []))
        # inside a map the values are still compared
        structure, values = check.shape(example, {"by_endpoint": {"ep_a_1": {"deliveries": "dlv_1"}}, "skipped_rows": 3})
        self.assertEqual(structure, ['report.by_endpoint.ep_a_1: missing "amount_minor"',
                                     "report.by_endpoint.ep_a_1.deliveries: expected a list, found text"])

    def test_report_differences_never_block(self):
        root, check.ROOT = check.ROOT, tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(check.ROOT, "out"))
            task = os.path.join(check.ROOT, "task.md")
            with open(task, "w", encoding="utf-8") as handle:
                handle.write(TICKET)
            self.assertEqual(check.check_report(task), (["out/summary.json does not exist yet", "out/notes.txt does not exist yet"], []))
            with open(os.path.join(check.ROOT, "out", "notes.txt"), "w") as handle:
                handle.write("x")
            with open(os.path.join(check.ROOT, "out", "summary.json"), "w") as handle:
                handle.write('{"items": {}, "total": 1}')
            hard, notes = check.check_report(task)
            self.assertEqual(hard, [])
            self.assertEqual(len(notes), 1)
            self.assertIn("do not change a correct report to match a placeholder", notes[0])
            with open(os.path.join(check.ROOT, "out", "summary.json"), "w") as handle:
                handle.write("{not json")
            self.assertIn("is not valid JSON", check.check_report(task)[0][0])
        finally:
            check.ROOT = root

    def test_named_outputs_pair_files_with_the_example_after_them(self):
        self.assertEqual(check.named_outputs(TICKET), [("out/summary.json", EXAMPLE), ("out/notes.txt", None)])
        self.assertEqual(check.named_outputs("nothing to write"), [])


class LedgerAndCommandTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root, check.ROOT = check.ROOT, self.tmp.name
        os.makedirs(os.path.join(self.tmp.name, "work"))

    def tearDown(self):
        check.ROOT = self.root
        self.tmp.cleanup()

    def ledger(self, text):
        with open(os.path.join(self.tmp.name, "work", "ledger.md"), "w", encoding="utf-8") as handle:
            handle.write(text)
        return check.check_ledger()

    def test_ledger(self):
        self.assertIn("does not exist", check.check_ledger()[0])
        self.assertIn("no checkbox lines", self.ledger("just prose\n")[0])
        self.assertIn("1 requirement(s) not checked off", self.ledger("- [x] one\n- [ ] two: how\n")[0])
        self.assertEqual(self.ledger("- [x] one\n* [X] two\n"), [])

    def test_test_command_comes_from_the_service(self):
        with open(os.path.join(self.tmp.name, "Makefile"), "w", encoding="utf-8") as handle:
            handle.write("build:\n\ttrue\n\ntest:\n\t@go test ./...\n\techo done\n\nclean:\n\trm x\n")
        self.assertEqual(check.test_command(self.tmp.name), "go test ./... && echo done")
        with open(os.path.join(self.tmp.name, "package.json"), "w", encoding="utf-8") as handle:
            handle.write('{"scripts": {"test": "node --test"}}')
        self.assertEqual(check.test_command(self.tmp.name), "node --test")



class ReuseTest(unittest.TestCase):
    """The stop hook uses the last result again only for the same tree with nothing blocking."""

    def tree(self, top):
        for path, text in (("app/services/api/src/main.ts", "a"), ("app/services/router/main.py", "b"),
                           ("app/services/worker/main.go", "c"), ("work/scenarios/x.json", "{}"),
                           ("work/ledger.md", "- [ ] x"), ("out/report.json", "{}"), ("task.md", "t")):
            os.makedirs(os.path.dirname(os.path.join(top, path)), exist_ok=True)
            with open(os.path.join(top, path), "w", encoding="utf-8") as handle:
                handle.write(text)

    def stamp(self, top, only=None):
        return check.tree_stamp(os.path.join(top, "task.md"), only, root=top, app=os.path.join(top, "app"))

    def test_the_stamp_changes_with_code_scenarios_report_and_scope_and_not_with_caches(self):
        with tempfile.TemporaryDirectory() as top:
            self.tree(top)
            first = self.stamp(top)
            self.assertEqual(first, self.stamp(top))
            self.assertNotEqual(first, self.stamp(top, only="repair"))
            os.makedirs(os.path.join(top, "app/services/router/__pycache__"))
            with open(os.path.join(top, "app/services/router/__pycache__/main.pyc"), "w") as handle:
                handle.write("x")
            self.assertEqual(first, self.stamp(top))
            for path in ("app/services/router/main.py", "work/scenarios/x.json", "out/report.json", "work/ledger.md"):
                before = self.stamp(top)
                with open(os.path.join(top, path), "a", encoding="utf-8") as handle:
                    handle.write("more")
                self.assertNotEqual(before, self.stamp(top), path)

    def test_only_the_hook_reuses_and_only_a_result_without_blocking_lines(self):
        last = {"stamp": "s", "hard": False, "soft": True, "by_agent": True, "text": "check: nothing blocking"}
        self.assertTrue(check.reusable(last, "s", hook=True))
        self.assertFalse(check.reusable(last, "s", hook=False))          # the agent asked: work it out
        self.assertFalse(check.reusable(last, "other", hook=True))       # something changed
        self.assertFalse(check.reusable(dict(last, hard=True), "s", hook=True))
        self.assertFalse(check.reusable(None, "s", hook=True))


if __name__ == "__main__":
    unittest.main()
