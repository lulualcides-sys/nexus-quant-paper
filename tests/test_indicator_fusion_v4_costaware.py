import unittest
from math import sin
from research.indicator_fusion_v4_costaware import (
  SCENARIOS, LOT_STEP_OZ, FBS_TYPICAL_SPREAD_USD_PER_OZ,
  run, STOP_ATR_V4, TARGET_R_V4, MAX_HOLD_V4,
)
from research.indicator_fusion_v3_frequency import portfolio, NAMES


def prices(n=280):
    out=[]
    for i in range(n):
        val=4100+1.3*sin(i/6)+i*.06
        out.append({'time':1700000100+i*300,'open':val,'high':val+1.5,'low':val-1.5,'close':val+0.25})
    return out


def one(name,i,n,side=1):
    z={k:[0]*n for k in NAMES}
    z[name][i]=side
    return z

class TestCostAware(unittest.TestCase):
    def test_spread_units_and_lot_step(self):
        self.assertEqual(LOT_STEP_OZ,1.0)
        self.assertEqual(FBS_TYPICAL_SPREAD_USD_PER_OZ,0.31)
        self.assertEqual(SCENARIOS['fbs_spread_plus_0p15_each_side']['fee_per_oz'],0.61)
    def test_params_predefined_and_no_live(self):
        self.assertEqual((STOP_ATR_V4,TARGET_R_V4,MAX_HOLD_V4),(3.0,3.0,36))
        x=run(prices())
        self.assertTrue(x['paper_only']);self.assertFalse(x['qualified_for_live'])
        self.assertTrue(x['historically_optimized_for_trade_frequency'])
    def test_minimum_one_ounce_enforced(self):
        b=prices();atr=[2.]*len(b);s=one(NAMES[0],240,len(b))
        r=portfolio(b,atr,s,interval=300,fee_bps=0,fee_per_oz=.31,
                    stop_atr=3,target_r=3,max_hold=36,risk_frac=.0075,min_qty_step_oz=1.0)
        self.assertEqual(len(r['ledger']),1)
        self.assertEqual(r['ledger'][0]['qty'],1)
        self.assertAlmostEqual(r['ledger'][0]['cost'],.31)
    def test_sub_minimum_lot_skips_instead_of_fractional_fill(self):
        b=prices();atr=[20.]*len(b);s=one(NAMES[0],240,len(b))
        z=portfolio(b,atr,s,interval=300,fee_bps=0,fee_per_oz=.31,
                    stop_atr=3,target_r=3,max_hold=36,risk_frac=.0035,min_qty_step_oz=1.0)
        self.assertEqual(z['closed_trades'],0)
        self.assertEqual(z['min_lot_rejections'],1)
    def test_cost_sensitivity_not_traded_profit_claim(self):
        x=run(prices())
        self.assertIn('legacy_stress_14bps',x['cost_scenarios'])
        self.assertIn('fbs_spread_plus_0p75_each_side',x['cost_scenarios'])
        self.assertFalse(x['robust_profit_confirmed'])
    def test_no_claim_for_partial_month(self):
        x=run(prices())
        self.assertFalse(x['cost_scenarios']['fbs_spread_plus_0p15_each_side']['goal_200_full_calendar_month_verified'])
    def test_one_position_only_filled_not_multiple_same_bar(self):
        b=prices();s={k:[0]*len(b) for k in NAMES}
        for k in NAMES:s[k][240]=1
        r=portfolio(b,[2.]*len(b),s,interval=300,min_qty_step_oz=1.,
                    risk_frac=.0075,stop_atr=3.,target_r=3.,max_hold=36)
        self.assertEqual(sum(r['entered_by_type'].values()),1)

if __name__=='__main__':unittest.main()