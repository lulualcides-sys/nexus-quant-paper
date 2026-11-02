"""Deterministic research-only tests: synthetic prices, zero outside requests."""
from copy import deepcopy
from datetime import datetime, timezone
from math import sin
import unittest

from research.entry_frequency_lab import (
    BASELINES, MARKET, RULES, TRAIN_START, TRAIN_END, TEST_END,
    candidate_signal, compare, markdown,
)
from research.screen_v2 import evaluate, sign
from src.strategies import make_indicators

def rows():
    # Include a warmup before the pre-registered training window.
    # These are synthetic candles, NOT evidence of financial performance.
    pre = [TRAIN_START - (280-i)*14400 for i in range(280)]
    train = [TRAIN_START + i*14400 for i in range(660)]
    review = [TRAIN_END + i*14400 for i in range(950)]
    result = []
    for i, ts in enumerate(pre+train+review):
        v = 2500 + i*.06 + 9*sin(i/9)
        result.append({"time": ts, "open": v-0.3, "high": v+1.2,
                       "low": v-1.2, "close": v+0.4})
    return result


class EntryFrequencyLabTests(unittest.TestCase):
    def test_reference_rules_equal_existing_backtester(self):
        bars = rows()
        indicators = make_indicators(bars)
        for rule in ("channel20","momentum40","momentum100"):
            before = evaluate(bars,indicators,rule,MARKET,TRAIN_END,TEST_END)
            after = evaluate(bars,indicators,rule,MARKET,TRAIN_END,TEST_END,
                             signal_function=candidate_signal)
            self.assertEqual(before,after)
            self.assertEqual(candidate_signal(rule,bars,indicators,500),
                             sign(rule,bars,indicators,500))

    def test_reproducible_comparison_and_no_promotion(self):
        bars = rows()
        before = deepcopy(bars)
        report = compare(bars)
        self.assertEqual(bars,before)
        self.assertEqual(set(report["comparisons"]),set(RULES))
        self.assertEqual(set(BASELINES),{"channel35_lab","momentum60_lab"})
        self.assertTrue(report["historical_period_already_inspected"])
        self.assertFalse(report["auto_promote"])
        self.assertEqual(report["h4_train_bars"],660)
        self.assertEqual(report["h4_revisited_bars"],950)
        self.assertIn("NO PROMOTION",report["decision"])
        self.assertIn("NOT fresh out-of-sample",markdown(report))
        for name, info in report["comparisons"].items():
            self.assertGreaterEqual(info["signals_review"],0)
            self.assertGreaterEqual(info["review_revisited_not_unseen"]["trades"],0)
            if name in BASELINES:
                self.assertEqual(info["status"],"candidate_unvalidated")
                self.assertIn("vs_reference",info)

    def test_future_bars_do_not_change_prior_signals(self):
        bars = rows()
        shorter = bars[:-25]
        i = 700
        old = candidate_signal("momentum60_lab",shorter,make_indicators(shorter),i)
        new = candidate_signal("momentum60_lab",bars,make_indicators(bars),i)
        self.assertEqual(old,new)
        self.assertEqual(old,0 if old==0 else old)

    def test_unknown_strategy_rejected(self):
        bars=rows()
        with self.assertRaises(KeyError):
            candidate_signal("made_up",bars,make_indicators(bars),500)

    def test_missing_window_or_invalid_prices_fail_closed(self):
        bars=rows()
        with self.assertRaisesRegex(ValueError,"Insufficient"):
            compare(bars[:800])
        broken=deepcopy(bars)
        broken[15]["low"] = -1
        with self.assertRaisesRegex(ValueError,"Invalid OHLC"):
            compare(broken)

    def test_research_cannot_turn_into_broker_execution(self):
        result=compare(rows())
        self.assertTrue(result["paper_only"])
        self.assertTrue(result["no_live_orders"])
        self.assertNotIn("api_key",str(result).lower())


if __name__=="__main__":
    unittest.main()
