"""Synthetic strict accounting for higher frequency Price Action scorecard."""
import json
from pathlib import Path
import tempfile
import unittest

from research.xau_pa_frequency_v2 import DAYS,APRIL,AUGUST,ARMS,COSTS
from research.xau_pa_frequency_v2_scorecard import consolidate,to_markdown


def fake_day(day):
    arms={}
    for tf in ("M1","M5"):
        arms[tf]={}
        for arm in ARMS:
            n=1 if arm!="combined" else 2
            sources={"level_break_retest":n}
            arms[tf][arm]={"signals":n,"setups":sources,"costs":{}}
            for cost in COSTS:
                pnl=(-1. if cost=="standard" else -2.)
                ledger=[{"setup":"level_break_retest","net_usd_per_oz":pnl,
                         "reason":"STOP"}]
                arms[tf][arm]["costs"][cost]={
                    "signals":n,"filled":1,"net_usd_per_oz":pnl,
                    "trades":ledger,"rejected":{"wide_spread":0},
                }
    # For combined, ensure 2 signals <= 1 + 1.
    return {"day":day,"source":{"sha256":"a"*64,"raw_quote_rows":8000},
            "live_approval":False,"connected_broker_validated":False,
            "USD_per_one_theoretical_ounce":True,
            "historical_not_forward_trading":True,
            "identical_execution_bid_ask_tape":True,
            "trade_window_utc":"12:00-21:00",
            "train_history_utc":"09:00-12:00","arms":arms}


class ScorecardV2Tests(unittest.TestCase):
    def folder(self):
        td=tempfile.TemporaryDirectory()
        root=Path(td.name)
        for day in DAYS:
            (root/f"xau_v2_{day}.json").write_text(json.dumps(fake_day(day)))
        return td,root

    def test_all_modes_months_costs_preserved_and_not_live(self):
        td,root=self.folder()
        with td:
            r=consolidate(root)
            self.assertFalse(r["trading_approved"])
            self.assertTrue(r["not_future_forward_trading"])
            self.assertEqual(len(r["clean_dates"]["april"]),10)
            self.assertEqual(len(r["clean_dates"]["august"]),10)
            self.assertEqual(r["result"]["M1"]["structural"]["double"]["april"]["net_usd_per_oz"],-20)
            self.assertEqual(r["result"]["M5"]["combined"]["standard"]["august"]["filled"],10)
            self.assertIn("NÃO aprovar",to_markdown(r))

    def test_one_day_cannot_disappear(self):
        td,root=self.folder()
        with td:
            (root/f"xau_v2_{DAYS[0]}.json").unlink()
            with self.assertRaisesRegex(ValueError,"Missing or duplicate"):
                consolidate(root)

    def test_corruption_quarantines_whole_day(self):
        td,root=self.folder()
        with td:
            day=DAYS[0]
            (root/f"xau_v2_{day}.json").unlink()
            (root/f"quarantine_{day}.json").write_text(json.dumps({
                "day":day,"whole_day_excluded":True,
                "reason":"invalid crossed quotes","included_trades":0,
            }))
            r=consolidate(root)
            self.assertEqual(len(r["clean_dates"]["april"]),9)
            self.assertEqual(len(r["quarantined_full_days"]),1)

    def test_claiming_live_profit_fails(self):
        td,root=self.folder()
        with td:
            file=root/f"xau_v2_{DAYS[0]}.json"
            d=json.loads(file.read_text())
            d["live_approval"]=True
            file.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError,"Invalid source"):
                consolidate(root)

    def test_missing_signal_label_fails(self):
        td,root=self.folder()
        with td:
            file=root/f"xau_v2_{DAYS[0]}.json"
            d=json.loads(file.read_text())
            d["arms"]["M1"]["structural"]["setups"]={}
            file.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError,"Setup signal tally"):
                consolidate(root)


if __name__=="__main__":
    unittest.main()
