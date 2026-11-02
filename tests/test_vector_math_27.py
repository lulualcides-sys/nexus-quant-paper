"""Deterministic checks for the 19-step, 27-dimensional math audit."""
import json
import unittest
from copy import deepcopy
from pathlib import Path

from research.vector_math_27 import SOURCE, analyze, markdown, row_vector, wilson


class MathematicalVector27Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads(SOURCE.read_text(encoding="utf-8"))

    def test_exact_census_and_unmodified_inputs(self):
        source=deepcopy(self.source)
        result=analyze(source)
        self.assertEqual(source,self.source)
        self.assertEqual(result["all_27_count"],27)
        self.assertEqual(len(result["vectors"]),27)
        self.assertTrue(result["no_order_execution"])
        self.assertTrue(result["no_strategy_changes"])
        self.assertTrue(result["no_automated_promotion"])
        self.assertEqual(sum(result["sign_count"].values()),27)

    def test_h1_costs_swallow_brutal_gross(self):
        report=analyze(self.source)
        h1=report["groups"]["experimental_h1"]
        self.assertEqual(h1["bots"],15)
        self.assertEqual(h1["closed_trades"],2454)
        self.assertAlmostEqual(h1["costs_usd"],701.31,places=2)
        self.assertAlmostEqual(h1["net_usd"],-576.78,places=2)
        self.assertAlmostEqual(h1["gross_usd"],124.53,places=2)
        self.assertTrue(h1["model_cost_exceeds_positive_gross"])
        self.assertAlmostEqual(h1["double_cost_net_usd"],-1239.68,places=2)

    def test_leveraged_cost_stress_changes_sign(self):
        row=analyze(self.source)["groups"]["leveraged_h4"]
        self.assertAlmostEqual(row["net_usd"],405.97,places=2)
        self.assertAlmostEqual(row["double_cost_net_usd"],-69.01,places=2)
        self.assertEqual(row["bots"],5)
        self.assertTrue(row["gross_usd"]>row["net_usd"])

    def test_per_bot_all_nineteen_steps_and_wilson_interval(self):
        result=analyze(self.source)
        for v in result["vectors"].values():
            d=v["math_steps"]
            self.assertEqual(len(d),19)
            self.assertAlmostEqual(d["5_net_realized_usd"]+d["6_booked_costs_usd"],
                                   d["7_implied_gross_before_booked_costs_usd"],places=2)
            self.assertEqual(v["paper_only"],True)
            self.assertEqual(v["validated_for_real_money"],False)
            self.assertLessEqual(d["17_wilson_95pct_win_rate_interval_pct"][0],
                                 d["17_wilson_95pct_win_rate_interval_pct"][1])
        self.assertEqual(wilson(0,0),[None,None])

    def test_incomplete_or_fictitious_data_fail_closed(self):
        original=deepcopy(self.source)
        original["robots"].pop(next(iter(original["robots"])))
        with self.assertRaisesRegex(ValueError,"27 distinct"):
            analyze(original)
        original=deepcopy(self.source)
        original["analyzed"]=26
        with self.assertRaisesRegex(ValueError,"27 observed"):
            analyze(original)
        original=deepcopy(self.source)
        original["robots"]["gold_h4:rsi_trend"]["net_realized_usd"]=float("nan")
        with self.assertRaisesRegex(ValueError,"numérico"):
            analyze(original)

    def test_markdown_contains_all_names_and_formula(self):
        report=analyze(self.source)
        document=markdown(report)
        self.assertIn("vetor matemático dos 27",document)
        self.assertIn("Payoff aproximado",document)
        self.assertIn("momentum60_h4:momentum60",document)
        self.assertIn("experimental_h1:EURUSD:ema20_retest",document)
        self.assertIn("-576.78",document)


if __name__=="__main__":
    unittest.main()
