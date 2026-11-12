"""Unit tests for Greenhouse public gallery *price-only* forensic probes.

No source code from Greenhouse licensed indicator is used here.
Tests do not prove any financial edge.
"""
import unittest
from research.greenhouse_deeper_signal_forensics import features
from research.greenhouse_public_gallery_decode import geom_for_candle

def sample():
    bars={}
    for minute in range(540,561):
        bars[minute]={"open":100050,"high":100100,"low":100000,"close":100050}
    return bars

class PublicForensicsTests(unittest.TestCase):
    def test_buy_reversal_price_only_features_are_not_original_tracker(self):
        bars=sample()
        bars[560]={"open":100025,"high":100080,"low":99970,"close":100045}
        result=features(bars,560,"c")
        self.assertTrue(result["full_price_sweep_hypothesis"])
        self.assertTrue(result["swept_20bar_extreme"])
        self.assertTrue(result["wick_35_pct"])

    def test_buy_price_extreme_without_wick_does_not_pass(self):
        bars=sample()
        bars[560]={"open":99985,"high":100090,"low":99980,"close":100050}
        result=features(bars,560,"c")
        self.assertTrue(result["swept_20bar_extreme"])
        self.assertFalse(result["full_price_sweep_hypothesis"])

    def test_sell_reversal_mirrors_buy(self):
        bars=sample()
        bars[560]={"open":100075,"high":100140,"low":100010,"close":100045}
        result=features(bars,560,"v")
        self.assertTrue(result["full_price_sweep_hypothesis"])

    def test_trades_at_start_with_less_than_20_bars_are_unscorable(self):
        self.assertIsNone(features(sample(),545,"c"))
        self.assertIsNone(features(sample(),560+10,"c"))

    def test_future_prices_never_change_closed_bar_features(self):
        bars=sample()
        bars[560]={"open":100020,"high":100090,"low":99985,"close":100050}
        original=features(bars,560,"c")
        bars[561]={"open":100050,"high":200000,"low":100000,"close":150000}
        self.assertEqual(features(bars,560,"c"),original)

    def test_public_fibonacci_mirrored_geometry(self):
        bar={"open":100000,"high":100100,"low":99900,"close":100000}
        self.assertEqual(geom_for_candle(bar,"c"),(100000,100300,99700))
        self.assertEqual(geom_for_candle(bar,"v"),(100000,99700,100300))

if __name__=="__main__":
    unittest.main()
