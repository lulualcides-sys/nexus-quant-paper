"""V2 regression: no lookahead, no fee-stress-dependent signal selection, no fake promotion."""
from __future__ import annotations

import unittest
from dataclasses import asdict
from unittest.mock import patch

from research.nexus_m1m5.data import Bar, month_range
from research.nexus_m1m5.engine import SCENARIOS, replay
from research.nexus_m1m5.strategies import Signal, build_features
from research.nexus_m1m5.v2_policy import approve_closed_signal, policies
from research.nexus_m1m5.v2_run import judge, QUARTERS


def synthetic(n=420, *, high=100.2, low=99.8, step=300_000):
    return [Bar(i * step, 100.0, high, low, 100.0, 100.0, 58.0)
            for i in range(n)]


class V2PolicyTests(unittest.TestCase):
    def test_preregistered_policies_not_optimizer(self):
        for tf in ("1m", "5m"):
            choices = policies(tf)
            self.assertEqual(len(choices), 2)
            self.assertEqual(choices[0].reward_to_cost, 2.0)
            self.assertEqual(choices[0].target_r, 4.0)
            self.assertFalse(choices[0].trend_gate)
            self.assertTrue(choices[1].trend_gate)
            self.assertGreater(choices[0].max_hold, 90)

    def test_closed_candle_rejects_unaffordable_target(self):
        bars = synthetic(high=100.02, low=99.98)
        f = build_features(bars)
        sig = Signal("sweep", 1.25, 2.0, 99.99, "synthetic")
        allowed = approve_closed_signal(
            "sweep", sig, bars, f, 230,
            cost=SCENARIOS["base"], reward_to_cost=2.0,
            target_r=4.0, trend_gate=False,
        )
        self.assertFalse(allowed)

    def test_closed_candle_accepts_large_theoretical_target_not_profit_claim(self):
        bars = synthetic()
        f = build_features(bars)
        sig = Signal("sweep", 1.25, 2.0, 99.7, "synthetic")
        self.assertTrue(approve_closed_signal(
            "sweep", sig, bars, f, 230, cost=SCENARIOS["base"],
            reward_to_cost=2.0, target_r=4.0, trend_gate=False))

    def test_high_target_does_not_override_downtrend_veto(self):
        bars = synthetic()
        f = build_features(bars)
        sig = Signal("flow", 1.3, 1.8, 99.7, "test")
        self.assertFalse(approve_closed_signal(
            "flow", sig, bars, f, 230, cost=SCENARIOS["base"],
            reward_to_cost=2, target_r=4, trend_gate=True))

    def test_future_bars_cannot_retroactively_change_gate(self):
        bars = synthetic(n=350)
        f = build_features(bars)
        future = bars + [Bar(i * 300_000, 100, 150, 80, 120, 100_000, 70_000)
                         for i in range(350, 380)]
        ff = build_features(future)
        sig = Signal("flow", 1.3, 1.8, 99.7, "test")
        def verdict(b, features):
            return approve_closed_signal(
                "flow", sig, b, features, 260,
                cost=SCENARIOS["base"], reward_to_cost=2,
                target_r=4, trend_gate=False)
        self.assertEqual(verdict(bars, f), verdict(future, ff))

    def test_stress_cost_must_not_change_frozen_entry_signal_count(self):
        bars = synthetic(n=260)
        f = build_features(bars)
        sig = Signal("sweep", 1.25, 2.0, 99.6, "synthetic")
        policy = asdict(policies("1m")[0])
        def one_signal(*args, **kwargs):
            return sig if args[3] == 210 else None
        metrics = []
        for scenario in ("base", "double_cost", "adverse"):
            with patch("research.nexus_m1m5.engine.signal", side_effect=one_signal):
                rep, trades = replay(
                    bars, f, "sweep", scenario, start=210, stop=245,
                    research_policy=policy)
            metrics.append(rep)
        self.assertEqual([r["signals"] for r in metrics], [1, 1, 1])
        self.assertTrue(all(r["gate_vetoes"] == 0 for r in metrics))
        self.assertEqual([r["trades_closed"] for r in metrics], [1, 1, 1])
        self.assertLessEqual(metrics[1]["net_usd"], metrics[0]["net_usd"])

    def test_policy_none_is_reproducibly_v1(self):
        bars = synthetic(n=260)
        f = build_features(bars)
        a, trades_a = replay(bars, f, "vwap", "base", start=210, stop=240)
        b, trades_b = replay(bars, f, "vwap", "base", start=210, stop=240,
                             research_policy=None)
        self.assertEqual(a, b)
        self.assertEqual(trades_a, trades_b)

    def test_v2_does_not_reuse_exposed_holdout(self):
        months = list(month_range("2026-06", 18))
        self.assertEqual(months[0], "2025-01")
        self.assertEqual(months[-1], "2026-06")
        self.assertEqual(QUARTERS[-1][2], 18)
        self.assertEqual(sum(v[2] - v[1] for v in QUARTERS), 18)

    def test_no_promotion_even_when_all_paper_metrics_positive(self):
        quarters = {}
        for name, _, _ in QUARTERS:
            quarters[name] = {sc: {
                "net_usd": 100,
                "trades_closed": 40,
                "max_drawdown_pct_mark_to_market": 1,
            } for sc in SCENARIOS}
        state, reason = judge({"quarters": quarters})
        self.assertEqual(state, "INCONCLUSIVO")
        self.assertIn("exposed", reason)

    def test_reject_negative_validation_without_any_selection(self):
        quarters = {}
        for name, _, _ in QUARTERS:
            quarters[name] = {sc: {
                "net_usd": 100,
                "trades_closed": 40,
                "max_drawdown_pct_mark_to_market": 1,
            } for sc in SCENARIOS}
        quarters["retrospective_validation_Q1_2026"]["adverse"]["net_usd"] = -1
        self.assertEqual(judge({"quarters": quarters})[0], "REPROVADO")

    def test_small_sample_with_observed_net_loss_is_still_rejected(self):
        quarters = {}
        for name, _, _ in QUARTERS:
            quarters[name] = {sc: {
                "net_usd": 12, "trades_closed": 5,
                "max_drawdown_pct_mark_to_market": 1,
            } for sc in SCENARIOS}
        quarters["retrospective_validation_Q1_2026"]["base"]["net_usd"] = -0.5
        self.assertEqual(judge({"quarters": quarters})[0], "REPROVADO")

    def test_inconclusive_when_there_are_no_signals(self):
        quarters = {}
        for name, _, _ in QUARTERS:
            quarters[name] = {sc: {
                "net_usd": 0,
                "trades_closed": 0,
                "max_drawdown_pct_mark_to_market": 0,
            } for sc in SCENARIOS}
        self.assertEqual(judge({"quarters": quarters})[0], "INCONCLUSIVO")


if __name__ == "__main__":
    unittest.main()
