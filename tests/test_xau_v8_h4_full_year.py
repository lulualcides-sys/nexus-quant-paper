import unittest
from datetime import datetime,timezone
from research import xau_v8_h4_full_year as x
from research.xau_v7_preserved_h4_bidask import RULES


class V8Tests(unittest.TestCase):
    def test_year_and_warmup_are_disjoint(self):
        self.assertEqual(len(x.CALENDAR),18)
        self.assertEqual(x.CALENDAR[0],(2025,4))
        self.assertEqual(x.CALENDAR[-1],(2026,9))
        self.assertEqual(datetime.fromtimestamp(x.EVAL_FIRST,timezone.utc).isoformat(),'2025-10-01T00:00:00+00:00')
    def test_exact_four_quarters(self):
        self.assertEqual([q[0] for q in x.QUARTERS],['2025-Q4','2026-Q1','2026-Q2','2026-Q3'])
        self.assertEqual(int(x.QUARTERS[0][1].timestamp()),x.EVAL_FIRST)
        self.assertEqual(int(x.QUARTERS[-1][2].timestamp()),x.EVAL_LAST)
    def test_frozen_h4_rules_and_no_new_filters(self):
        self.assertEqual(RULES,('channel20','channel55','momentum100','rsi_trend','pullback20'))
        self.assertEqual(x.SLIPPAGES,(.15,.75))
        self.assertEqual(x.CAPITALS,(5000.,10000.,20000.))
    def test_read_only_no_orders(self):
        self.assertNotIn('send_order',x.run.__code__.co_names)
        self.assertNotIn('create_order',x.load_h4.__code__.co_names)

if __name__=='__main__':unittest.main()