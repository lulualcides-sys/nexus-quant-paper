"""Tests for XAUUSD reverse BUY/SELL counterfactual; synthetic fixtures only."""
from pathlib import Path
import json
import tempfile
import unittest

from research.xau_frequency_lab import VARIANTS,policies_for
from research.xau_inverted_tracker_experiment import (
    mirrored_plans, summarize, AUGUST, JULY, VARIANT_KEYS,
)
from research.xau_quote_execution_backtest import (
    ExecutionAssumptions, simulate_quote_execution,
)


def synthetic_signal_bars(n=26, tf=60):
    bars=[
        {"time":int(1782838800+i*tf),"open":2005., "high":2010.,
         "low":2000., "close":2005.,"tick_volume":100,"spread_points":30}
        for i in range(n)
    ]
    bars[22]={**bars[22],"open":2002.,"high":2009.,"low":1998.5,
              "close":2007.,"tick_volume":240,"spread_points":35}
    return bars


def fixture_day(date):
    d={}
    for key in VARIANT_KEYS:
        d[key]={"signals":2,"sides":{}}
        for name,net in (("original",-3.),("inverted",2.)):
            d[key]["sides"][name]={
                "filled":1,"wins":int(net>0),"losses":int(net<0),
                "net_usd_per_oz":net,
                "ledger":[{"net_usd_per_oz":net}],
            }
    return {
        "date":date,"source_sha256":"f"*64,"quote_rows":40000,
        "identical_original_greenhouse_signals_verified":False,
        "broker_real_execution_verified":False,"approved_for_live":False,
        "results":d,
    }


class InvertedXAUQuoteTests(unittest.TestCase):
    def test_inverted_side_same_signal_time_repriced_at_opposite_anchor(self):
        bars=synthetic_signal_bars()
        policy=policies_for(60)["reference"]
        original,inverse=mirrored_plans(bars,60,VARIANTS[0],policy)
        self.assertEqual(len(original),1)
        self.assertEqual(len(inverse),1)
        self.assertEqual(original[0]["side"],1)
        self.assertEqual(inverse[0]["side"],-1)
        self.assertEqual(original[0]["eligible_ms"],inverse[0]["eligible_ms"])
        self.assertEqual(original[0]["entry"],inverse[0]["entry"])
        self.assertLess(inverse[0]["target"],inverse[0]["entry"])
        self.assertGreater(inverse[0]["stop"],inverse[0]["entry"])
        self.assertNotEqual(original[0]["target"],inverse[0]["target"])

    def test_inverse_is_not_negative_of_original_return(self):
        bars=synthetic_signal_bars()
        p=policies_for(60)["reference"]
        original,inverse=mirrored_plans(bars,60,VARIANTS[0],p)
        ts=original[0]["eligible_ms"]
        candle=[(ts,2007.,2007.3), (ts+5000,2006.5,2006.8),
                (ts+6000,2004.5,2004.8),(ts+7000,2005.5,2005.8),
                (ts+8000,2003.5,2003.8)]
        cfg=ExecutionAssumptions(timeframe_seconds=60,
                                  commission_roundtrip_usd_per_oz=.60,
                                  slippage_usd_per_side=.20)
        a=simulate_quote_execution(candle,original,cfg)
        b=simulate_quote_execution(candle,inverse,cfg)
        self.assertEqual(a["filled"],0)
        self.assertEqual(b["filled"],1)
        self.assertNotEqual(b["net_usd_per_oz"],-a["net_usd_per_oz"])

    def test_both_sides_are_reported_for_each_timeframe_and_variant(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for date in JULY+AUGUST:
                (root/f"xau_{date}.json").write_text(json.dumps(fixture_day(date)))
            report=summarize(root)
            self.assertEqual(report["clean_days"],{"july":10,"august":20})
            self.assertEqual(len(report["variants"]),12)
            self.assertFalse(report["profitability_approved"])
            self.assertTrue(report["not_a_prospective_future_holdout"])
            for item in report["variants"].values():
                self.assertEqual(item["july"]["original"]["net_usd_per_oz"],-30.)
                self.assertEqual(item["july"]["inverted"]["net_usd_per_oz"],20.)
                self.assertEqual(item["august"]["original"]["filled"],20)
                self.assertEqual(item["august"]["inverted"]["filled"],20)

    def test_does_not_pick_a_winner_or_make_a_broker_claim(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for date in JULY+AUGUST:
                (root/f"xau_{date}.json").write_text(json.dumps(fixture_day(date)))
            out=summarize(root)
            self.assertNotIn("selected_strategy",out)
            self.assertFalse(out["original_tracker_equivalence"])

    def test_rejects_missing_source_day_instead_of_inventing_trade(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for date in JULY+AUGUST[:-1]:
                (root/f"xau_{date}.json").write_text(json.dumps(fixture_day(date)))
            with self.assertRaisesRegex(ValueError,"Missing or double evidence"):
                summarize(root)

    def test_whole_corrupted_day_is_quarantined_before_scoring(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for date in JULY+AUGUST:
                if date=="20260807":
                    (root/f"quarantine_{date}.json").write_text(json.dumps({
                      "day_id":date,"all_trades_excluded_before_scoring":True,
                      "data_quality_error":"Crossed bid ask quote"}))
                else:
                    (root/f"xau_{date}.json").write_text(json.dumps(fixture_day(date)))
            out=summarize(root)
            self.assertEqual(out["clean_days"]["august"],19)
            self.assertEqual(len(out["whole_day_quarantines"]),1)

    def test_rejects_mixed_or_missing_paired_pnl(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for date in JULY+AUGUST:
                (root/f"xau_{date}.json").write_text(json.dumps(fixture_day(date)))
            path=root/f"xau_{JULY[0]}.json"
            v=json.loads(path.read_text())
            v["results"][VARIANT_KEYS[0]]["sides"].pop("inverted")
            path.write_text(json.dumps(v))
            with self.assertRaisesRegex(ValueError,"Missing paired"):
                summarize(root)


if __name__=="__main__":
    unittest.main()
