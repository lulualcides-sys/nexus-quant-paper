"""V4 executed-price and temporal causality tests (no Binance network)."""
from __future__ import annotations

import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from research.nexus_m1m5.data import Bar
from research.nexus_m1m5.engine import SCENARIOS
from research.nexus_m1m5.v3_policy import aggregate_closed_h1
from research.nexus_m1m5.v4_run import classify
from research.nexus_m1m5.v4_system import (
    HOUR_MS, M5_MS, POLICIES, _close, _entry_signal,
    aligned_closed_hour_at_entry, detect_closed_hour, replay_v4,
)
from research.nexus_m1m5.strategies import build_features


def m5_history(n=3000):
    return [Bar(i * M5_MS, 100., 100.4, 99.6, 100., 100., 50.)
            for i in range(n)]


def mock_signal(h=240):
    return {
        "hour_i": h, "signal_t": h * HOUR_MS, "signal_close": 100.,
        "atr": 1.0, "structure_low": 99., "reason": "frozen_hourly_setup",
    }


class V4ProofTests(unittest.TestCase):
    def test_no_trade_before_closed_hour(self):
        bars = m5_history(3000)
        hours = aggregate_closed_h1(bars)
        ends = [b.t + HOUR_MS for b in hours]
        h = 240
        self.assertEqual(aligned_closed_hour_at_entry(
            bars[(h + 1) * 12 - 1], ends), -1)
        self.assertEqual(aligned_closed_hour_at_entry(
            bars[(h + 1) * 12], ends), h)

    def test_closed_h1_aggregate_only_full_chunks(self):
        self.assertEqual(len(aggregate_closed_h1(m5_history(37))), 3)
        self.assertEqual(len(aggregate_closed_h1(m5_history(35))), 2)

    def test_same_entry_bar_stop_is_not_ignored(self):
        bars = m5_history(3000)
        entry_i = 241 * 12
        bars[entry_i] = Bar(bars[entry_i].t, 100, 110, 90, 101, 100, 50)
        hours = aggregate_closed_h1(bars)
        f = build_features(hours)
        with patch("research.nexus_m1m5.v4_system.detect_closed_hour",
                   side_effect=lambda _h,_f,h,_p: mock_signal(h) if h == 240 else None):
            report, trades = replay_v4(
                bars, hours, f, POLICIES[0], "base",
                start=entry_i, stop=entry_i + 2)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["entry_t"], bars[entry_i].t)
        self.assertEqual(trades[0]["exit_t"], bars[entry_i].t)
        self.assertEqual(trades[0]["exit_reason"], "stop")
        self.assertLess(trades[0]["pnl_usd"], 0)
        self.assertEqual(report["signals"], 1)

    def test_risk_includes_full_fee_and_slippage_and_40pct_notional(self):
        b = Bar(241 * HOUR_MS, 100, 103, 98, 101, 10, 5)
        p = _entry_signal(
            mock_signal(), POLICIES[0], b, 10000,
            SCENARIOS["base"]["fee"], SCENARIOS["base"]["slip"])
        self.assertIsNotNone(p)
        self.assertLessEqual(p["spent"], 4000 + 1e-7)
        stop_fill = p["stop"] * (1 - SCENARIOS["base"]["slip"])
        net_loss = p["spent"] - p["qty"] * stop_fill * (1 - SCENARIOS["base"]["fee"])
        self.assertLessEqual(net_loss, 50 + 1e-6)
        self.assertGreaterEqual(p["distance"] / p["entry"], .012)

    def test_stop_target_ambiguous_candle_chooses_stop(self):
        bars = m5_history(3000)
        idx = 241 * 12
        bars[idx] = Bar(bars[idx].t, 100, 109, 80, 101, 100, 50)
        hours = aggregate_closed_h1(bars)
        f = build_features(hours)
        with patch("research.nexus_m1m5.v4_system.detect_closed_hour",
                   side_effect=lambda _h,_f,h,_p: mock_signal(h) if h == 240 else None):
            _, trades = replay_v4(bars, hours, f, POLICIES[0],
                                  start=idx, stop=idx + 3)
        self.assertEqual(trades[0]["exit_reason"], "stop")

    def test_gap_stop_not_filled_at_stale_stop_level(self):
        p = _entry_signal(
            mock_signal(), POLICIES[0],
            Bar(241 * HOUR_MS, 100, 101, 99, 100, 10, 5),
            10000, .001, .0002)
        b = Bar(p["entry_t"] + M5_MS, 80, 90, 79, 85, 5, 2.5)
        tr = _close(p, b, b.o, "gap_stop", .001, .0002)
        self.assertLess(tr["exit_ref"], p["stop"])
        self.assertLess(tr["pnl_usd"], -50)  # gap can exceed planned loss

    def test_ledger_gross_minus_fees_and_slippage_equals_net(self):
        b = Bar(241 * HOUR_MS, 100, 103, 98, 101, 10, 5)
        p = _entry_signal(mock_signal(), POLICIES[0], b, 10000, .001, .0002)
        t = _close(p, b, p["target"], "target", .001, .0002)
        self.assertAlmostEqual(
            t["gross_usd"] - t["fees_usd"] -
            t["execution_deviation_usd"], t["pnl_usd"], places=5)

    def test_no_new_signal_leaks_from_future_hour(self):
        bars = m5_history(3000)
        hours = aggregate_closed_h1(bars)
        target = 241 * 12
        ends = [h.t + HOUR_MS for h in hours]
        i = aligned_closed_hour_at_entry(bars[target], ends)
        edited = bars[:target + 1] + [
            Bar(z.t, 100, 200, 1, 150, 999, 100)
            for z in bars[target + 1:]]
        hours2 = aggregate_closed_h1(edited)
        ends2 = [h.t + HOUR_MS for h in hours2]
        self.assertEqual(i, aligned_closed_hour_at_entry(
            edited[target], ends2))
        self.assertEqual(hours[i], hours2[i])

    def test_donchian_24h_closes_above_previous_24h_high(self):
        hours = [Bar(i*HOUR_MS, 100., 101., 99., 100., 100., 50.)
                 for i in range(260)]
        h = 240
        hours[h] = Bar(hours[h].t, 100., 103., 99.5, 102., 100., 50.)
        f = SimpleNamespace(
            atr=[1.0] * 260, vol20=[50.0] * 260,
            ema20=[101.] * 260,
            ema50=[95. + .02 * j for j in range(260)],
            ema200=[90. + .01 * j for j in range(260)])
        s = detect_closed_hour(hours, f, h, POLICIES[0])
        self.assertIsNotNone(s)
        self.assertEqual(s["reason"], "closed_h1_donchian_24h_breakout")
        hours[h] = Bar(hours[h].t, 100., 103., 99.5, 100., 100., 50.)
        self.assertIsNone(detect_closed_hour(hours, f, h, POLICIES[0]))

    def test_pullback_signal_independent_of_m5_future(self):
        hours = [Bar(i*HOUR_MS, 100., 101., 99., 100., 100., 50.)
                 for i in range(260)]
        h = 240
        hours[h] = Bar(hours[h].t, 100., 102., 99.6, 101.5, 100., 50.)
        f = SimpleNamespace(
            atr=[1.0] * 260, vol20=[50.] * 260,
            ema20=[101.] * 260,
            ema50=[95. + .02 * j for j in range(260)],
            ema200=[90. + .01 * j for j in range(260)])
        self.assertIsNotNone(
            detect_closed_hour(hours, f, h, POLICIES[2]))

    def test_fee_stress_does_not_turn_loss_into_risk_free_trade(self):
        b = Bar(241 * HOUR_MS, 100, 103, 98, 101, 10, 5)
        for sc, values in SCENARIOS.items():
            dev = values["slip"] + values["impact"]
            p = _entry_signal(
                mock_signal(), POLICIES[2], b, 10000, values["fee"], dev)
            self.assertIsNotNone(p)
            tr = _close(p, b, p["stop"], "stop", values["fee"], dev)
            self.assertLess(tr["pnl_usd"], 0, sc)
            self.assertLessEqual(abs(tr["pnl_usd"]), 50.01, sc)

    def test_at_most_one_trade_per_calendar_day(self):
        bars = m5_history(3500)
        hours = aggregate_closed_h1(bars)
        f = build_features(hours)
        with patch("research.nexus_m1m5.v4_system.detect_closed_hour",
                   side_effect=lambda _h,_f,h,_p: mock_signal(h)):
            _, trades = replay_v4(
                bars, hours, f, POLICIES[0], "base",
                start=241*12, stop=243*12+1)
        from research.nexus_m1m5.engine import local_date
        from collections import Counter
        counts = Counter(local_date(t["entry_t"]) for t in trades)
        self.assertTrue(all(n <= 1 for n in counts.values()))

    def test_absence_of_trades_not_labelled_lucrative(self):
        q = {sc: {"trades_closed": 0, "net_usd": 0,
                  "max_drawdown_pct_mark_to_market": 0,
                  "profit_factor": None,
                  "ci95_expectancy_day_bootstrap_usd": None}
             for sc in SCENARIOS}
        names = [f"development_Q{i}_2025" for i in range(1,5)] + [
            "retrospective_validation_Q1_2026",
            "retrospective_validation_Q2_2026"]
        result, _ = classify({"quarters": {n: q for n in names}})
        self.assertEqual(result, "INCONCLUSIVO")

    def test_small_sample_loss_rejected_before_insufficient_n(self):
        names = [f"development_Q{i}_2025" for i in range(1,5)] + [
            "retrospective_validation_Q1_2026",
            "retrospective_validation_Q2_2026"]
        qs = {n:{sc: {"trades_closed": 1, "net_usd": 1.0,
                      "max_drawdown_pct_mark_to_market": 0,
                      "profit_factor": 2.0,
                      "ci95_expectancy_day_bootstrap_usd": None}
               for sc in SCENARIOS} for n in names}
        qs["retrospective_validation_Q2_2026"]["adverse"]["net_usd"] = -1
        status, _ = classify({"quarters": qs})
        self.assertEqual(status, "REPROVADO")

    def test_frozen_hypotheses_have_no_search_grid(self):
        self.assertEqual(len(POLICIES), 4)
        self.assertEqual({x.setup for x in POLICIES}, {"channel", "pullback"})
        self.assertEqual({x.exit_mode for x in POLICIES}, {"fixed", "trail"})


    def test_independent_backfill_window_is_only_2023_2024(self):
        from research.nexus_m1m5.data import month_range
        from research.nexus_m1m5.v4_backfill import backfill_windows
        months = list(month_range("2024-12", 24))
        windows = backfill_windows(months)
        self.assertEqual(months[0], "2023-01")
        self.assertEqual(months[-1], "2024-12")
        self.assertEqual(len(windows), 8)
        self.assertEqual(sum(b - a for _, a, b in windows), 24)
        with self.assertRaises(ValueError):
            backfill_windows(list(month_range("2025-12", 24)))

    def test_backfill_even_if_2023_and_2024_win_cannot_be_apt(self):
        from research.nexus_m1m5.v4_backfill import assess_backfill
        q = {}
        for year in (2023, 2024):
            for quarter in range(1, 5):
                q[f"unseen_backfill_{year}_Q{quarter}"] = {
                    sc: {"net_usd": 100, "trades_closed": 35}
                    for sc in SCENARIOS
                }
        status, _ = assess_backfill(q)
        self.assertEqual(status, "INCONCLUSIVO")

    def test_backfill_stress_negative_year_is_rejected(self):
        from research.nexus_m1m5.v4_backfill import assess_backfill
        q = {}
        for year in (2023, 2024):
            for quarter in range(1, 5):
                q[f"unseen_backfill_{year}_Q{quarter}"] = {
                    sc: {"net_usd": 10, "trades_closed": 35}
                    for sc in SCENARIOS
                }
        for quarter in range(1, 5):
            q[f"unseen_backfill_2023_Q{quarter}"]["double_cost"]["net_usd"] = -20
        status, _ = assess_backfill(q)
        self.assertEqual(status, "REPROVADO")



if __name__ == "__main__":
    unittest.main()
