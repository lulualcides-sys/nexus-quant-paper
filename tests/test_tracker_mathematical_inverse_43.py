"""Vector inverse / one-WIN feasibility tests: no vendor secrets or broker data."""
import math
import unittest

from research.tracker_mathematical_inverse_43 import (
    reconstruct_levels,one_contract_economics,wilson_interval,
    mathematical_nonidentifiability,BANKROLL_BRL,RISK_CAP_BRL
)

class TrackerMathInverseTests(unittest.TestCase):
    def test_buy_symmetry_and_exact_inverse_endpoints(self):
        m=reconstruct_levels(100000,100150,99850,1)
        self.assertEqual(m["inferred_range_points"],100)
        self.assertEqual(m["advertised_center_from_extremes"],100000)
        self.assertEqual(m["inferred_high"],100050)
        self.assertEqual(m["inferred_low"],99950)
        self.assertEqual(m["gross_payoff_imbalance_pts"],0)
        self.assertTrue(m["symmetric_under_level_rounding"])

    def test_sell_symmetry_same_endpoints(self):
        m=reconstruct_levels(100000,99850,100150,-1)
        self.assertEqual(m["inferred_range_points"],100)
        self.assertEqual(m["inferred_high"],100050)
        self.assertEqual(m["inferred_low"],99950)
        self.assertEqual(m["gross_payoff_imbalance_pts"],0)

    def test_tick_level_rounding_five_point_deviation_allowed(self):
        m=reconstruct_levels(100000,100155,99850,1)
        self.assertEqual(m["midpoint_error_twice_points"],-5)
        self.assertTrue(m["approx_equal_distance_5pt"])

    def test_wrong_direction_or_offgrid_price_rejected(self):
        for params in ((100000,99850,100150,1),(100002,100150,99850,1),
                       (100000,100150,99850,0)):
            with self.assertRaises(ValueError):reconstruct_levels(*params)

    def test_gross_equal_reward_risk_but_net_not_equal(self):
        econ=one_contract_economics(100000,100150,99850,1,6.)
        self.assertEqual(econ["gross_win_brl"],30)
        self.assertEqual(econ["gross_loss_brl"],30)
        self.assertEqual(econ["net_win_brl"],24)
        self.assertEqual(econ["net_loss_brl"],36)
        self.assertAlmostEqual(econ["minimum_break_even_win_rate_for_this_vector"],.6)
        self.assertFalse(econ["planned_loss_within_budget"])
        self.assertEqual(econ["available_contracts_under_1pct"],0)

    def test_one_WIN_smaller_vector_may_fit_risk_but_need_75percent(self):
        econ=one_contract_economics(100000,100060,99940,1,6.)
        self.assertEqual(econ["gross_win_brl"],12)
        self.assertEqual(econ["net_loss_brl"],18)
        self.assertEqual(econ["net_win_brl"],6)
        self.assertTrue(econ["planned_loss_within_budget"])
        self.assertAlmostEqual(econ["minimum_break_even_win_rate_for_this_vector"],.75)

    def test_lower_fee_widens_feasible_stop_distance_without_proving_edge(self):
        expensive=one_contract_economics(100000,100085,99915,1,6.)
        cheaper=one_contract_economics(100000,100085,99915,1,3.4)
        self.assertFalse(expensive["planned_loss_within_budget"])
        self.assertFalse(cheaper["planned_loss_within_budget"])
        limit=one_contract_economics(100000,100080,99920,1,3.4)
        self.assertTrue(limit["planned_loss_within_budget"])

    def test_fee_cannot_be_negative(self):
        with self.assertRaises(ValueError):
            one_contract_economics(100000,100060,99940,1,-.01)

    def test_unverified_claimed_win_rate_interval_not_statistical_proof(self):
        low,high=wilson_interval(36,43)
        self.assertTrue(0.69<low<0.77)
        self.assertTrue(0.9<high<0.96)
        with self.assertRaises(ValueError):wilson_interval(44,43)

    def test_prove_nonidentifiability_from_positive_examples_only(self):
        fake=[(i,0,560+i,"c",100000,100060,99940,"w",570+i,60)
              for i in range(1,44)]
        candles=[{k:{"open":100000,"high":100100,"low":99900,"close":100010}
                  for k in range(540,660)}, {k:{"open":100000,"high":100100,
                  "low":99900,"close":100010} for k in range(540,660)}]
        proof=mathematical_nonidentifiability(fake,candles)
        self.assertTrue(proof["model_A_matches_all_published_positives"])
        self.assertTrue(proof["model_B_matches_all_published_positives"])
        self.assertNotEqual(proof["model_A_emits_extra_unlabeled_tuple"],
                            proof["model_B_emits_extra_unlabeled_tuple"])
        self.assertGreater(proof["minute_direction_possibilities"],43)

if __name__=="__main__":
    unittest.main()
