import unittest
from research.regime_v3 import trade_math,size_position,KEYS
from src.feed import MARKETS

class ResearchRiskTests(unittest.TestCase):
    def test_five_markets_and_ten_rules(self):
        self.assertEqual(len(MARKETS),5)
        self.assertEqual(len(KEYS),10)
    def test_usdjpy_profit_converts_from_yen_to_usd(self):
        pnl,fee=trade_math("USDJPY",1,150,151,10000)
        self.assertAlmostEqual(fee,5,places=6)
        self.assertAlmostEqual(pnl,10000/151-5,places=6)
    def test_usdjpy_stop_position_sizes_in_usd(self):
        q=size_position("USDJPY",5000,150,1.2,1.8)
        self.assertGreater(q,0)
        self.assertLessEqual(q,10000)
        approx_risk=q*1.8*1.2/150
        self.assertLessEqual(approx_risk,5000*0.0075+.001)
    def test_cost_stress_cannot_improve_fixed_trade(self):
        base,_=trade_math("XAUUSD",1,4000,4100,.3,1)
        stress,_=trade_math("XAUUSD",1,4000,4100,.3,2)
        self.assertLess(stress,base)

if __name__=="__main__": unittest.main()
