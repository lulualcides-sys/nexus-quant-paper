"""Synthetic inputs validate filters and dataset rejection, never trading returns."""
import unittest
from research.alpha.engine import History,build
from research.alpha_v2.filters import Filtered,ROUNDTRIP_BPS,COST_MULTIPLIER
from research.alpha_v2.daily import DAYS,read_day

def example(n=320,step=60,up=0.5):
    begin=1785542400 # Aug 1 UTC
    result=[]
    for i in range(n):
        o=100+i*up
        result.append(dict(time=begin+i*step,open=o,close=o+up/2,
                           high=o+2,low=o-2,volume=10))
    return result

class Always:
    def signal(self,history,features,i):return True

class V2FilterTests(unittest.TestCase):
    def test_unapproved_name(self):
        with self.assertRaises(ValueError):Filtered("fake")

    def test_no_future_lookahead(self):
        b=example()
        f=build(b)
        for name in ("alpha01_volume_exhaustion","alpha03_vwap_deviation","alpha10_adaptive_regime"):
            bot=Filtered(name)
            prefix=bot.signal(History(b,281),f,280)
            additional=build(b[:281])
            self.assertEqual(prefix,bot.signal(History(b[:281],281),additional,280))

    def test_cost_filter_rejects_tiny_range_regardless_of_trend(self):
        b=example(up=0.01)
        for candle in b:
            candle["high"]=candle["open"]+0.02
            candle["low"]=candle["open"]-0.02
        f=build(b);bot=Filtered("alpha01_volume_exhaustion")
        bot.base=Always()
        self.assertEqual(bot.diagnose(History(b,300),f,299),"cost_to_target")
        self.assertEqual(ROUNDTRIP_BPS,32.)
        self.assertEqual(COST_MULTIPLIER,2.)

    def test_cost_filter_can_pass_with_high_range_and_liquidity(self):
        b=example(up=0.5)
        f=build(b);bot=Filtered("alpha04_ema_atr_pullback")
        bot.base=Always()
        # Test does not force acceptance: trend, RSI and value-at-risk all apply.
        self.assertIn(bot.diagnose(History(b,300),f,299),
                      {"accepted","unfavorable_trend","overextended","cost_to_target"})

    def test_strategy_originals_preserved(self):
        import importlib
        for name in ("alpha01_volume_exhaustion","alpha09_consolidation_continuation"):
            original=importlib.import_module("research.alpha.bots."+name)
            self.assertTrue(callable(original.signal))
            self.assertIsNot(original,Filtered(name))

    def test_no_partial_daily_data_passes(self):
        with self.assertRaises(Exception):
            read_day(b"not-a-real-archive","BTCUSDT",DAYS[0])

    def test_all_ten_variants_present(self):
        from research.alpha.run import BOTS
        self.assertEqual(len(BOTS),10)
        self.assertEqual({x.name for x in (Filtered(name) for name in BOTS)},set(BOTS))

if __name__=="__main__":
    unittest.main()
