"""Synthetic accounting tests for read-only XAU evidence diagnostics."""
import json
import tempfile
import unittest
from pathlib import Path
from research.xau_quote_evidence_audit import analyze_evidence,human_report


def fixture(folder, day, tf, mode, *, profit=5.,reason="TARGET", gross_fills=1):
    ledger=[]
    for i in range(gross_fills):
        ledger.append({
            "entry_time_utc":f"{day[:4]}-{day[4:6]}-{day[6:]}T12:03:00+00:00",
            "exit_time_utc":f"{day[:4]}-{day[4:6]}-{day[6:]}T12:04:00+00:00",
            "side":"BUY", "reason":reason, "net_usd_per_oz":profit
        })
    blob={
        "source":{"first_candle_utc":f"{day[:4]}-{day[4:6]}-{day[6:]}T12:00:00+00:00",
                  "source_sha256":"1"*64,"source_rows":125000},
        "broker_lot_or_commission_verified":False,
        "independently_validated_with_original_greenhouse":False,
        "spread_accounted_through_actual_bid_ask":True,
        "execution":{"planned_signals":2,"filled":gross_fills,
                     "closed":gross_fills,"unfilled_expired":2-gross_fills,
                     "ledger":ledger},
    }
    (folder/f"xau_{day}_{tf}_{mode}.json").write_text(json.dumps(blob))


class EvidenceTests(unittest.TestCase):
    def make_folder(self):
        td=tempfile.TemporaryDirectory()
        p=Path(td.name)
        for tf in ("M1","M5"):
            fixture(p,"20261109",tf,"base",profit=-4.0,reason="STOP")
            fixture(p,"20261109",tf,"friction",profit=-4.5,reason="STOP")
        return td,p

    def test_report_reports_the_loss_and_no_approval(self):
        td,p=self.make_folder()
        with td:
            result=analyze_evidence(p,["20261109"])
            e=result["strategies"]["M1"]["friction"]
            self.assertEqual(e["signals"],2)
            self.assertEqual(e["filled"],1)
            self.assertEqual(e["fill_rate"],.5)
            self.assertEqual(e["net_usd_per_oz"],-4.5)
            self.assertEqual(e["exit_reason_counts"],{"STOP":1})
            self.assertFalse(result["eligible_for_broker_orders"])
            self.assertTrue(any("fewer than" in x for x in result["approval_fail_reasons"]))
            self.assertIn("-4.500",human_report(result))

    def test_ordered_unique_dates_gate(self):
        td,p=self.make_folder()
        with td:
            with self.assertRaisesRegex(ValueError,"chronologically sorted"):
                analyze_evidence(p,["20261109","20261109"])

    def test_missing_audit_artifact_fails(self):
        td,p=self.make_folder()
        with td:
            (p/"xau_20261109_M1_base.json").unlink()
            with self.assertRaisesRegex(ValueError,"Missing evidence"):
                analyze_evidence(p,["20261109"])

    def test_no_fill_reports_null_pf_not_false_profit(self):
        td,p=self.make_folder()
        with td:
            for mode in ("base","friction"):
                fixture(p,"20261109","M5",mode,profit=0,gross_fills=0)
            r=analyze_evidence(p,["20261109"])
            self.assertIsNone(r["strategies"]["M5"]["friction"]["profit_factor"])
            self.assertIsNone(r["strategies"]["M5"]["friction"]["expectancy_usd_per_oz"])

    def test_rejects_missing_trade_in_ledger(self):
        td,p=self.make_folder()
        with td:
            f=p/"xau_20261109_M5_friction.json"
            item=json.loads(f.read_text())
            item["execution"]["ledger"]=[]
            f.write_text(json.dumps(item))
            with self.assertRaisesRegex(ValueError,"Missing closed-trade"):
                analyze_evidence(p,["20261109"])

    def test_costs_cannot_magically_improve_net_pnl(self):
        td,p=self.make_folder()
        with td:
            fixture(p,"20261109","M1","friction",profit=-2)
            with self.assertRaisesRegex(ValueError,"perversely"):
                analyze_evidence(p,["20261109"])

    def test_no_broker_equivalence_claims(self):
        td,p=self.make_folder()
        with td:
            f=p/"xau_20261109_M1_base.json"
            item=json.loads(f.read_text())
            item["broker_lot_or_commission_verified"]=True
            f.write_text(json.dumps(item))
            with self.assertRaisesRegex(ValueError,"Invalid provenance"):
                analyze_evidence(p,["20261109"])


if __name__=="__main__":
    unittest.main()
