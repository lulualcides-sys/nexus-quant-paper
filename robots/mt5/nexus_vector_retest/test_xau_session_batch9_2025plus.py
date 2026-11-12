"""XAUUSD batch9 causality, UTC session reset and immutable controls."""
import unittest
import numpy as np
import pandas as pd
from research_oos import prepared,bars_for
from xau_session_batch9_2025plus import (
    ALLOWED,MODELS,FROZEN,features,events,source_events,summarize_screen)
from xau_independent_batch8_2025plus import input_model as frozen_input


def synthetic(n=9000):
    rng=np.random.default_rng(9307)
    c=2650+np.cumsum(rng.normal(0,1.3,n))
    o=np.r_[c[0],c[:-1]]
    hi=np.maximum(o,c)+rng.uniform(.08,.6,n)
    lo=np.minimum(o,c)-rng.uniform(.08,.6,n)
    idx=pd.date_range("2025-04-01T00:00:00Z",periods=n,freq="1min")
    return pd.DataFrame(dict(open=o,high=hi,low=lo,close=c,
                   volume=rng.integers(20,250,n)),index=idx)


class TestBatch9(unittest.TestCase):
    def test_timeframes_scope_and_models(self):
        self.assertEqual(ALLOWED,(1,5,15,30))
        self.assertEqual(len(MODELS),4)
        self.assertEqual(len(FROZEN),2)
        for tf in (2,3,6,10,12,20,60):
            with self.assertRaises(ValueError):
                source_events(synthetic(1300),tf,MODELS[0])

    def test_utc_asia_high_uses_only_running_past(self):
        raw=synthetic(3500)
        d=features(prepared(raw))
        day=d.loc["2025-04-01"]
        hi=day.loc[day.index.hour<7,"high"].max()
        lo=day.loc[day.index.hour<7,"low"].min()
        late=day.loc[day.index.hour>=7]
        self.assertTrue((late.asia_hi==hi).all())
        self.assertTrue((late.asia_lo==lo).all())
        self.assertEqual(day.iloc[0].asia_hi,day.iloc[0].high)
        self.assertEqual(day.iloc[0].asia_lo,day.iloc[0].low)

    def test_utc13_range_not_future_full_day(self):
        raw=synthetic(3500)
        d=features(prepared(raw))
        day=d.loc["2025-04-01"]
        self.assertTrue(day.loc[day.index.hour<13,"utc13_hi"].isna().all())
        h13=day.loc[day.index.hour==13,"high"].max()
        after=day.loc[day.index.hour>=14]
        self.assertTrue((after.utc13_hi==h13).all())

    def test_session_features_no_lookahead(self):
        raw=synthetic(6500)
        a=features(prepared(raw))
        braw=raw.copy()
        for col in ("open","high","low","close"):
            braw.iloc[4300:,braw.columns.get_loc(col)]+=700.
        b=features(prepared(braw))
        for col in ("asia_hi","asia_lo","utc13_hi","utc13_lo",
                    "prev_close","prev_low","prev_high","prev_vwap"):
            np.testing.assert_allclose(a[col].iloc[:4300],
                   b[col].iloc[:4300],rtol=1e-10,atol=1e-10,
                   equal_nan=True,err_msg=col)

    def test_no_lookahead_in_eligible_events(self):
        raw=synthetic(6500)
        a=features(prepared(raw))
        braw=raw.copy()
        for col in ("open","high","low","close"):
            braw.iloc[4400:,braw.columns.get_loc(col)]+=400.
        b=features(prepared(braw))
        for model in MODELS:
            ar=[s for s in events(a,model) if s[0]<4399]
            br=[s for s in events(b,model) if s[0]<4399]
            self.assertEqual(ar,br,model)

    def test_stop_direction_and_signal_order(self):
        raw=synthetic(12000)
        d=features(prepared(raw))
        op=d.open.to_numpy(dtype=float)
        atr=d.atr.to_numpy(dtype=float)
        for model in MODELS:
            ev=events(d,model)
            self.assertEqual(ev,sorted(ev,key=lambda x:x[0]))
            self.assertEqual(len(ev),len(set(x[0] for x in ev)))
            for i,side,stop,quality in ev:
                risk=side*(op[i+1]-stop)
                self.assertGreaterEqual(risk+1e-8,.12*atr[i])
                self.assertLessEqual(risk,4*atr[i]+1e-8)
                self.assertTrue(0<=quality<=1)

    def test_frozen_references_are_exact_same(self):
        raw=synthetic()
        for model,tf in FROZEN:
            df,a=source_events(raw,tf,model)
            _,b=frozen_input(raw,tf,model)
            self.assertEqual(a,b)

    def test_refuse_unknown_and_pre_2025(self):
        with self.assertRaises(ValueError):
            events(features(prepared(synthetic(500))),"PRINT_MONEY")
        d=synthetic(700)
        d.index-=pd.Timedelta(days=600)
        with self.assertRaises(ValueError):
            source_events(d,5,MODELS[0])

    def test_screen_does_not_promote_three_trade_examples(self):
        plans=[(m,t) for m in MODELS for t in ALLOWED]+list(FROZEN)
        panels=[]
        for m,tf in plans:
            for yr in ("2025","2026"):
                metrics={k:dict(N=3,net_pts=2000.,PF=3.,
                           net_R=10.,PF_R=3.,mdd_pts=2.)
                         for k in ("1.2","1.6")}
                quarters=[dict(quarter="test",metrics={"1.2":{"net_R":2.}})]
                panels.append(dict(model=m,tf=f"M{tf}",year=yr,
                                   summary=metrics,quarters=quarters))
        rows=summarize_screen(panels)
        self.assertEqual(len(rows),18)
        self.assertFalse(any(z["predeclared_screen"] for z in rows))


if __name__=="__main__":
    unittest.main()
