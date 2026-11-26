"""Tests for kit/evidence.py on a small made-up packet. Run: python3 -m unittest discover -s kit/tests"""

import gzip
import json
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import evidence  # noqa: E402

API = [
    '{"ts":"2026-01-01T00:00:00Z","svc":"api","msg":"api.started","release":"9.9"}',
    '{"ts":"2026-01-01T00:00:10Z","svc":"api","msg":"event.accepted","event":"evt_aaaa","merchant":"m_one","type":"payment.captured","amount_minor":1250,"currency":"USD"}',
    '{"ts":"2026-01-01T00:00:11Z","svc":"api","msg":"event.accepted","event":"evt_bbbb","merchant":"m_one","type":"payout.paid","amount_minor":710438,"currency":"JPY"}',
    # the shipper sent this line twice
    '{"ts":"2026-01-01T00:00:11Z","svc":"api","msg":"event.accepted","event":"evt_bbbb","merchant":"m_one","type":"payout.paid","amount_minor":710438,"currency":"JPY"}',
    # cut short, and cut short again later: counted twice
    '{"ts":"2026-01-01T00:00:12Z","svc":"api","msg":"event.acc',
    '{"ts":"2026-01-01T00:00:12Z","svc":"api","msg":"event.acc',
    "10",
]
ROUTER = [
    "2026-01-01T00:00:12Z level=info msg=delivery.created delivery=dlv_1111aaaa event=evt_aaaa endpoint=ep_one_1 version=1",
    "2026-01-01T00:00:12Z level=info msg=delivery.created delivery=dlv_2222bbbb event=evt_bbbb endpoint=ep_one_1 version=1",
    '2026-01-01T00:00:13Z level=warn msg=note text="two words" delivery=dlv_1111aaaa',
    "2026-01-01T00:00:14Z level=info msg=delivery.delivered delivery=dlv_1111aaaa status=200",
    "2026-01-01T00:00:15Z level=info msg=delivery.delivered delivery=",
    "2026-01-01T00:00:15Z level=info msg=delivery.delivered del",
    '2026-01-01T00:00:16Z level=info msg=note text="cut in a quo',
]
WORKER = [
    {"t": 1767225650, "worker": "wrk_1", "op": "attempt.started", "delivery": "dlv_2222bbbb", "attempt": "att_1", "endpoint": "ep_one_1"},
    {"t": 1767225651, "worker": "wrk_1", "op": "attempt.finished", "delivery": "dlv_2222bbbb", "attempt": "att_1", "status": 0},
    # the only file that knows this delivery
    {"t": 1767225652, "worker": "wrk_1", "op": "attempt.started", "delivery": "dlv_3333cccc", "attempt": "att_2", "endpoint": "ep_one_2"},
]
EGRESS = [
    "2026-01-01T00:00:13Z egress POST https://hooks.merchant.example/hooks/ep_one_1 200 webhook-id=dlv_1111aaaa attempt=att_0 event=evt_aaaa bytes=170",
    "2026-01-01T00:00:14Z egress POST https://hooks.merchant.example/hooks/ep_one_1 000 webhook-id=dlv_2222bbbb attempt=att_1 event=evt_bbbb bytes=171 err=upstream_reset",
    "2026-01-01T00:00:15Z egress POST https://hooks.merchant.example/hooks/ep_one_1 200 webho",
    "2026-01-01T00:00:16Z egress POST https://hooks.merchant.example/hooks/ep_one_1 200 webhook-id=dlv_2222bbbb attempt=att_3 event=evt_bbbb bytes=",
]
EXPORT = [
    "received_at,webhook_id,event_id,type,amount,currency,http_status",
    "12/31/2025 19:00,dlv_1111aaaa,evt_aaaa,payment.captured,12.5,USD,200",
    '12/31/2025 19:00,dlv_2222,evt_bbbb,payout.paid,"710,438",JPY,',
    "12/31/2025 19:01,dlv_,evt_aaaa,payment.captured,1.2345,USD,200",
    '12/31/2025 19:01,dlv_2222bbbb,evt_bbbb,payout.paid,"710,4',
    "12/31",
]
SNAPSHOT = {
    "service": "router",
    "now": 1767225700,
    "endpoints": [{"id": "ep_one_1", "merchant_id": "m_one", "enabled": 1, "version": 1}],
    "deliveries": [
        {"id": "dlv_4444dddd", "event_id": "evt_cccc", "endpoint_id": "ep_one_1", "resend_of": None, "state": "queued", "attempts": 0, "available_at": 1767225700}
    ],
}


def write_packet(directory):
    def put(name, lines):
        with open(os.path.join(directory, name), "w", encoding="utf-8", newline="") as handle:
            handle.write("\n".join(lines) + "\n")

    put("api.ndjson", API)
    put("router.log", ROUTER)
    put("egress.log", EGRESS)
    with open(os.path.join(directory, "merchant_export.csv"), "w", encoding="utf-8", newline="") as handle:
        handle.write("\r\n".join(EXPORT) + "\r\n")
    with gzip.open(os.path.join(directory, "worker.jsonl.gz"), "wt", encoding="utf-8") as handle:
        handle.write("\n".join(json.dumps(r, sort_keys=True) for r in WORKER) + '\n{"t":17672256\n')
    os.makedirs(os.path.join(directory, "snapshots"))
    with open(os.path.join(directory, "snapshots", "router-20260101T000140Z.json"), "w", encoding="utf-8") as handle:
        json.dump(SNAPSHOT, handle)


class EvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        incident = os.path.join(cls.tmp.name, "incident")
        os.makedirs(incident)
        write_packet(incident)
        cls.db_path = evidence.build(incident, os.path.join(cls.tmp.name, "work", "evidence.db"))
        cls.db = sqlite3.connect(cls.db_path)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        cls.tmp.cleanup()

    def one(self, query, *args):
        return self.db.execute(query, args).fetchone()

    def test_corrupted_rows_are_counted_each_time_they_appear(self):
        counts = dict(self.db.execute("SELECT file, corrupted_rows FROM skipped"))
        self.assertEqual(
            counts,
            {"api.ndjson": 3, "router.log": 3, "worker.jsonl.gz": 1, "egress.log": 2, "merchant_export.csv": 2},
        )

    def test_a_resent_line_is_one_record(self):
        self.assertEqual(self.one("SELECT count(*), max(copies) FROM api WHERE event = 'evt_bbbb'"), (1, 2))

    def test_clocks_are_normalised_per_file(self):
        self.assertEqual(self.one("SELECT ts, ts_iso FROM api WHERE msg = 'api.started'"), (1767225600, "2026-01-01T00:00:00Z"))
        self.assertEqual(self.one("SELECT ts, ts_iso FROM worker WHERE attempt = 'att_2'"), (1767225652, "2026-01-01T00:00:52Z"))

    def test_log_values_are_typed_and_unquoted(self):
        self.assertEqual(self.one("SELECT text, level FROM router WHERE msg = 'note'"), ("two words", "warn"))
        self.assertEqual(self.one("SELECT status FROM router WHERE msg = 'delivery.delivered'"), (200,))

    def test_request_lines_keep_status_endpoint_and_error(self):
        self.assertEqual(
            self.one("SELECT method, status, url_endpoint, webhook_id, err FROM egress WHERE attempt = 'att_1'"),
            ("POST", 0, "ep_one_1", "dlv_2222bbbb", "upstream_reset"),
        )

    def test_the_address_of_a_request_does_not_decide_the_endpoint(self):
        # dlv_1111aaaa: the router names its endpoint; the address agrees and is kept apart
        self.assertEqual(
            self.one("SELECT endpoint_id, url_endpoint FROM deliveries WHERE delivery_id = 'dlv_1111aaaa'"),
            ("ep_one_1", "ep_one_1"),
        )

    def test_export_ids_amounts_and_statuses(self):
        rows = self.db.execute(
            "SELECT webhook_id, delivery_id, amount_minor, status FROM merchant_export ORDER BY line_no"
        ).fetchall()
        self.assertEqual(
            rows,
            [
                ("dlv_1111aaaa", "dlv_1111aaaa", 1250, 200),
                ("dlv_2222", "dlv_2222bbbb", 710438, None),  # cut id resolved; no answer recorded
                ("dlv_", None, None, 200),  # ambiguous prefix; amount has too many digits for USD
            ],
        )

    def test_export_clock_offset_needs_enough_matches(self):
        self.assertEqual(self.one("SELECT count(ts) FROM merchant_export"), (0,))

    def test_deliveries_are_joined_across_files(self):
        self.assertEqual(
            self.one("SELECT event_id, endpoint_id, conflict FROM deliveries WHERE delivery_id = 'dlv_1111aaaa'"),
            ("evt_aaaa", "ep_one_1", 0),
        )
        # known to the worker only, and to a snapshot only
        self.assertEqual(self.one("SELECT endpoint_id, sources FROM deliveries WHERE delivery_id = 'dlv_3333cccc'"), ("ep_one_2", "worker"))
        self.assertEqual(self.one("SELECT event_id FROM deliveries WHERE delivery_id = 'dlv_4444dddd'"), ("evt_cccc",))

    def test_events_are_joined_across_files(self):
        self.assertEqual(
            self.one("SELECT merchant_id, type, amount_minor, currency, conflict FROM events WHERE event_id = 'evt_bbbb'"),
            ("m_one", "payout.paid", 710438, "JPY", 0),
        )

    def test_responses_union_every_file_with_a_status(self):
        rows = self.db.execute(
            "SELECT source, status FROM responses WHERE delivery_id = 'dlv_1111aaaa' ORDER BY source"
        ).fetchall()
        self.assertEqual(rows, [("egress", 200), ("merchant_export", 200), ("router", 200)])
        rows = self.db.execute(
            "SELECT source, status FROM responses WHERE delivery_id = 'dlv_2222bbbb' ORDER BY source"
        ).fetchall()
        self.assertEqual(rows, [("egress", 0), ("worker", 0)])

    def test_snapshots_become_tables(self):
        self.assertEqual(self.one("SELECT state, snapshot_now FROM snapshot_deliveries"), ("queued", 1767225700))
        self.assertEqual(self.one("SELECT merchant_id FROM snapshot_endpoints"), ("m_one",))


class PacketLayoutTest(unittest.TestCase):
    def build(self, files):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        incident = os.path.join(tmp.name, "incident")
        for name, lines in files.items():
            path = os.path.join(incident, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines) + "\n")
        db = sqlite3.connect(evidence.build(incident, os.path.join(tmp.name, "work", "evidence.db")))
        self.addCleanup(db.close)
        return db

    def test_files_that_share_a_name_are_one_table(self):
        line = "2026-01-01T00:00:0%dZ level=info msg=delivery.created delivery=dlv_%d event=evt_1 endpoint=ep_1"
        db = self.build({"router.log": [line % (1, 1), "2026-01-01T00:00:02Z level=info msg=x del"],
                         "router.log.1": [line % (3, 2), line % (1, 1)],
                         "more/router.log": [line % (4, 3)]})
        self.assertEqual(db.execute("SELECT delivery, file, copies FROM router ORDER BY delivery").fetchall(),
                         [("dlv_1", "router.log", 2), ("dlv_2", "router.log.1", 1)])
        self.assertEqual(db.execute("SELECT delivery FROM more_router").fetchall(), [("dlv_3",)])
        self.assertEqual(dict(db.execute("SELECT file, corrupted_rows FROM skipped")),
                         {"router.log": 1, "router.log.1": 0, os.path.join("more", "router.log"): 0})
        self.assertEqual(db.execute("SELECT count(*) FROM deliveries").fetchone(), (3,))

    def test_a_file_named_like_a_joined_table_does_not_break_the_build(self):
        db = self.build({"events.ndjson": ['{"ts":"2026-01-01T00:00:00Z","msg":"x","event":"evt_9"}']})
        self.assertEqual(db.execute("SELECT event FROM events_file").fetchall(), [("evt_9",)])
        self.assertEqual(db.execute("SELECT event_id FROM events").fetchall(), [("evt_9",)])


class RulesTest(unittest.TestCase):
    def test_log_line_rule(self):
        good = "2026-01-01T00:00:00Z level=info msg=x a=1"
        self.assertIsNotNone(evidence.parse_log_line(good))
        for cut in (good + " b=", good + " b", good + ' c="x y', "2026-01-01T00:0"):
            self.assertIsNone(evidence.parse_log_line(cut), cut)

    def test_major_to_minor(self):
        digits = evidence.MINOR_DIGITS
        self.assertEqual(evidence.to_minor("12.5", "USD", digits), 1250)
        self.assertEqual(evidence.to_minor("1,250.00", "EUR", digits), 125000)
        self.assertEqual(evidence.to_minor("12", "JPY", digits), 12)
        self.assertEqual(evidence.to_minor("12.5", "KWD", digits), 12500)
        self.assertIsNone(evidence.to_minor("12.5", "JPY", digits))
        self.assertIsNone(evidence.to_minor("12.5", "XXX", digits))


if __name__ == "__main__":
    unittest.main()
