"""Constrained synthetic tests of XAU August aggregation; not trading evidence."""
import json
from pathlib import Path
import tempfile
import unittest

from research.xau_august_frozen_replication import DATES, KEYS, summarize, markdown_report


def make_report(day):
    rows={}
    for name in KEYS:
        rows[name]={
          "signals":1,
          "scenarios":{
            cost:{
              "filled":1,"expired":0,"skipped":0,
              "wins":int(cost=="no_costs"),"losses":int(cost!="no_costs"),
              "net_usd_per_oz":pnl,
              "max_closed_drawdown_usd_per_oz":max(-pnl,0),
              "ledger":[{"net_usd_per_oz":pnl}]
            }
            for cost,pnl in (("no_costs",.50),("friction",-.10),("double_friction",-.70))
          }
        }
    return {
      "day":day,"source":"Dukascopy public bid/ask quotes",
      "original_greenhouse_tracker_match":False,
      "real_broker_backtest":False,"trading_approved":False,
      "source_sha256":"f"*64,"quote_rows":10000,
      "m1_bars":300,"m5_bars":60,"variants":rows,
    }


class AugustPanelTests(unittest.TestCase):
    def prepare(self):
        tmp=tempfile.TemporaryDirectory()
        p=Path(tmp.name)
        for day in DATES:
            (p/f"xau_{day}.json").write_text(json.dumps(make_report(day)))
        return tmp,p

    def test_all_variants_all_timeframes_all_costs_are_preserved(self):
        tmp,p=self.prepare()
        with tmp:
            r=summarize(p)
            self.assertEqual(len(r["clean_days"]),20)
            self.assertEqual(len(r["variants"]),12)
            self.assertFalse(r["any_strategy_approved_for_trading"])
            self.assertTrue(r["not_a_future_holdout"])
            for key in KEYS:
                d=r["variants"][key]["double_friction"]
                self.assertEqual(d["all"]["filled_count"],20)
                self.assertAlmostEqual(d["all"]["net_usd_per_oz"],-14)
                self.assertAlmostEqual(d["first_half"]["net_usd_per_oz"],-7)
                self.assertAlmostEqual(d["second_half"]["net_usd_per_oz"],-7)
            self.assertIn("not a real MT5 account backtest",markdown_report(r))

    def test_missing_day_without_quarantine_refused(self):
        tmp,p=self.prepare()
        with tmp:
            (p/f"xau_{DATES[0]}.json").unlink()
            with self.assertRaisesRegex(ValueError,"exactly one"):
                summarize(p)

    def test_invalid_original_tracker_claim_is_refused(self):
        tmp,p=self.prepare()
        with tmp:
            file=p/f"xau_{DATES[0]}.json"
            d=json.loads(file.read_text())
            d["original_greenhouse_tracker_match"]=True
            file.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError,"provenance"):
                summarize(p)

    def test_whole_day_quarantine_is_reported_without_trades(self):
        tmp,p=self.prepare()
        with tmp:
            file=p/f"xau_{DATES[0]}.json"
            file.unlink()
            (p/f"quarantine_{DATES[0]}.json").write_text(json.dumps({
                "day_id":DATES[0],
                "all_trades_excluded_before_scoring":True,
                "data_quality_error":"crossed quote",
            }))
            r=summarize(p)
            self.assertEqual(len(r["clean_days"]),19)
            self.assertEqual(r["variants"][KEYS[0]]["double_friction"]["all"]["filled_count"],19)
            self.assertIn("crossed quote",markdown_report(r))

    def test_oversized_spurious_signal_or_missing_scenario_refused(self):
        tmp,p=self.prepare()
        with tmp:
            file=p/f"xau_{DATES[0]}.json"
            d=json.loads(file.read_text())
            d["variants"][KEYS[0]]["scenarios"].pop("friction")
            file.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError,"Missing cost"):
                summarize(p)


if __name__ == "__main__":
    unittest.main()
