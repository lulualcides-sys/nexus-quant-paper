"""Regression: the Nexus Quant monitor must never send intraday Telegram alerts."""
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src import runner


class DailyOnlyTelegramTests(unittest.TestCase):
    def test_m15_scan_never_sends_entries_or_exits(self):
        sent = []
        with patch.object(runner, "fetch_usdcad_m15", return_value=[]), \
             patch.object(runner, "process_bb20", return_value={"last_reason": "Saída virtual"}):
            runner.run("mtf", send=lambda msg: sent.append(msg) or True)
        self.assertEqual(sent, [])

    def test_regular_scans_silent_and_daily_digest_once(self):
        sent = []
        def fake_fetch(asset, now):
            return [{"time": now - 3600, "open": 1.0, "high": 1.0,
                     "low": 1.0, "close": 1.0}]
        shadow = {"books": {}, "watermarks": {}, "unavailable": []}
        now = int(datetime(2026, 10, 30, 22, 15, tzinfo=timezone.utc).timestamp())
        with TemporaryDirectory() as td, \
             patch.object(runner, "scan_market", return_value=0), \
             patch.object(runner, "process_gold", return_value={"books": {}}), \
             patch.object(runner, "process_leveraged", return_value={"books": {}}), \
             patch.object(runner, "fetch_usdcad_m15", return_value=[]), \
             patch.object(runner, "process_bb20", return_value={"last_reason": "Entrada virtual"}), \
             patch.object(runner, "process_h1", return_value=shadow), \
             patch.object(runner, "h1_diagnostics", return_value={}), \
             patch.object(runner, "ten_bot_digest", return_value="RESUMO DIÁRIO VIRTUAL"):
            s = Path(td) / "state.json"
            reports = Path(td) / "reports"
            sender = lambda msg: sent.append(msg) or True
            runner.run("scan", now=now, fetch=fake_fetch, send=sender,
                       statefile=s, reports=reports)
            self.assertEqual(sent, [])
            runner.run("report", now=now, fetch=fake_fetch, send=sender,
                       statefile=s, reports=reports)
            runner.run("report", now=now, fetch=fake_fetch, send=sender,
                       statefile=s, reports=reports)
            self.assertEqual(sent, ["RESUMO DIÁRIO VIRTUAL"])
            self.assertTrue((reports / "2026-10-30.txt").exists())

    def test_schedule_does_not_run_hourly_telegram_check(self):
        yaml = Path(".github/workflows/monitor.yml").read_text(encoding="utf-8")
        self.assertNotIn("python -m src.telegram_check", yaml)
        self.assertNotIn("'2 * * * *'", yaml)
        self.assertIn("'15 22 * * 1-5'", yaml)


if __name__ == "__main__":
    unittest.main()
