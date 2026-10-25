import unittest
from unittest.mock import patch
from src.green_stop import update_after_close, check_mode
from src import leveraged_gold as lever

class GreenStopTests(unittest.TestCase):
    def book(self,side=1,mode="green_runner"):
        entry=100.0
        return {"side":side,"entry":entry,"start":1000000,
                "qty":100.0,"entry_risk":1.0,"mode":mode,
                "stop":entry-side*1.0,"target":None,"borrowed":500.0,
                "peak_favorable":0,"green_protected":False}
    def test_cost_aware_long_green_starts_next_bar(self):
        p=self.book()
        prior=p["stop"]
        self.assertTrue(update_after_close(p,
            {"open":100,"high":101.2,"low":99.6,"close":100.7},
            1000000+14400,14,.08))
        self.assertGreater(p["stop"],100.14)
        self.assertGreater(p["stop"],prior)
        stop=p["stop"]
        # Carry cost grows with time, so the green floor may tighten
        # slightly even if price fails to set a new high; it never loosens.
        update_after_close(p,
            {"open":100,"high":100.5,"low":99.9,"close":100.1},
            1000000+28800,14,.08)
        self.assertGreaterEqual(p["stop"],stop)
    def test_trail_after_one_and_half_r(self):
        p=self.book()
        update_after_close(p,{"open":100,"high":101.7,"low":99.9,"close":101.5},
                           1000000+14400,14,.08)
        self.assertGreaterEqual(p["stop"],100.70-1e-9)
    def test_short_green_is_monotone(self):
        p=self.book(side=-1)
        a=p["stop"]
        update_after_close(p,{"open":100,"high":100.4,"low":98.4,"close":98.6},
                            1000000+14400,14,.08)
        self.assertLess(p["stop"],a)
        self.assertLessEqual(p["stop"],99.4+1e-8)
    def test_fixed_unchanged(self):
        p=self.book(mode="fixed")
        self.assertFalse(update_after_close(p,{"open":100,"high":120,"low":80,"close":115},
                                           1000000+14400,14,.08))
        self.assertEqual(p["stop"],99)
    def test_not_activated_before_one_r(self):
        p=self.book()
        self.assertFalse(update_after_close(p,{"open":100,"high":100.8,"low":99.2,"close":100.4},
                                           1000000+14400,14,.08))
        self.assertEqual(p["stop"],99)
    def test_runner_has_no_fixed_tp_but_keeps_risk(self):
        b=lever.fresh([{"time":i*14400} for i in range(245)])["books"]["lev_channel20"]
        bars=[{"time":i*14400,"open":100,"high":102,"low":98,"close":101} for i in range(251)]
        ind=[{"atr":2} for _ in range(251)]
        with patch("src.leveraged_gold.sign",side_effect=[1,0]):
            lever.one_bar(b,"lev_channel20",bars,ind,250,mode="green_runner")
        p=b["position"]
        self.assertIsNone(p["target"])
        self.assertEqual(p["mode"],"green_runner")
        self.assertAlmostEqual(p["notional_leverage"],2,places=6)
        self.assertLessEqual(p["qty"]*abs(p["entry"]-p["stop"]),5000*0.015+0.001)
    def test_older_open_positions_continue_fixed(self):
        # Even after LIVE_POLICY changes, existing positions should retain
        # the policy written when those particular positions were opened.
        p=self.book(mode="fixed")
        self.assertFalse(update_after_close(p,
          {"open":100,"high":102,"low":99.9,"close":101.9},1000000+14400,14,.08))
        self.assertEqual(p["stop"],99)
    def test_reject_unknown_mode(self):
        with self.assertRaises(ValueError):
            check_mode("profit-guaranteed")

if __name__=="__main__":
    unittest.main()
