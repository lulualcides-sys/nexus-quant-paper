"""Deterministic, synthetic tests; no claim of positive historical results."""
import unittest
import pandas as pd
from alpha_xau_longhold import simulate_xau, stats

def frame():
    n=520
    f=pd.DataFrame({"open":[100.]*n,"high":[100.5]*n,
                    "low":[99.5]*n,"close":[100.]*n})
    f.loc[3,"high"]=104.5
    f.loc[3,"low"]=99.
    return f

class TestXAUEMA21(unittest.TestCase):
    def test_three_fixed_targets_and_net_cost(self):
        t=simulate_xau(frame(),[(1,1,98.,1.)],0,520,48)
        self.assertEqual(len(t),1)
        self.assertEqual(t[0]["reason"],"TP3")
        self.assertAlmostEqual(t[0]["gross_pts"],300)
        self.assertAlmostEqual(t[0]["net_pts"],220)
    def test_reverse_stop_repositioned_not_profit_negation(self):
        t=simulate_xau(frame(),[(1,1,98.,1.)],0,520,48,reverse=True)
        self.assertEqual(t[0]["side"],-1)
        self.assertEqual(t[0]["reason"],"SL")
        self.assertAlmostEqual(t[0]["net_pts"],-280)
    def test_runner_keeps_final_third_until_time(self):
        t=simulate_xau(frame(),[(1,1,98.,1.)],0,520,96,runner=True)
        self.assertEqual(t[0]["reason"],"TIME")
        self.assertAlmostEqual(t[0]["gross_pts"],500/3)
        self.assertAlmostEqual(t[0]["net_pts"],500/3-80)
    def test_stop_first_when_both_in_one_bar(self):
        f=frame()
        f.loc[3,"low"]=97.
        t=simulate_xau(f,[(1,1,98.,1.)],0,520,48)
        self.assertEqual(t[0]["reason"],"SL")
        self.assertAlmostEqual(t[0]["net_pts"],-280)
    def test_same_tail_embargo_for_all_holds(self):
        for hold in (48,96,192,384):
            t=simulate_xau(frame(),[(200,1,98.,1.)],0,520,hold)
            self.assertEqual(t,[])
    def test_no_trade_overlap(self):
        t=simulate_xau(frame(),[(1,1,98.,1.),(2,1,98.,1.)],0,520,48)
        self.assertEqual(len(t),1)
    def test_drawdown(self):
        t=[{"gross_pts":100,"net_pts":100},{"gross_pts":-40,"net_pts":-40}]
        self.assertEqual(stats(t)["mdd_pts"],40.)

if __name__=="__main__":unittest.main()
