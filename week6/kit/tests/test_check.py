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
        self.assertEqual(check.shape(EXAMPLE, report), [])
        self.assertEqual(check.shape(EXAMPLE, {"items": [], "sums": {}, "count": 0}), [])

    def test_keys_of_a_record_must_match_but_keys_of_a_map_are_free(self):
        found = check.shape(EXAMPLE, {"items": [], "sums": {"ZZZ": 1}, "total": 0})
        self.assertEqual(found, ['report: missing "count"', 'report: unexpected "total"'])

    def test_value_kinds(self):
        report = {"items": [{"id": 5, "parts": "p_1"}], "sums": {"AAA": 1.5}, "count": True}
        self.assertEqual(
            check.shape(EXAMPLE, report),
            [
                "report.items[0].id: expected text, found a whole number",
                "report.items[0].parts: expected a list, found text",
                "report.sums.AAA: expected a whole number, found a number",
                "report.count: expected a whole number, found true/false",
            ],
        )

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
