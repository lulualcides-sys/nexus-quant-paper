"""Deterministic synthetic technical tests; NEVER financial validation."""
import unittest
from unittest.mock import patch
from research.alpha_v4.strategy import MultiTimeframe,H1_WARMUP
from research.alpha_v4.data import SYMBOLS,MONTHS,aggregate,month
from research.alpha_v4.engine import backtest
from research.alpha.run import BOTS

START=1790812800 # UTC 2026-10-01 00:00 (only synthetic tests)
def bars(n):
    return [dict(time=START+60*i,open=100.+0.001*i,
                 high=100.1+0.001*i,low=99.9+0.001*i,
                 close=100.+0.001*i,volume=100.) for i in range(n)]

class Proxy:
    minutes=5
    def __init__(self):
        self.bars=aggregate(bars(60*215),5)
        self.hf={"atr":[1.]*215}
    def signal(self,i):
        return i==(H1_WARMUP+1)*12
    def last_closed_h1(self,i):
        return (i+1)//12-1
    def h1_exiting(self,i):
        return False

class V4Causality(unittest.TestCase):
    def test_h1_index_cannot_read_partial_hour(self):
        h=MultiTimeframe(BOTS[0],bars(60*212))
        self.assertEqual(h.last_closed_h1(58),-1)
        self.assertEqual(h.last_closed_h1(59),0)
        self.assertEqual(h.last_closed_h1(60),0)
        m=MultiTimeframe("alpha02_breakout_retest",bars(60*212))
        self.assertEqual(m.last_closed_h1(10),-1)
        self.assertEqual(m.last_closed_h1(11),0)
        self.assertEqual(m.last_closed_h1(12),0)

    def test_gate_is_stable_when_future_is_appended(self):
        allbars=bars(60*213)
        prefix=allbars[:60*212]
        a=MultiTimeframe("alpha04_ema_atr_pullback",prefix)
        b=MultiTimeframe("alpha04_ema_atr_pullback",allbars)
        for i in (H1_WARMUP*12+11,H1_WARMUP*12+12):
            self.assertEqual(a.filter(i),b.filter(i))
        self.assertEqual(a.filter(H1_WARMUP*12+11),b.filter(H1_WARMUP*12+11))

    def test_next_open_not_same_bar(self):
        model=Proxy()
        x=backtest(model,5.)
        self.assertEqual(x["orders_filled"],1)
        self.assertEqual(x["signals_seen"],1)
        self.assertTrue(x["open_end"])
        self.assertFalse(x["ledger"])

    def test_costs_and_stop_risk_bounded_without_gap(self):
        model=Proxy()
        idx=(H1_WARMUP+1)*12+1
        model.bars[idx]["low"]=95.
        x=backtest(model,10.)
        self.assertEqual(x["orders_filled"],1)
        self.assertEqual(len(x["ledger"]),1)
        t=x["ledger"][0]
        self.assertLess(t["net_usdt"],0.)
        self.assertGreater(t["costs_usdt"],0.)
        self.assertLessEqual(-t["net_usdt"],5000*.0075+.03)

    def test_downloading_invalid_market_blocked_without_network(self):
        with patch("research.alpha_v4.data.retrieve",side_effect=AssertionError("network")):
            with self.assertRaises(ValueError):month("WINFUT",MONTHS[0])

    def test_M5_aggregation_is_exact(self):
        b=bars(300)
        self.assertEqual(len(aggregate(b,5)),60)
        b[8]["time"]+=60
        with self.assertRaises(ValueError):aggregate(b,5)

    def test_aggregate_does_not_fabricate_zero_no_trade(self):
        from research.alpha_v4.run import _aggregate_net
        self.assertIsNone(_aggregate_net([dict(trades=0,net_usdt=None)]))
        self.assertEqual(_aggregate_net([dict(trades=0,net_usdt=None),
                                         dict(trades=2,net_usdt=-12.35)]),-12.35)

    def test_scope(self):
        self.assertEqual(SYMBOLS,("BTCUSDT","ETHUSDT","SOLUSDT"))
        self.assertEqual(len(BOTS),10)

if __name__=="__main__":
    unittest.main()
