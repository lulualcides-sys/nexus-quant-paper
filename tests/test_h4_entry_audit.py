"""Offline deterministic checks: no live broker/data/model dependencies."""
import unittest
from copy import deepcopy
from unittest.mock import patch

from research.screen_v2 import aggregate_hourly_to_h4
from src.gold_forward import STUDY
from src.leveraged_gold import CONFIG
from src.h4_entry_audit import audit, telegram_summary

T0 = 1791000000 // 14400 * 14400


def hourly(n=1032):
    """One complete hourly sequence: 258 H4 bars, enough for EMA200."""
    return [
        {"time": T0 + i * 3600, "open": 2500.0 + i * 0.08,
         "high": 2500.5 + i * 0.08, "low": 2499.5 + i * 0.08,
         "close": 2500.2 + i * 0.08}
        for i in range(n)
    ]


def books(data):
    latest = aggregate_hourly_to_h4(data)[-1]["time"]
    conventional = {
        "h4_watermark": latest, "paper_only": True,
        "books": {name: {"equity": 5000.0, "position": None, "closed": []} for name in STUDY}
    }
    leveraged = {
        "h4_watermark": latest, "paper_only": True,
        "books": {name: {"equity": 5000.0, "day_start_equity": 5000.0,
                         "frozen": False, "position": None, "closed": []} for name in CONFIG}
    }
    return conventional, leveraged


class H4EntryAuditTests(unittest.TestCase):
    def setUp(self):
        self.data = hourly()
        self.conventional, self.leveraged = books(self.data)
        self.now = aggregate_hourly_to_h4(self.data)[-1]["time"] + 14400 + 3600

    def test_read_only_and_ten_distinct_books(self):
        prior = deepcopy((self.conventional, self.leveraged, self.data))
        result = audit(self.data, self.conventional, self.leveraged, self.now)
        self.assertTrue(result["paper_only"] and result["read_only"])
        self.assertFalse(result["candidates_are_orders"])
        self.assertEqual(len(result["robots"]), 10)
        self.assertEqual(sum(result["counts"].values()), 10)
        self.assertEqual(prior, (self.conventional, self.leveraged, self.data))
        self.assertIn("não ordens", telegram_summary(result))

    def test_fresh_transition_is_preview_only_and_persistent_is_not_new(self):
        latest_index = len(aggregate_hourly_to_h4(self.data)) - 1

        def direction(rule, bars, indicators, index):
            if rule == "rsi_trend" and index == latest_index:
                return 1
            if rule == "channel20" and index >= latest_index - 1:
                return 1
            return 0

        with patch("src.h4_entry_audit.sign", side_effect=direction):
            result = audit(self.data, self.conventional, self.leveraged, self.now)
        self.assertEqual(result["robots"]["rsi_trend"]["status"], "candidate_next_bar")
        self.assertEqual(result["robots"]["rsi_trend"]["preview_direction"], 1)
        self.assertEqual(result["robots"]["channel20"]["status"], "persistent_signal")
        self.assertEqual(result["robots"]["lev_channel20"]["status"], "persistent_signal")
        self.assertEqual(result["counts"]["candidate_next_bar"], 1)
        self.assertTrue(all(b["position"] is None for b in self.conventional["books"].values()))

    def test_position_and_risk_pauses_take_priority(self):
        self.conventional["books"]["channel20"]["position"] = {
            "start": self.now - 14400, "entry": 2500.0, "side": 1}
        self.leveraged["books"]["lev_channel20"]["frozen"] = True
        self.leveraged["books"]["lev_channel55"]["equity"] = 4800.0
        self.leveraged["books"]["lev_momentum40"]["equity"] = float("nan")
        result = audit(self.data, self.conventional, self.leveraged, self.now)
        self.assertEqual(result["robots"]["channel20"]["status"], "in_position")
        self.assertEqual(result["robots"]["lev_channel20"]["status"], "frozen_drawdown")
        self.assertEqual(result["robots"]["lev_channel55"]["status"], "daily_loss_limit")
        self.assertEqual(result["robots"]["lev_momentum40"]["status"], "invalid_equity")
        self.assertEqual(result["robots"]["channel20"]["last_virtual_entry_ts"], self.now - 14400)

    def test_old_data_not_mistaken_for_new_signal(self):
        result = audit(self.data, self.conventional, self.leveraged, self.now + 14 * 3600)
        self.assertTrue(result["stale_or_closed"])
        self.assertEqual(result["counts"]["feed_stale"], 10)

    def test_watermark_mismatch_fail_closed(self):
        self.conventional["h4_watermark"] -= 14400
        with self.assertRaisesRegex(ValueError, "Watermark"):
            audit(self.data, self.conventional, self.leveraged, self.now)

    def test_missing_books_fail_closed(self):
        self.leveraged["books"].pop("lev_channel20")
        with self.assertRaisesRegex(ValueError, "exatamente 5\\+5"):
            audit(self.data, self.conventional, self.leveraged, self.now)

    def test_future_candle_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "futuro"):
            audit(self.data, self.conventional, self.leveraged, self.now - 7200)

    def test_bootstrap_never_invents_entries(self):
        self.conventional["books"]["rsi_trend"]["closed"] = [
            {"entry_ts": T0 + 100000, "exit_ts": T0 + 110000, "net_usd": 2.0}]
        result = audit(self.data, self.conventional, self.leveraged, self.now)
        self.assertEqual(result["robots"]["rsi_trend"]["last_virtual_entry_ts"], T0 + 100000)
        self.assertIsNone(result["robots"]["channel55"]["last_virtual_entry_ts"])


if __name__ == "__main__":
    unittest.main()
