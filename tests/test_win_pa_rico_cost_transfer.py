"""WIN Price Action optional Rico-cost transfer tests, no external network."""
import unittest
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from unittest.mock import patch

from research.win_pa_rico_cost_transfer import SCENARIOS,eval_bars
from research.win_price_action import Settings


class PriceActionCostTests(unittest.TestCase):
    def test_cost_models_are_immutable_and_distinct(self):
        self.assertEqual(round(SCENARIOS["original_r6_1tick"][0]+2*SCENARIOS["original_r6_1tick"][1],2),6.0)
        self.assertEqual(round(SCENARIOS["rico_no_rlp_r3_40_1tick"][0]+2*SCENARIOS["rico_no_rlp_r3_40_1tick"][1],2),3.4)
        self.assertEqual(round(SCENARIOS["rico_no_rlp_r5_40_2tick"][0]+2*SCENARIOS["rico_no_rlp_r5_40_2tick"][1],2),5.4)
        self.assertEqual(round(SCENARIOS["hypothetical_rlp_r2_50_1tick"][0]+2*SCENARIOS["hypothetical_rlp_r2_50_1tick"][1],2),2.5)

    def test_zero_trades_remain_zero_not_a_profit_claim(self):
        first=datetime(2026,6,9,9,10,tzinfo=ZoneInfo("America/Sao_Paulo"))
        bars=[{"time":int((first+timedelta(minutes=i)).timestamp()),
               "open":100000.0,"high":100010.0,"low":99990.0,
               "close":100000.0,"volume":123.0} for i in range(160)]
        with patch("research.win_price_action.candidate",return_value=None):
            results=eval_bars(bars,start="2026-06-01",end="2026-07-01")
        self.assertEqual(len(results),8)
        for res in results.values():
            self.assertEqual(res["net_brl"],0)
            self.assertEqual(res["closed"],0)
            self.assertFalse(res["passes_any_review"])
            self.assertFalse(res["daily_loss_limit_enabled"])
            self.assertTrue(res["one_contract_only"])

    def test_infeasible_stop_is_still_rejected_not_scaled_up(self):
        self.assertEqual(Settings().risk_fraction,0.01)
        self.assertEqual(Settings().starting_brl,2000)
        self.assertEqual(Settings(min_net_rr=1).risk_fraction,0.01)


if __name__ == "__main__":
    unittest.main()
