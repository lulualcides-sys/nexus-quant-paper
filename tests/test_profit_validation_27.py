"""Offline tests for time-disjoint profit validation, without financial APIs."""
from __future__ import annotations
import math
import os
import unittest
from copy import deepcopy
from unittest.mock import patch

from research import backtest_27 as bt
from research import profit_validation_27 as pv

T0=1791000000 // 14400 * 14400

def hourly(n=2400,shift=0):
    rows=[]
    for i in range(n):
        value=2600+shift+i*.13+3*math.sin(i/17)
        rows.append({"time":T0+i*3600,"open":value,"high":value+2,
                     "low":value-1.8,"close":value+.35})
    return rows

def quarter(n=1150):
    return [{"time":T0+i*900,
             "open":1.35+i*.0000005,"high":1.351+i*.0000005,
             "low":1.349+i*.0000005,"close":1.3502+i*.0000005}
            for i in range(n)]

class ProfitValidation27Tests(unittest.TestCase):
    def test_fold_boundaries_disjoint_and_aligned(self):
        rows=hourly()
        fs=pv.fold_windows(rows,interval=3600,warmup=240,
                           earliest=rows[0]["time"],latest=rows[-1]["time"]+3600,
                           minimum_selected=200)
        self.assertEqual([x["fold"] for x in fs],[1,2,3])
        self.assertEqual(sum(x["selected_bars"] for x in fs),len(rows)-240)
        for a,b in zip(fs,fs[1:]):
            self.assertEqual(a["end_exclusive"],b["start"])

    def test_no_forged_folds_and_no_duplicate_prices(self):
        rows=hourly(100)
        with self.assertRaisesRegex(ValueError,"Not enough"):
            pv.fold_windows(rows,interval=3600,warmup=50,
                            earliest=rows[0]["time"],latest=rows[-1]["time"]+3600,
                            minimum_selected=30)
        rows=hourly(700)
        rows[200]["time"]=rows[199]["time"]
        with self.assertRaisesRegex(ValueError,"unordered or duplicated"):
            pv.fold_windows(rows,interval=3600,warmup=100,
                            earliest=rows[0]["time"],latest=rows[-1]["time"]+3600,
                            minimum_selected=50)

    def test_screening_never_means_authorized_real_money(self):
        f=[]
        for i in range(3):
            f.append({"fold":i+1,"group":"leveraged_h4","name":"Test",
                      "start_utc":f"2026-0{i+1}-01",
                      "end_utc_exclusive":f"2026-0{i+2}-01",
                      "candidate_closed":10,"baseline_net_usd":3,
                      "baseline_2x_cost_net_usd":2,
                      "candidate_net_usd":8,"candidate_2x_cost_net_usd":5,
                      "candidate_closed_drawdown_pct":3})
        summary=pv.summarize(f)
        self.assertTrue(summary["retrospective_consistency_pass"])
        self.assertFalse(summary["safe_to_trade_real_money"])
        f[1]["candidate_2x_cost_net_usd"]=-.1
        self.assertFalse(pv.summarize(f)["retrospective_consistency_pass"])
        self.assertIn("double_cost_failed_in_period",pv.summarize(f)["rejection_reasons"])

    def test_all_27_replayed_in_disjoint_folds_without_mutations(self):
        markets={name:hourly(shift=100*i) for i,name in enumerate(bt.MARKETS)}
        m15=quarter()
        before=deepcopy(markets),deepcopy(m15)
        with patch.object(bt,"HIST_START",T0), \
             patch.object(bt,"HIST_END",T0+2400*3600), \
             patch.dict(os.environ,{"NEXUS_NEWS_GUARD_ENABLED":"1"}):
            report=pv.run(markets,m15)
        self.assertEqual((markets,m15),before)
        self.assertEqual(report["bots"],27)
        self.assertEqual(report["fold_results"],81)
        self.assertEqual(len(report["robots"]),27)
        self.assertEqual({len(x) for x in report["segments"].values()},{3})
        self.assertFalse(report["news_filter_backtested"])
        self.assertFalse(report["all_approved_real_money"])
        for key,segments in report["segments"].items():
            for earlier,later in zip(segments,segments[1:]):
                self.assertLessEqual(earlier["end_utc_exclusive"],later["start_utc"])
            if report["robots"][key]["group"] in ("gold_h4","momentum60_h4","usdcad_m15"):
                for segment in segments:
                    self.assertEqual(segment["baseline_net_usd"],segment["candidate_net_usd"])
                    self.assertEqual(segment["baseline_2x_cost_net_usd"],segment["candidate_2x_cost_net_usd"])
        self.assertIn("lucro líquido",pv.markdown(report))
        self.assertIn("NÃO é out-of-sample independente",pv.markdown(report))

    def test_missing_market_fails_closed(self):
        markets={"EURUSD":hourly()}
        with self.assertRaisesRegex(ValueError,"Missing"):
            pv.run(markets,quarter())


if __name__=="__main__":
    unittest.main()
