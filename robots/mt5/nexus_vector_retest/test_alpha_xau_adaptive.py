"""Deterministic synthetic checks; historical profitability not asserted."""
import unittest
import numpy as np
import pandas as pd
from alpha_xau_adaptive import simulate_adaptive, trend_masks, extended_stats

N = 650

def sample():
    d = pd.DataFrame(dict(open=[100.]*N, high=[100.1]*N,
       low=[99.9]*N, close=[100.]*N,
       atr=[1.]*N, fema=[100.]*N, sema=[100.]*N))
    return d

def bullish_followthrough(f):
    f.loc[3,"high"]=103.1
    f.loc[4:,["open","high","low","close"]]=[100.5,100.6,100.4,100.5]

def bearish_followthrough(f):
    f.loc[3,"low"]=96.9
    f.loc[4:,["open","high","low","close"]]=[99.5,99.6,99.4,99.5]

def forced_masks():
    return np.zeros((2,N),dtype=bool), np.zeros((2,N),dtype=bool)

class TestAdaptiveXAU(unittest.TestCase):
    def test_flat_market_never_extends_beyond_48(self):
        t=simulate_adaptive(sample(),[(1,1,98.,1.)],0,N)
        self.assertEqual(len(t),1)
        self.assertEqual((t[0]["reason"],t[0]["duration_bars"]),
                         ("TIME_BASE",48))
        self.assertFalse(t[0]["ever_runner"])

    def test_no_trend_preserves_original_tp3(self):
        f=sample();f.loc[3,"high"]=104.5
        t=simulate_adaptive(f,[(1,1,98.,1.)],0,N)
        self.assertEqual(t[0]["reason"],"TP3")
        self.assertAlmostEqual(t[0]["net_pts"],220.)

    def test_trend_holds_runner_but_hard_caps_at_384(self):
        f=sample();bullish_followthrough(f)
        a,b=forced_masks();a[0,1:]=True
        t=simulate_adaptive(f,[(1,1,98.,1.)],0,N,(a,b))
        self.assertEqual(t[0]["reason"],"TIME_MAX")
        self.assertEqual(t[0]["duration_bars"],384)
        self.assertTrue(t[0]["extended"])
        self.assertTrue(t[0]["ever_runner"])

    def test_two_closed_bars_trend_loss_next_open(self):
        f=sample();bullish_followthrough(f)
        a,b=forced_masks();a[0,1:60]=True
        t=simulate_adaptive(f,[(1,1,98.,1.)],0,N,(a,b))
        self.assertEqual(t[0]["reason"],"TREND_LOST")
        # At j=60, prev=59 still trend; j=61 prev=60 absent and prev-1=59 present;
        # j=62 prev=61 absent and prev-1=60 absent -> exit index 62.
        self.assertEqual(t[0]["exit"],62)

    def test_stop_has_priority_over_all_partial_targets(self):
        f=sample();f.loc[3,"high"]=105.;f.loc[3,"low"]=97.
        t=simulate_adaptive(f,[(1,1,98.,1.)],0,N)
        self.assertEqual(t[0]["reason"],"SL")
        self.assertAlmostEqual(t[0]["net_pts"],-280)

    def test_gap_through_stop_uses_open(self):
        f=sample()
        f.loc[3,["open","high","low","close"]]=[96.,97.,95.,96.]
        t=simulate_adaptive(f,[(1,1,98.,1.)],0,N)
        self.assertEqual(t[0]["reason"],"SL")
        self.assertAlmostEqual(t[0]["net_pts"],-480.)

    def test_short_direction_can_extend(self):
        f=sample();bearish_followthrough(f)
        a,b=forced_masks();a[1,1:]=True
        t=simulate_adaptive(f,[(1,-1,102.,1.)],0,N,(a,b))
        self.assertTrue(t[0]["ever_runner"])
        self.assertEqual(t[0]["reason"],"TIME_MAX")

    def test_future_bars_cannot_change_prior_trend_masks(self):
        f=sample()
        for t in range(N):
            f.loc[t,["close","fema","sema"]]=[100+.2*t,99.7+.2*t,98.+.2*t]
        a1,b1=trend_masks(f)
        self.assertTrue(a1[0,20])
        self.assertTrue(b1[0,20])
        self.assertFalse(a1[1,20])
        f.loc[101:,["close","fema","sema"]]=[-500.,600.,-600.]
        a2,b2=trend_masks(f)
        self.assertTrue(np.array_equal(a1[:,:100],a2[:,:100]))
        self.assertTrue(np.array_equal(b1[:,:100],b2[:,:100]))

    def test_flat_has_no_trend_classification(self):
        m,s=trend_masks(sample())
        self.assertFalse(m.any())
        self.assertFalse(s.any())

    def test_same_right_tail_embargo(self):
        t=simulate_adaptive(sample(),[(300,1,98.,1.)],0,N)
        self.assertEqual(t,[])

    def test_two_signals_do_not_overlap(self):
        f=sample();bullish_followthrough(f)
        a,b=forced_masks();a[0,1:]=True
        t=simulate_adaptive(f,[(1,1,98.,1.),(2,1,98.,1.)],0,N,(a,b))
        self.assertEqual(len(t),1)

    def test_extended_stats(self):
        t=[dict(gross_pts=200.,net_pts=120.,extended=True,
                ever_runner=True,duration_bars=70,reason="TREND_LOST"),
           dict(gross_pts=-200.,net_pts=-280.,extended=False,
                ever_runner=False,duration_bars=4,reason="SL")]
        s=extended_stats(t)
        self.assertEqual(s["extended_n"],1)
        self.assertEqual(s["trend_runner_n"],1)
        self.assertEqual(s["median_bars"],37)

if __name__=="__main__":
    unittest.main()
