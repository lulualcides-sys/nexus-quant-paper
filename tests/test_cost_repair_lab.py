"""Offline validation of cost-aware research; deterministic synthetic data only."""
import math
import unittest
from copy import deepcopy
from unittest.mock import patch

from research import backtest_27 as bt
from research import cost_repair_lab as lab
from src import experimental_h1 as h1
from src import leveraged_gold as lev
from src.strategies import make_indicators

T0=1791000000//14400*14400
TRAIN_START=T0+260*14400
TEST_END=T0+630*14400

def candles(n=640*4, shift=0):
    out=[]
    for i in range(n):
        v=2600+shift+i*.1+2*math.sin(i/23)
        out.append({"time":T0+i*3600,"open":v,"high":v+1.8,
                    "low":v-1.5,"close":v+.2})
    return out

def quarter(n=440):
    base=T0+300*14400
    return [{"time":base+i*900,"open":1.38+i*.000001,
             "high":1.3805+i*.000001,"low":1.3795+i*.000001,
             "close":1.3801+i*.000001} for i in range(n)]


class CostAwareRepairTests(unittest.TestCase):
    def test_causal_filter_uses_only_closed_h1(self):
        b=candles()
        ind=make_indicators(b)
        i=570
        original=lambda rule,rows,indicators,index: 1
        old=lab.h1_gate_signal("rsi50",b[:-40],make_indicators(b[:-40]),
                               i,"EURUSD",original,base_cost_bps=3)
        new=lab.h1_gate_signal("rsi50",b,ind,i,"EURUSD",
                               original,base_cost_bps=3)
        self.assertEqual(old,new)

    def test_double_cost_does_not_change_filter_threshold(self):
        b=candles()
        ind=make_indicators(b)
        original=lambda rule,rows,indicators,index: 1
        before=lab.h1_gate_signal("rsi50",b,ind,570,"EURUSD",
                                   original,base_cost_bps=3)
        with patch.object(h1,"COST_BPS",{**h1.COST_BPS,"EURUSD":6}):
            stressed=lab.h1_gate_signal("rsi50",b,ind,570,"EURUSD",
                                        original,base_cost_bps=3)
        self.assertEqual(before,stressed)

    def test_1x_research_exposure_does_not_touch_paper_defaults(self):
        original=lev.TARGET_NOTIONAL_LEVERAGE
        original_risk=lev.RISK_FRACTION
        rows=bt.aggregate_hourly_to_h4(candles())
        idx=450
        inds=make_indicators(rows)
        book=lev.fresh(rows)["books"]["lev_channel20"]
        with patch.object(lev,"TARGET_NOTIONAL_LEVERAGE",1.0), \
             patch.object(lev,"RISK_FRACTION",0.0075), \
             patch.object(lev,"sign",side_effect=lambda strategy, b, ii, j:1 if j==idx-1 else 0):
            lev.one_bar(book,"lev_channel20",rows,inds,idx,mode=lev.LIVE_POLICY)
        self.assertIsNotNone(book["position"])
        self.assertAlmostEqual(book["position"]["notional_leverage"],1.0,places=8)
        self.assertEqual(lev.TARGET_NOTIONAL_LEVERAGE,original)
        self.assertEqual(lev.RISK_FRACTION,original_risk)

    def test_all_27_same_candles_and_unchanged_controls(self):
        feeds={market:candles(shift=100*j)
               for j,market in enumerate(bt.MARKETS)}
        m15=quarter()
        inputs=deepcopy(feeds),deepcopy(m15)
        with patch.object(bt,"HIST_START",TRAIN_START), \
             patch.object(bt,"HIST_END",TEST_END):
            report=lab.compare(feeds,m15)
        self.assertEqual((feeds,m15),inputs)
        self.assertEqual(len(report["robots"]),27)
        self.assertEqual(sum(1 for x in report["robots"].values() if x["changed_engine"]),20)
        self.assertTrue(report["no_auto_promotion"])
        self.assertTrue(report["historical_data_previously_inspected"])
        self.assertTrue(report["compare_same_exact_feeds"])
        for k,entry in report["robots"].items():
            if not entry["changed_engine"]:
                self.assertEqual(entry["candidate_net_usd"],entry["baseline_net_usd"],k)
                self.assertEqual(entry["candidate_stress_net_usd"],entry["baseline_stress_net_usd"],k)
        self.assertIn("candidato",lab.markdown(report).lower())

    def test_failure_without_all_27_valid_prices(self):
        feeds={"EURUSD":candles()}
        with patch.object(bt,"HIST_START",TRAIN_START), \
             patch.object(bt,"HIST_END",TEST_END):
            with self.assertRaisesRegex(ValueError,"Insufficient price history"):
                lab.compare(feeds,quarter())

    def test_rejection_with_no_genuine_profit(self):
        initial={"closed_trades":40,"net_realized_usd":-20,
                 "double_cost_net_usd":-35}
        candidate={"closed_trades":32,"net_realized_usd":-10,
                   "costs_and_funding_usd":10,
                   "closed_only_drawdown_pct":2}
        stressed={"net_realized_usd":-15}
        result=lab.assessment(initial,candidate,stressed,"experimental_h1")
        self.assertEqual(result["decision"],"rejected_no_stress_profit")
        self.assertTrue(result["no_auto_promotion"])


if __name__=="__main__":
    unittest.main()
