"""Synthetic regression on exact STOP/WIN/Red behavior, not fictional gains."""
import json
from pathlib import Path
import tempfile
import unittest

from research.xau_price_action_m1m5 import Settings,simulate_ticks
from research.xau_pa_exit_fidelity_audit import quote_gaps,day_audit,DAYS,ARMS
from research.xau_pa_exit_fidelity_scorecard import report,markdown


T0=1782129600000

def buy_signal(when=T0):
    return {
        "side":1,"setup":"break_retest",
        "signal_ms":when-60000,"eligible_ms":when,
        "timeframe_seconds":60,
        "stop":99.2,"atr":2.
    }


def mock_date(day):
    arms={}
    for policy in ARMS:
        arms[policy]={"signals":1,"costs":{}}
        for cost in ("standard","double"):
            pnl=-1. if cost=="standard" else -2.
            arms[policy]["costs"][cost]={
                "signals":1,"filled":1,"wins":0,"losses":1,
                "net_usd_per_oz":pnl,
                "trades":[{"net_usd_per_oz":pnl,"reason":"STOP",
                           "setup":"break_retest"}],
                "rejected":{"wide_spread":0}
            }
    return {
        "day":day,"source":{"date_utc":day,"sha256":"e"*64},
        "quote_gaps":{"total_execution_quotes":4000,
                      "gaps_over_one_minute":0,"largest_gap_seconds":10},
        "same_signal_list_in_both_arms":True,
        "original_v6_reproduced_exactly":True,
        "time_exit_not_user_confirmed":True,
        "original_stop_target_prices_unchanged":True,
        "no_manual_user_drawings":True,
        "not_real_mt5_broker_executions":True,
        "live_approved":False,
        "session_start_utc":"12:00","session_end_utc":"21:00",
        "results":arms,
    }


class StopWinRedOnlyTests(unittest.TestCase):
    def test_backward_compatibility_default_timeout_same_as_explicit_true(self):
        cfg=Settings()
        quotes=[(T0,100.,100.2),
                (T0+19*60000,100.02,100.22),
                (T0+21*60000,100.02,100.22),
                (T0+22*60000,100.02,100.22)]
        ref=simulate_ticks(quotes,[buy_signal()],60,cfg)
        explicit=simulate_ticks(quotes,[buy_signal()],60,cfg,
                                time_stop_enabled=True)
        self.assertEqual(ref,explicit)
        self.assertEqual(ref["trades"][0]["reason"],"TIME")

    def test_no_time_exit_leaves_trade_open_until_session_end(self):
        cfg=Settings()
        ticks=[(T0,100.,100.2),
               (T0+21*60000,100.1,100.3),
               (T0+25*60000,100.1,100.3)]
        out=simulate_ticks(ticks,[buy_signal()],60,cfg,
                           time_stop_enabled=False)
        self.assertEqual(out["filled"],1)
        self.assertEqual(out["trades"][0]["reason"],"SESSION_END")
        self.assertEqual(out["trades"][0]["exit_ms"],T0+25*60000)

    def test_even_without_time_exit_stop_red_is_executed(self):
        cfg=Settings()
        ticks=[(T0,100.,100.2),
               (T0+21*60000,99.0,99.2),
               (T0+30*60000,101.0,101.2)]
        out=simulate_ticks(ticks,[buy_signal()],60,cfg,
                           time_stop_enabled=False)
        self.assertEqual(out["filled"],1)
        self.assertEqual(out["trades"][0]["reason"],"STOP")
        self.assertEqual(out["trades"][0]["exit_ms"],T0+21*60000)

    def test_removing_timeout_does_not_create_new_signals(self):
        cfg=Settings()
        next_signal=buy_signal(T0+22*60000)
        ticks=[(T0,100.,100.2),
               (T0+21*60000,100.1,100.3),
               (T0+22*60000,100.1,100.3),
               (T0+30*60000,100.1,100.3)]
        original=simulate_ticks(ticks,[buy_signal(),next_signal],60,cfg)
        no_time=simulate_ticks(ticks,[buy_signal(),next_signal],60,cfg,
                               time_stop_enabled=False)
        self.assertEqual(original["signals"],2)
        self.assertEqual(no_time["signals"],2)
        self.assertEqual(no_time["filled"],1)
        self.assertEqual(no_time["rejected"]["already_in_position"],1)
        self.assertEqual(original["filled"],2)

    def test_quote_gap_report_is_diagnostic_only(self):
        result=quote_gaps([
            (T0,100.,100.2),
            *[(T0+i*1000,100.,100.2) for i in range(1,1600)],
            (T0+2000000,100.,100.2)
        ],T0,T0+2100000)
        self.assertEqual(result["gaps_over_one_minute"],1)
        self.assertEqual(len(result["top_gaps_utc_ms"]),1)

    def test_predeclared_date_cannot_be_changed_after_results(self):
        with self.assertRaisesRegex(ValueError,"original v6"):
            day_audit("missing.csv","20260404")

    def cases(self):
        td=tempfile.TemporaryDirectory()
        path=Path(td.name)
        for day in DAYS:
            (path/f"time_exit_{day}.json").write_text(json.dumps(mock_date(day)))
        return td,path

    def test_scorecard_covers_whole_original_panels(self):
        td,path=self.cases()
        with td:
            r=report(path)
            self.assertFalse(r["auto_trading_approved"])
            self.assertEqual(len(r["clean_days"]["june"]),5)
            self.assertEqual(len(r["clean_days"]["july"]),5)
            self.assertIn("20 candles",markdown(r))
            self.assertEqual(r["results"][ARMS[1]]["double"]["july"]["time_exits"],0)

    def test_missing_single_day_must_block_audit(self):
        td,path=self.cases()
        with td:
            (path/f"time_exit_{DAYS[0]}.json").unlink()
            with self.assertRaisesRegex(ValueError,"Incomplete"):
                report(path)

    def test_whole_day_quarantine_not_silent(self):
        td,path=self.cases()
        with td:
            (path/f"time_exit_{DAYS[0]}.json").unlink()
            (path/f"quarantine_{DAYS[0]}.json").write_text(json.dumps({
                "day":DAYS[0],"excluded_entire_day":True,
                "reason":"crossed quote","trades_counted":0,
            }))
            r=report(path)
            self.assertEqual(len(r["clean_days"]["june"]),4)

    def test_no_fabricated_broker_results(self):
        td,path=self.cases()
        with td:
            f=path/f"time_exit_{DAYS[0]}.json"
            d=json.loads(f.read_text());d["live_approved"]=True
            f.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError,"Unverified"):
                report(path)


if __name__=="__main__":
    unittest.main()
