"""Focused regressions: new virtual operations and truthful reports."""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.entry_alerts import changes, bb_changes, send_pending
from src.daily_digest import digest
from src.gold_forward import DISPLAY, STUDY
from src.leveraged_gold import CONFIG
from src.bb_rebound_mtf import CAPITAL as BB_CAPITAL


class EntryAlertsTests(unittest.TestCase):
    def setUp(self):
        self.old = {"books": {"bot": {"position": None, "closed": []}}}
        self.trade = {"side": -1, "entry": 4010.0, "start": 1793260800, "qty": 0.2}
        self.labels = {"bot": "My Bot"}

    def test_new_open_alert_once_not_replayed(self):
        current = {"books": {"bot": {"position": self.trade, "closed": []}}}
        events = changes(self.old, current, self.labels, "gold")
        self.assertEqual(len(events), 1)
        self.assertIn("ENTRADA virtual", events[0]["line"])
        self.assertIn("VENDA", events[0]["line"])
        self.assertEqual(changes(current, current, self.labels, "gold"), [])

    def test_close_of_existing_position_not_new_entry(self):
        close = {"entry_ts": self.trade["start"], "exit_ts": 1793275200,
                 "side": -1, "entry": 4010.0, "net_usd": -2.75}
        before = {"books": {"bot": {"position": self.trade, "closed": []}}}
        after = {"books": {"bot": {"position": None, "closed": [close]}}}
        events = changes(before, after, self.labels, "gold")
        self.assertEqual(len(events), 1)
        self.assertIn("SAÍDA virtual", events[0]["line"])
        self.assertIn("-2.75", events[0]["line"])

    def test_entry_and_exit_between_scans_both_reported(self):
        close = {"entry_ts": self.trade["start"], "exit_ts": 1793275200,
                 "side": -1, "entry": 4010.0, "net_usd": 5.45}
        after = {"books": {"bot": {"position": None, "closed": [close]}}}
        events = changes(self.old, after, self.labels, "gold")
        self.assertEqual(len(events), 2)
        self.assertEqual(len({e["id"] for e in events}), 2)

    def test_m15_market_is_labeled_without_fake_broker_fill(self):
        old = {"position": None, "closed": []}
        new = {"position": {"entry": 1.4, "side": 1, "entry_ts": 1793260800}, "closed": []}
        events = bb_changes(old, new)
        self.assertEqual(len(events), 1)
        self.assertIn("USD/CAD", events[0]["line"])

    def test_telegram_failure_keeps_queue_and_success_deduplicates(self):
        event = changes(self.old, {"books": {"bot": {"position": self.trade,
                                                      "closed": []}}}, self.labels, "gold")
        with TemporaryDirectory() as td:
            path = Path(td) / "outbox.json"
            self.assertEqual(send_pending(event, lambda msg: False, path), 0)
            self.assertEqual(len(json.loads(path.read_text())["pending"]), 1)
            sent = []
            self.assertEqual(send_pending(event, lambda msg: sent.append(msg) or True, path), 1)
            self.assertEqual(send_pending(event, lambda msg: sent.append(msg) or True, path), 0)
            self.assertEqual(len(sent), 1)
            self.assertIn("NÃO é ordem FBS", sent[0])


class DailyEntryDigestTests(unittest.TestCase):
    def test_reports_open_entries_even_when_no_exits(self):
        conv = {"books": {k: {"position": None, "closed": [], "equity": 5000}
                          for k in STUDY}}
        lev = {"books": {k: {"position": None, "closed": [], "equity": 5000,
                            "peak_equity": 5000, "frozen": False}
                         for k in CONFIG}}
        conv["books"]["channel20"]["position"] = {
            "side": -1, "entry": 3984.3, "start": 1793347200,
        }
        msg = digest("2026-10-30", conv, lev)
        self.assertIn("1 entradas / 0 fech.", msg)
        self.assertIn("aberta VENDA", msg)
        self.assertIn("Entradas virtuais abertas hoje: 1", msg)
        self.assertIn("RESULTADOS VIRTUAIS", msg)


if __name__ == "__main__":
    unittest.main()
