"""Price Action causal intrabar retest tests using SYNTHETIC candles/quotes.

Verify event chronology: confirmed breakout candle -> later line touch ->
subsequent real quote rejection -> order only at the NEXT quote.
"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research.xau_pa_manual_rules_v3 import Trendline
from research.xau_pa_intrabar_retest_execution import (
    MAY,OCT,DAYS,ARMS,COSTS,observed_breakouts,
    reactive_retest_signals,day_study,
)
from research.xau_pa_intrabar_entry_scorecard import audit,markdown
from research.xau_price_action_m1m5 import Settings,simulate_ticks

T0=1779085200000


def bars(n=60):
    return [{
        "time":T0//1000+60*i,
        "open":100.,"high":101.,"low":99.,"close":100.,
        "quote_updates":50,
    } for i in range(n)]


def breakout():
    line=Trendline("LTD",10,103.,30,101.,(T0+43*60000),"proxy")
    return {
        "known_ms":T0+46*60000,
        "index":45,"line":line,"side":1,
        "atr":2.,"kind":"LTD",
    }


def fake_day(day):
    result={}
    for name in ARMS:
        result[name]={
            "signals":2,
            "signal_setups":{"break_retest":1,"range_rejection":1},
            "costs":{},
        }
        for cost in COSTS:
            pnl=-1 if cost=="standard" else -2
            result[name]["costs"][cost]={
                "signals":2,"filled":1,"wins":0,"losses":1,
                "net_usd_per_oz":pnl,
                "rejected":{"stop_geometry":0},
                "trades":[{
                    "setup":"range_rejection",
                    "side":1,"entry":100.,"stop":99.,"exit":98.8,
                    "net_usd_per_oz":pnl,"reason":"STOP",
                }],
            }
    return {
        "day":day,"source":{"sha256":"f"*64,"date_utc":day},
        "same_BID_ASK_execution_quotes":True,
        "same_stop_target_cost_rules":True,
        "causal_intrabar_reaction_only":True,
        "user_manual_levels_verified":False,
        "exact_manual_entry_timing_verified":False,
        "not_MT5_broker_execution":True,
        "approved_for_live":False,
        "trading_utc":"12:00-21:00","warmup_utc":"09:00-12:00",
        "retest_event_counters":{"retouched_line":1},
        "results":result,
    }


class IntrabarRetestTests(unittest.TestCase):
    def test_touch_then_reaction_on_later_quote(self):
        bb=bars()
        e=breakout()
        t=e["known_ms"]
        line=e["line"].value(46)
        tape=[(t,line,line+.15),
              (t+1000,line+.20,line+.35),
              (t+2000,line+.21,line+.36)]
        with patch("research.xau_pa_intrabar_retest_execution.observed_breakouts",
                   return_value=[e]):
            signals,counts=reactive_retest_signals(
                tape,bb,t,t+5*60000
            )
        self.assertEqual(len(signals),1)
        s=signals[0]
        self.assertEqual(s["touch_ms"],t)
        self.assertEqual(s["signal_ms"],t+1000)
        self.assertEqual(s["eligible_ms"],t+1001)
        self.assertEqual(s["line_kind"],"LTD")
        self.assertEqual(s["side"],1)
        self.assertEqual(counts["intrabar_reaction_signal"],1)

    def test_no_signal_without_touch_even_after_favorable_quotes(self):
        bb=bars();e=breakout();t=e["known_ms"]
        lvl=e["line"].value(46)
        tape=[(t,lvl+1.5,lvl+1.65),
              (t+1000,lvl+2.,lvl+2.15)]
        with patch("research.xau_pa_intrabar_retest_execution.observed_breakouts",
                   return_value=[e]):
            signals,_=reactive_retest_signals(tape,bb,t,t+200000)
        self.assertEqual(signals,[])

    def test_no_entry_from_same_quote_as_touch(self):
        bb=bars();e=breakout();t=e["known_ms"]
        lvl=e["line"].value(46)
        with patch("research.xau_pa_intrabar_retest_execution.observed_breakouts",
                   return_value=[e]):
            signals,_=reactive_retest_signals([(t,lvl,lvl+.15)],
                                               bb,t,t+60000)
        self.assertEqual(signals,[])

    def test_no_future_price_changes_previous_reaction(self):
        bb=bars();e=breakout();t=e["known_ms"]
        lvl=e["line"].value(46)
        tape=[(t,lvl,lvl+.15),(t+1000,lvl+.2,lvl+.35),
              (t+2000,lvl+.21,lvl+.36)]
        with patch("research.xau_pa_intrabar_retest_execution.observed_breakouts",
                   return_value=[e]):
            before,_=reactive_retest_signals(tape,bb,t,t+200000)
            bb[55].update(open=999999.,high=999999.,
                          low=1.,close=999999.)
            after,_=reactive_retest_signals(
                tape+[(t+3000,9999.,9999.2)],bb,t,t+200000
            )
        self.assertEqual(before,after)
        self.assertLess(before[0]["signal_ms"],before[0]["eligible_ms"])

    def test_simulator_never_executes_on_detection_tick(self):
        bb=bars();e=breakout();t=e["known_ms"]
        lvl=e["line"].value(46)
        tape=[(t,lvl,lvl+.15),(t+1000,lvl+.20,lvl+.35),
              (t+2000,lvl+.19,lvl+.34)]
        with patch("research.xau_pa_intrabar_retest_execution.observed_breakouts",
                   return_value=[e]):
            signals,_=reactive_retest_signals(tape,bb,t,t+200000)
        # Even when signal exists earlier in the complete source,
        # the executor must wait until the NEXT chronological quote.
        out=simulate_ticks(tape,signals,60,Settings())
        for trade in out["trades"]:
            self.assertGreater(trade["entry_ms"],signals[0]["signal_ms"])

    def test_study_cannot_select_lucky_dates_after_result(self):
        with self.assertRaisesRegex(ValueError,"preregistered"):
            day_study("notexists.csv","20260630")

    def create(self):
        temp=tempfile.TemporaryDirectory()
        folder=Path(temp.name)
        for day in DAYS:
            (folder/f"intrabar_{day}.json").write_text(json.dumps(fake_day(day)))
        return temp,folder

    def test_all_10_dates_provenance_and_broker_not_claimed(self):
        tmp,root=self.create()
        with tmp:
            r=audit(root)
            self.assertFalse(r["live_approved"])
            self.assertFalse(r["manual_trader_markings_verified"])
            self.assertEqual(len(r["clean_days"]["may"]),5)
            self.assertEqual(len(r["clean_days"]["sep_oct"]),5)
            self.assertIn("Entrada",markdown(r).title())

    def test_different_range_signals_are_rejected(self):
        tmp,root=self.create()
        with tmp:
            f=root/f"intrabar_{DAYS[0]}.json"
            x=json.loads(f.read_text())
            x["results"][ARMS[1]]["signal_setups"]={"break_retest":2}
            f.write_text(json.dumps(x))
            with self.assertRaisesRegex(ValueError,"Range signals changed"):
                audit(root)

    def test_no_silent_missing_dates(self):
        tmp,root=self.create()
        with tmp:
            (root/f"intrabar_{DAYS[0]}.json").unlink()
            with self.assertRaisesRegex(ValueError,"Missing"):
                audit(root)

    def test_quarantine_source_whole_day(self):
        tmp,root=self.create()
        with tmp:
            (root/f"intrabar_{DAYS[0]}.json").unlink()
            (root/f"quarantine_{DAYS[0]}.json").write_text(json.dumps({
                "day":DAYS[0],"full_day_quarantine":True,
                "trades_counted":0,"reason":"crossed quote",
            }))
            r=audit(root)
            self.assertEqual(len(r["clean_days"]["may"]),4)

    def test_prevent_unverified_live_execution_claim(self):
        tmp,root=self.create()
        with tmp:
            f=root/f"intrabar_{DAYS[0]}.json"
            d=json.loads(f.read_text());d["approved_for_live"]=True
            f.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError,"unverified"):
                audit(root)


if __name__=="__main__":
    unittest.main()
