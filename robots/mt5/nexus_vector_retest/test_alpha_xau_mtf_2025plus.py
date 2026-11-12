"""Synthetic, isolated checks for XAUUSD M1..M30 historical research."""
import unittest
import numpy as np
import pandas as pd
from alpha_xau_mtf_2025plus import (
    TF_MINUTES, PROFILES, horizon_bars, replay_one, summarize,
    windows_by_quarter, run_period)
from alpha_xau_longhold import simulate_xau

def sample(n=650):
    d=pd.DataFrame(dict(open=np.full(n,100.),high=np.full(n,100.2),
        low=np.full(n,99.8),close=np.full(n,100.),
        fema=np.full(n,100.),sema=np.full(n,100.),atr=np.ones(n)))
    return d

class TestXAUAllTFs(unittest.TestCase):
    def test_all_native_minute_timeframes_covered(self):
        self.assertEqual(TF_MINUTES,(1,2,3,4,5,6,10,12,15,20,30))
        self.assertEqual(len(TF_MINUTES),11)
        self.assertEqual(horizon_bars(1),5760)
        self.assertEqual(horizon_bars(15),384)
        self.assertEqual(horizon_bars(30),192)
        for period in TF_MINUTES:
            self.assertEqual(horizon_bars(period)*period,5760)

    def test_reject_nonstandard_timeframe(self):
        for tf in (0,7,25,31,60):
            with self.assertRaises(ValueError):
                horizon_bars(tf)

    def test_frozen_m15_runner_is_identical_on_partial_take_profit(self):
        f=sample()
        f.loc[3,"high"]=103.5
        src=[(1,1,98.,.8)]
        a=simulate_xau(f,src,0,len(f),384,runner=True)
        b=replay_one(f,src,0,len(f),15,"RUNNER_96H")
        self.assertEqual(len(a),len(b))
        self.assertAlmostEqual(a[0]["gross_pts"],b[0]["gross_pts"])
        self.assertEqual(a[0]["exit"],b[0]["exit"])
        self.assertEqual(a[0]["side"],b[0]["side"])

    def test_stop_first_ambiguous_candle_all_profiles(self):
        f=sample();f.loc[3,"high"]=104.;f.loc[3,"low"]=97.
        for name in PROFILES:
            t=replay_one(f,[(1,1,98.,.8)],0,len(f),30,name)
            if "QUALITY" in name:
                self.assertEqual(t,[])
            else:
                self.assertEqual(len(t),1)
                self.assertEqual(t[0]["reason"],"SL")
                self.assertAlmostEqual(t[0]["gross_pts"],-200.)

    def test_runner_gap_exit_at_real_open(self):
        f=sample()
        f.loc[3,["open","high","low","close"]]=[96.,97.,95.,96.]
        t=replay_one(f,[(1,1,98.,.8)],0,len(f),30,"RUNNER_96H")
        self.assertEqual(t[0]["reason"],"SL")
        self.assertAlmostEqual(t[0]["gross_pts"],-400.)

    def test_never_exit_before_after_trade_beyond_horizon(self):
        f=sample()
        t=replay_one(f,[(1,1,98.,.8)],0,len(f),30,"RUNNER_96H")
        self.assertEqual(t[0]["exit"],2+192)

    def test_baseline_excludes_same_tail_all_profiles(self):
        f=sample()
        for name in PROFILES:
            self.assertEqual(replay_one(f,[(470,1,98.,.8)],0,len(f),30,name),[])

    def test_cost_stress_subtracts_exactly_N_roundtrips(self):
        trades=[dict(gross_pts=180.,entry=0,exit=20),
                dict(gross_pts=-70.,entry=22,exit=44)]
        a=summarize(trades,0.8);b=summarize(trades,1.2)
        self.assertEqual(a["N"],2)
        self.assertAlmostEqual(a["net_pts"]-b["net_pts"],80.)

    def test_quarter_scope_is_not_10k_bar_window(self):
        q1=pd.date_range("2025-01-06",periods=1000,freq="30min",tz="UTC")
        q2=pd.date_range("2025-04-01",periods=1000,freq="30min",tz="UTC")
        f=pd.DataFrame(index=q1.append(q2))
        items=list(windows_by_quarter(f,192))
        self.assertEqual(len(items),2)
        self.assertEqual([a[0] for a in items],["2025Q1","2025Q2"])
        self.assertEqual(items[0][1],240)
        self.assertEqual(items[1][1],1000)

    def test_reject_pre2025_dataset(self):
        ix=pd.date_range("2024-12-31",periods=20,freq="1min",tz="UTC")
        f=pd.DataFrame(dict(open=np.ones(20),close=np.ones(20),
               high=np.ones(20),low=np.ones(20),volume=np.ones(20)),index=ix)
        with self.assertRaises(ValueError):
            run_period(f,"2024",1)

    def test_nonoverlap_per_timeframe(self):
        f=sample();signals=[(1,1,98.,.8),(2,1,98.,.8)]
        t=replay_one(f,signals,0,len(f),30,"RUNNER_96H")
        self.assertEqual(len(t),1)

    def test_no_future_data_used_in_first_entry(self):
        f=sample()
        s=[(1,1,98.,.8)]
        a=replay_one(f,s,0,len(f),30,"RUNNER_96H")
        f.loc[300:,["fema","sema"]]=[0.,999.]
        b=replay_one(f,s,0,len(f),30,"RUNNER_96H")
        self.assertEqual(a,b)

if __name__=="__main__":
    unittest.main()
