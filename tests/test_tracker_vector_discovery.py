"""Tests of non-leaking vector reconstruction and held-day public-label probe."""
import unittest
from research.tracker_vector_discovery_43 import (
    derive_implied_vector, vec_features, threshold_with_frozen_budget,
    evaluate_holdout, rank_auc, build_demo
)

class DiscoveryTests(unittest.TestCase):
    def test_symmetric_public_geometry_buy(self):
        d=derive_implied_vector(100000,100150,99850,1)
        self.assertEqual(d["implied_candle_range"],100)
        self.assertEqual(d["implied_high"],100050)
        self.assertEqual(d["implied_low"],99950)
        self.assertEqual(d["gross_imbalance_points"],0)
    def test_symmetric_public_geometry_sell(self):
        d=derive_implied_vector(100000,99850,100150,-1)
        self.assertEqual(d["implied_high"],100050)
        self.assertEqual(d["implied_low"],99950)
        self.assertEqual(d["gross_imbalance_points"],0)
    def test_tick_rounded_public_prices_may_be_unequal_five_points(self):
        d=derive_implied_vector(100000,100155,99850,1)
        self.assertEqual(d["gross_imbalance_points"],5)
        self.assertAlmostEqual(d["implied_candle_range"],101.667,places=3)
    def test_wrong_direction_is_rejected(self):
        with self.assertRaises(ValueError): derive_implied_vector(100000,99850,100150,1)
    def test_only_past_features_no_future_label(self):
        bars={}
        for t in range(540,575):
            bars[t]={"open":100050,"high":100090,"low":100010,"close":100055}
        x=vec_features(bars,565,1)
        bars[566]={"open":120000,"high":300000,"low":1,"close":2}
        self.assertEqual(vec_features(bars,565,1),x)
        self.assertIsNone(vec_features(bars,541,1))
    def test_direction_is_measured_causally(self):
        bars={}
        for t in range(540,571):
            bars[t]={"open":100050,"high":100090,"low":100010,"close":100050}
        bars[560]={"open":100020,"high":100090,"low":99980,"close":100080}
        buy=vec_features(bars,560,1)
        sell=vec_features(bars,560,-1)
        self.assertEqual(buy["body_positive"],1)
        self.assertEqual(sell["body_positive"],0)
        self.assertEqual(buy["has_sweep"],1)
    def test_auc_perfect_vs_reverse_and_ties(self):
        self.assertEqual(rank_auc([(2,1),(3,1),(0,0),(1,0)]),1.)
        self.assertEqual(rank_auc([(0,1),(1,1),(2,0),(3,0)]),0.)
        self.assertEqual(rank_auc([(1,1),(1,0)]),.5)
    def test_threshold_uses_train_only_not_test_label_frequency(self):
        tr=[
            {"features":{"f":10},"label":1},
            {"features":{"f":8},"label":0},
            {"features":{"f":2},"label":0},
            {"features":{"f":1},"label":0},
        ]
        te=[{"features":{"f":9},"label":0},
            {"features":{"f":7},"label":1},
            {"features":{"f":1},"label":1},
            {"features":{"f":0},"label":0}]
        a=evaluate_holdout(tr,te,"f",1)
        self.assertEqual(a["threshold_from_training_only"],10)
        self.assertEqual(a["predicted"],0)
        te[0]["label"]=1
        b=evaluate_holdout(tr,te,"f",1)
        self.assertEqual(b["threshold_from_training_only"],10)
        self.assertEqual(b["predicted"],0)
    def test_promotional_unmarked_are_not_claimed_true_negatives(self):
        rows=[{"features":{"f":3},"label":1},
              {"features":{"f":1},"label":0}]
        a=evaluate_holdout(rows,rows,"f",1)
        self.assertIn("false_positive_marketing_unlabeled",a)
        self.assertNotIn("false_positive_real_non_signal",a)

if __name__=="__main__":
    unittest.main()
