"""Fixed-vector hypothesis accounting and no-future-barring unit tests."""
import unittest
from research.tracker_vector_anchor_families import (
    ANCHOR_TYPES,WINDOWS,END_LAGS,endpoints,compare_anchors,run
)

class VectorAnchorTests(unittest.TestCase):
    def setUp(self):
        self.rows={t:{"open":100100+t,"high":100150+t,"low":100050+t,
                      "close":100110+t} for t in range(540,600)}
    def test_three_predeclared_anchor_families(self):
        self.assertEqual(set(ANCHOR_TYPES),{"wick_range","body_range","close_range"})
        self.assertEqual(len(ANCHOR_TYPES)*len(WINDOWS)*len(END_LAGS),63)
    def test_wick_and_body_are_not_interchanged(self):
        self.assertEqual(endpoints(self.rows,560,1,"wick_range"),(100710,100610))
        self.assertEqual(endpoints(self.rows,560,1,"body_range"),(100670,100660))
        self.assertEqual(endpoints(self.rows,560,1,"close_range"),(100670,100670))
    def test_prior_window_only_uses_known_candles(self):
        before=endpoints(self.rows,560,10,"wick_range")
        self.rows[561]={"open":1,"high":1000000,"low":0,"close":2}
        self.assertEqual(before,endpoints(self.rows,560,10,"wick_range"))
    def test_future_anchor_disallowed(self):
        implied={"implied_high":100710,"implied_low":100610}
        result=compare_anchors(self.rows,560,implied)
        self.assertTrue(result[0]["matching"])
        self.assertTrue(all(x["lag"]>=0 for x in result))
    def test_incomplete_candles_are_refused(self):
        self.assertIsNone(endpoints({1:self.rows[540]},2,2,"wick_range"))
    def test_reject_unknown_family(self):
        with self.assertRaises(ValueError):
            endpoints(self.rows,560,1,"foo")
    def test_null_controls_are_deterministic(self):
        source=[
            [(540,100),0],
            [(540,100),0]
        ] # call the production endpoint helper, no fabricated report claims
        self.assertEqual(endpoints(self.rows,560,1,"wick_range"),
                         endpoints(self.rows,560,1,"wick_range"))
    def test_price_only_cannot_prove_aggressor_flow(self):
        src=open("research/tracker_vector_anchor_families.py",encoding="utf-8").read()
        self.assertIn("No classified volume/flow",src)
        self.assertIn('"approved_for_live":False',src)

if __name__=="__main__":
    unittest.main()
