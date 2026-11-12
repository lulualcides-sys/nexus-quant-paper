"""Regression tests: allowed TF, causal features, no repaint, no broker API."""
import unittest
import numpy as np
import pandas as pd
from research_oos import prepared
from points10k import events as original_events
from alpha_xau_mtf_2025plus import replay_one
from xau_statistical_regimes_batch5_2025plus import (
    ALLOWED_TF, MODELS, features, signals, run_year, screen)


def sample(n=1050,seed=16):
    g=np.random.default_rng(seed)
    close=2700+g.normal(0,1.7,n).cumsum()
    opening=np.r_[close[0],close[:-1]]
    high=np.maximum(opening,close)+g.uniform(.1,.8,n)
    low=np.minimum(opening,close)-g.uniform(.1,.8,n)
    ix=pd.date_range("2025-03-01",periods=n,freq="1min",tz="UTC")
    return pd.DataFrame(dict(open=opening,high=high,low=low,
                  close=close,volume=g.integers(10,100,n)),index=ix)


class TestStatisticalRegimes(unittest.TestCase):
    def test_timeframes_strictly_allowed(self):
        self.assertEqual(ALLOWED_TF,(1,5,15,30))
        self.assertEqual(len(MODELS),5)
        for x in (2,3,4,6,10,12,20):
            with self.assertRaises(ValueError):
                run_year(sample(400),"2025",x)

    def test_features_trailing_only_and_finite(self):
        f=features(prepared(sample()))
        z=(f.close-f.close.rolling(80,min_periods=80).mean()) / (
             f.close.rolling(80,min_periods=80).std(ddof=0))
        np.testing.assert_allclose(f.z80.to_numpy(),z.to_numpy(),equal_nan=True)
        self.assertTrue(np.isnan(f.z80.iloc[0]))
        self.assertTrue(np.isnan(f.vr5.iloc[0]))
        self.assertTrue(np.isfinite(f.z80.iloc[300]))
        self.assertTrue(np.isfinite(f.vr5.iloc[300]))
        self.assertAlmostEqual(f.prior14_hi.iloc[500],f.high.iloc[486:500].max())
        self.assertAlmostEqual(f.prior14_lo.iloc[500],f.low.iloc[486:500].min())
        self.assertTrue((f.chop14.dropna()>=0).all())

    def test_future_mutation_cannot_change_completed_features(self):
        raw=sample(1150)
        before=features(prepared(raw))
        changed=raw.copy()
        indices=changed.columns.get_indexer(["open","high","low","close"])
        changed.iloc[880:,indices]+=250.
        after=features(prepared(changed))
        for k in ("z80","vr5","chop14","prior14_hi","prior14_lo",
                  "prior_hi","prior_lo","prior_mid","prev_atr",
                  "prev_body","prev_range"):
            np.testing.assert_allclose(before[k].iloc[:880],
                after[k].iloc[:880],equal_nan=True,rtol=1e-10,atol=1e-10,
                err_msg=k)

    def test_future_mutation_cannot_change_past_signals(self):
        raw=sample(1150)
        a=features(prepared(raw))
        modified=raw.copy()
        indices=modified.columns.get_indexer(["open","high","low","close"])
        modified.iloc[880:,indices]+=250.
        b=features(prepared(modified))
        for m in MODELS:
            x=[s for s in signals(a,m) if s[0]<879]
            y=[s for s in signals(b,m) if s[0]<879]
            self.assertEqual(x,y,m)

    def test_ema21_baseline_events_exactly_same(self):
        f=features(prepared(sample()))
        ref=original_events(f,"EMA21_PULLBACK")
        self.assertEqual(signals(f,"EMA21_BASE",ref),ref)

    def test_outcome_stop_in_correct_direction(self):
        f=features(prepared(sample()))
        opening=f.open.to_numpy()
        for m in MODELS:
            prev=-1
            for i,side,stop,quality in signals(f,m):
                self.assertGreater(i,prev)
                self.assertLess(i,len(f)-1)
                self.assertIn(side,(-1,1))
                self.assertGreater(side*(opening[i+1]-stop),0)
                self.assertGreaterEqual(quality,0)
                self.assertLessEqual(quality,1)
                prev=i

    def test_ema21_stop_first_replay_unchanged(self):
        f=features(prepared(sample()))
        entry=float(f.open.iloc[243])
        f.iloc[243,f.columns.get_loc("high")]=entry+8
        f.iloc[243,f.columns.get_loc("low")]=entry-8
        trades=replay_one(f,[(242,1,entry-2.,.8)],240,len(f),30,"RUNNER_96H")
        self.assertEqual(len(trades),1)
        self.assertEqual(trades[0]["reason"],"SL")
        self.assertLess(trades[0]["gross_pts"],0)

    def test_refuse_dates_earlier_than_2025(self):
        d=sample(600)
        d.index=d.index-pd.Timedelta(days=500)
        with self.assertRaises(ValueError):
            run_year(d,"2024",1)

    def test_reject_unknown_models(self):
        with self.assertRaises(ValueError):
            signals(features(prepared(sample())),"MAGIC_WIN_999")

    def test_screen_does_not_promote_sparse_trades(self):
        cases=[]
        for tf in ALLOWED_TF:
            for year in ("2025","2026"):
                s={m:{"1.2":dict(N=4,net_pts=8000,PF=1.8)} for m in MODELS}
                q=[{"summary":{m:{"1.2":{"net_pts":500}}
                                for m in MODELS}}]
                cases.append(dict(tf=f"M{tf}",year=year,
                                  summary=s,quarters=q))
        scored=screen(cases)
        self.assertEqual(len(scored),20)
        self.assertFalse(any(r["preliminary_screen"] for r in scored))


if __name__=="__main__":
    unittest.main()
