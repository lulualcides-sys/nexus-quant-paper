"""Synthetic regressions for causal breakout-quality gate, never trading proof."""
import unittest
from unittest.mock import patch
from research.alpha_v6.data import load_month,MARKETS
from research.alpha_v5.strategy import ConfirmedRegime
from research.alpha_v7.strategy import QualityRetest,BOT
from research.alpha_v7.run import MARKETS as V7MARKETS

BASE=1735689600
def data(n=60*245):
    return [dict(time=BASE+60*i,open=100.+0.0002*i,
                 high=100.15+0.0002*i,low=99.85+0.0002*i,
                 close=100.+0.0002*i,volume=10.) for i in range(n)]

class V7Integrity(unittest.TestCase):
    def test_other_bot_unmodified_and_rejected_in_v7(self):
        with self.assertRaises(ValueError):
            QualityRetest("alpha03_vwap_deviation",data(60*212))
        self.assertEqual(BOT,"alpha02_breakout_retest")

    def test_future_append_does_not_change_past_veto(self):
        from research.alpha_v4.data import aggregate
        small=data(60*250)
        large=data(60*252)
        a=QualityRetest(BOT,small)
        b=QualityRetest(BOT,large)
        for i in (2500,2800):
            self.assertEqual(a.filter(i),b.filter(i))

    def test_breakout_volume_filter_can_veto_without_future(self):
        b=data(60*245)
        model=QualityRetest(BOT,b)
        i=2525 # M5, after H4 and H1 warmup
        from unittest.mock import patch
        with patch.object(ConfirmedRegime,"filter",return_value="accepted"):
            value=model.filter(i)
        self.assertIn(value,("unconvincing_breakout","no_volume_confirmation",
                             "failed_retest_close","weak_retest_close_location",
                             "late_chase","accepted"))

    def test_source_expansion_preserves_v6_markets(self):
        self.assertEqual(MARKETS,("SOLUSDT","BNBUSDT","XRPUSDT"))
        self.assertEqual(V7MARKETS,("BNBUSDT","XRPUSDT","ADAUSDT","DOGEUSDT"))
        for symbol in ("ADAUSDT","DOGEUSDT"):
            with patch("research.alpha_v6.data.retrieve",
                       side_effect=RuntimeError("source-unavailable")):
                with self.assertRaisesRegex(RuntimeError,"source-unavailable"):
                    load_month(symbol,"2025-01")

if __name__=="__main__":
    unittest.main()
