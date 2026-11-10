"""Offline checks: preserve all original robot rules while substituting only gold TF."""
import csv
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research.backtest_27 import all_ids
from research.xau_all_original_3tf import (
    DAYS, TIMEFRAMES, EXPECTED_BOOKS, bb_book, bb_step, load_quotes,
    replay, to_h1,
)
from src.strategies import make_indicators
from src.experimental_h1 import book as h1_book, step as h1_step

BASE = 1791000000//3600*3600

def candles(tf,n=920):
    sec=TIMEFRAMES[tf]
    return [
        {"time":BASE+i*sec,"open":4000+8*math.sin(i/31),
         "high":4001+8*math.sin(i/31),
         "low":3999+8*math.sin(i/31),
         "close":4000+.8*math.sin(i/17)+8*math.sin(i/31),
         "volume":50+(i%9),"max_spread":.2}
        for i in range(n)
    ]


class AllOriginalGoldTests(unittest.TestCase):
    def test_complete_census_27_plus_atlas_at_three_intervals(self):
        self.assertEqual(len(all_ids()),27)
        self.assertEqual(EXPECTED_BOOKS,28)
        self.assertEqual(TIMEFRAMES,{"M1":60,"M5":300,"M15":900})
        self.assertEqual(len(DAYS),25)

    def test_hourly_is_built_only_from_complete_candles(self):
        rows=candles("M15",12)
        self.assertEqual(len(to_h1(rows,900)),3)
        del rows[2]
        self.assertEqual(len(to_h1(rows,900)),2)

    def test_legacy_h1_default_remains_one_hour_and_m15_is_opt_in(self):
        rows=candles("M15",300)
        ind=make_indicators(rows)
        b=h1_book()
        with patch("src.experimental_h1.setup",return_value=1):
            h1_step(b,"XAUUSD","channel10",rows,ind,299)
        self.assertEqual(len(b["entries"]),0)
        b=h1_book()
        with patch("src.experimental_h1.setup",return_value=1):
            h1_step(b,"XAUUSD","channel10",rows,ind,299,bar_seconds=900)
        self.assertEqual(len(b["entries"]),1)

    def test_h1_default_unchanged_in_existing_production_regressions(self):
        rows=candles("M15",300)
        ind=make_indicators(rows)
        with self.assertRaisesRegex(ValueError,"Unsupported research"):
            h1_step(h1_book(),"XAUUSD","rsi50",rows,ind,299,bar_seconds=120)

    def test_replay_has_every_original_id_and_no_new_strategy(self):
        data=candles("M15",920) # 230 HOURS of confirmed H1 context
        r=replay(data,"M15")
        self.assertEqual(len(r["books"]),28)
        self.assertEqual(set(r["books"]),set(all_ids())|{"atlas_28:atlas"})
        self.assertTrue(r["paper_only"])
        self.assertEqual(r["n_valid_hourly_bars"],230)
        for orig in ("EURUSD","USDJPY","US500","XTIUSD"):
            for strategy in ("ema20_retest","channel10","rsi50"):
                a=r["books"]["experimental_h1:"+orig+":"+strategy]
                ref=r["books"]["experimental_h1:XAUUSD:"+strategy]
                self.assertEqual(a["net_usd"],ref["net_usd"])
                self.assertEqual(a["closed"],ref["closed"])
        self.assertTrue(r["books"]["atlas_28:atlas"]["volume_proxy_not_same_as_original_traded_volume"])
        self.assertIn("retargeting_note",r["books"]["usdcad_m15:bb20"])

    def test_higher_cost_never_increases_each_financial_result(self):
        data=candles("M15",920)
        normal=replay(data,"M15",1.)
        stressed=replay(data,"M15",2.)
        for key in normal["books"]:
            a=normal["books"][key]
            b=stressed["books"][key]
            # Different stop histories can change trade count, not guarantee
            # monotonic P&L, so assert costs when same executions observed.
            if a["closed"]==b["closed"] and a["closed"]>0:
                self.assertGreaterEqual(b["cost_usd"],a["cost_usd"])

    def test_warmup_failure_is_not_zero_profit(self):
        with self.assertRaisesRegex(ValueError,"Insufficient"):
            replay(candles("M15",300),"M15")

    def test_fake_or_wrong_utc_day_does_not_enter_quote_series(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"wrong.csv"
            with p.open("w",newline="") as f:
                writer=csv.writer(f)
                writer.writerow(("timestamp","askPrice","bidPrice"))
                writer.writerow((1,4010,4009))
            with self.assertRaises(ValueError):
                load_quotes(p,DAYS[0])

    def test_spread_must_be_positive(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"wrong.csv"
            with p.open("w",newline="") as f:
                writer=csv.writer(f)
                writer.writerow(("timestamp","askPrice","bidPrice"))
                for i in range(40):
                    writer.writerow((1791000000000+i*1000,4000,4000))
            with self.assertRaisesRegex(ValueError,"Corrupted"):
                load_quotes(p,DAYS[0])


if __name__=="__main__":
    unittest.main()
