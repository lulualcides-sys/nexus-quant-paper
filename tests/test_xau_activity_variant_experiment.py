"""Tests for frozen hypothesis policy, not profitable-performance claims."""
import unittest
from research.xau_activity_variant_experiment import (
    VARIANTS, TRAIN_DATES, EVAL_DATES, ALL_DATES, run_one
)
from research.xau_quote_tracker_reference import QuotePolicy


class VariantsTests(unittest.TestCase):
    def test_disjoint_chronological_windows(self):
        self.assertFalse(set(TRAIN_DATES)&set(EVAL_DATES))
        self.assertLess(max(TRAIN_DATES),min(EVAL_DATES))
        self.assertEqual(len(ALL_DATES),6)

    def test_baseline_unchanged(self):
        self.assertEqual(VARIANTS["baseline"],{})

    def test_variants_are_valid_and_moderately_relaxed(self):
        from dataclasses import replace
        for name,settings in VARIANTS.items():
            policy=replace(QuotePolicy(),**settings)
            policy.validate()
            self.assertGreaterEqual(policy.activity_factor,1.)
            self.assertGreaterEqual(policy.min_wick_fraction,.20)
            self.assertGreaterEqual(policy.close_location,.55)

    def test_unlisted_timeframe_or_variant_rejected(self):
        with self.assertRaisesRegex(ValueError,"Unknown"):
            run_one("not-found.csv","M15","baseline")
        with self.assertRaisesRegex(ValueError,"Unknown"):
            run_one("not-found.csv","M1","optimized_after_test")


if __name__=="__main__": unittest.main()
