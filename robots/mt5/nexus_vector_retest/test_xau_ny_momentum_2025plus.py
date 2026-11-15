"""Test strict closed-bar causality and common exit assumptions in NY XAUUSD research."""
import unittest
import numpy as np
import pandas as pd
from xau_ny_momentum_2025plus import features,signal_pairs,sim_quarter,MODELS,ALLOWED

def fake(n=4500):
    rng=np.random.default_rng(20261114)
    c=3200+np.cumsum(rng.normal(0,0.7,n))
    o=np.r_[c[0],c[:-1]]
    return pd.DataFrame(dict(open=o,close=c,
       high=np.maximum(o,c)+rng.uniform(.05,.7,n),
       low=np.minimum(o,c)-rng.uniform(.05,.7,n),
       volume=rng.integers(10,80,n)),
       index=pd.date_range("2025-02-03",periods=n,freq="min",tz="UTC"))

class TestNexusNY(unittest.TestCase):
 def test_timeframes_and_models(self):
    self.assertEqual(ALLOWED,(1,5,15,30))
    self.assertEqual(len(MODELS),4)
    for tf in (2,3,12,20,60):
        with self.assertRaises(ValueError):features(fake(800),tf)
 def test_no_lookahead(self):
    a=fake(4400)
    p=signal_pairs(features(a,1))
    b=a.copy()
    # change only current (forming) and FUTURE prices, never past
    b.iloc[3000:,b.columns.get_loc("close")]+=900
    b.iloc[3000:,b.columns.get_loc("high")]+=900
    b.iloc[3000:,b.columns.get_loc("low")]+=900
    q=signal_pairs(features(b,1))
    for model in MODELS:
       np.testing.assert_array_equal(p[model][:3001],q[model][:3001],err_msg=model)
 def test_long_only_is_subset(self):
    x=signal_pairs(features(fake(),1))
    self.assertTrue(np.all((x["BREAK_LONG"]==0)|(x["BREAK_LONG"]==x["BREAK_BOTH"])))
    self.assertTrue(np.all((x["PULL_LONG"]==0)|(x["PULL_LONG"]==x["PULL_BOTH"])))
 def test_stop_gap_and_loss(self):
    f=features(fake(700),1)
    sig=np.zeros(len(f),dtype=np.int8)
    sig[300]=1
    f.iloc[300,f.columns.get_loc("low")]=float(f.open.iloc[300]-50)
    q=sim_quarter(f,sig,290,500,1.2)
    self.assertEqual(q["N"],1)
    self.assertEqual(q["reasons"]["stop"],1)
    self.assertLess(q["net_pts"],0)
 def test_no_spurious_profit(self):
    f=features(fake(700),1)
    sig=np.zeros(len(f),dtype=np.int8)
    z=sim_quarter(f,sig,250,650,1.2)
    self.assertEqual(z["N"],0)
    self.assertEqual(z["net_pts"],0.)
 def test_costs_not_increasing_profit(self):
    f=features(fake(),1);s=signal_pairs(f)["BREAK_BOTH"]
    a=sim_quarter(f,s,250,4300,0.8)
    b=sim_quarter(f,s,250,4300,1.6)
    self.assertEqual(a["N"],b["N"])
    self.assertGreaterEqual(a["net_pts"],b["net_pts"])

if __name__=="__main__":unittest.main()
