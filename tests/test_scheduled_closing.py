"""Testes determinísticos do fechamento por snapshot."""
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.gold_forward import STUDY
from src.leveraged_gold import CONFIG
from src.scheduled_closing import compose, report_day, run


class ScheduledClosingTests(unittest.TestCase):
    def test_local_business_day_and_delayed_run(self):
        scheduled = int(datetime(2026, 11, 6, 22, 30, tzinfo=timezone.utc).timestamp())
        delayed = int(datetime(2026, 11, 7, 4, 30, tzinfo=timezone.utc).timestamp())
        self.assertEqual(report_day(scheduled), "2026-11-06")
        self.assertEqual(report_day(delayed), "2026-11-06")

    def test_read_only_snapshot_reports_no_invented_trades(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            state.mkdir()
            watermark = int(datetime(2026, 11, 6, 16, tzinfo=timezone.utc).timestamp())
            gold_books = {k: {"equity": 5000.0, "closed": [], "position": None}
                          for k in STUDY}
            leveraged_books = {k: {"equity": 5000.0, "closed": [], "position": None,
                                   "frozen": False} for k in CONFIG}
            (state / "selected_gold_v2.json").write_text(json.dumps({
                "paper_only": True, "h4_watermark": watermark, "books": gold_books
            }))
            (state / "leveraged_gold_v1.json").write_text(json.dumps({
                "paper_only": True, "h4_watermark": watermark, "books": leveraged_books
            }))
            now = int(datetime(2026, 11, 6, 22, 30, tzinfo=timezone.utc).timestamp())
            original = (state / "selected_gold_v2.json").read_text()
            message = compose("2026-11-06", root, now)
            self.assertIn("snapshot, sem preço ao vivo", message)
            self.assertIn("Entradas: <b>0</b>", message)
            self.assertEqual((state / "selected_gold_v2.json").read_text(), original)
            self.assertLessEqual(len(message), 4000)

    def test_confirmed_delivery_sets_marker_no_duplicate(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "state").mkdir()
            marker = root / "state" / "market_monitor.json"
            marker.write_text('{"last_report_day": "2026-11-05", "markets": {}}')
            day = int(datetime(2026, 11, 6, 22, 30, tzinfo=timezone.utc).timestamp())
            delivered = []
            with patch("src.scheduled_closing.compose", return_value="<b>📊 NEXUS QUANT</b>"):
                self.assertTrue(run(now=day, root=root, send=lambda message: delivered.append(message) or True))
                self.assertFalse(run(now=day, root=root, send=lambda message: delivered.append(message) or True))
            self.assertEqual(len(delivered), 1)
            self.assertEqual(json.loads(marker.read_text())["last_report_day"], "2026-11-06")
            self.assertTrue((root / "reports" / "2026-11-06.txt").exists())

    def test_failed_delivery_preserves_marker_for_retry(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "state").mkdir()
            marker = root / "state" / "market_monitor.json"
            marker.write_text('{"last_report_day": "2026-11-05"}')
            now = int(datetime(2026, 11, 6, 22, 30, tzinfo=timezone.utc).timestamp())
            with patch("src.scheduled_closing.compose", return_value="Report without live prices"):
                with self.assertRaisesRegex(RuntimeError, "não confirmou"):
                    run(now=now, root=root, send=lambda message: False)
            self.assertEqual(json.loads(marker.read_text())["last_report_day"], "2026-11-05")


if __name__ == "__main__":
    unittest.main()
