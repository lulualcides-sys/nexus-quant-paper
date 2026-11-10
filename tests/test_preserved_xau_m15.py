"""Ensure the archived research snapshot never turns into a live bot deployment."""
import json
import unittest
from pathlib import Path

FILE = Path("research/preserved/xau_m15_positive_20261110.json")


class PreservedGoldM15Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(FILE.read_text(encoding="utf-8"))

    def test_all_positive_slot_ids_and_census(self):
        d=self.data
        rows=d["slots"]
        self.assertEqual(len(rows),d["positive_slots"])
        self.assertEqual(len(rows),20)
        self.assertEqual(len({x["id"] for x in rows}),20)
        self.assertEqual(len({x["original_rule_id"] for x in rows}),8)
        self.assertEqual(d["distinct_rules"],8)
        self.assertTrue(all(x["net_usd"]>0 and x["timeframe"]=="M15" for x in rows))

    def test_all_four_robust_unique_rules_preserved(self):
        d=self.data
        independent=[r for r in d["slots"] if r["independent_signal_family"]]
        self.assertEqual(len(independent),8)
        winners={r["original_rule_id"] for r in independent if r["positive_under_double_cost"]}
        self.assertEqual(winners,{
            "gold_h4:channel55","leveraged_h4:lev_channel55",
            "experimental_h1:XAUUSD:ema20_retest",
            "experimental_h1:XAUUSD:rsi50"})
        self.assertEqual(d["distinct_rules_positive_double_cost"],4)

    def test_no_live_promotion_and_provenance(self):
        d=self.data
        self.assertTrue(d["paper_only"] and d["do_not_change_production"])
        self.assertFalse(d["auto_trade_allowed"])
        self.assertEqual(d["valid_historical_sessions"],24)
        self.assertEqual(len(d["source_json_sha256"]),64)
        self.assertIn("actions/runs/42847239203",d["source_workflow"])
        self.assertEqual(len([r for r in d["slots"] if r["id"].startswith("experimental_h1:")]),15)
        self.assertTrue(all(r["market_for_this_snapshot"]=="XAUUSD" for r in d["slots"]))


if __name__=="__main__":
    unittest.main()
