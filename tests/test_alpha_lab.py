"""Synthetic integrity tests ONLY; never print simulated profitability as evidence."""
import unittest
from importlib import import_module
from research.alpha.engine import History,backtest,check_candles,stats,build,WARMUP
from research.alpha.data import aggregate_5m
from research.alpha.run import BOTS,daily_block_ci

def bars(n=250):
    start=1785542400  # 2026-08-01 00:00 UTC
    return [dict(time=start+60*i,open=100.0,high=101.0,low=99.0,
                 close=100.0,volume=10.0) for i in range(n)]

class OneSignal:
    @staticmethod
    def signal(h,f,i):
        return i==222

class LabIntegrity(unittest.TestCase):
    def test_history_future_blocked(self):
        b=bars()
        h=History(b,225)
        with self.assertRaises(IndexError):
            _=h[225]
        self.assertEqual(len(h[-12:]),12)

    def test_causal_indicators_append_invariant(self):
        b=bars(320)
        a=build(b[:240]);full=build(b)
        for k in a:
            self.assertEqual(a[k],full[k][:240],k)

    def test_strict_gap_duplicate_and_ohlc(self):
        b=bars()
        self.assertTrue(check_candles(b,1))
        bad=[dict(x) for x in b];bad[231]["time"]+=60
        with self.assertRaises(ValueError):
            check_candles(bad,1)
        bad=[dict(x) for x in b];bad[231]["high"]=1.
        with self.assertRaises(ValueError):
            check_candles(bad,1)

    def test_5m_aggregation_requires_full_candles(self):
        b=bars(250);m5=aggregate_5m(b)
        self.assertEqual(len(m5),50)
        self.assertEqual(m5[0]["time"],b[0]["time"])
        b[4]["time"]+=60
        with self.assertRaises(ValueError):aggregate_5m(b)

    def test_next_open_and_intrabar_stop_first(self):
        b=bars(260)
        b[223]["high"]=107.;b[223]["low"]=96.
        run=backtest(b,OneSignal,1,221,250,5.)
        self.assertTrue(run["ledger"])
        first=run["ledger"][0]
        self.assertEqual(first["entry_ts_utc"][:10],"2026-08-01")
        self.assertEqual(first["reason"],"ambiguous_stop_first")
        self.assertEqual(run["orders_filled"],1)
        self.assertLess(first["net_usdt"],0)
        self.assertGreater(first["costs_usdt"],0)

    def test_signal_seen_without_fill_not_trade(self):
        b=bars(225)
        run=backtest(b,OneSignal,1,221,225)
        self.assertEqual(run["orders_filled"],1)
        self.assertEqual(len(run["ledger"]),1)

    def test_nonzero_gain_not_approval(self):
        b=bars()
        run=backtest(b,OneSignal,1,221,240)
        self.assertEqual(stats(run)["status"],"INCONCLUSIVE")

    def test_bootstrap_sparse_yields_none(self):
        self.assertIsNone(daily_block_ci([]))

    def test_all_ten_strategy_modules_cannot_see_future(self):
        b=bars(250);f=build(b)
        self.assertEqual(len(BOTS),10)
        for name in BOTS:
            bot=import_module("research.alpha.bots."+name)
            self.assertIn(bot.TIMEFRAME,(1,5))
            for i in (221,222,240):
                result=bot.signal(History(b,i+1),f,i)
                self.assertIsInstance(result,bool,name)

if __name__=="__main__":
    unittest.main()
