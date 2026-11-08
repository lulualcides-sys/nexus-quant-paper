"""Synthetic regressions: protect-next-bar, conservative stop-first and carry.

No synthetic win is a claim about actual Binance trading performance.
"""
import unittest
from unittest.mock import patch
from research.alpha_v6.data import MARKETS,MONTHS,load_month
from research.alpha_v6.engine import replay,PROTECT_ACTIVATE_ATR,TRAIL_FROM_CLOSE_ATR
from research.alpha_v6.run import _monthly_breakdown,BOT

START=1737590400 # 2025-01-23 UTC; 5m aligned
WARM=(210+1)*12

def sample(n=3600):
    return [dict(time=START+300*i,open=100.,high=100.5,
                 low=99.5,close=100.,volume=10.) for i in range(n)]

class OneEntry:
    minutes=5
    def __init__(self,bars):self.bars=bars;self.hf={"atr":[1.]}
    def signal(self,i):return i==WARM-1
    def last_closed_h1(self,i):return 0
    def h1_exiting(self,i):return False

class V6Safety(unittest.TestCase):
    def test_prices_and_broker_lookups_remain_disallowed(self):
        self.assertEqual(BOT,"alpha02_breakout_retest")
        self.assertEqual(MARKETS,("SOLUSDT","BNBUSDT","XRPUSDT"))
        self.assertEqual((PROTECT_ACTIVATE_ATR,TRAIL_FROM_CLOSE_ATR),(2.,2.))
        self.assertEqual(len(MONTHS),22)
        with patch("research.alpha_v6.data.retrieve",
                   side_effect=RuntimeError("network_isolated")):
            with self.assertRaisesRegex(RuntimeError,"network_isolated"):
                load_month("BNBUSDT","2025-01")
            with self.assertRaises(ValueError):
                load_month("WINFUT","2025-01")

    def test_trail_only_after_favorable_candle_closes(self):
        a=sample()
        # First entry at WARM. At WARM+1 price closes +3 ATR.
        a[WARM+1].update(open=100.,high=103.4,low=99.5,close=103.)
        # Only NEXT candle can hit the raised trailing stop around 101.
        a[WARM+2].update(open=103.,high=103.2,low=100.6,close=101.5)
        old=replay(OneEntry(a),5.,protect=False)
        new=replay(OneEntry(a),5.,protect=True)
        self.assertEqual(new["orders_filled"],old["orders_filled"])
        self.assertEqual(new["protection_activations"],1)
        self.assertEqual(new["ledger"][0]["reason"],"protected_stop")
        self.assertGreater(new["ledger"][0]["net_usdt"],0)
        self.assertNotEqual(new["ledger"][0]["exit_ts_utc"],old["ledger"][0]["exit_ts_utc"])

    def test_stop_first_on_colliding_candle_and_risk_cap(self):
        a=sample()
        a[WARM].update(open=100.,high=105.,low=97.,close=100.)
        x=replay(OneEntry(a),5.,True)
        self.assertEqual(len(x["ledger"]),1)
        self.assertEqual(x["ledger"][0]["reason"],"ambiguous_stop_first")
        self.assertLess(x["ledger"][0]["net_usdt"],0)
        self.assertLessEqual(-x["ledger"][0]["net_usdt"],37.52)

    def test_position_and_cash_carry_across_real_month_boundary(self):
        a=sample()
        # First entry 2025-01-31; closes in February solely due to 72h limit.
        x=replay(OneEntry(a),5.,False)
        self.assertGreaterEqual(len(x["ledger"]),1)
        row=x["ledger"][0]
        self.assertEqual(row["entry_ts_utc"][:7],"2025-01")
        self.assertEqual(row["exit_ts_utc"][:7],"2025-02")
        month_summary=_monthly_breakdown(x["ledger"])
        self.assertEqual(month_summary["2025-02"]["closed"],1)
        self.assertEqual(month_summary["2025-01"]["closed"],0)

    def test_no_end_of_window_fake_close(self):
        a=sample(WARM+60)
        x=replay(OneEntry(a),5.,False)
        self.assertEqual(len(x["ledger"]),0)
        self.assertTrue(x["open_at_end"])
        self.assertIsNotNone(x["marked_open_net_usdt"])

    def test_model_cannot_claim_zero_trade_profit(self):
        a=sample(WARM+20)
        x=replay(OneEntry(a),5.,False)
        from research.alpha.engine import stats
        self.assertIsNone(stats(x)["net_usdt"])

if __name__=="__main__":
    unittest.main()
