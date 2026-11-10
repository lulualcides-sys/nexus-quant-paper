"""Unit tests for audited XAUUSD PA whole-session accounting."""
from datetime import datetime,timezone
import json
from pathlib import Path
import tempfile
import unittest

from research.xau_pa_scorecard import DATES,score,markdown


def day_record(day):
    trades=[{"net_usd_per_oz":1.0,"setup":"break_retest",
             "reason":"TARGET"}]
    results={}
    for tf in ("M1","M5"):
        results[tf]={
            "signals":2,"filled":1,"wins":1,"losses":0,
            "net_usd_per_oz":1.,"profit_factor":None,
            "trades":trades
        }
    return {
        "day":day,"source":{"date_utc":day,"sha256":"e"*64,"raw_quote_rows":10000},
        "spread_included_bid_ask":True,
        "is_actual_broker_backtest":False,"approval_for_live":False,
        "results":results,
    }


class ScoreTests(unittest.TestCase):
    def populate(self):
        temp=tempfile.TemporaryDirectory()
        root=Path(temp.name)
        for day in DATES:
            (root/f"xau_pa_{day}.json").write_text(json.dumps(day_record(day)))
        return temp,root

    def test_split_results_and_fail_closed_default(self):
        temp,root=self.populate()
        with temp:
            r=score(root)
            self.assertTrue(r["approval_blocked"])
            self.assertEqual(r["tf"]["M1"]["all"]["filled"],10)
            self.assertEqual(r["tf"]["M5"]["first_week"]["filled"],5)
            self.assertEqual(r["tf"]["M1"]["second_week"]["filled"],5)
            self.assertEqual(r["tf"]["M1"]["all"]["net_usd_per_oz"],10)
            self.assertIn("NÃO APROVADO",markdown(r))

    def test_no_missing_date_silent_substitution(self):
        temp,root=self.populate()
        with temp:
            (root/f"xau_pa_{DATES[0]}.json").unlink()
            with self.assertRaisesRegex(ValueError,"Missing/ambiguous"):
                score(root)

    def test_entire_corrupt_day_removed_before_accounting(self):
        temp,root=self.populate()
        with temp:
            day=DATES[0]
            (root/f"xau_pa_{day}.json").unlink()
            (root/f"quarantine_{day}.json").write_text(json.dumps({
                "day":day,"whole_session_excluded":True,
                "trades_included":0,"reason":"crossed bid/ask",
            }))
            r=score(root)
            self.assertEqual(r["tf"]["M1"]["all"]["filled"],9)
            self.assertEqual(len(r["quarantined_sessions"]),1)

    def test_false_live_approval_rejected(self):
        temp,root=self.populate()
        with temp:
            f=root/f"xau_pa_{DATES[0]}.json"
            r=json.loads(f.read_text())
            r["approval_for_live"]=True
            f.write_text(json.dumps(r))
            with self.assertRaisesRegex(ValueError,"provenance|fabricated"):
                score(root)

    def test_net_ledger_must_match_display(self):
        temp,root=self.populate()
        with temp:
            f=root/f"xau_pa_{DATES[0]}.json"
            r=json.loads(f.read_text())
            r["results"]["M1"]["net_usd_per_oz"]=90.
            f.write_text(json.dumps(r))
            with self.assertRaisesRegex(ValueError,"Net PnL"):
                score(root)


if __name__=="__main__":
    unittest.main()
