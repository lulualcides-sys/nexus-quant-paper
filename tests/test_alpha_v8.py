"""No-lookahead, data allowlist and unchanged V5 exits; synthetic tests only."""
import unittest
from unittest.mock import patch
from research.alpha_v8.strategy import StructureRetest
from research.alpha_v8.run import MARKETS
from research.alpha_v5.strategy import ConfirmedRegime
from research.alpha_v6.data import load_month
from research.alpha_v7.strategy import BREAKOUT_MIN_ATR,RETEST_MIN_CLOSE_RANGE_FRACTION

START=1735689600
def synthetic(n=60*266):
    return [dict(time=START+i*60,open=100+i*.0001,
                 close=100+i*.0001,high=100.2+i*.0001,
                 low=99.8+i*.0001,volume=10) for i in range(n)]

class V8Tests(unittest.TestCase):
    def test_market_allowlist_only(self):
        self.assertEqual(MARKETS,("AVAXUSDT","LINKUSDT","LTCUSDT"))
        for symbol in MARKETS:
            with patch("research.alpha_v6.data.retrieve",
                       side_effect=RuntimeError("offline-test")):
                with self.assertRaisesRegex(RuntimeError,"offline-test"):
                    load_month(symbol,"2025-01")

    def test_thresholds_unchanged_from_prior_hypothesis(self):
        self.assertEqual((BREAKOUT_MIN_ATR,RETEST_MIN_CLOSE_RANGE_FRACTION),(.20,.60))
        with self.assertRaises(ValueError):
            StructureRetest("alpha03_vwap_deviation",synthetic())

    def test_future_candles_unavailable_for_same_signal(self):
        rows=synthetic()
        a=StructureRetest("alpha02_breakout_retest",rows[:-60])
        b=StructureRetest("alpha02_breakout_retest",rows)
        for i in (2900,3050,3150):
            self.assertEqual(a.filter(i),b.filter(i))

    def test_preserves_same_model_exit_and_risk_logic(self):
        rows=synthetic()
        a=StructureRetest("alpha02_breakout_retest",rows)
        b=ConfirmedRegime("alpha02_breakout_retest",rows)
        self.assertIs(a.original,b.original)
        for i in (2920,3100):
            self.assertEqual(a.h1_exiting(i),b.h1_exiting(i))

if __name__=="__main__":
    unittest.main()
