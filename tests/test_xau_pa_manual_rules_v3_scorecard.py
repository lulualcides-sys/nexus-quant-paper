"""Synthetic scorecard evidence tests for manual-rule v3."""
import json
from pathlib import Path
import tempfile
import unittest

from research.xau_pa_manual_rules_v3 import DAYS
from research.xau_pa_manual_rules_v3_scorecard import summarize,markdown


def fake_day(day):
    data={}
    for tf in ("M1","M5","SHARED"):
        data[tf]={}
        for model in ("legacy","marked_rules_v3"):
            models={"legacy":"break_retest","marked_rules_v3":"range_rejection"}
            data[tf][model]={
                "signals":1,
                "signal_setups":{models[model]:1},
                "events":{"breakout_waiting_retest":1},
                "costs":{},
            }
            for cost in ("standard","double"):
                pnl=-1 if cost=="standard" else -2
                data[tf][model]["costs"][cost]={
                    "signals":1,"filled":1,
                    "net_usd_per_oz":pnl,"rejected":{"wide_spread":0},
                    "trades":[{"setup":models[model],
                               "net_usd_per_oz":pnl}],
                }
    return {
        "day":day,"symbol":"XAUUSD",
        "source":{"sha256":"a"*64,"date_utc":day,"raw_quote_rows":10000},
        "live_approval":False,"not_an_MT5_broker_backtest":True,
        "user_drawn_marking_fidelity_verified":False,
        "one_concurrent_position":True,
        "trade_utc":"12:00-21:00",
        "marking_mode":"proxy","results":data,
    }


class ScorecardAudit(unittest.TestCase):
    def create_fixture(self):
        temp=tempfile.TemporaryDirectory()
        root=Path(temp.name)
        for d in DAYS:
            (root/f"xau_manual_v3_{d}.json").write_text(json.dumps(fake_day(d)))
        return temp,root

    def test_complete_comparison_and_unverified_manual_fidelity(self):
        tmp,root=self.create_fixture()
        with tmp:
            r=summarize(root)
            self.assertFalse(r["manual_fidelity_verified"])
            self.assertFalse(r["live_trading_approved"])
            self.assertEqual(r["marking_mode"],"proxy")
            self.assertEqual(len(r["clean_days"]["october"]),5)
            self.assertEqual(r["result"]["M1"]["marked_rules_v3"]["double"]["october"]["net_usd_per_oz"],-10)
            self.assertIn("Não é a marcação do usuário",markdown(r))

    def test_missing_day_is_not_omitted(self):
        tmp,root=self.create_fixture()
        with tmp:
            (root/f"xau_manual_v3_{DAYS[0]}.json").unlink()
            with self.assertRaisesRegex(ValueError,"Missing or double"):
                summarize(root)

    def test_day_quarantine_entire_data(self):
        tmp,root=self.create_fixture()
        with tmp:
            d=DAYS[0]
            (root/f"xau_manual_v3_{d}.json").unlink()
            (root/f"quarantine_{d}.json").write_text(json.dumps({
                "day":d,"whole_day_excluded":True,
                "included_trades":0,"reason":"crossed feed"
            }))
            r=summarize(root)
            self.assertEqual(len(r["whole_day_quarantines"]),1)
            self.assertEqual(len(r["clean_days"]["october"]),4)

    def test_false_broker_profit_claim_is_rejected(self):
        tmp,root=self.create_fixture()
        with tmp:
            f=root/f"xau_manual_v3_{DAYS[0]}.json"
            row=json.loads(f.read_text())
            row["live_approval"]=True
            f.write_text(json.dumps(row))
            with self.assertRaisesRegex(ValueError,"Source/provenance"):
                summarize(root)

    def test_bad_ledger_is_refused(self):
        tmp,root=self.create_fixture()
        with tmp:
            f=root/f"xau_manual_v3_{DAYS[0]}.json"
            row=json.loads(f.read_text())
            row["results"]["M1"]["marked_rules_v3"]["costs"]["double"]["net_usd_per_oz"]=99
            f.write_text(json.dumps(row))
            with self.assertRaisesRegex(ValueError,"Inconsistent filled"):
                summarize(root)


if __name__=="__main__":
    unittest.main()
