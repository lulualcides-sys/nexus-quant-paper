"""Synthetic-only proof of conservative next-open execution and risk caps."""
import unittest
from research.alpha.engine import build,History
from research.alpha_v3.swing import SwingFilter,test_engine,TARGET_ATR,STOP_ATR

START=1785542400
def bars(n=300,spacing=60):
    return [dict(time=START+i*spacing,open=100.,high=100.5,
                 low=99.5,close=100.,volume=10.) for i in range(n)]
class OneSignal:
    def signal(self,h,f,i):return i==242

class SwingTests(unittest.TestCase):
    def test_frozen_parameters(self):
        self.assertEqual((TARGET_ATR,STOP_ATR),(8.,2.))
        self.assertEqual(SwingFilter("alpha02_breakout_retest").TIMEFRAME,5)
        with self.assertRaises(ValueError):SwingFilter("invalid")

    def test_stop_prioritized_when_both_levels_touched(self):
        a=bars()
        # Entry at i=243, stop around 99, target near 104.
        a[243]["high"]=110.;a[243]["low"]=80.
        run=test_engine(a,OneSignal(),1,5.)
        self.assertEqual(run["orders_filled"],1)
        self.assertEqual(run["ledger"][0]["reason"],"ambiguous_stop_first")
        self.assertLess(run["ledger"][0]["net_usdt"],0)
        self.assertLessEqual(-run["ledger"][0]["net_usdt"],5000*.0075+.02)

    def test_future_append_does_not_change_past_filter(self):
        a=bars(320);f=build(a)
        m=SwingFilter("alpha10_adaptive_regime")
        first=m.signal(History(a,285),f,284)
        second=m.signal(History(a[:285],285),build(a[:285]),284)
        self.assertEqual(first,second)

    def test_no_free_last_close_fill(self):
        a=bars(260);r=test_engine(a,OneSignal(),1,5.)
        self.assertEqual(r["orders_filled"],1)
        self.assertEqual(r["open_at_period_end"],1)
        self.assertEqual(r["ledger"],[])

if __name__=="__main__":
    unittest.main()
