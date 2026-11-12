"""Synthetic tests for additional XAU indicators. No external data or live orders."""
import unittest
import numpy as np
import pandas as pd
from research_oos import prepared
from points10k import events as frozen_ema_events
from alpha_xau_mtf_2025plus import replay_one, summarize, TF_MINUTES
from xau_indicator_lab_2025plus import (
    MODELS, BASELINE, build_signals, indicators, rank_models, run_year)


def fake_frame(n=630):
    rng=np.random.default_rng(11)
    c=2400.+np.cumsum(rng.normal(0,1.5,n))
    op=np.r_[c[0],c[:-1]]
    hi=np.maximum(op,c)+rng.uniform(.2,1.1,n)
    lo=np.minimum(op,c)-rng.uniform(.2,1.1,n)
    ix=pd.date_range("2025-01-01",periods=n,freq="1min",tz="UTC")
    raw=pd.DataFrame(dict(open=op,high=hi,low=lo,close=c,
                          volume=rng.integers(10,300,n)),index=ix)
    return indicators(prepared(raw))


class NewXAUIndicatorsTests(unittest.TestCase):
    def test_all_models_unique_and_new(self):
        self.assertEqual(len(MODELS),len(set(MODELS)))
        self.assertGreaterEqual(len(MODELS),8)
        self.assertEqual(len(TF_MINUTES),11)
        self.assertIn("ADX_DONCHIAN24",MODELS)
        self.assertIn("RSI_BOLLINGER20",MODELS)
        self.assertIn("KELTNER_SQUEEZE",MODELS)
        self.assertIn("STOCH_REJECTION",MODELS)

    def test_each_indicator_uses_only_completed_past_and_current_bars(self):
        d=fake_frame(650)
        prefix=d.iloc[:360].copy()
        # indicator values computed on prefix must match original full feed.
        first=indicators(prepared(prefix[["open","high","low","close","volume"]]))
        cols=("adx","plus_di","minus_di","rsi14",
              "bb_mid","bb_upper","bb_lower",
              "macd_hist","stoch_k","stoch_d","squeeze")
        for col in cols:
            a=np.asarray(first[col])
            b=np.asarray(d[col].iloc[:360])
            if col=="squeeze":
                self.assertTrue(np.array_equal(a,b))
            else:
                np.testing.assert_allclose(a,b,rtol=1e-10,atol=1e-10,
                                           equal_nan=True,err_msg=col)

    def test_future_ohlc_mutations_cannot_change_past_events(self):
        d=fake_frame(800)
        base=frozen_ema_events(d,"EMA21_PULLBACK")
        a={m:build_signals(d,m,baseline=base) for m in MODELS}
        raw=d[["open","high","low","close","volume"]].copy()
        # Completely replace data AFTER cutoff with distant prices.
        raw.loc[raw.index[650]:,["open","high","low","close"]]+=900.
        updated=indicators(prepared(raw))
        future_base=frozen_ema_events(updated,"EMA21_PULLBACK")
        for model in MODELS:
            b=build_signals(updated,model,baseline=future_base)
            past_a=[s for s in a[model] if s[0]<649]
            past_b=[s for s in b if s[0]<649]
            self.assertEqual(past_a,past_b,model)

    def test_ema_baseline_is_identical_to_frozen_source(self):
        d=fake_frame()
        frozen=frozen_ema_events(d,"EMA21_PULLBACK")
        self.assertEqual(frozen,build_signals(d,BASELINE,frozen))

    def test_adx_and_rsi_confluences_cannot_add_new_ema_signals(self):
        d=fake_frame()
        orig=frozen_ema_events(d,"EMA21_PULLBACK")
        for m in ("EMA21_ADX_DI","EMA21_RSI_MACD"):
            filt=build_signals(d,m,orig)
            self.assertTrue(all(item in orig for item in filt))

    def test_all_signals_sorted_and_stop_direction_correct(self):
        d=fake_frame()
        op=d.open.to_numpy()
        for m in MODELS:
            events=build_signals(d,m)
            prev=-1
            for i,side,stop,quality in events:
                self.assertGreater(i,prev,m)
                self.assertLess(i,len(d)-1)
                self.assertIn(side,(-1,1))
                self.assertGreater(side*(op[i+1]-stop),0.)
                self.assertTrue(np.isfinite(quality))
                prev=i

    def test_rsi_neutral_when_price_unchanged(self):
        n=300
        t=pd.date_range("2025-02-01",periods=n,freq="1min",tz="UTC")
        d=pd.DataFrame(dict(open=100.,high=100.1,low=99.9,
            close=100.,volume=5),index=t)
        x=indicators(prepared(d))
        self.assertAlmostEqual(x.rsi14.iloc[-1],50.)
        self.assertFalse(x.stoch_k.iloc[-1]==float("inf"))

    def test_donchian_is_shifted_and_no_future_swing_pivot(self):
        d=fake_frame()
        self.assertAlmostEqual(d.rhi.iloc[270],d.high.iloc[246:270].max())
        self.assertAlmostEqual(d.rlo.iloc[270],d.low.iloc[246:270].min())

    def test_runner_applies_same_stop_first_to_all_new_signals(self):
        d=fake_frame()
        fake=[(241,1,float(d.open.iloc[242]-2.),.7)]
        # Force entry-bar high reaching TP while same candle breaks stop.
        entry=d.open.iloc[242]
        d.iloc[242,d.columns.get_loc("high")]=entry+6.
        d.iloc[242,d.columns.get_loc("low")]=entry-4.
        trades=replay_one(d,fake,240,630,30,"RUNNER_96H")
        self.assertEqual(trades[0]["reason"],"SL")
        self.assertLess(trades[0]["gross_pts"],0)

    def test_reject_any_pre2025_dataset(self):
        d=fake_frame()
        d.index=d.index-pd.Timedelta(days=400)
        with self.assertRaises(ValueError):
            run_year(d,"2024",15)

    def test_unknown_indicator_rejected(self):
        with self.assertRaises(ValueError):
            build_signals(fake_frame(),"FUTURE_MAGIC")

    def test_stress_cost_subtracts_trade_count(self):
        trades=[dict(gross_pts=200,entry=0,exit=8),
                dict(gross_pts=-120,entry=10,exit=14)]
        low=summarize(trades,.8)
        high=summarize(trades,1.2)
        self.assertAlmostEqual(low["net_pts"]-high["net_pts"],80.)

    def test_conservative_screen_rejects_small_samples(self):
        fake=[]
        for tf in TF_MINUTES:
            for year in ("2025","2026"):
                summary={}
                for model in MODELS:
                    summary[model]={
                        "0.8":dict(N=5,net_pts=10000,PF=2,mdd_pts=50),
                        "1.2":dict(N=5,net_pts=9000,PF=1.5,mdd_pts=55)}
                fake.append(dict(tf=f"M{tf}",year=year,summary=summary))
        ranked=rank_models(fake)
        self.assertEqual(len(ranked),len(TF_MINUTES)*len(MODELS))
        self.assertFalse(any(q["conservative_screen_pass"] for q in ranked))


if __name__=="__main__":
    unittest.main()
