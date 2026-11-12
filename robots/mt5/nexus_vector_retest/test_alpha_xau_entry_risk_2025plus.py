"""Focussed synthetic regression tests — no claims of profitable trades."""
import unittest
import numpy as np
import pandas as pd
from alpha_xau_entry_risk_2025plus import (
    MAX_HOLD, PROFILES, checked_window, comparison, metrics,
    qualified_entry, replay, simulate_profile)


def synthetic(n=540):
    return pd.DataFrame({
        "open":[100.]*n, "high":[100.2]*n, "low":[99.8]*n,
        "close":[100.]*n, "atr":[1.]*n,
        "fema":[100.]*n, "sema":[100.]*n})


class TestEntryRiskXAU(unittest.TestCase):
    def test_frozen_runner_trade_by_trade_equivalence(self):
        f=synthetic()
        f.loc[3,"high"]=103.5
        a=checked_window(f,[(1,1,98.,.7)],0,len(f))
        b=simulate_profile(f,[(1,1,98.,.7)],0,len(f),"RUNNER384_ORIGINAL")
        self.assertEqual(a,b)

    def test_stop_first_even_when_tp2_also_hit(self):
        f=synthetic();f.loc[3,"high"]=104.;f.loc[3,"low"]=97.
        t=simulate_profile(f,[(1,1,98.,.7)],0,len(f),"BREAKEVEN_AFTER_TP2")
        self.assertEqual(len(t),1)
        self.assertEqual(t[0]["reason"],"SL")
        self.assertAlmostEqual(t[0]["net_pts"],-280.)

    def test_breakeven_only_activates_on_following_candle(self):
        f=synthetic();f.loc[3,"high"]=104.;f.loc[3,"low"]=99.
        t=simulate_profile(f,[(1,1,98.,.7)],0,len(f),"BREAKEVEN_AFTER_TP2")
        self.assertTrue(t[0]["stopped_at_be"])
        self.assertEqual(t[0]["exit"],4)
        self.assertAlmostEqual(t[0]["gross_pts"],(2+3)/3*100)

    def test_gap_below_breakeven_is_not_filled_at_entry(self):
        f=synthetic();f.loc[3,"high"]=104.
        f.loc[4,["open","high","low","close"]]=[99.,99.8,98.8,99.]
        t=simulate_profile(f,[(1,1,98.,.7)],0,len(f),"BREAKEVEN_AFTER_TP2")
        self.assertEqual(t[0]["exit"],4)
        self.assertAlmostEqual(t[0]["gross_pts"],(2+3)/3*100-100/3)

    def test_entry_gate_never_uses_future_bar(self):
        f=synthetic()
        f.loc[5,"fema"]=100.
        f.loc[10,["fema","sema","atr","high","low"]]=[100.6,100.1,1.,100.8,99.8]
        a=qualified_entry(f,10,1,1.)
        f.loc[11:,["fema","sema","high","low"]]=[-100.,999.,1000.,-1000.]
        self.assertTrue(a)
        self.assertEqual(a,qualified_entry(f,10,1,1.))

    def test_entry_guard_requires_directional_slope(self):
        f=synthetic()
        self.assertFalse(qualified_entry(f,10,1,1.))
        self.assertFalse(qualified_entry(f,10,-1,1.))

    def test_entry_guard_limits_risk_and_signal_candle_range(self):
        f=synthetic()
        f.loc[10,["fema","sema"]]=[100.6,100.1]
        self.assertFalse(qualified_entry(f,10,1,3.))
        self.assertFalse(qualified_entry(f,10,1,.1))
        self.assertTrue(qualified_entry(f,10,1,1.))
        f.loc[10,"high"]=104.
        self.assertFalse(qualified_entry(f,10,1,1.))

    def test_quality_filter_does_not_modify_baseline(self):
        f=synthetic()
        s=[(1,1,98.,.7)]
        base=simulate_profile(f,s,0,len(f),"RUNNER384_ORIGINAL")
        filt=simulate_profile(f,s,0,len(f),"ENTRY_QUALITY")
        self.assertEqual(len(base),1)
        self.assertEqual(filt,[])

    def test_short_direction_stop_before_tp(self):
        f=synthetic()
        f.loc[3,["high","low"]]=[103.,96.]
        t=simulate_profile(f,[(1,-1,102.,.7)],0,len(f),"RUNNER384_ORIGINAL")
        self.assertEqual(t[0]["reason"],"SL")
        self.assertAlmostEqual(t[0]["net_pts"],-280.)

    def test_all_profiles_no_overlap(self):
        f=synthetic();s=[(1,1,98.,.7),(2,1,98.,.7)]
        for name in PROFILES:
            t=simulate_profile(f,s,0,len(f),name)
            self.assertLessEqual(len(t),1)

    def test_tail_embargo_shared_between_models(self):
        f=synthetic()
        for name in PROFILES:
            t=simulate_profile(f,[(200,1,98.,.7)],0,len(f),name)
            self.assertEqual(t,[])

    def test_cost_grid_is_strictly_monotone_for_trade_count(self):
        f=synthetic();f.loc[3,"high"]=103.5
        t=simulate_profile(f,[(1,1,98.,.7)],0,len(f),"RUNNER384_ORIGINAL")
        x=metrics(t,.8);y=metrics(t,1.2);z=metrics(t,1.6)
        self.assertEqual(x["N"],1)
        self.assertAlmostEqual(x["net_pts"]-y["net_pts"],40,places=1)
        self.assertGreater(y["net_pts"],z["net_pts"])

    def test_pre2025_feed_is_rejected(self):
        i=pd.date_range("2024-12-31",periods=10,freq="15min",tz="UTC")
        d=synthetic(10);d.index=i
        with self.assertRaises(ValueError):
            replay(d,"INVALID")

    def test_invalid_profile_rejected(self):
        with self.assertRaises(ValueError):
            simulate_profile(synthetic(),[],0,540,"MAGIC")

    def test_reversal_be_does_not_move_stop_in_normal_trend(self):
        f=synthetic();f.loc[3,"high"]=104.
        s=[(1,1,98.,.7)]
        base=simulate_profile(f,s,0,len(f),"RUNNER384_ORIGINAL")
        gated=simulate_profile(f,s,0,len(f),"REVERSAL_GATED_BE")
        self.assertEqual(base,gated)

    def test_reversal_be_arms_only_after_two_closed_adverse_bars(self):
        f=synthetic();f.loc[3,"high"]=103.3
        f.loc[4:5,["low","close"]]=[99.3,99.5]
        s=[(1,1,98.,.7)]
        gated=simulate_profile(f,s,0,len(f),"REVERSAL_GATED_BE")
        self.assertEqual(gated[0]["reason"],"SL_AFTER_TP2")
        self.assertEqual(gated[0]["exit"],6)
        self.assertTrue(gated[0]["stopped_at_be"])

    def test_reversal_be_requires_two_adverse_closes(self):
        f=synthetic();f.loc[3,"high"]=103.3
        f.loc[4,["low","close"]]=[99.3,99.5]
        s=[(1,1,98.,.7)]
        gated=simulate_profile(f,s,0,len(f),"REVERSAL_GATED_BE")
        self.assertEqual(gated[0]["reason"],"TIME")
        self.assertFalse(gated[0]["stopped_at_be"])

    def test_reversal_be_short_direction(self):
        f=synthetic();f.loc[3,"low"]=96.7
        f.loc[4:5,["high","close"]]=[100.7,100.5]
        gated=simulate_profile(f,[(1,-1,102.,.7)],0,len(f),
                               "REVERSAL_GATED_BE")
        self.assertEqual(gated[0]["reason"],"SL_AFTER_TP2")
        self.assertEqual(gated[0]["exit"],6)

    def test_comparison_requires_all_blocks(self):
        rows=[]
        for model,net,dd in [
            ("RUNNER384_ORIGINAL",10,100),
            ("ENTRY_QUALITY",9,90),
            ("BREAKEVEN_AFTER_TP2",11,110),
            ("ENTRY_QUALITY_BE",12,90),
            ("REVERSAL_GATED_BE",9,90)]:
            stats=dict(N=100,net_pts=net,mdd_pts=dd)
            rows.append(dict(dataset="2025",window=0,model=model,costs={
                "0.8":stats,"1.2":stats}))
        r=comparison(rows)
        self.assertFalse(r["ENTRY_QUALITY"]["beats_all_blocks"])
        self.assertFalse(r["BREAKEVEN_AFTER_TP2"]["beats_all_blocks"])
        self.assertTrue(r["ENTRY_QUALITY_BE"]["beats_all_blocks"])


if __name__=="__main__":
    unittest.main()
