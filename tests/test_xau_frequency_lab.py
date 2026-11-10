"""Frozen XAU research variants: structural, no-lookahead, bid/ask and costs."""
import csv
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from research.xau_frequency_lab import (
    POLICY_OVERRIDES, VARIANTS, Variant, levels_for, planned_for,
    policies_for, run_day,
)
from research.xau_quote_tracker_reference import QuotePolicy, signal

T0=int(datetime(2026, 10, 5, 12, tzinfo=timezone.utc).timestamp())


def sample(n=36):
    b=[{"time": T0+60*i,"open":2005.,"high":2010.,"low":2000.,
         "close":2005.,"tick_volume":100,"spread_points":100} for i in range(n)]
    b[30]={**b[30],"open":2002.,"high":2009.,"low":1998.5,
           "close":2007.,"tick_volume":240,"spread_points":100}
    return b


class VariantTests(unittest.TestCase):
    def test_reference_policy_is_not_mutated(self):
        p=policies_for(60,0.001)
        self.assertEqual(p["reference"],QuotePolicy(timeframe_seconds=60,point=.001,tick_size=.001))
        self.assertEqual(p["active"].lookback,10)
        self.assertEqual(p["balanced"].activity_factor,1.10)
        self.assertEqual(len(VARIANTS),6)
        self.assertEqual(len({x.name for x in VARIANTS}),6)

    def test_all_policy_variants_emit_only_on_closed_candles(self):
        b=sample()
        for policy in policies_for(60).values():
            self.assertEqual(signal(b,30,29,policy),0)
            self.assertEqual(signal(b,30,34,policy),1)

    def test_fibonacci_entry_50_and_75_for_buy_sell(self):
        candle=sample()[30]
        strict,fast=VARIANTS[0],VARIANTS[4]
        self.assertEqual(levels_for(candle,1,strict,.001),
                         {"entry":2003.75,"target":2019.5,"stop":1988.})
        self.assertEqual(levels_for(candle,-1,strict,.001),
                         {"entry":2003.75,"target":1988.,"stop":2019.5})
        active=levels_for(candle,1,fast,.001)
        self.assertEqual(active,{"entry":2006.375,"target":2024.75,"stop":1988.})

    def test_sweep_requires_confirmation_and_uses_future_never(self):
        b=sample()
        policy=policies_for(60)["active"]
        v=VARIANTS[4]
        planned=planned_for(b,60,v,policy)
        self.assertEqual(len(planned),1)
        self.assertEqual(planned[0]["eligible_ms"],(T0+31*60)*1000)
        self.assertEqual(planned[0]["signal_ms"],(T0+30*60)*1000)
        previous=planned[:]
        b[32]={**b[32],"low":1500.,"high":2500.,"close":2005.}
        self.assertEqual(previous,planned_for(b,60,v,policy))

    def test_invalid_variants_rejected_not_silently_changed(self):
        for var in [Variant("bad","none",.5,2),Variant("bad","active",1.5,1.2),
                    Variant("bad","reference",-.5,2)]:
            with self.assertRaises(ValueError):var.validate()

    def test_quoted_csv_smoke_runs_all_variants_both_timeframes(self):
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/"xau.csv"
            with file.open("w",newline="",encoding="utf-8") as f:
                w=csv.DictWriter(f,fieldnames=["timestamp","bidPrice","askPrice","askVolume","bidVolume"])
                w.writeheader()
                for i in range(310):
                    for k in range(4):
                        bid=2750+(i%7)*.02 + (k%2)*.05
                        w.writerow({"timestamp":(T0+i*60+k*12)*1000,
                                    "bidPrice":bid,"askPrice":bid+.16,
                                    "askVolume":100,"bidVolume":100})
            r=run_day(file,"20261005")
            self.assertEqual(r["m1_bars"],310)
            self.assertEqual(r["m5_bars"],62)
            self.assertEqual(len(r["variants"]),len(VARIANTS)*2)
            self.assertFalse(r["trading_approved"])
            for x in r["variants"].values():
                self.assertEqual(set(x["scenarios"]),{"no_costs","friction","double_friction"})
                self.assertEqual(x["scenarios"]["friction"]["filled"],0)
                self.assertEqual(x["scenarios"]["friction"]["net_usd_per_oz"],0)
            self.assertEqual(r["quote_rows"],1240)

    def test_mt5_research_presets_match_independent_python_hypotheses(self):
        lab=Path("indicators/mt5/NQ_XAU_Quote_Tracker_Lab_Research.mq5").read_text(encoding="utf-8")
        for term in ("LAB_REFERENCE=0", "LAB_BALANCED=1", "LAB_ACTIVE=2",
                     "InpLabPreset=LAB_REFERENCE", "gLb=14; gMinTick=12; gActivity=1.10;",
                     "gMinRange=0.50; gMaxRange=2.75;",
                     "gWick=0.22; gClose=0.58; gSweep=0.025; gSpread=0.32;",
                     "gLb=10; gMinTick=10; gActivity=1.02;",
                     "gMinRange=0.40; gMaxRange=3.00;",
                     "gWick=0.18; gClose=0.55; gSweep=0.015; gSpread=0.30;",
                     "NAO APROVADO (VALIDACAO NEGATIVA)",
                     "NQXAULAB_", "BufferBuy[0]=EMPTY_VALUE"):
            self.assertIn(term,lab)
        for forbidden in ("OrderSend(", "CTrade ", "trade.Buy(", "WebRequest(",
                          "TICK_FLAG_BUY", "TICK_FLAG_SELL"):
            self.assertNotIn(forbidden,lab)

    def test_executable_variants_do_not_use_trading_api(self):
        from research import xau_frequency_lab as lab
        import inspect
        source=inspect.getsource(lab)
        for forbidden in ("OrderSend(","CTrade(", "trade.Buy(", "positions_get(",
                          "login(", "request_margin("):
            self.assertNotIn(forbidden,source)


if __name__=="__main__":
    unittest.main()
