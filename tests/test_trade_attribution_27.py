"""Focused, offline regressions for paper-trade loss attribution."""
import copy
import unittest

from research.trade_attribution_27 import attribute_trades


class TradeAttribution27Tests(unittest.TestCase):
    def trades(self):
        return [
            {"entry_ts": 1764579600, "exit_ts": 1764583200,
             "exit_type": "TARGET", "net_usd": 12, "cost_usd": 2},
            {"entry_ts": 1764586800, "exit_ts": 1764594000,
             "exit_type": "STOP", "net_usd": -7, "cost_usd": 1},
            {"entry_ts": 1764673200, "exit_ts": 1764676800,
             "exit_type": "STOP", "net_usd": -3, "cost_usd": 1},
            {"entry_ts": 1764676800, "exit_ts": 1764680400,
             "exit_type": "TIME", "net_usd": 0, "cost_usd": 0.5},
        ]

    def test_profit_factor_payoff_expectancy_and_loss_reason(self):
        d = attribute_trades(self.trades())
        self.assertEqual(d["trades"], 4)
        self.assertEqual((d["wins"], d["losses"], d["flats"]), (1, 2, 1))
        self.assertEqual(d["net_usd"], 2)
        self.assertEqual(d["avg_net_usd"], 0.5)
        self.assertEqual(d["profit_factor"], 1.2)
        self.assertEqual(d["mean_winner_usd"], 12)
        self.assertEqual(d["mean_loser_abs_usd"], 5)
        self.assertEqual(d["payoff_win_loss"], 2.4)
        self.assertEqual(d["recorded_costs_usd"], 4.5)
        self.assertEqual(d["by_exit_reason"]["STOP"]["total_losing_trades_abs_usd"], 10)
        self.assertEqual(d["by_exit_reason"]["STOP"]["losses"], 2)
        self.assertEqual(d["worst_five"][0]["net"], -7)

    def test_calendar_buckets_are_utc_and_all_trades_are_counted(self):
        d = attribute_trades(self.trades())
        self.assertEqual(sum(v["trades"] for v in d["by_entry_hour_utc"].values()), 4)
        self.assertEqual(sum(v["trades"] for v in d["by_exit_month_utc"].values()), 4)
        self.assertIn("2025-12", d["by_exit_month_utc"])

    def test_no_trades_is_not_proof_of_zero_risk(self):
        d = attribute_trades([])
        self.assertEqual(d["trades"], 0)
        self.assertIsNone(d["avg_net_usd"])
        self.assertIsNone(d["profit_factor"])
        self.assertIsNone(d["payoff_win_loss"])
        self.assertEqual(d["worst_five"], [])

    def test_missing_cost_does_not_become_fake_zero(self):
        d = attribute_trades([{"net_usd": -1, "exit_type": "STOP"}])
        self.assertIsNone(d["recorded_costs_usd"])
        self.assertEqual(d["trades_missing_cost"], 1)
        self.assertEqual(d["trades_missing_entry_or_exit_time"], 1)
        self.assertIn("UNKNOWN", d["by_exit_month_utc"])

    def test_funding_cost_is_additive_not_double_counted(self):
        d = attribute_trades([{"net_usd": 5, "cost_usd": 2,
                                "transaction_cost": 2, "funding_cost": 0.5}])
        self.assertEqual(d["recorded_costs_usd"], 2.5)

    def test_cost_can_erase_positive_pre_cost_result(self):
        d = attribute_trades([{"net_usd": -0.2, "cost_usd": 0.5}])
        self.assertEqual(d["cost_erased_positive_gross_trades"], 1)

    def test_bad_financial_inputs_fail_closed(self):
        for bad in (float("nan"), float("inf"), None, "unparseable", True):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                attribute_trades([{"net_usd": bad, "cost_usd": 1}])
        with self.assertRaises(ValueError):
            attribute_trades([{"net_usd": 2, "cost_usd": -1}])
        with self.assertRaises(ValueError):
            attribute_trades({"net_usd": 1})

    def test_exit_before_entry_is_rejected(self):
        with self.assertRaises(ValueError):
            attribute_trades([{"net_usd": -1, "entry_ts": 2000,
                                "exit_ts": 1000, "cost_usd": 0.1}])

    def test_source_trades_are_never_modified(self):
        source = self.trades()
        original = copy.deepcopy(source)
        attribute_trades(source)
        self.assertEqual(source, original)

    def test_empty_loss_set_never_invents_losses(self):
        d = attribute_trades([{"net_usd": 4, "cost_usd": 1}])
        self.assertEqual(d["losses"], 0)
        self.assertIsNone(d["profit_factor"])
        self.assertEqual(d["by_exit_reason"]["UNKNOWN"]["total_losing_trades_abs_usd"], 0)


if __name__ == "__main__":
    unittest.main()
