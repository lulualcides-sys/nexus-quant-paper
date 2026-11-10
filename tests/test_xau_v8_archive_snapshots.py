"""Verify immutable positive scenario archival is not a live approval or double-counting."""
import json
import unittest
from pathlib import Path

PATH=Path(__file__).resolve().parents[1]/"research/preserved/xau_v8_all_positive_h4_snapshots_20261110.json"
class ArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.data=json.loads(PATH.read_text())
    def test_30_positive_scenario_snapshots(self):
        d=self.data
        self.assertEqual(d["historical_positive_scenarios"],30)
        self.assertEqual(len(d["entries"]),30)
        self.assertTrue(all(e["net_usd"]>0 and e["closed_trades"]>0 for e in d["entries"]))
    def test_no_duplicate_scenario_ids(self):
        keys=[e["scenario_key"] for e in self.data["entries"]]
        self.assertEqual(len(keys),len(set(keys)))
    def test_not_30_distinct_robots(self):
        d=self.data
        self.assertEqual(d["unique_signal_families"],5)
        self.assertTrue(d["not_independent_robots"])
        self.assertEqual(len(set(x["family"] for x in d["entries"])),5)
    def test_prospective_research_only(self):
        d=self.data
        self.assertTrue(d["paper_only"])
        self.assertFalse(d["live_approved"])
        self.assertEqual(d["original_positives_archive_scenario_slots"],52)
        self.assertTrue(all(e["approval"]=="retrospective_positive_only" for e in d["entries"]))
    def test_positive_under_both_costs_is_not_executable_guarantee(self):
        self.assertTrue(all(e["positive_under_stress"] for e in self.data["entries"]))
        self.assertEqual(len([e for e in self.data["entries"] if e["research_screen_pass"]]),1)
        c=[e for e in self.data["entries"] if e["research_screen_pass"]][0]
        self.assertEqual(c["family"],"channel20")
        self.assertEqual(c["virtual_start_usd"],10000)
        self.assertEqual(c["closed_trades"],40)
        self.assertEqual(c["net_usd"],844.56)