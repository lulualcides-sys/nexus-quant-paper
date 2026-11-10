"""Regression checks for price-action Stop Red vs marked-line geometry.

All prices here are synthetic code fixtures, never evidence of gold profit.
"""
import json
from pathlib import Path
import tempfile
import unittest

from research.xau_pa_stop_geometry_audit import (
    DAYS,stop_geometry,stop_line_repair,audit_day,
)
from research.xau_pa_stop_geometry_scorecard import summarize,markdown


def trade(side,stop,line,atr=2):
    return {
      "setup":"break_retest","side":side,"stop":stop,
      "line_retest_level":line,"atr":atr,
      "timeframe_seconds":60,"eligible_ms":60000,
      "signal_ms":0,"breakout_ms":-60000,"line_kind":"LTD" if side==1 else "LTA",
    }


def fake_day(day):
    modes={}
    for name in ("unchanged_v6","line_stop_check"):
        modes[name]={"signals":1,"costs":{}}
        for cost in ("standard","double"):
            loss=-2 if cost=="double" else -1
            modes[name]["costs"][cost]={
                "signals":1,"filled":1,"net_usd_per_oz":loss,
                "trades":[{"net_usd_per_oz":loss,"reason":"STOP"}],
                "rejected":{"stop_geometry":0}
            }
    return {
        "day":day,"source":{"date_utc":day,"sha256":"1"*64},
        "original_v6_exactly_replayed":True,
        "same_M1_signals_and_execution_ticks":True,
        "only_stop_geometry_changed":True,
        "correct_stop_distances_user_confirmed":False,
        "is_not_mt5_broker":True,"live_trading_approved":False,
        "candidate_geometry":{
            "break_retest_candidates":2,
            "stop_wrong_side_candidates":1,
            "original_filled":1,
            "filled_stop_wrong_side":1,
            "actually_adjusted_candidate_stops":1,
        },
        "models":modes,
    }


class PriceActionStopGeometryTests(unittest.TestCase):
    def test_buy_stop_inside_broken_LTD_is_detected_and_repositioned(self):
        buy=trade(1,100.08,100.)
        self.assertTrue(stop_geometry(buy)["stop_on_invalidated_side"])
        out,changes=stop_line_repair([buy])
        self.assertAlmostEqual(out[0]["stop"],99.8)
        self.assertEqual(out[0]["line_retest_level"],100.)
        self.assertEqual(out[0]["eligible_ms"],buy["eligible_ms"])
        self.assertEqual(buy["stop"],100.08)
        self.assertEqual(len(changes),1)

    def test_sell_stop_inside_broken_LTA_is_repaired_above_line(self):
        sell=trade(-1,99.95,100.)
        out,changes=stop_line_repair([sell])
        self.assertAlmostEqual(out[0]["stop"],100.2)
        self.assertGreater(out[0]["stop"],out[0]["line_retest_level"])

    def test_stop_already_beyond_level_preserved(self):
        good=trade(1,99.5,100.)
        corrected,changes=stop_line_repair([good])
        self.assertEqual(corrected,[good])
        self.assertEqual(changes,[])

    def test_never_change_entry_signal_or_filter_a_trade(self):
        original=[trade(1,100.01,100.),trade(-1,99.99,100.)]
        original[1]["eligible_ms"]=120000
        corrected,changes=stop_line_repair(original)
        self.assertEqual(len(corrected),len(original))
        self.assertEqual(len(changes),2)
        for s,t in zip(original,corrected):
            for k in ("signal_ms","eligible_ms","side","setup","atr",
                      "line_retest_level","breakout_ms"):
                self.assertEqual(s[k],t[k])

    def test_range_strategy_stop_is_not_modified(self):
        original=trade(1,99.9,100.)
        original["setup"]="range_rejection"
        actual,changes=stop_line_repair([original])
        self.assertEqual(actual,[original])
        self.assertFalse(stop_geometry(original)["applicable"])

    def test_broken_line_level_must_be_present(self):
        bad=trade(1,100,100)
        bad.pop("line_retest_level")
        with self.assertRaisesRegex(ValueError,"missing its level"):
            stop_line_repair([bad])

    def test_only_fixed_research_dates_accepted(self):
        with self.assertRaisesRegex(ValueError,"Fixed previous-price"):
            audit_day("/nonexistent.csv","20260505")

    def records(self):
        temp=tempfile.TemporaryDirectory()
        path=Path(temp.name)
        for day in DAYS:
            (path/f"stop_geom_{day}.json").write_text(json.dumps(fake_day(day)))
        return temp,path

    def test_complete_scorecard_without_live_approval(self):
        temp,path=self.records()
        with temp:
            d=summarize(path)
            self.assertFalse(d["auto_trade_approved"])
            self.assertEqual(d["geometry"]["stop_wrong_side_candidates"],10)
            self.assertEqual(d["result"]["unchanged_v6"]["double"]["june"]["net_usd_per_oz"],-10)
            self.assertIn("hipótese",markdown(d).lower())

    def test_missing_day_not_omitted(self):
        temp,path=self.records()
        with temp:
            (path/f"stop_geom_{DAYS[0]}.json").unlink()
            with self.assertRaisesRegex(ValueError,"Missing or duplicate"):
                summarize(path)

    def test_quarantine_excludes_an_entire_session(self):
        temp,path=self.records()
        with temp:
            d=DAYS[0]
            (path/f"stop_geom_{d}.json").unlink()
            (path/f"quarantine_{d}.json").write_text(json.dumps({
                "day":d,"whole_day_quarantined":True,
                "trades_included":0,"reason":"invalid crossed BID ASK",
            }))
            report=summarize(path)
            self.assertEqual(len(report["clean_dates"]["june"]),4)

    def test_fake_verified_stop_claim_does_not_pass(self):
        temp,path=self.records()
        with temp:
            f=path/f"stop_geom_{DAYS[0]}.json"
            d=json.loads(f.read_text())
            d["correct_stop_distances_user_confirmed"]=True
            f.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError,"Unverified"):
                summarize(path)


if __name__=="__main__":
    unittest.main()
