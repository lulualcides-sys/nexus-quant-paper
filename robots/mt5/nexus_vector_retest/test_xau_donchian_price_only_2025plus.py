"""Price-only Donchian: explicit causal and risk regression tests."""
import unittest
import numpy as np
import pandas as pd
from xau_donchian_price_only_2025plus import (
  MODELS,FRAMES,features,directions,simulate,summarize
)

def bars(n=2200):
    rng=np.random.default_rng(1106)
    close=3000+np.cumsum(rng.normal(0,1.8,n))
    op=np.r_[close[0],close[:-1]]
    hi=np.maximum(op,close)+rng.uniform(.03,.5,n)
    lo=np.minimum(op,close)-rng.uniform(.03,.5,n)
    ix=pd.date_range("2025-04-01",periods=n,freq="min",tz="UTC")
    return pd.DataFrame(dict(open=op,high=hi,low=lo,close=close,
                             volume=rng.integers(1,300,n)),index=ix)

class DonchianTests(unittest.TestCase):
 def test_models_and_timeframes(self):
    self.assertEqual(len(MODELS),4)
    self.assertEqual(FRAMES,(1,5,15,30))
    for tf in (2,12,20,60):
      with self.assertRaises(ValueError):features(bars(),tf)

 def test_no_lookahead(self):
    raw=bars()
    before=directions(features(raw,1))
    change=raw.copy()
    # Alter only current forming bar and its future; prior close signal
    # must be unaffected at this same index.
    change.iloc[1400:,change.columns.get_loc("close")]+=100
    change.iloc[1400:,change.columns.get_loc("high")]+=100
    change.iloc[1400:,change.columns.get_loc("low")]+=100
    after=directions(features(change,1))
    for model in MODELS:
      np.testing.assert_array_equal(before[model][:1401],after[model][:1401])

 def test_subsets(self):
    signals=directions(features(bars(),1))
    both=signals["DON20_BOTH"];long=signals["DON20_LONG"]
    trend=signals["DON20_LONG_EMA200"]
    self.assertTrue(np.all((long==0)|(long==both)))
    self.assertTrue(np.all((trend==0)|(trend==long)))

 def test_adverse_gap_and_stops(self):
    f=features(bars(500),1)
    s=np.zeros(len(f),dtype=np.int8);s[300]=1
    f.iloc[300,f.columns.get_loc("low")]=float(f.open.iloc[300]-100)
    r=simulate(f,s,1.2)
    self.assertEqual(len(r),1)
    self.assertEqual(r[0]["reason"],"stop")
    self.assertLess(r[0]["net_pts"],0.)

 def test_cost_stress_monotonic(self):
    f=features(bars(2500),1)
    sig=directions(f)["DON20_LONG"]
    a=simulate(f,sig,.8)
    b=simulate(f,sig,1.6)
    self.assertEqual(len(a),len(b))
    self.assertGreaterEqual(summarize(a)["net_pts"],summarize(b)["net_pts"])

 def test_zero_trades_is_not_profitable(self):
    f=features(bars(700),1)
    r=simulate(f,np.zeros(len(f),dtype=np.int8),1.2)
    m=summarize(r)
    self.assertEqual(m["N"],0)
    self.assertEqual(m["net_pts"],0.)
    self.assertIsNone(m["PF"])

if __name__=="__main__":unittest.main()
