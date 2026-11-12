"""Batch8 invariants: causal closed-bar features, new signal modes and frozen controls."""
import unittest
import numpy as np
import pandas as pd
from research_oos import prepared,bars_for
from xau_independent_batch8_2025plus import (
    ALLOWED_TF,NEW_MODELS,FROZEN_REFERENCES,feature_frame8,emit,input_model,screen)
from xau_volatility_breakouts_2025plus import feature_frame,make_signals
from xau_statistical_regimes_batch5_2025plus import features as shock_features,signals as shock_signals


def sample(n=1150):
    rng=np.random.default_rng(1120)
    close=2700+np.cumsum(rng.normal(0,1.7,n))
    op=np.r_[close[0],close[:-1]]
    hi=np.maximum(close,op)+rng.uniform(.15,.7,n)
    lo=np.minimum(close,op)-rng.uniform(.15,.7,n)
    idx=pd.date_range("2025-04-15",periods=n,freq="1min",tz="UTC")
    return pd.DataFrame(dict(open=op,high=hi,low=lo,close=close,
                             volume=rng.integers(2,80,n)),index=idx)


class TestBatch8(unittest.TestCase):
    def test_strict_scope_and_fixed_reference_list(self):
        self.assertEqual(ALLOWED_TF,(1,5,15,30))
        self.assertEqual(len(NEW_MODELS),4)
        self.assertEqual(FROZEN_REFERENCES,
                         (("ER20_M30_FROZEN",30),("SHOCK_M15_FROZEN",15)))
        for tf in (2,3,4,6,10,12,20):
            with self.assertRaises(ValueError):
                input_model(sample(500),tf,"RSI2_EMA200_REBOUND")

    def test_no_future_prices_in_features(self):
        a=sample()
        original=feature_frame8(prepared(a))
        alt=a.copy()
        for col in ("open","high","low","close"):
            alt.iloc[900:,alt.columns.get_loc(col)]+=5000.
        changed=feature_frame8(prepared(alt))
        for col in ("ema50","ema200","rsi2","prev_rsi2","prior24_hi",
                    "prior24_lo","prev_hi","prev_lo","prev_close",
                    "prev_open","before_close","before_open","body_fraction",
                    "prev_body_fraction","before_body_fraction",
                    "prev_range","prior_atr","vwap_prev"):
            np.testing.assert_allclose(
                 original[col].iloc[:900],changed[col].iloc[:900],
                 rtol=1e-10,atol=1e-10,equal_nan=True,err_msg=col)

    def test_no_future_mutation_of_prior_signals(self):
        raw=sample()
        a=feature_frame8(prepared(raw))
        changed=raw.copy()
        for col in ("open","high","low","close"):
            changed.iloc[850:,changed.columns.get_loc(col)]+=800.
        b=feature_frame8(prepared(changed))
        for model in NEW_MODELS:
            seen_a=[v for v in emit(a,model) if v[0]<849]
            seen_b=[v for v in emit(b,model) if v[0]<849]
            self.assertEqual(seen_a,seen_b,model)

    def test_stop_direction_risk_bounds_and_no_duplicate(self):
        f=feature_frame8(prepared(sample(2000)))
        op=f.open.to_numpy(dtype=float)
        atr=f.atr.to_numpy(dtype=float)
        for model in NEW_MODELS:
            ev=emit(f,model)
            self.assertEqual(ev,sorted(ev,key=lambda z:z[0]))
            self.assertEqual(len(ev),len(set(z[0] for z in ev)))
            for i,side,stop,quality in ev:
                risk=side*(op[i+1]-stop)
                self.assertGreaterEqual(risk+1e-8,.12*atr[i])
                self.assertLessEqual(risk,4*atr[i]+1e-8)
                self.assertTrue(0<=quality<=1)

    def test_frozen_er20_same_events(self):
        raw=sample(1600)
        ref=feature_frame(prepared(bars_for(raw,30)))
        df,actual=input_model(raw,30,"ER20_M30_FROZEN")
        self.assertEqual(actual,make_signals(ref,"EFFICIENCY_ER20_BREAK"))

    def test_frozen_shock_same_events(self):
        raw=sample(1600)
        ref=shock_features(prepared(bars_for(raw,15)))
        df,actual=input_model(raw,15,"SHOCK_M15_FROZEN")
        self.assertEqual(actual,shock_signals(ref,"SHOCK_EXHAUSTION"))

    def test_unknown_model_refused(self):
        with self.assertRaises(ValueError):
            emit(feature_frame8(prepared(sample())),"ALWAYS_WIN")

    def test_date_guard(self):
        df=sample(800)
        df.index-=pd.Timedelta(days=1000)
        with self.assertRaises(ValueError):
            input_model(df,1,"RSI2_EMA200_REBOUND")

    def test_screen_refuses_fake_small_sample(self):
        pairs=[(m,tf) for m in NEW_MODELS for tf in ALLOWED_TF]+list(FROZEN_REFERENCES)
        panel=[]
        for m,tf in pairs:
            for year in ("2025","2026"):
                dummy={k:dict(N=3,net_R=400,PF_R=4.4,MDD_R=1.)
                       for k in ("1.2","1.6")}
                quarters=[dict(metrics={"1.2":{"net_R":150}},quarter="fake")]
                panel.append(dict(year=year,model=m,tf=f"M{tf}",
                                  quarters=quarters,summary=dummy))
        score=screen(panel)
        self.assertEqual(len(score),18)
        self.assertFalse(any(x["preliminary_screen"] for x in score))


if __name__=="__main__":
    unittest.main()
