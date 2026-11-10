"""Scorecard tests: sequential selection, no future data leakage, sample gates."""
import json
from pathlib import Path
import tempfile
import unittest

from research.xau_frequency_scorecard import (
    TRAIN, VALIDATION, FUTURE_HOLDOUT,
    _load_windows, rank_training, final_assessment, sum_stats,
)


def day_report(day, n, pnl):
    def scenario(v):
        return {"filled":n,"expired":0,"skipped":0,
                "wins":n if v>0 else 0,"losses":n if v<0 else 0,
                "net_usd_per_oz":round(v*n,6),
                "max_closed_drawdown_usd_per_oz":max(0,-n*v),
                "ledger":[{"net_usd_per_oz":v} for _ in range(n)]}
    return {
        "day":day[:8],"quote_rows":10000,"source_sha256":"a"*64,
        "trading_approved":False,"original_greenhouse_tracker_match":False,
        "real_broker_backtest":False,
        "variants":{"active_F50_M1":{
            "signals":n,"scenarios":{"no_costs":scenario(pnl+.2),
                                     "friction":scenario(pnl),
                                     "double_friction":scenario(pnl-.2)}
        }},
    }


class ScoreTests(unittest.TestCase):
    def test_cannot_use_future_data_in_training_selection(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for day in TRAIN:
                (root/f"xau_{day}.json").write_text(json.dumps(day_report(day,2,2.)))
            selection=rank_training(root)
            self.assertEqual(selection["preselected_candidate"],"active_F50_M1")
            (root/"xau_20261109_18.json").write_text("INVALID FUTURE FILE")
            selected_again=rank_training(root)
            self.assertEqual(selection,selected_again)

    def test_future_cannot_be_presented_as_approved_without_sample(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for day in TRAIN+VALIDATION+FUTURE_HOLDOUT:
                (root/f"xau_{day}.json").write_text(json.dumps(day_report(day,2,2.)))
            s=rank_training(root)
            out=final_assessment(root,s)
            self.assertTrue(out["approval_blocked"])
            self.assertEqual(out["train_selected_before_future_data"],"active_F50_M1")
            self.assertEqual(out["future_preselected_only"]["friction"]["filled_count"],4)
            self.assertTrue(any("Too few" in x for x in out["approval_reasons"]))

    def test_negative_training_has_no_selected_candidate(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for day in TRAIN:
                (root/f"xau_{day}.json").write_text(json.dumps(day_report(day,3,-1.)))
            out=rank_training(root)
            self.assertIsNone(out["preselected_candidate"])
            self.assertFalse(out["trading_approved"])

    def test_bad_quarantine_id_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for day in TRAIN[:-1]:
                (root/f"xau_{day}.json").write_text(json.dumps(day_report(day,3,1.)))
            (root/f"quarantine_{TRAIN[-1]}.json").write_text(json.dumps({"day_id":"20261001"}))
            with self.assertRaisesRegex(ValueError,"Mismatched quarantine"):
                _load_windows(root,TRAIN,12)

    def test_cost_scenarios_and_ci_do_not_invent_pnl(self):
        a=day_report("20261001",2,1)
        v=sum_stats([a],"active_F50_M1","friction")
        self.assertEqual(v["filled_count"],2)
        self.assertAlmostEqual(v["net_usd_per_oz"],2)
        self.assertEqual(v["signal_count"],2)
        self.assertEqual(v["active_days"],1)
        self.assertEqual(v["day_bootstrap_net_p025"],2)

    def test_incorrect_report_pnl_is_hard_failure(self):
        a=day_report("20261001",3,1)
        a["variants"]["active_F50_M1"]["scenarios"]["friction"]["net_usd_per_oz"]=5000
        with self.assertRaisesRegex(ValueError,"P&L mismatch"):
            sum_stats([a],"active_F50_M1","friction")


if __name__=="__main__":
    unittest.main()
