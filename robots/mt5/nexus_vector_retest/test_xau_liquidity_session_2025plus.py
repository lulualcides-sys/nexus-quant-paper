"""Causal, session-time and conservative-execution tests for gold liquidity lab."""
import unittest
import numpy as np
import pandas as pd
from research_oos import prepared
from points10k import events as reference_ema
from alpha_xau_mtf_2025plus import TF_MINUTES, replay_one
from xau_liquidity_session_2025plus import (
    MODELS, session_levels, build_signals, run_period, screen)


def fake(start="2025-03-10 00:00:00",n=2500,freq="1min"):
    rng=np.random.default_rng(71)
    ix=pd.date_range(start,periods=n,freq=freq,tz="UTC")
    c=2500.+rng.standard_normal(n).cumsum()
    o=np.r_[c[0],c[:-1]]
    h=np.maximum(c,o)+.3
    l=np.minimum(c,o)-.3
    return prepared(pd.DataFrame(dict(open=o,high=h,low=l,close=c,
             volume=np.full(n,10)),index=ix))


class TestLiquiditySessionLab(unittest.TestCase):
    def test_all_11_timeframes_and_independent_models(self):
        self.assertEqual(TF_MINUTES,(1,2,3,4,5,6,10,12,15,20,30))
        self.assertEqual(len(MODELS),5)
        self.assertIn("YDAY_SWEEP_RECLAIM",MODELS)
        self.assertIn("ASIA_SWEEP_RECLAIM",MODELS)
        self.assertIn("NY_ORB_BREAK_RETEST",MODELS)
        self.assertIn("YDAY_BREAK_HOLD",MODELS)

    def test_previous_utc_day_is_closed_and_shifted(self):
        d=fake("2025-04-01 00:00:00",n=48,freq="1h")
        ctx=session_levels(d,1)
        first=ctx["utcday"][0]
        second=ctx["utcday"][24]
        self.assertNotEqual(first,second)
        self.assertTrue(np.isnan(ctx["yesterday_high"][8]))
        self.assertEqual(ctx["yesterday_high"][30],d.high.iloc[:24].max())
        self.assertEqual(ctx["yesterday_low"][30],d.low.iloc[:24].min())

    def test_incomplete_asia_range_is_rejected_not_lookahead(self):
        d=fake("2025-04-07 03:00:00",n=420)
        ctx=session_levels(d,1)
        hour=ctx["utc_hour"]
        self.assertTrue(np.isnan(ctx["asia_high"][(hour>=7)]).all())

    def test_completed_asia_only_visible_after_6_utc(self):
        d=fake("2025-04-08 00:00:00",n=660)
        ctx=session_levels(d,1)
        self.assertTrue(np.isnan(ctx["asia_high"][:360]).all())
        self.assertTrue(np.isnan(ctx["asia_low"][:360]).all())
        self.assertAlmostEqual(ctx["asia_high"][421],d.high.iloc[:360].max())
        self.assertAlmostEqual(ctx["asia_low"][421],d.low.iloc[:360].min())

    def test_new_york_opening_range_respects_dst(self):
        a=fake("2025-03-07 12:00:00",n=180)
        b=fake("2025-03-10 11:00:00",n=180)
        d=pd.concat([a,b])
        ctx=session_levels(d,1)
        self.assertEqual(ctx["ny_opening_count"],2)
        # Mar 7 2025 NY 09:00 is 14 UTC (EST); Mar 10 NY 09:00 = 13 UTC (EDT).
        i=d.index.get_loc(pd.Timestamp("2025-03-07T14:00:00Z"))
        j=d.index.get_loc(pd.Timestamp("2025-03-10T13:00:00Z"))
        self.assertAlmostEqual(ctx["ny_orb_high"][i],d.high.iloc[60:120].max())
        self.assertAlmostEqual(ctx["ny_orb_high"][j],d.high.iloc[240:300].max())
        self.assertTrue(np.isnan(ctx["ny_orb_high"][i-1]))
        self.assertTrue(np.isnan(ctx["ny_orb_high"][j-1]))

    def test_no_future_data_can_modify_signal_history(self):
        d=fake("2025-04-07 00:00:00",n=7500)
        old={k:build_signals(d,1,k) for k in MODELS}
        raw=d[["open","high","low","close","volume"]].copy()
        raw.iloc[6000:,raw.columns.get_indexer(["open","high","low","close"])]+=400.
        after=prepared(raw)
        for k in MODELS:
            a=[x for x in old[k] if x[0]<5999]
            b=[x for x in build_signals(after,1,k) if x[0]<5999]
            self.assertEqual(a,b,k)

    def test_same_frozen_ema21_reference_is_not_changed(self):
        d=fake()
        r=reference_ema(d,"EMA21_PULLBACK")
        self.assertEqual(r,build_signals(d,1,"EMA21_BASE",baseline=r))

    def test_signal_entry_open_and_stop_are_valid(self):
        d=fake("2025-04-07 00:00:00",n=7500)
        opening=d.open.to_numpy()
        for k in MODELS:
            last=-1
            for i,side,stop,quality in build_signals(d,1,k):
                self.assertGreater(i,last)
                self.assertIn(side,(-1,1))
                self.assertLess(i,len(d)-1)
                self.assertGreater(side*(opening[i+1]-stop),0)
                self.assertTrue(np.isfinite(quality))
                last=i

    def test_at_most_one_signal_per_day_for_session_models(self):
        d=fake("2025-04-07 00:00:00",n=8000)
        ctx=session_levels(d,1)
        for kind in MODELS[1:]:
            sig=build_signals(d,1,kind,ctx)
            ny=kind=="NY_ORB_BREAK_RETEST"
            days=[ctx["nyday" if ny else "utcday"][i] for i,_,_,_ in sig]
            self.assertEqual(len(days),len(set(days)))

    def test_unknown_model_and_unsupported_tf(self):
        d=fake()
        with self.assertRaises(ValueError):
            build_signals(d,1,"QUANTUM_ULTRA")
        with self.assertRaises(ValueError):
            session_levels(d,17)

    def test_reject_pre2025_data(self):
        d=fake("2024-11-01",n=500)
        with self.assertRaises(ValueError):
            run_period(d,"2024",1)

    def test_identical_stop_first_execution_engine(self):
        d=fake("2025-04-07",n=1000)
        op=float(d.open.iloc[245])
        d.iloc[245,d.columns.get_loc("high")]=op+5
        d.iloc[245,d.columns.get_loc("low")]=op-5
        t=replay_one(d,[(244,1,op-2,.7)],240,1000,30,"RUNNER_96H")
        self.assertEqual(t[0]["reason"],"SL")
        self.assertLess(t[0]["gross_pts"],0)

    def test_screen_rejects_rare_or_cost_negative_models(self):
        cases=[]
        for tf in TF_MINUTES:
            for yr in ("2025","2026"):
                s={k:{"1.2":dict(N=2,net_pts=-100.,PF=.4)} for k in MODELS}
                qs=[{"models":{k:{"1.2":{"net_pts":-10.}} for k in MODELS}}]
                cases.append(dict(tf=f"M{tf}",year=yr,summary=s,quarters=qs))
        r=screen(cases)
        self.assertEqual(len(r),len(TF_MINUTES)*len(MODELS))
        self.assertFalse(any(x["screened"] for x in r))


if __name__=="__main__":
    unittest.main()
