"""V3 regression: fully closed H1, causal stops, fixed risk, scenario isolation."""
import unittest
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import patch

from research.nexus_m1m5.data import Bar
from research.nexus_m1m5.engine import SCENARIOS, replay
from research.nexus_m1m5.strategies import Signal, build_features
from research.nexus_m1m5.v3_policy import (
    aggregate_closed_h1, last_fully_closed_h1_index,
    approve_macro_signal, extra_stop_distance, policies,
)
from research.nexus_m1m5.v3_run import SETUPS


def m5(n=3000):
    return [Bar(i * 300_000, 100.0, 100.4, 99.6, 100.0, 1.0, .5)
            for i in range(n)]


def bullish_mf(n=300):
    # Synthetic monotone, clearly bullish H1 indicators for edge-case tests.
    return SimpleNamespace(
        ema20=[104.0] * n, ema50=[101.0 + .03 * i for i in range(n)],
        ema200=[99.0 + .005 * i for i in range(n)],
        atr=[1.0] * n,
    )


class V3Regressions(unittest.TestCase):
    def test_h1_aggregation_requires_12_exact_contiguous_five_minute_bars(self):
        bars = m5(36)
        hours = aggregate_closed_h1(bars)
        self.assertEqual(len(hours), 3)
        self.assertEqual([b.t for b in hours], [0, 3_600_000, 7_200_000])
        self.assertEqual(hours[0].v, 12.0)

    def test_h1_rejects_incomplete_last_hour(self):
        self.assertEqual(len(aggregate_closed_h1(m5(35))), 2)

    def test_h1_refuses_gap_not_synthetic_fill(self):
        bars = m5(24)
        bars.pop(6)
        hours = aggregate_closed_h1(bars)
        self.assertEqual(len(hours), 1)
        self.assertEqual(hours[0].t, 3_600_000)

    def test_hour_index_excludes_h1_until_exact_hour_close(self):
        bars = m5(36)
        closes = [3_600_000, 7_200_000, 10_800_000]
        self.assertEqual(last_fully_closed_h1_index(bars, 10, closes), -1)
        self.assertEqual(last_fully_closed_h1_index(bars, 11, closes), 0)
        self.assertEqual(last_fully_closed_h1_index(bars, 12, closes), 0)
        self.assertEqual(last_fully_closed_h1_index(bars, 23, closes), 1)

    def test_hour_index_m1_precision(self):
        bars = [Bar(i * 60_000, 100, 101, 99, 100, 1, .5)
                for i in range(120)]
        closes = [3_600_000, 7_200_000]
        self.assertEqual(last_fully_closed_h1_index(bars, 58, closes), -1)
        self.assertEqual(last_fully_closed_h1_index(bars, 59, closes), 0)

    def test_policy_frozen_and_nonzero_cost_stop(self):
        for tf in ("1m", "5m"):
            x, y = policies(tf)
            self.assertEqual(x.mode, "v3")
            self.assertEqual(y.mode, "v3")
            self.assertLess(x.min_stop_pct, y.min_stop_pct)
            self.assertGreater(y.max_hold, x.max_hold)
            self.assertGreater(x.min_stop_pct, 2 * (.001 + .0002))

    def test_200_slope_strict_only(self):
        a, b = policies("5m")
        self.assertFalse(a.require_200_slope)
        self.assertTrue(b.require_200_slope)

    def test_no_future_candle_sneaks_into_h1_signal(self):
        bars = m5(3150)
        closed_hours = aggregate_closed_h1(bars)
        closes = [h.t + 3_600_000 for h in closed_hours]
        idx = 3000
        h0 = last_fully_closed_h1_index(bars, idx, closes)
        changed_future = bars[:idx + 1] + [
            Bar(t.t, 1, 20_000, .1, 10_000, t.v, t.taker)
            for t in bars[idx + 1:]]
        h1 = aggregate_closed_h1(changed_future)
        cl1 = [h.t + 3_600_000 for h in h1]
        self.assertEqual(h0, last_fully_closed_h1_index(changed_future, idx, cl1))
        self.assertEqual(closes[h0], cl1[h0])

    def test_hourly_macro_only_applies_to_selected_closed_signal(self):
        bars = m5(3120)
        hours = aggregate_closed_h1(bars)
        mf = bullish_mf(len(hours))
        closes = [h.t + 3_600_000 for h in hours]
        policy = asdict(policies("5m")[0])
        # Synthetic price is below rising EMA50, which must veto longs.
        self.assertFalse(approve_macro_signal(
            bars, 3100, hours, mf, closes, policy))

    def test_hourly_volatility_filter_must_hold(self):
        bars = m5(3120)
        hours = aggregate_closed_h1(bars)
        mf = bullish_mf(len(hours))
        mf.ema50 = [90.0 + .001 * i for i in range(len(hours))]
        mf.ema200 = [80.0] * len(hours)
        mf.ema20 = [95.0] * len(hours)
        mf.atr = [.001] * len(hours)
        closes = [h.t + 3_600_000 for h in hours]
        self.assertFalse(approve_macro_signal(
            bars, 3100, hours, mf, closes, asdict(policies("5m")[0])))

    def test_stop_floor_never_below_percentage(self):
        bars = m5(3120)
        hours = aggregate_closed_h1(bars)
        mf = bullish_mf(len(hours))
        closes = [h.t + 3_600_000 for h in hours]
        p = asdict(policies("5m")[1])
        value = extra_stop_distance(bars, 3100, hours, mf, closes, p, 101.0)
        self.assertGreaterEqual(value, 101.0 * .009)
        self.assertGreaterEqual(value, 1.0 * 1.2)

    def test_simulator_does_not_shift_v1_and_v2_default_behavior(self):
        bars = m5(320)
        features = build_features(bars)
        first, trades0 = replay(bars, features, "trend", "base",
                                start=220, stop=280)
        second, trades1 = replay(
            bars, features, "trend", "base", start=220, stop=280,
            macro=None, macro_features=None, macro_closes=None)
        self.assertEqual(first, second)
        self.assertEqual(trades0, trades1)

    def test_macro_required_for_opt_in_v3_gate(self):
        bars = m5(320)
        features = build_features(bars)
        conf = asdict(policies("5m")[0])
        mock_sig = Signal("trend", 1.4, 2.0, 99.5, "test")
        with patch("research.nexus_m1m5.engine.signal", return_value=mock_sig):
            rep, trades = replay(
                bars, features, "trend", "base", start=220, stop=260,
                research_policy=conf, macro=None,
                macro_features=None, macro_closes=None)
        self.assertEqual(len(trades), 0)
        self.assertGreater(rep["gate_vetoes"], 0)

    def test_only_predeclared_setup_list(self):
        self.assertEqual(SETUPS, (
            ("sweep", "immediate"), ("trend", "immediate"),
            ("breakout", "retest")))
        self.assertEqual(tuple(SCENARIOS), ("base", "double_cost", "adverse"))


if __name__ == "__main__":
    unittest.main()
