"""Synthetic accounting tests: do not claim fictional PnL as real."""
import json
from pathlib import Path
import tempfile
import unittest
from research.xau_pa_m5_context_m1_v6 import DAYS,POLICIES,COSTS
from research.xau_pa_m5_context_m1_v6_scorecard import audit,report_text


def synthetic_evidence(day):
    modes={}
    for policy in POLICIES:
        modes[policy]={
          "signals":3 if policy==POLICIES[0] else 2,
          "setup_signals":{"break_retest":1,
                           "range_rejection":2 if policy==POLICIES[0] else 1},
          "costs":{},
        }
        for cost in COSTS:
            pnl=-2. if cost=="double" else -1.
            modes[policy]["costs"][cost]={
                "signals":modes[policy]["signals"],
                "filled":1,"wins":0,"losses":1,
                "net_usd_per_oz":pnl,
                "rejected":{"wide_spread":0},
                "trades":[{"setup":"range_rejection","net_usd_per_oz":pnl,
                           "reason":"STOP","MFE_R_before_actual_exit":0.4,
                           "MAE_R_before_actual_exit":-1.2,
                           "stopped_after_0_5R":False,
                           "stopped_after_1R":False}],
            }
    return {
        "day":day,"source":{"date_utc":day,"sha256":"a"*64,
                            "raw_quote_rows":5000},
        "auto_trading_approved":False,
        "M5_context_M1_entries_only":True,
        "no_independent_M5_orders":True,"single_XAU_position":True,
        "source_is_not_MT5_broker":True,
        "manual_user_marks_present":False,
        "strategy_fidelity_verified":False,
        "warmup_utc":"09:00-12:00","trading_utc":"12:00-21:00",
        "M5_context_rejections":{"M5_not_lateral":1},
        "M1_M5_zone_touch_rejections":{},
        "results":modes,
    }


class AuditTests(unittest.TestCase):
    def records(self):
        tmp=tempfile.TemporaryDirectory()
        root=Path(tmp.name)
        for date in DAYS:
            (root/f"m5_m1_{date}.json").write_text(json.dumps(synthetic_evidence(date)))
        return tmp,root

    def test_both_timeframes_consistent_with_no_m5_trades(self):
        tmp,root=self.records()
        with tmp:
            a=audit(root)
            self.assertFalse(a["user_marks_verified"])
            self.assertFalse(a["trading_approved"])
            self.assertEqual(a["results"][POLICIES[1]]["double"]["june"]["net_usd_per_oz"],-10)
            self.assertEqual(a["M5_veto_reasons"]["M5_not_lateral"],10)
            self.assertIn("não sua análise discricionária",report_text(a))

    def test_missing_day_must_fail(self):
        tmp,root=self.records()
        with tmp:
            (root/f"m5_m1_{DAYS[0]}.json").unlink()
            with self.assertRaisesRegex(ValueError,"Missing or ambiguous"):
                audit(root)

    def test_whole_day_exclusion_no_partial_trade_cherry_picking(self):
        tmp,root=self.records()
        with tmp:
            day=DAYS[0]
            (root/f"m5_m1_{day}.json").unlink()
            (root/f"quarantine_{day}.json").write_text(json.dumps({
                "day":day,"whole_source_quarantined":True,
                "reason":"crossed BID/ASK","trades_included":0}))
            a=audit(root)
            self.assertEqual(len(a["clean_dates"]["june"]),4)
            self.assertEqual(len(a["quarantined"]),1)

    def test_fake_broker_approval_rejected(self):
        tmp,root=self.records()
        with tmp:
            f=root/f"m5_m1_{DAYS[0]}.json"
            d=json.loads(f.read_text())
            d["auto_trading_approved"]=True
            f.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError,"Data source"):
                audit(root)

    def test_m5_context_must_only_veto(self):
        tmp,root=self.records()
        with tmp:
            f=root/f"m5_m1_{DAYS[0]}.json"
            d=json.loads(f.read_text())
            d["results"][POLICIES[1]]["signals"]=10
            f.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError,"fabricated"):
                audit(root)


if __name__=="__main__":
    unittest.main()
