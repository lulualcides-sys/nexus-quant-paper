"""Synthetic causal/regression checks for batch 2 independent XAU indicators."""
import unittest
import numpy as np
import pandas as pd
from research_oos import prepared
from points10k import events as base_events
from alpha_xau_mtf_2025plus import TF_MINUTES, replay_one
from xau_indicator_batch2_2025plus import (
    MODELS, indicators, create_signals, weighted_moving_average,
    supertrend_direction, replay_year, screen)


def sample(n=660):
    rng=np.random.default_rng(801)
    close=2600+rng.normal(0,2,n).cumsum()
    op=np.r_[close[0],close[:-1]]
    high=np.maximum(op,close)+rng.uniform(.1,.9,n)
    low=np.minimum(op,close)-rng.uniform(.1,.9,n)
    ts=pd.date_range("2025-02-01",periods=n,freq="1min",tz="UTC")
    return pd.DataFrame(dict(open=op,high=high,low=low,close=close,
                             volume=rng.integers(1,100,n)),index=ts)


class TestBatch2Indicators(unittest.TestCase):
    def test_models_and_all_timeframes(self):
        self.assertEqual(len(MODELS),5)
        self.assertEqual(len(TF_MINUTES),11)
        self.assertIn("SUPERTREND_10_3",MODELS)
        self.assertIn("CCI20_RECLAIM",MODELS)
        self.assertIn("WILLIAMS_R14_RECLAIM",MODELS)
        self.assertIn("HULL21_PULLBACK",MODELS)

    def test_wma_trailing_alignment(self):
        arr=np.arange(1.,9.)
        w=weighted_moving_average(arr,3)
        self.assertTrue(np.isnan(w[0]))
        self.assertTrue(np.isnan(w[1]))
        self.assertAlmostEqual(w[2],(1*1+2*2+3*3)/6)
        self.assertAlmostEqual(w[7],(6+14+24)/6)

    def test_supertrend_no_future_and_known_flip(self):
        close=np.array([100.,101.,102.,103.,100.,96.,94.,93.,94.,110.])
        high=close+.1
        low=close-.1
        atr=np.ones(len(close))
        direction,band=supertrend_direction(close,high,low,atr)
        self.assertEqual(direction[0],1)
        self.assertTrue((np.abs(direction)==1).all())
        self.assertTrue(np.isfinite(band).all())
        self.assertIn(-1,direction.tolist())
        self.assertEqual(direction[-1],1)
        long=supertrend_direction(close[:7],high[:7],low[:7],atr[:7])
        np.testing.assert_array_equal(long[0],direction[:7])
        np.testing.assert_allclose(long[1],band[:7])

    def test_indicator_values_past_unchanged_when_future_changes(self):
        raw=sample(850)
        before=indicators(prepared(raw))
        modified=raw.copy()
        modified.loc[modified.index[650]:,["open","close","high","low"]]+=200.
        after=indicators(prepared(modified))
        for name in ("cci20","willr14","hma21","supertrend_side","supertrend_band"):
            v=before[name].iloc[:650].to_numpy()
            x=after[name].iloc[:650].to_numpy()
            np.testing.assert_allclose(v,x,equal_nan=True,atol=1e-10,
                                       rtol=1e-10,err_msg=name)

    def test_signal_no_lookahead(self):
        raw=sample(850)
        base=indicators(prepared(raw))
        changed=raw.copy()
        changed.loc[changed.index[650]:,["open","close","high","low"]]+=200.
        later=indicators(prepared(changed))
        for model in MODELS:
            earlier=[s for s in create_signals(base,model) if s[0]<649]
            posterior=[s for s in create_signals(later,model) if s[0]<649]
            self.assertEqual(earlier,posterior,model)

    def test_baseline_exactly_matches_previous_engine(self):
        d=indicators(prepared(sample()))
        b=base_events(d,"EMA21_PULLBACK")
        self.assertEqual(b,create_signals(d,"EMA21_BASE",b))

    def test_signals_have_forward_open_and_correct_stop(self):
        d=indicators(prepared(sample(800)))
        entry=d.open.to_numpy(dtype=float)
        for model in MODELS:
            signals=create_signals(d,model)
            prev=-1
            for i,side,stop,_ in signals:
                self.assertGreater(i,prev)
                self.assertGreaterEqual(i,240)
                self.assertLess(i,len(d)-1)
                self.assertGreater(side*(entry[i+1]-stop),0)
                prev=i

    def test_runner_preserves_stop_first(self):
        d=indicators(prepared(sample(650)))
        entry=float(d.open.iloc[242])
        d.iloc[242,d.columns.get_loc("high")]=entry+5.
        d.iloc[242,d.columns.get_loc("low")]=entry-5.
        t=replay_one(d,[(241,1,entry-2.,.6)],240,len(d),30,"RUNNER_96H")
        self.assertEqual(len(t),1)
        self.assertEqual(t[0]["reason"],"SL")
        self.assertLess(t[0]["gross_pts"],0)

    def test_refuse_data_before_2025(self):
        raw=sample()
        raw.index=raw.index-pd.Timedelta(days=500)
        with self.assertRaises(ValueError):
            replay_year(raw,"2024",1)

    def test_unknown_model_rejected(self):
        with self.assertRaises(ValueError):
            create_signals(indicators(prepared(sample())),"MAGIC_500")

    def test_screen_rejects_insufficient_trades(self):
        cases=[]
        for tf in TF_MINUTES:
            for year in ("2025","2026"):
                s={model:{"1.2":dict(N=8,PF=2.0,net_pts=10000)}
                   for model in MODELS}
                cases.append(dict(tf=f"M{tf}",year=year,summary=s))
        compared,short=screen(cases)
        self.assertEqual(len(compared),55)
        self.assertEqual(short,[])


if __name__=="__main__":
    unittest.main()
