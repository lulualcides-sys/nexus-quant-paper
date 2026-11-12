"""Tests: M5 only CLOSED candle context; M1 alone opens XAU trades."""
from datetime import datetime,timezone
from pathlib import Path
import csv
import json
import math
import tempfile
import unittest

from research.xau_pa_m5_context_m1_v6 import (
    DAYS,POLICIES,m5_context_at,filter_m1_with_m5,
    confirm_m5_zone_touch,evaluate_day,audit_excursions,utc_ms,
)


def m5_bar(i,base=2000.,first=1782126000):
    return {
        "time":first+300*i,
        "open":base,
        "high":base+1.5,"low":base-1.5,
        "close":base,
        "quote_updates":50,
    }


def signal(day,side=1,setup="range_rejection"):
    end=utc_ms(day,12)
    return {
        "signal_ms":end-60000,"eligible_ms":end,
        "timeframe_seconds":60,"setup":setup,"side":side,
        "stop":1998.0,"atr":1.0,
    }


class M5ContextM1Tests(unittest.TestCase):
    def test_m5_excludes_partial_candle_on_m1_close(self):
        bars=[m5_bar(i) for i in range(75)]
        # First 42 completed M5 candles must exist for context.
        cutoff=(bars[50]["time"]+120)*1000
        context=m5_context_at(bars,cutoff)
        self.assertEqual(context["last_m5_end_ms"],
                         (bars[49]["time"]+300)*1000)
        self.assertLessEqual(context["last_m5_end_ms"],cutoff)
        self.assertNotEqual(context["last_m5_end_ms"],
                            (bars[50]["time"]+300)*1000)

    def test_future_price_mutation_does_not_rewrite_historical_m5_context(self):
        bars=[m5_bar(i) for i in range(75)]
        at=(bars[49]["time"]+300)*1000
        old=m5_context_at(bars,at)
        bars[50].update(high=300000,low=1,close=100000)
        bars[-1].update(high=99999)
        new=m5_context_at(bars,at)
        self.assertEqual(old,new)

    def test_breakout_retest_is_preserved_without_ema(self):
        day=DAYS[0]
        s=signal(day,setup="break_retest")
        keep,why,details=filter_m1_with_m5(
            [s],[m5_bar(i) for i in range(75)]
        )
        self.assertEqual(len(keep),1)
        self.assertEqual(keep[0]["setup"],"break_retest")
        self.assertEqual(why["break_retest_preserved"],1)
        self.assertEqual(details,[])

    def test_ranging_signal_blocked_without_confirmed_m5_zone(self):
        day=DAYS[0]
        s=signal(day)
        keep,why,details=filter_m1_with_m5(
            [s],[m5_bar(i) for i in range(75)]
        )
        self.assertEqual(keep,[])
        self.assertEqual(sum(why.values()),1)
        self.assertEqual(len(details),1)

    def test_m1_m5_zone_requires_candle_intersection_buy_and_sell(self):
        day=DAYS[0];end=utc_ms(day,12)
        m1bars=[{"time":end//1000-60,"open":2000.0,
                 "high":2000.8,"low":1999.4,"close":2000.6}]
        base={
            "setup":"range_rejection","eligible_ms":end,
            "signal_ms":end-60000,"timeframe_seconds":60,
            "m5_support_low":1999.2,"m5_support_high":1999.7,
            "m5_resistance_low":2000.5,"m5_resistance_high":2001.3
        }
        allowed,veto=confirm_m5_zone_touch([
            {**base,"side":1},{**base,"side":-1}
        ],m1bars)
        self.assertEqual(len(allowed),2)
        # Move the ONLY completed M1 signal candle away from M5 support.
        m1bars[0]["low"]=1999.9
        allowed,veto=confirm_m5_zone_touch([
            {**base,"side":1}
        ],m1bars)
        self.assertEqual(allowed,[])
        self.assertEqual(veto["M1_rejection_not_at_M5_mark"],1)

    def test_rejects_missing_signal_candle_or_future_close(self):
        day=DAYS[0]
        s={
            **signal(day),
            "m5_support_low":1999.2,"m5_support_high":1999.7,
            "m5_resistance_low":2000.5,"m5_resistance_high":2001.3,
        }
        with self.assertRaisesRegex(ValueError,"M1 signal candle not available"):
            confirm_m5_zone_touch([s],[])

    def test_mfe_mae_only_until_actual_exit_and_executable_side(self):
        ms=100000
        trade={
            "side":1,"entry":100.2,"stop":99.2,"entry_ms":ms,
            "exit_ms":ms+2000,"reason":"STOP",
        }
        # Long exits use BID. Never use ASK peaks or post-stop recovery.
        quotes=[
            (ms,100.,100.3),(ms+1000,100.81,101.5),
            (ms+2000,99.1,99.3),
            (ms+3000,105.,105.2),
        ]
        tagged=audit_excursions([trade],quotes)[0]
        self.assertAlmostEqual(tagged["MFE_R_before_actual_exit"],.61)
        self.assertTrue(tagged["stopped_after_0_5R"])
        self.assertFalse(tagged["stopped_after_1R"])
        self.assertLessEqual(tagged["MAE_R_before_actual_exit"],-1.)

    def test_disallows_unselected_optimization_dates(self):
        with self.assertRaisesRegex(ValueError,"preregistered"):
            evaluate_day("/not/a/file","20260909")

    def test_m5_not_an_independent_order_strategy(self):
        # Source-code behavioral integration tested by synthetic quote tape.
        day=DAYS[0]
        start=utc_ms(day,9)
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/"quotes.csv"
            with f.open("w",newline="") as handle:
                writer=csv.writer(handle)
                writer.writerow(["timestamp","askPrice","bidPrice"])
                for minute in range(12*60):
                    bid=2000+math.sin(minute/19)*1.8
                    for second in (0,12,24,36,48):
                        writer.writerow([start+60000*minute+second*1000,
                                         bid+0.14,bid])
            result=evaluate_day(f,day)
            self.assertTrue(result["M5_context_M1_entries_only"])
            self.assertTrue(result["no_independent_M5_orders"])
            self.assertTrue(result["single_XAU_position"])
            self.assertFalse(result["auto_trading_approved"])
            self.assertEqual(set(result["results"]),set(POLICIES))
            for p in POLICIES:
                rec=result["results"][p]
                self.assertLessEqual(rec["costs"]["double"]["filled"],rec["signals"])
                self.assertTrue(all(t["timeframe_seconds"]==60
                                    for t in rec["costs"]["double"]["trades"]))


if __name__=="__main__":
    unittest.main()
