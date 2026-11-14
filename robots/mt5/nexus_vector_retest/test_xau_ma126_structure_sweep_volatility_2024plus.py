"""Regression/causality and no-spurious-approval tests for MA12 structure lab."""
import unittest
import numpy as np
import pandas as pd
from xau_ma126_structure_sweep_volatility_2024plus import (
 ALLOWED,MODELS,features,signal_pairs,sim_quarter,screen,POINT)

def example(n=3600):
    rng=np.random.default_rng(1106)
    prices=2800+np.cumsum(rng.normal(0,.9,n))
    op=np.r_[prices[0],prices[:-1]]
    hi=np.maximum(op,prices)+rng.uniform(.01,.35,n)
    lo=np.minimum(op,prices)-rng.uniform(.01,.35,n)
    idx=pd.date_range("2025-05-01",periods=n,freq="1min",tz="UTC")
    return pd.DataFrame(dict(open=op,high=hi,low=lo,close=prices,
                 volume=rng.integers(3,50,n)),index=idx)

class TestMA12Experiments(unittest.TestCase):
    def test_four_models_and_only_authorized_native_tf(self):
        self.assertEqual(ALLOWED,(1,5,15,30))
        self.assertEqual(len(MODELS),4)
        for bad in (2,3,4,6,10,12,20,60):
            with self.assertRaises(ValueError):
                features(example(400),bad)

    def test_ma_at_open_frozen_formula(self):
        f=features(example(1000),1)
        i=240
        v=(f.open.iloc[i]+sum(f.close.iloc[i-k] for k in range(1,12)))/12
        self.assertAlmostEqual(f.ma_at_open.iloc[i],v,places=9)
        self.assertEqual(bool(f.cross_buy.iloc[i]),
            bool(f.open.iloc[i-1]<v and f.close.iloc[i-1]>v))
        self.assertEqual(bool(f.cross_sell.iloc[i]),
            bool(f.open.iloc[i-1]>v and f.close.iloc[i-1]<v))

    def test_signals_stable_after_future_prices_change(self):
        raw=example(1800)
        f1=features(raw,1); sig1=signal_pairs(f1)
        altered=raw.copy()
        for col in ("open","high","low","close"):
            altered.iloc[1100:,altered.columns.get_loc(col)]+=1600.
        f2=features(altered,1);sig2=signal_pairs(f2)
        for key in MODELS:
            np.testing.assert_array_equal(sig1[key][:1100],sig2[key][:1100],
                                         err_msg=key)

    def test_structure_gated_signals_subset_of_baseline(self):
        f=features(example(4000),1);s=signal_pairs(f)
        baseline=s["A_MA12_ORIGINAL"]
        new=s["B_MA12_STRUCTURE_BREAK"]
        self.assertTrue(np.all((new==0)|(new==baseline)))

    def test_no_current_candle_high_low_close_in_signals(self):
        raw=example(1600)
        fa=features(raw,1);a=signal_pairs(fa)
        change=raw.copy()
        j=1000
        # mutate ONLY current-bar high low close, while OPEN unchanged;
        # preceding closed values and entry decisions must remain unchanged.
        change.iloc[j,change.columns.get_loc("high")]+=70
        change.iloc[j,change.columns.get_loc("low")]-=70
        change.iloc[j,change.columns.get_loc("close")]+=1
        fb=features(change,1);b=signal_pairs(fb)
        for k in MODELS:
            self.assertEqual(int(a[k][j]),int(b[k][j]),k)

    def test_stop_first_worst_fill_on_gap(self):
        raw=example(500)
        f=features(raw,1)
        s=np.zeros(len(f),dtype=np.int8);s[260]=1
        # Force an unambiguous adverse hit in the same candle, to test
        # stop-first rather than relying on a random favorable path.
        f.loc[f.index[260],"low"]=float(f.open.iloc[260]-10*f.atr_pre.iloc[260])
        m=sim_quarter(f,s,250,450,1.2)
        self.assertEqual(m["N"],1)
        self.assertGreater(m["closed_trade_MDD_pts"],0)
        self.assertEqual(sum(m["reasons"].values()),m["N"])

    def test_no_small_sample_auto_pass(self):
        fake=[]
        for tf in ALLOWED:
            for model in MODELS:
                for yr in ("2024","2025","2026_partial"):
                    fake.append(dict(year=yr,model=model,timeframe=f"M{tf}",
                        metrics={"1.2":dict(net_pts=10000,net_R=100,N=3,positive_quarters=4),
                                 "1.6":dict(net_pts=10000,net_R=100,N=3,positive_quarters=4)}))
        rows=screen(fake)
        self.assertEqual(len(rows),16)
        self.assertFalse(any(r["tentative_screen"] for r in rows))

if __name__=="__main__":
    unittest.main()
