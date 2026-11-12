"""Volatility-breakout lab: strict causality, signal stop and baseline tests."""
import unittest
import numpy as np
import pandas as pd
from research_oos import prepared
from points10k import events as original_events
from alpha_xau_mtf_2025plus import TF_MINUTES, replay_one
from xau_volatility_breakouts_2025plus import (
    MODELS, feature_frame, make_signals, evaluate_year, screening)


def sample(n=950):
    rng=np.random.default_rng(23)
    closes=2700+np.cumsum(rng.normal(0,1.6,n))
    opens=np.r_[closes[0],closes[:-1]]
    highs=np.maximum(opens,closes)+rng.uniform(.1,.8,n)
    lows=np.minimum(opens,closes)-rng.uniform(.1,.8,n)
    ix=pd.date_range("2025-05-01",periods=n,freq="1min",tz="UTC")
    return pd.DataFrame(dict(open=opens,high=highs,low=lows,
                             close=closes,volume=rng.integers(10,200,n)),
                        index=ix)


class TestVolatilityBreakouts(unittest.TestCase):
    def test_models_cover_new_independent_mechanics_and_all_tfs(self):
        self.assertEqual(len(MODELS),5)
        self.assertEqual(TF_MINUTES,(1,2,3,4,5,6,10,12,15,20,30))
        for m in ("NR7_BAR_BREAK","INSIDE_MOTHER_BREAK",
                  "VOL_COMPRESSION_RELEASE","EFFICIENCY_ER20_BREAK"):
            self.assertIn(m,MODELS)

    def test_trailing_levels_use_only_previous_candles(self):
        f=feature_frame(prepared(sample()))
        i=420
        self.assertAlmostEqual(f.prior8_hi.iloc[i],f.high.iloc[i-8:i].max())
        self.assertAlmostEqual(f.prior12_lo.iloc[i],f.low.iloc[i-12:i].min())
        self.assertEqual(bool(f.nr7_prev.iloc[i]),
                         bool((f.high-f.low).iloc[i-1]<=
                              (f.high-f.low).iloc[i-7:i].min()))
        self.assertEqual(bool(f.inside_prev.iloc[i]),
            bool(f.high.iloc[i-1]<f.high.iloc[i-2] and
                 f.low.iloc[i-1]>f.low.iloc[i-2]))

    def test_future_change_cannot_repaint_past_indicator_values(self):
        raw=sample(880)
        a=feature_frame(prepared(raw))
        alt=raw.copy()
        cols=alt.columns.get_indexer(["open","high","low","close"])
        alt.iloc[680:,cols]+=1000
        b=feature_frame(prepared(alt))
        for c in ("nr7_prev","inside_prev","prev_mother_hi","prev_mother_lo",
                  "prev_hi","prev_lo","short_tr6","old_tr20",
                  "prior8_hi","prior8_lo","prior12_hi","prior12_lo","er20"):
            if c in ("nr7_prev","inside_prev"):
                np.testing.assert_array_equal(a[c].iloc[:680].to_numpy(),
                                              b[c].iloc[:680].to_numpy())
            else:
                np.testing.assert_allclose(a[c].iloc[:680],
                    b[c].iloc[:680],rtol=1e-12,atol=1e-12,equal_nan=True,
                    err_msg=c)

    def test_future_prices_cannot_change_past_emitted_signals(self):
        raw=sample(890)
        a=feature_frame(prepared(raw))
        alt=raw.copy()
        cols=alt.columns.get_indexer(["open","high","low","close"])
        alt.iloc[700:,cols]+=1000
        b=feature_frame(prepared(alt))
        for model in MODELS:
            earlier=[v for v in make_signals(a,model) if v[0]<699]
            later=[v for v in make_signals(b,model) if v[0]<699]
            self.assertEqual(earlier,later,model)

    def test_preserved_ema_runner_event_parity(self):
        d=feature_frame(prepared(sample()))
        frozen=original_events(d,"EMA21_PULLBACK")
        self.assertEqual(frozen,make_signals(d,"EMA21_BASE",frozen))

    def test_signal_order_direction_and_stop_sane(self):
        d=feature_frame(prepared(sample()))
        op=d.open.to_numpy()
        for model in MODELS:
            signals=make_signals(d,model)
            last=-1
            for i,side,stop,quality in signals:
                self.assertGreater(i,last)
                self.assertLess(i,len(d)-1)
                self.assertGreaterEqual(i,240)
                self.assertIn(side,(-1,1))
                self.assertGreater(side*(op[i+1]-stop),0)
                self.assertTrue(np.isfinite(quality))
                last=i

    def test_original_conservative_stop_first(self):
        d=feature_frame(prepared(sample()))
        entry=float(d.open.iloc[242])
        d.iloc[242,d.columns.get_loc("low")]=entry-4
        d.iloc[242,d.columns.get_loc("high")]=entry+8
        r=replay_one(d,[(241,1,entry-2.,0.9)],240,950,30,"RUNNER_96H")
        self.assertEqual(r[0]["reason"],"SL")
        self.assertLess(r[0]["gross_pts"],0.)

    def test_disallow_pre2025_dataset(self):
        d=sample()
        d.index=d.index-pd.Timedelta(days=700)
        with self.assertRaises(ValueError):
            evaluate_year(d,"2024",5)

    def test_unknown_setup_is_rejected(self):
        with self.assertRaises(ValueError):
            make_signals(feature_frame(prepared(sample())),"MAGIC_PROFIT")

    def test_cost_screen_requires_enough_trades(self):
        cases=[]
        for tf in TF_MINUTES:
            for year in ("2025","2026"):
                s={m:{"1.2":dict(N=4,PF=2.0,net_pts=5000)}
                   for m in MODELS}
                qs=[{"models":{m:{"1.2":{"net_pts":500}}
                               for m in MODELS}}]
                cases.append(dict(tf=f"M{tf}",year=year,summary=s,quarters=qs))
        r=screening(cases)
        self.assertEqual(len(r),55)
        self.assertFalse(any(row["screened"] for row in r))


if __name__=="__main__":
    unittest.main()
