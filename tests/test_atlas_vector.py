"""ATLAS: math, forward-only accounting and worst-case OHLC execution tests."""
import copy
import unittest
from unittest.mock import patch

from src.atlas_vector import (
    CAPITAL, RISK, aggregate_h4, daily_line, initial, scorecard, signal,
    step, update, vector_levels,
)
from src.feed import parse_yahoo

T0 = (1791000000 // 14400) * 14400


def hourly(n=64, *, volume=100):
    result = []
    for i in range(n):
        for j in range(4):
            result.append({
                "time": T0 + i * 14400 + j * 3600,
                "open": 100.0, "high": 102.0, "low": 98.0, "close": 100.0,
                **({"volume": float(volume)} if volume is not None else {}),
            })
    return result


def mutate_h4(candles, i, *, high=None, low=None, open=None, close=None, volume=None):
    # The four-bar aggregate has exactly the requested OHLCV extremes.
    for j in range(4):
        bar = candles[4 * i + j]
        for name, value in (("high", high), ("low", low), ("open", open), ("close", close)):
            if value is not None:
                bar[name] = value
        if volume is not None:
            bar["volume"] = volume


class AtlasVectorTests(unittest.TestCase):
    def test_vector_is_nominal_one_to_one_not_two_to_one(self):
        bar = {"low": 90.0, "high": 100.0}
        for side in (1, -1):
            levels = vector_levels(bar, side)
            self.assertEqual(levels["entry"], 95)
            self.assertEqual(abs(levels["target"] - levels["entry"]),
                             abs(levels["entry"] - levels["stop"]))
        self.assertEqual(vector_levels(bar, 1)["target"], 110)
        self.assertEqual(vector_levels(bar, 1)["stop"], 80)
        self.assertEqual(vector_levels(bar, -1)["target"], 80)
        self.assertEqual(vector_levels(bar, -1)["stop"], 110)

    def test_wick_volume_sweep_and_no_volume_fail_closed(self):
        prior = [{"time": i, "open": 95.0, "close": 95.0, "high": 100.0,
                  "low": 90.0, "volume": 100.0} for i in range(20)]
        buy = {"time": 20, "open": 94.0, "close": 92.0, "low": 88.0,
               "high": 98.0, "volume": 200.0}
        sell = {"time": 20, "open": 96.0, "close": 98.0, "low": 92.0,
                "high": 102.0, "volume": 200.0}
        self.assertEqual(signal(prior + [buy], 20), 1)
        self.assertEqual(signal(prior + [sell], 20), -1)
        self.assertEqual(signal(prior + [{**buy, "volume": 50}], 20), 0)
        self.assertEqual(signal(prior + [{k:v for k,v in buy.items() if k!="volume"}], 20), 0)

    def test_bootstrap_does_not_retrotrade_and_is_idempotent(self):
        data = hourly()
        book = update(None, data)
        self.assertEqual(book["h4_watermark"], aggregate_h4(data)[-1]["time"])
        self.assertEqual((book["entries"], book["closed"]), ([], []))
        snapshot = copy.deepcopy(book)
        self.assertEqual(update(book, data), snapshot)

    def test_entry_requires_next_bar_and_respects_capital_risk(self):
        data = hourly(64)
        book = update(None, data)
        upcoming = hourly(65)
        with patch("src.atlas_vector.signal", side_effect=lambda bars, i: 1 if i == 63 else 0), \
             patch("src.atlas_vector.entry_permission", return_value=True):
            update(book, upcoming)
        self.assertEqual(len(book["entries"]), 1)
        self.assertIsNotNone(book["position"])
        p = book["position"]
        self.assertEqual(p["entry_ts"], aggregate_h4(upcoming)[-1]["time"])
        self.assertEqual(p["entry"], 100)
        self.assertEqual(p["stop"], 94)
        self.assertEqual(p["target"], 106)
        self.assertLessEqual(p["qty"] * p["entry"], CAPITAL + 1e-6)
        self.assertLessEqual(p["qty"] * (p["entry"] - p["stop"]), CAPITAL * RISK + 1e-6)
        self.assertEqual(len(book["closed"]), 0)
        update(book, upcoming)  # never double-fill same timestamp
        self.assertEqual(len(book["entries"]), 1)

        more = hourly(66)
        mutate_h4(more, 65, high=107, low=99, close=105)
        update(book, more)
        stats = scorecard(book)
        self.assertEqual((stats["closed"], stats["wins"], stats["losses"]), (1, 1, 0))
        self.assertEqual(stats["winrate_pct"], 100)
        self.assertIn("V/D 1/0", daily_line(book, "2026-11-05"))

    def test_target_on_fill_bar_is_not_counted_as_certain_win(self):
        book = update(None, hourly(64))
        data = hourly(65)
        mutate_h4(data, 64, high=108, low=98)
        with patch("src.atlas_vector.signal", side_effect=lambda bars, i: 1 if i == 63 else 0), \
             patch("src.atlas_vector.entry_permission", return_value=True):
            update(book, data)
        self.assertIsNotNone(book["position"])
        self.assertEqual(book["closed"], [])
        self.assertEqual(book["last_reason"], "entered_target_order_uncertain")

    def test_stop_and_target_same_fill_bar_is_conservative_loss(self):
        book = update(None, hourly(64))
        data = hourly(65)
        mutate_h4(data, 64, high=108, low=93)
        with patch("src.atlas_vector.signal", side_effect=lambda bars, i: 1 if i == 63 else 0), \
             patch("src.atlas_vector.entry_permission", return_value=True):
            update(book, data)
        self.assertIsNone(book["position"])
        self.assertEqual(book["closed"][0]["exit_type"], "STOP_SAME_BAR")
        self.assertTrue(book["closed"][0]["same_bar_order_uncertain"])
        self.assertLess(book["closed"][0]["net_usd"], 0)
        self.assertEqual(scorecard(book)["winrate_pct"], 0)

    def test_missing_volume_never_forges_signals(self):
        book = update(None, hourly(64, volume=None))
        update(book, hourly(65, volume=None))
        self.assertEqual(book["entries"], [])
        self.assertEqual(book["last_reason"], "volume_missing_no_signal")

    def test_watermark_and_tampered_state_fail_closed(self):
        book = update(None, hourly(64))
        book["h4_watermark"] = 1
        with self.assertRaisesRegex(ValueError, "watermark lost"):
            update(book, hourly(65))
        book = update(None, hourly(64))
        book["paper_only"] = False
        with self.assertRaisesRegex(ValueError, "incompatible"):
            update(book, hourly(65))

    def test_volume_is_optional_not_synthesized_in_yahoo_parser(self):
        ts = 1791000000
        quotes = {"open": [100], "high": [102], "low": [98], "close": [100], "volume": [153]}
        payload = {"chart": {"result": [{"timestamp": [ts], "indicators": {"quote": [quotes]}}]}}
        result = parse_yahoo(payload, ts + 7200)
        self.assertEqual(result[0]["volume"], 153)
        quotes.pop("volume")
        result = parse_yahoo(payload, ts + 7200)
        self.assertNotIn("volume", result[0])


if __name__ == "__main__":
    unittest.main()
