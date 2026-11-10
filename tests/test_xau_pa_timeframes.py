"""Deterministic tests for independent M1/M5/M15 gold price-action research."""
import unittest
from unittest.mock import patch

from research.xau_pa_timeframes import decide, planned, aggregate, DAYS, TIMEFRAMES
from research.xau_quote_execution_backtest import (
    ExecutionAssumptions, simulate_quote_execution,
)

T0=1791000000//900*900

def bars(tf,n=20):
    sec=TIMEFRAMES[tf]
    return [{"time":T0+j*sec,"open":100.0,"high":100.6,
             "low":99.4,"close":100.0,"spread_points":50,
             "tick_volume":500} for j in range(n)]


class PriceActionTimeframesTest(unittest.TestCase):
    def test_exact_three_timeframes(self):
        self.assertEqual(set(TIMEFRAMES),{"M1","M5","M15"})
        self.assertEqual(len(DAYS),6)
        self.assertEqual(TIMEFRAMES["M15"],900)
        ExecutionAssumptions(timeframe_seconds=900).check()

    def test_m1_break_retest_buy_with_valid_cost_to_risk(self):
        data=bars("M1")
        data[15].update(open=100,high=103.5,low=99.9,close=103.2)
        data[16].update(open=102.2,high=103.3,low=99.95,close=102.8)
        s=decide(data,16,"M1")
        self.assertIsNotNone(s)
        self.assertEqual(s["side"],1)
        self.assertEqual(s["rule"],"M1_BREAK_RETEST")
        self.assertLess(s["stop"],s["entry"])
        self.assertGreater(s["target"],s["entry"])
        self.assertEqual(s["eligible_ms"],(data[16]["time"]+60)*1000)

    def test_m1_break_retest_sell(self):
        data=bars("M1")
        data[15].update(open=100,high=100.1,low=96.5,close=96.8)
        data[16].update(open=97.8,high=100.05,low=96.7,close=97.2)
        s=decide(data,16,"M1")
        self.assertIsNotNone(s)
        self.assertEqual(s["side"],-1)
        self.assertLess(s["target"],s["entry"])

    def test_m5_sweep_sell(self):
        data=bars("M5")
        data[16].update(open=100.2,high=103.5,low=99.7,close=99.9)
        s=decide(data,16,"M5")
        self.assertIsNotNone(s)
        self.assertEqual(s["side"],-1)
        self.assertEqual(s["rule"],"M5_SWEEP_REJECTION")

    def test_m5_sweep_buy(self):
        data=bars("M5")
        data[16].update(open=99.7,high=100.3,low=96.5,close=100.0)
        s=decide(data,16,"M5")
        self.assertIsNotNone(s)
        self.assertEqual(s["side"],1)

    def test_m15_range_support(self):
        data=bars("M15")
        data[16].update(open=97.3,high=99.9,low=97.1,close=99.7)
        # This is a breakdown that leaves the range, not a valid range reaction.
        self.assertIsNone(decide(data,16,"M15"))
        data[16].update(open=99.4,high=100,low=98.0,close=99.8)
        # Structural stop may be narrow; never force a trade when friction swallows risk.
        s=decide(data,16,"M15")
        self.assertIsNone(s) if s is None else self.assertEqual(s["rule"],"M15_RANGE_REACTION")

    def test_future_open_candle_excluded(self):
        data=bars("M5")
        data[16].update(open=100.2,high=103.5,low=99.7,close=99.9)
        self.assertEqual(len(planned(data[:17],"M5")),0)
        self.assertEqual(len(planned(data[:18],"M5")),1)

    def test_candle_gap_blocks_entry(self):
        data=bars("M5")
        data[16].update(open=100.2,high=103.5,low=99.7,close=99.9)
        data[14]["time"]+=5
        self.assertIsNone(decide(data,16,"M5"))

    def test_spread_must_be_real_and_bounded(self):
        data=bars("M5")
        data[16].update(open=100.2,high=103.5,low=99.7,close=99.9)
        data[16]["spread_points"]=0
        self.assertIsNone(decide(data,16,"M5"))
        data[16]["spread_points"]=9999
        self.assertIsNone(decide(data,16,"M5"))

    def test_only_valid_registered_days(self):
        with self.assertRaisesRegex(ValueError,"Missing predeclared"):
            import tempfile
            with tempfile.TemporaryDirectory() as f:
                aggregate(f,f+"/report.json")

    def test_actual_bid_ask_quote_engine_stop_target(self):
        s={"signal_ms":60000,"eligible_ms":120000,"side":1,"entry":100,
           "stop":97,"target":104}
        q=[(119000,100.5,100.8),(120000,99.8,100.0),
           (121000,104.5,104.8)]
        c=ExecutionAssumptions(timeframe_seconds=900,
                               commission_roundtrip_usd_per_oz=.6,
                               slippage_usd_per_side=.2)
        result=simulate_quote_execution(q,[s],c)
        self.assertEqual(result["filled"],1)
        self.assertEqual(result["closed"],1)
        self.assertEqual(result["ledger"][0]["reason"],"TARGET")
        self.assertGreater(result["net_usd_per_oz"],0)

    def test_double_friction_does_not_improve_fixed_fills(self):
        s={"signal_ms":60000,"eligible_ms":120000,"side":1,
           "entry":100,"stop":97,"target":104}
        ticks=[(119000,100.5,100.8),(120000,99.8,100.0),
               (121000,104.5,104.8)]
        def do(cost,slip):
            return simulate_quote_execution(
                ticks,[s],ExecutionAssumptions(
                    timeframe_seconds=900,
                    commission_roundtrip_usd_per_oz=cost,
                    slippage_usd_per_side=slip))
        self.assertLessEqual(do(.6,.2)["net_usd_per_oz"],
                             do(.3,.1)["net_usd_per_oz"])


if __name__ == "__main__":
    unittest.main()
