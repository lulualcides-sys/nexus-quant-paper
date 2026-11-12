"""Regression safety for frozen XAU entry/exit research."""
import unittest
import numpy as np
import pandas as pd
from research_oos import prepared
from points10k import events as ema_events
from alpha_xau_mtf_2025plus import replay_one, summarize
from xau_exit_risk_batch6_2025plus import (
    ALLOWED_TF,CANDIDATES,EXIT_MODES,entry_inputs,replay_new_exit,
    run_exit,risk_stats,screening)


def sample(n=2800):
    r=np.random.default_rng(69)
    c=2650+np.cumsum(r.normal(0,1.8,n))
    o=np.r_[c[0],c[:-1]]
    hi=np.maximum(o,c)+r.uniform(.1,.8,n)
    lo=np.minimum(o,c)-r.uniform(.1,.8,n)
    ix=pd.date_range("2025-03-17",periods=n,freq="1min",tz="UTC")
    return pd.DataFrame({"open":o,"high":hi,"low":lo,"close":c,
                         "volume":r.integers(1,100,n)},index=ix)


class TestExitRiskAudit(unittest.TestCase):
    def test_timeframes_allowed_and_exact_candidates(self):
        self.assertEqual(ALLOWED_TF,(1,5,15,30))
        self.assertEqual(len(CANDIDATES),5)
        self.assertEqual(len(EXIT_MODES),5)
        self.assertTrue(all(x[1] in ALLOWED_TF for x in CANDIDATES))
        self.assertEqual({x[2] for x in CANDIDATES},
          {"EMA21_BASE","EMA21_RSI_MACD","EFFICIENCY_ER20_BREAK",
           "SHOCK_EXHAUSTION"})
        for tf in (2,3,4,6,10,12,20):
            with self.assertRaises(ValueError):
                entry_inputs(sample(300),tf,"EMA21_BASE")

    def test_entry_signals_of_ema21_completely_unchanged(self):
        raw=sample()
        f,event=entry_inputs(raw,1,"EMA21_BASE")
        self.assertEqual(event,ema_events(f,"EMA21_PULLBACK"))

    def test_same_frozen_ema_rsi_baseline_entries(self):
        from xau_indicator_lab_2025plus import indicators,build_signals
        raw=sample()
        f,e=entry_inputs(raw,30,"EMA21_RSI_MACD")
        original=ema_events(f,"EMA21_PULLBACK")
        self.assertEqual(e,build_signals(f,"EMA21_RSI_MACD",original))

    def test_shock_entry_source_frozen(self):
        from xau_statistical_regimes_batch5_2025plus import features,signals
        raw=sample()
        f,e=entry_inputs(raw,5,"SHOCK_EXHAUSTION")
        self.assertEqual(e,signals(features(prepared(
          __import__('research_oos').bars_for(raw,5))),"SHOCK_EXHAUSTION"))

    def test_runner_reference_is_exact_native_engine(self):
        f=prepared(sample())
        events=[(260,1,float(f.open.iloc[261])-2.,.9)]
        actual=run_exit(f,events,240,2800,30,"RUNNER_96H")
        original=replay_one(f,events,240,2800,30,"RUNNER_96H")
        self.assertEqual(actual,original)

    def test_stop_hit_first_and_unchanged_before_tp2(self):
        f=prepared(sample())
        o=float(f.open.iloc[261])
        i=260
        stop=o-2.
        f.iloc[261,f.columns.get_loc("high")]=o+4.
        f.iloc[261,f.columns.get_loc("low")]=o-4.
        a=replay_new_exit(f,[(i,1,stop,.9)],240,2800,30,
                         "TRAIL_ATR2_AFTER_TP2")
        b=replay_one(f,[(i,1,stop,.9)],240,2800,30,
                         "RUNNER_96H")
        self.assertEqual(a[0]["reason"],"SL")
        self.assertEqual(a[0]["gross_pts"],b[0]["gross_pts"])

    def test_24hour_exit_does_not_peek_at_exit_candle(self):
        # A 24h time exit is based on the open of the exit bar, not its
        # high/low/close. Construct an artificial straight-line series.
        idx=pd.date_range("2025-03-17",periods=850,freq="30min",tz="UTC")
        op=np.full(850,2600.)
        hi=np.full(850,2600.1)
        lo=np.full(850,2599.9)
        close=np.full(850,2600.)
        raw=pd.DataFrame(dict(open=op,high=hi,low=lo,close=close,
                              volume=np.ones(850)),index=idx)
        f=prepared(raw)
        ss=[(260,1,2598.,.7)]
        a=replay_new_exit(f,ss,240,850,30,"TIME_EXIT_24H")
        self.assertEqual(len(a),1)
        self.assertEqual(a[0]["exit"],309)
        raw2=raw.copy()
        raw2.iloc[309,raw2.columns.get_loc("high")]=3000.
        raw2.iloc[309,raw2.columns.get_loc("low")]=2200.
        raw2.iloc[309,raw2.columns.get_loc("close")]=3000.
        b=replay_new_exit(prepared(raw2),ss,240,850,30,"TIME_EXIT_24H")
        self.assertEqual(a[0]["gross_pts"],b[0]["gross_pts"])
        self.assertEqual(a[0]["reason"],"TIME24_OPEN")

    def test_cost_r_normalization(self):
        f=prepared(sample())
        entry=float(f.open.iloc[261])
        ev=[(260,1,entry-2.,.8)]
        deals=[{"signal":260,"entry":261,"exit":266,"side":1,
                "gross_pts":300.,"reason":"TP"}]
        r=risk_stats(deals,ev,f,1.2)
        # gain price = $3, cost = $1.2, risk price = $2 -> 0.9R
        self.assertEqual(r["N"],1)
        self.assertAlmostEqual(r["net_R"],.9,places=5)

    def test_no_auto_promote_without_sample(self):
        fake=[]
        for name,tf,model in CANDIDATES:
            for year in ("2025","2026"):
                summ={mode:{"1.2":dict(N=4,net_R=100.,PF_R=2.0,MDD_R=8.),
                            "1.6":dict(N=4,net_R=60.,PF_R=1.8,MDD_R=9.)}
                      for mode in EXIT_MODES}
                q=[{"modes":{mode:{"1.2":{"net_R":10}}
                    for mode in EXIT_MODES}}]
                fake.append(dict(year=year,candidate=name,summary=summ,quarterly=q))
        s=screening(fake)
        self.assertEqual(len(s),25)
        self.assertFalse(any(x["preliminary_screen"] for x in s))


if __name__=="__main__":
    unittest.main()
