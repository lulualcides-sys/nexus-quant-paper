"""Deterministic, offline audit tests for NEXUS CYCLES M5."""
import unittest
from datetime import datetime, timedelta, timezone

from src.nexus_cycles_m5 import (
    NY, Settings, complete_sessions, chronological_report, run, trend_at,
    validate_bars,
)


def sample_session(day=6, worst_case=False, confirmation=True):
    first = datetime(2026, 10, day, 8, 0, tzinfo=NY)
    rows = []
    for j in range(96):
        ts = int((first + timedelta(minutes=5 * j)).timestamp())
        b = dict(time=ts, open=100.0, high=100.4, low=99.6, close=100.0)
        if j == 4:
            b.update(open=100.5, high=101.2, low=100.5, close=101.0)
        if j == 5 and confirmation:
            b.update(open=101.0, high=101.7, low=100.95, close=101.5)
        if j == 6 and confirmation:
            b.update(open=101.8, high=105.0,
                     low=99.4 if worst_case else 101.3, close=102.0)
        rows.append(b)
    return rows


class NexusCyclesM5Tests(unittest.TestCase):
    def test_first_trade_enters_only_next_candle(self):
        rows = sample_session()
        result = run(rows, "A")
        self.assertEqual(result["sessions"], 1)
        self.assertEqual(len(result["trades"]), 1)
        trade = result["trades"][0]
        self.assertEqual(trade["entry_time"], rows[6]["time"])
        self.assertEqual(trade["signal_time"], rows[5]["time"])
        self.assertEqual(trade["exit_reason"], "TARGET")
        self.assertGreater(trade["net_usd"], 0)
        self.assertTrue(result["paper_only"])

    def test_without_c2_no_trade(self):
        rows = sample_session(confirmation=False)
        self.assertEqual(len(run(rows, "A")["trades"]), 0)

    def test_ambiguous_stop_and_target_prefers_stop(self):
        rows = sample_session(worst_case=True)
        trade = run(rows, "A")["trades"][0]
        self.assertEqual(trade["exit_reason"], "STOP")
        self.assertLess(trade["net_usd"], 0)
        self.assertLessEqual(trade["net_usd"], -0.01)

    def test_missing_m5_bar_fails_closed(self):
        rows = sample_session()
        rows.pop(15)
        result = run(rows, "A")
        self.assertEqual(result["sessions"], 0)
        self.assertEqual(len(result["trades"]), 0)
        self.assertEqual(result["skipped_incomplete_sessions"]["2026-10-06"], 1)

    def test_duplicate_bad_ohlc_and_naive_time_are_rejected(self):
        rows = sample_session()
        with self.assertRaises(ValueError):
            validate_bars(rows + [rows[0]])
        broken = [dict(rows[0], high=99)]
        with self.assertRaises(ValueError):
            validate_bars(broken)
        with self.assertRaises(ValueError):
            validate_bars([dict(rows[0], time="2026-10-06T08:00:00")])

    def test_zero_costs_forbidden_and_2x_cost_hurts(self):
        with self.assertRaises(ValueError):
            Settings(fees_roundtrip_bps=0)
        with self.assertRaises(ValueError):
            Settings(slippage_each_side_bps=0)
        rows = sample_session()
        t1 = run(rows, "A", Settings())["trades"][0]
        t2 = run(rows, "A", Settings(fees_roundtrip_bps=16, slippage_each_side_bps=4))["trades"][0]
        self.assertLess(t2["net_usd"], t1["net_usd"])

    def test_h1_uses_last_completed_hour(self):
        h = [{"end": i * 3600, "e50": 120.0, "e200": 100.0, "close": 125.0}
             for i in range(211)]
        for i in range(205):
            h[i]["e50"] = 110.0
        # At hour 205 there is a bullish trend, but it has not closed yet.
        ends = [b["end"] for b in h]
        self.assertFalse(trend_at(h, ends, ends[205] - 1, 1))
        self.assertTrue(trend_at(h, ends, ends[205], 1))
        self.assertFalse(trend_at(h, ends, ends[205], -1))

    def test_variants_are_independent_and_holdout_is_explicit(self):
        rows = sample_session(6) + sample_session(7) + sample_session(8) + sample_session(9)
        report = chronological_report(rows, source="synthetic")
        self.assertEqual(set(report["variants"]), {"A", "B", "C"})
        self.assertFalse(report["valid_for_profit_claim"])
        self.assertEqual(report["variants"]["A"]["all"]["trades"], 4)
        self.assertEqual(report["variants"]["B"]["all"]["trades"], 0)
        self.assertEqual(report["variants"]["A"]["holdout"]["trades"], 2)
        self.assertLess(report["variants"]["A"]["holdout_2x_cost"]["net_usd"],
                        report["variants"]["A"]["holdout"]["net_usd"])

    def test_simple_breakout_baseline_uses_earlier_signal(self):
        rows = sample_session()
        simple = run(rows, "SIMPLE")["trades"][0]
        cycles = run(rows, "A")["trades"][0]
        self.assertEqual(simple["signal_time"], rows[4]["time"])
        self.assertEqual(simple["entry_time"], rows[5]["time"])
        self.assertEqual(cycles["entry_time"], rows[6]["time"])
        self.assertNotEqual(simple["entry_time"], cycles["entry_time"])

    def test_rolling_origin_folds_are_disjoint(self):
        rows = [bar for day in range(6, 18) for bar in sample_session(day)]
        r = chronological_report(rows, source="SYNTHETIC - never market results")
        self.assertEqual(len(r["rolling_origin"]), 3)
        self.assertEqual(set(r["rolling_origin"][0]["results"]),
                         {"A", "B", "C", "SIMPLE"})
        previous_end = None
        for fold in r["rolling_origin"]:
            if previous_end:
                self.assertEqual(fold["test_start"], previous_end)
            previous_end = fold["test_end_exclusive"]
        self.assertFalse(r["valid_for_profit_claim"])

    def test_dst_session_alignment(self):
        first = datetime(2026, 11, 2, 8, 0, tzinfo=NY)
        self.assertEqual(first.utcoffset(), timedelta(hours=-5))
        b = sample_session()
        self.assertIn(datetime(2026, 10, 6).date(), complete_sessions(validate_bars(b))[0])


if __name__ == "__main__":
    unittest.main()
