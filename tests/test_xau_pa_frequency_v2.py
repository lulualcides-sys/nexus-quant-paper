"""Synthetic causality, session, frequency and execution tests for XAU PA v2.

Fixtures verify implementation logic, not realized XAU profitability.
"""
import csv
from datetime import datetime,timezone
from pathlib import Path
import math
import tempfile
import unittest
from unittest.mock import patch

from research.xau_pa_frequency_v2 import (
    DAYS,ARMS,utc_ms,moving_average,structural_candidate,
    pullback_candidate,signals_v2,experiment_day,
)
from research.xau_price_action_m1m5 import Settings,SourceQualityError


def bar(i,base=100.,tf=60,t0=1783267200):
    price=base+0.10*i
    return {"time":t0+i*tf,"open":price-.05,
            "high":price+.20,"low":price-.20,
            "close":price,"quote_updates":20}


def create_quotes(path,day):
    start=utc_ms(day,9)
    with path.open("w",newline="") as f:
        w=csv.writer(f);w.writerow(["timestamp","askPrice","bidPrice"])
        for i in range(12*60):
            bid=2000+3*math.sin(i/22)+.01*i
            for k in range(4):
                w.writerow([start+i*60000+k*10000,bid+.18,bid])


class FrequencyV2Tests(unittest.TestCase):
    def test_ema_uses_only_history_not_future(self):
        bars=[bar(i) for i in range(45)]
        old=moving_average(bars,30,9)
        bars[-1]["close"]=100000.
        self.assertAlmostEqual(old,moving_average(bars,30,9))
        self.assertIsNone(moving_average(bars,5,9))

    def test_ema_pullback_requires_actual_touch_and_bullish_recovery(self):
        bars=[bar(i) for i in range(45)]
        p=moving_average(bars,43,9)
        b=bars[44]
        b.update(open=p+.01,low=p-.04,close=p+.25,high=p+.33)
        s=pullback_candidate(bars,44,60)
        self.assertIsNotNone(s)
        self.assertEqual(s["side"],1)
        self.assertEqual(s["setup"],"ema_pullback")
        self.assertGreater(s["eligible_ms"],s["signal_ms"])
        b["low"]=p+.40
        self.assertIsNone(pullback_candidate(bars,44,60))

    def test_structural_buy_breakout_and_retest_of_past_closed_level(self):
        rows=[bar(i,base=110) for i in range(52)]
        # Fixed range before breakout at 46: high 115.0, close breaks.
        for j in range(27,46):
            rows[j].update(open=114.1,high=115.,low=113.7,close=114.3)
        rows[46].update(open=114.6,low=114.5,high=115.9,close=115.7)
        rows[47].update(open=115.3,low=115.06,high=115.52,close=115.4)
        for j in range(48,52):
            rows[j].update(open=115.4,low=115.2,high=115.6,close=115.5)
        found=structural_candidate(rows,47,60)
        self.assertIsNotNone(found)
        self.assertEqual(found["side"],1)
        self.assertEqual(found["setup"],"level_break_retest")
        self.assertEqual(found["breakout_ms"],rows[46]["time"]*1000)

    def test_cannot_use_latest_incomplete_candle(self):
        bars=[bar(i) for i in range(46)]
        with patch("research.xau_pa_frequency_v2.structural_candidate",
                   side_effect=lambda bars,i,tf: {
                       "side":1,"setup":"level_break_retest",
                       "eligible_ms":bars[i]["time"]*1000+tf*1000,
                       "signal_ms":bars[i]["time"]*1000}):
            with patch("research.xau_pa_frequency_v2.pullback_candidate",
                       return_value=None):
                out=signals_v2(bars,60,Settings())
        self.assertEqual(len(out["structural"]),45)
        self.assertLess(out["combined"][-1]["signal_ms"],bars[-1]["time"]*1000)
        self.assertLessEqual(len(out["combined"]),15)

    def test_sources_only_predeclared_dates(self):
        with self.assertRaisesRegex(ValueError,"predeclared"):
            experiment_day("does-not-exist","20261111")

    def test_both_timeframes_same_bid_ask_tape_without_warmup_orders(self):
        day=DAYS[0]
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/"ticks.csv"
            create_quotes(src,day)
            result=experiment_day(src,day)
            self.assertTrue(result["identical_execution_bid_ask_tape"])
            self.assertFalse(result["live_approval"])
            self.assertEqual(set(result["arms"]),{"M1","M5"})
            for tf in ("M1","M5"):
                self.assertEqual(set(result["arms"][tf]),set(ARMS))
                for name in ARMS:
                    row=result["arms"][tf][name]
                    for cost in ("standard","double"):
                        outcome=row["costs"][cost]
                        self.assertLessEqual(outcome["filled"],row["signals"])
                        for t in outcome["trades"]:
                            self.assertGreaterEqual(t["entry_ms"],utc_ms(day,12))
                            self.assertLess(t["entry_ms"],utc_ms(day,21))

    def test_crossed_quote_excludes_whole_day(self):
        day=DAYS[0]
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/"bad.csv"
            create_quotes(src,day)
            rows=src.read_text().splitlines()
            quote=rows[123].split(",")
            quote[1]=str(float(quote[2])-.01)
            rows[123]=",".join(quote)
            src.write_text("\n".join(rows)+"\n")
            with self.assertRaisesRegex(SourceQualityError,"Invalid crossed"):
                experiment_day(src,day)


if __name__=="__main__":
    unittest.main()
