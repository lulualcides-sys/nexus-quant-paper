"""Guard all historical positive original XAU robot slots without live promotion."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

ALL = Path("research/preserved/xau_all_positive_original_robots_20261110.json")
M15 = Path("research/preserved/xau_m15_positive_20261110.json")


class SavedAllPositiveXauTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(ALL.read_text(encoding="utf-8"))
        cls.existing_m15 = json.loads(M15.read_text(encoding="utf-8"))
        cls.snapshots = {s["id"]:s for s in cls.catalog["snapshots"]}

    def test_all_five_positive_groups_frozen(self):
        d=self.catalog
        expected={
            "m15_original_24_sessions":20,
            "m15_matched_short_window":21,
            "m30_matched_short_window":8,
            "m1_matched_short_window":1,
            "m5_clock_time_exp":2,
        }
        self.assertEqual(d["archived_positive_scenario_slots"],52)
        self.assertEqual(d["distinct_original_rule_families"],14)
        self.assertEqual(
            {k:len(s["entries"]) for k,s in self.snapshots.items()},expected)
        self.assertEqual({k:v["positive_slots"] for k,v in
                          d["snapshot_counts"].items()},expected)
        self.assertEqual(d["original_m5_positive_count"],0)

    def test_preserves_exact_existing_m15_catalog(self):
        prior={s["id"]:s for s in self.existing_m15["slots"]}
        newer={s["id"]:s for s in self.snapshots["m15_original_24_sessions"]["entries"]}
        self.assertEqual(set(prior),set(newer))
        for key,p in prior.items():
            n=newer[key]
            self.assertEqual(n["net_realized_usd"],p["net_usd"])
            self.assertEqual(n["double_cost_net_usd"],p["double_cost_net_usd"])
            self.assertEqual(n["closed_trades"],p["closed_trades"])

    def test_no_profit_claims_and_no_live_execution(self):
        d=self.catalog
        self.assertTrue(d["paper_only"])
        self.assertFalse(d["live_trading_enabled"])
        self.assertFalse(d["auto_deployment_allowed"])
        self.assertTrue(d["source_artifacts"])
        for artifact in d["source_artifacts"]:
            self.assertEqual(len(artifact["sha256"]),64)
        for snapshot in self.snapshots.values():
            self.assertEqual(len(snapshot["source_sha256"]),64)
            for row in snapshot["entries"]:
                self.assertGreater(row["net_realized_usd"],0)
                self.assertEqual(row["market"],"XAUUSD")
                self.assertFalse(row["entry_strategy_changed"])
                self.assertEqual(row["positive_under_double_cost"],
                                 row["double_cost_net_usd"]>0)

    def test_h1_aliases_are_not_independent(self):
        catalog=self.catalog
        for s in self.snapshots.values():
            entries=s["entries"]
            self.assertEqual(len(set(e["id"] for e in entries)),len(entries))
            aliases=[e for e in entries if e["id"].startswith("experimental_h1:")]
            for a in aliases:
                self.assertTrue(a["original_rule_id"].startswith(
                    "experimental_h1:XAUUSD:"))
                if a["id"]!=a["original_rule_id"]:
                    self.assertFalse(a["independent_signal_family"])
            for r in entries:
                if r["id"]==r["original_rule_id"]:
                    self.assertTrue(r["independent_signal_family"])

    def test_cost_sensitive_m1_m5_explicitly_not_approved(self):
        m1=self.snapshots["m1_matched_short_window"]
        m5=self.snapshots["m5_clock_time_exp"]
        self.assertEqual(len(m1["entries"]),1)
        self.assertEqual(len(m5["entries"]),2)
        self.assertTrue(m5["not_a_validated_improvement"])
        self.assertFalse(m5["original_time_exit_rules"])
        self.assertEqual(m5["isolated_holding_exit_multiplier"],3)
        self.assertTrue(all(e["experimental_exit_only"] for e in m5["entries"]))
        self.assertTrue(all(e["double_cost_net_usd"]<0 for e in
                            m1["entries"]+m5["entries"]))

    def test_original_strategy_source_files_are_preserved_as_references(self):
        allowed={"src/gold_forward.py","src/leveraged_gold.py",
                 "src/experimental_h1.py","src/momentum60_shadow.py",
                 "src/bb_rebound_mtf.py","src/atlas_vector.py"}
        for s in self.snapshots.values():
            for e in s["entries"]:
                self.assertIn(e["strategy_source_file"],allowed)
        self.assertEqual(len(self.catalog["historical_research_code_commit"]),40)
        self.assertEqual(len(self.catalog["preserved_original_engine_commit"]),40)


if __name__=="__main__":
    unittest.main()
