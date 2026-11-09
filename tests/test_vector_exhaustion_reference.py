"""Independent indicator test gates: NO lookahead, NO fabricated Tracker equivalence."""
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path

from research.vector_exhaustion_reference import (
    Rules, detect, planned_economics, replay, vector
)

START=datetime(2026,6,10,12,10,tzinfo=timezone.utc)  # 09:10 Sao Paulo

def mk(ts,op=100050,hi=100100,lo=100000,cl=100055,vol=100):
    return {"time":int(ts.timestamp()),"open":float(op),"high":float(hi),
            "low":float(lo),"close":float(cl),"volume":float(vol)}

def fixture():
    rows=[mk(START+timedelta(minutes=i)) for i in range(20)]
    rows.append(mk(START+timedelta(minutes=20),
                   op=100040,hi=100090,lo=99990,cl=100060,vol=200))
    return rows

class GeometryTests(unittest.TestCase):
    def test_buy_vector_matches_public_levels(self):
        levels=vector(high=100090,low=99990,side=1)
        self.assertEqual(levels,{"0":99990,"50":100040,"100":100090,
                                 "200":100190,"-100":99890})
        self.assertEqual(levels["200"]-levels["50"],levels["50"]-levels["-100"])

    def test_sell_vector_is_mirrored(self):
        levels=vector(high=100090,low=99990,side=-1)
        self.assertEqual(levels,{"0":100090,"50":100040,"100":99990,
                                 "200":99890,"-100":100190})
        self.assertEqual(levels["50"]-levels["200"],levels["-100"]-levels["50"])

    def test_invalid_candle_geometry_rejected(self):
        with self.assertRaises(ValueError):
            vector(100,100,1)
        with self.assertRaises(ValueError):
            vector(100,90,0)

    def test_signal_checks_closed_candle_only_no_future(self):
        a=fixture()
        signal=detect(a,20)
        self.assertEqual(signal["side"],1)
        later=[mk(START+timedelta(minutes=21),op=99100,hi=99150,lo=99000,cl=99125,vol=100000)]
        self.assertEqual(detect(a+later,20),signal,
                         "New candles cannot change prior signals")
        self.assertIsNone(detect(a,19),"Need 20 completed earlier candles")

    def test_fails_real_volume_and_sweep_conditions(self):
        a=fixture()
        a[-1]["volume"]=10
        self.assertIsNone(detect(a,20))
        b=fixture()
        b[-1]["low"]=100005
        self.assertIsNone(detect(b,20))

    def test_signals_do_not_bridge_another_local_day(self):
        a=fixture()
        a[0]["time"]-=86400
        self.assertIsNone(detect(a,20))

    def test_gross_one_to_one_is_not_net_one_to_one(self):
        signal=detect(fixture(),20)
        result=planned_economics(signal)
        self.assertEqual(result["gross_risk_brl"],30.0)
        self.assertEqual(result["gross_reward_brl"],30.0)
        self.assertEqual(result["cost_roundtrip_brl"],6.0)
        self.assertEqual(result["risk_net_brl"],36.0)
        self.assertEqual(result["reward_net_brl"],24.0)
        self.assertAlmostEqual(result["break_even_hit_rate"],0.60)
        self.assertTrue(result["exceeds_budget"])

    def test_small_signal_enters_budget_but_requires_75pct_winrate(self):
        data=fixture()
        data[-1]=mk(START+timedelta(minutes=20),
                    op=100015,hi=100035,lo=99995,cl=100025,vol=200)
        sig=detect(data,20)
        self.assertIsNotNone(sig)
        e=planned_economics(sig)
        self.assertEqual(e["gross_risk_brl"],12.0)
        self.assertEqual(e["risk_net_brl"],18.0)
        self.assertEqual(e["reward_net_brl"],6.0)
        self.assertAlmostEqual(e["break_even_hit_rate"],.75)
        self.assertFalse(e["exceeds_budget"])

    def test_signals_do_not_become_trades_without_limit_fill(self):
        a=fixture()
        a.extend([mk(START+timedelta(minutes=21+i),
                     op=100075,hi=100090,lo=100055,cl=100085)
                  for i in range(20)])
        r=replay(a)
        self.assertGreaterEqual(r["signals"],1)
        self.assertEqual(r["closed_paper_trades"],0)
        self.assertEqual(r["net_closed_brl"],0.0)
        self.assertFalse(r["approved_for_live"])

    def test_no_real_orders_or_proprietary_code_in_mql5(self):
        code=Path("indicators/mt5/NQ_Vector_Exhaustion_Research.mq5").read_text(encoding="utf-8")
        self.assertIn("#property indicator_buffers 2",code)
        self.assertIn("i<1 || i+InpLookbackBars>=count",code)
        self.assertIn("InpRequireRealVolume",code)
        self.assertIn("previous bar is now immutable and closed",code)
        self.assertIn("NOT Greenhouse Tracker",code)
        for unsafe in ("OrderSend(","OrderCheck(","CTrade","PositionOpen(","iCustom("):
            self.assertNotIn(unsafe,code)

if __name__=="__main__":
    unittest.main()
