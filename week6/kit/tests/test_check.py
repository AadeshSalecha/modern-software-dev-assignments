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


if __name__ == "__main__":
    unittest.main()
