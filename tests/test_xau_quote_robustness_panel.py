"""Synthetic accounting tests for chronological XAU quote session reports."""
import json
from pathlib import Path
import tempfile
import unittest
from research.xau_quote_robustness_panel import combined,aggregate


def record(pnls):
    return {
       "broker_lot_or_commission_verified":False,
       "independently_validated_with_original_greenhouse":False,
       "spread_accounted_through_actual_bid_ask":True,
       "execution":{"planned_signals":len(pnls),"filled":len(pnls),
                    "unfilled_expired":0,
                    "ledger":[{"net_usd_per_oz":p} for p in pnls]},
    }


class PanelTests(unittest.TestCase):
    def test_sum_and_drawdown_in_natural_chronological_order(self):
        a=combined([record([3,-2]),record([-4,5])])
        self.assertEqual(a["filled"],4)
        self.assertEqual(a["wins"],2)
        self.assertEqual(a["losses"],2)
        self.assertEqual(a["net_usd_per_oz"],2)
        self.assertEqual(a["max_closed_drawdown_usd_per_oz"],6.)
        self.assertFalse(a["sufficient_sample_for_promoting_to_broker"])

    def test_no_trades_returns_no_fake_pf(self):
        r=combined([record([])])
        self.assertIsNone(r["profit_factor"])
        self.assertIsNone(r["expectancy_usd_per_oz"])

    def test_reject_fabricated_broker_validation(self):
        a=record([5])
        a["broker_lot_or_commission_verified"]=True
        with self.assertRaisesRegex(ValueError,"Broker"):
            combined([a])

    def test_detect_missing_ledger(self):
        a=record([-3])
        a["execution"]["ledger"]=[]
        with self.assertRaisesRegex(ValueError,"Ledger"):
            combined([a])

    def test_fixed_date_order_and_partitions(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)
            for day, pnl in (("20261029",-3),("20261103",5)):
                for tf in ("M1","M5"):
                    for scenario in ("base","friction"):
                        a=record([pnl])
                        a["source"]={
                          "first_candle_utc":f"{day[:4]}-{day[4:6]}-{day[6:]}T12:00:00+00:00",
                          "source_rows":120000}
                        (folder/f"xau_{day}_{tf}_{scenario}.json").write_text(json.dumps(a))
            r=aggregate(folder,["20261029","20261103"])
            a=r["variants"]["M1"]["friction"]
            self.assertEqual(a["prior_block_through_oct30"]["net_usd_per_oz"],-3)
            self.assertEqual(a["later_block_november"]["net_usd_per_oz"],5)
            self.assertFalse(r["approved_for_trading"])
            with self.assertRaisesRegex(ValueError,"sorted"):
                aggregate(folder,["20261103","20261029"])


if __name__=="__main__": unittest.main()
