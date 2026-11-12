"""Synthetic checks for fixed May XAU PA reporting. Never trading evidence."""
import json
from pathlib import Path
import tempfile
import unittest

from research.xau_pa_may_replication import MAY_DATES,evaluate,as_markdown


def fake(day):
    return {
      "day":day,
      "source":{"date_utc":day,"sha256":"f"*64,"raw_quote_rows":5000},
      "spread_included_bid_ask":True,
      "approval_for_live":False,
      "is_actual_broker_backtest":False,
      "results":{
        tf:{"signals":1,"filled":1,"net_usd_per_oz":-2,
            "trades":[{"net_usd_per_oz":-2,
                       "reason":"STOP","setup":"break_retest"}]}
        for tf in ("M1","M5")
      }
    }


class MayResearchTests(unittest.TestCase):
    def populate(self):
        td=tempfile.TemporaryDirectory()
        folder=Path(td.name)
        for date in MAY_DATES:
            (folder/f"xau_pa_{date}.json").write_text(json.dumps(fake(date)))
        return td,folder

    def test_all_20_sessions_report_losses_in_two_blocks(self):
        td,p=self.populate()
        with td:
            r=evaluate(p)
            self.assertTrue(r["parameters_untouched_since_june"])
            self.assertFalse(r["approved_to_trade"])
            self.assertEqual(r["results"]["M1"]["all"]["filled"],20)
            self.assertEqual(r["results"]["M1"]["all"]["net_usd_per_oz"],-40)
            self.assertEqual(r["results"]["M5"]["may_18_to_29"]["net_usd_per_oz"],-20)
            self.assertIn("não é teste futuro",as_markdown(r))

    def test_missing_source_day_rejected(self):
        td,p=self.populate()
        with td:
            (p/f"xau_pa_{MAY_DATES[0]}.json").unlink()
            with self.assertRaisesRegex(ValueError,"Missing or ambiguous"):
                evaluate(p)

    def test_one_quarantine_removes_whole_day(self):
        td,p=self.populate()
        with td:
            date=MAY_DATES[0]
            (p/f"xau_pa_{date}.json").unlink()
            (p/f"quarantine_{date}.json").write_text(json.dumps({
                "day":date,"whole_session_excluded":True,
                "trades_included":0,"reason":"invalid quotes",
            }))
            r=evaluate(p)
            self.assertEqual(len(r["valid_dates"]),19)
            self.assertEqual(r["results"]["M1"]["all"]["filled"],19)

    def test_account_profit_claim_not_accepted(self):
        td,p=self.populate()
        with td:
            file=p/f"xau_pa_{MAY_DATES[0]}.json"
            report=json.loads(file.read_text())
            report["approval_for_live"]=True
            file.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError,"Unverified"):
                evaluate(p)


if __name__=="__main__":
    unittest.main()
