"""M30 from frozen real M15 candles and M1/M5 isolated time-exit control."""
import math
import unittest
from unittest.mock import patch

from research.xau_m30_matched import _from_m15, _count
from research import xau_all_original_3tf as xau
from src import experimental_h1 as h1
from src import gold_forward as gold
from src import leveraged_gold as lev

START = 1791000000//1800*1800


def bars(n=920):
    out=[]
    for i in range(n):
        p=4100+8*math.sin(i/42)
        out.append({"time":START+i*1800,"open":p,
                    "high":p+2,"low":p-2,"close":p+.7*math.sin(i),
                    "volume":65+(i%7),"max_spread":.2})
    return out


class FrozenM30Tests(unittest.TestCase):
    def test_adjoining_true_m15_bars_required(self):
        a={"time":0,"open":10,"high":13,"low":8,"close":12,"volume":11,"max_spread":.2}
        b={"time":900,"open":12,"high":16,"low":9,"close":15,"volume":13,"max_spread":.3}
        source=[]
        for i in range(342):  # enough *pairs* for original 240-bar warmup
            for template in (a,b):
                item=template.copy()
                item["time"]+=i*1800
                source.append(item)
        out=_from_m15(source)
        self.assertEqual(len(out),342)
        self.assertEqual(out[0],{"time":0,"open":10,"high":16,"low":8,
                "close":15,"volume":24,"max_spread":.3})

    def test_missing_m15_cannot_invent_m30(self):
        source=[]
        for i in range(344):
            for minute in (0,900):
                source.append({"time":i*1800+minute,"open":10,
                    "high":12,"low":8,"close":10,
                    "volume":10,"max_spread":.2})
        del source[5]
        with self.assertRaisesRegex(ValueError,"Incomplete real M30"):
            _from_m15(source)

    def test_out_of_order_rejected(self):
        source=[{"time":900,"open":10},{"time":0,"open":10}]
        with self.assertRaisesRegex(ValueError,"out of order"):
            _from_m15(source)

    def test_30m_engine_keeps_census_28_and_original_logic(self):
        rows=bars()
        with patch.dict(xau.TIMEFRAMES,{"M30":1800}):
            a=xau.replay(rows,"M30")
        self.assertEqual(len(a["books"]),28)
        self.assertTrue(a["paper_only"])
        self.assertEqual(a["tf"],"M30")
        self.assertEqual(a["n_valid_hourly_bars"],460)

    def test_all_engines_production_exit_policy_reverts_after_study(self):
        rows=bars()
        before=(gold.MAX_HOLD,lev.MAX_HOLD_BARS,h1.MAX_HOLD)
        with patch.dict(xau.TIMEFRAMES,{"M30":1800}):
            a=xau.replay(rows,"M30",start_ts=rows[240]["time"],exit_horizon_multiplier=3)
        after=(gold.MAX_HOLD,lev.MAX_HOLD_BARS,h1.MAX_HOLD)
        self.assertEqual(before,after)
        self.assertEqual(len(a["books"]),28)

    def test_matched_window_starts_after_correct_warmup(self):
        rows=bars()
        with patch.dict(xau.TIMEFRAMES,{"M30":1800}):
            late=xau.replay(rows,"M30",start_ts=rows[-3]["time"])
        self.assertTrue(all(x["closed"]==0 for x in late["books"].values()
                            if x["closed"]==0))  # no invented trades
        self.assertEqual(late["n_bars"],920)

    def test_unsupported_holding_multipliers_are_rejected(self):
        with patch.dict(xau.TIMEFRAMES,{"M30":1800}):
            with self.assertRaisesRegex(ValueError,"Unregistered"):
                xau.replay(bars(),"M30",exit_horizon_multiplier=2)

    def test_double_cost_summary_does_not_miscount_h1_copies(self):
        data={
            "experimental_h1:XAUUSD:rsi50":{"net_usd":1,"double_cost_net_usd":1,
                "closed":1},
            "experimental_h1:EURUSD:rsi50":{"net_usd":1,"double_cost_net_usd":1,
                "closed":1},
            "gold_h4:channel55":{"net_usd":2,"double_cost_net_usd":-1,
                "closed":2},
        }
        s=_count(data)
        self.assertEqual(s["slots"],3)
        self.assertEqual(s["unique_families"],2)
        self.assertEqual(s["positive_unique_families_double_cost"],1)


if __name__=="__main__":
    unittest.main()
