"""Synthetic tests of a locked XAU candlestick quality hypothesis.

No synthetic price result is claimed as a real profit/backtest.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from research.xau_pa_quality_experiment import (
    FIRST,SECOND,DAYS,pass_quality,quality_veto,run_day
)
from research.xau_pa_quality_scorecard import aggregate,markdown


def candle(*,time=1760000400,op=100.,high=101.2,low=99.8,close=101.1,updates=55):
    return {"time":time,"open":op,"high":high,"low":low,"close":close,
            "quote_updates":updates}


def signal(bar,*,side=1,setup="break_retest",atr=.8,tf=60):
    return {"side":side,"setup":setup,"atr":atr,
            "signal_ms":bar["time"]*1000,
            "eligible_ms":(bar["time"]+tf)*1000,
            "timeframe_seconds":tf}


def evidence(day):
    modes={}
    for tf in ("M1","M5"):
        modes[tf]={}
        for mode in ("control","quality_v1"):
            modes[tf][mode]={
               "signals":2 if mode=="control" else 1,
               "costs":{},
            }
            for scenario in ("standard","double"):
                pnl=1. if mode=="control" else -.7
                history={
                    "signals":modes[tf][mode]["signals"],
                    "filled":1,"net_usd_per_oz":pnl,
                    "rejected":{"delayed":0,"wide_spread":0},
                    "trades":[{"net_usd_per_oz":pnl,
                               "reason":"TARGET" if pnl>0 else "STOP",
                               "setup":"break_retest"}]
                }
                modes[tf][mode]["costs"][scenario]=history
    return {
        "day":day,"source":{"date_utc":day,"sha256":"f"*64,
                           "raw_quote_rows":50000},
        "approved_for_live":False,
        "broker_mt5_account_verification":False,
        "auto_order_execution":False,
        "modes":modes,
    }


class XAUQualityTests(unittest.TestCase):
    def test_strong_retest_signal_can_pass_without_future_tick(self):
        b=candle()
        self.assertTrue(pass_quality(b,signal(b),60))
        self.assertFalse(pass_quality(b,signal(b,side=-1),60))

    def test_weak_close_fails_for_buy(self):
        b=candle(close=100.25)
        self.assertFalse(pass_quality(b,signal(b),60))

    def test_overextended_volatility_is_vetoed(self):
        b=candle(high=107.0)
        self.assertFalse(pass_quality(b,signal(b),60))

    def test_range_rejection_requires_actual_support_wick(self):
        b=candle(op=100.8,close=101.,low=99.8,high=101.1)
        self.assertTrue(pass_quality(b,signal(b,setup="range_rejection",atr=.75),60))
        bad=candle(op=100.0,close=101.,low=99.8,high=101.1)
        self.assertFalse(pass_quality(bad,signal(bad,setup="range_rejection",atr=.75),60))

    def test_quote_count_is_not_aggressor_volume_but_can_veto_stale_bar(self):
        b=candle(updates=3)
        self.assertFalse(pass_quality(b,signal(b),60))

    def test_no_future_bar_or_side_fabrication(self):
        b=candle()
        wrong=dict(signal(b),signal_ms=1)
        with self.assertRaisesRegex(ValueError,"Signal/candle mismatch"):
            pass_quality(b,wrong,60)

    def test_one_gate_only_vetoes_original_signal_same_timestamp(self):
        a=candle()
        b=candle(time=a["time"]+60,close=100.2)
        s=[signal(a),signal(b)]
        keep=quality_veto([a,b],s,60)
        self.assertEqual(len(keep),1)
        self.assertEqual(keep[0],s[0])

    def _folder(self):
        tmp=tempfile.TemporaryDirectory()
        path=Path(tmp.name)
        for day in DAYS:
            (path/f"xau_pa_quality_{day}.json").write_text(json.dumps(evidence(day)))
        return tmp,path

    def test_all_20_dates_and_both_policies_all_timeframes(self):
        tmp,path=self._folder()
        with tmp:
            r=aggregate(path)
            self.assertEqual(len(r["valid_dates"]["july"]),10)
            self.assertEqual(len(r["valid_dates"]["september"]),10)
            self.assertTrue(r["approval_blocked"])
            self.assertEqual(r["results"]["M1"]["quality_v1"]["double"]["july"]["net_usd_per_oz"],-7.)
            self.assertEqual(r["results"]["M5"]["control"]["standard"]["september"]["filled"],10)
            self.assertIn("NÃO aprovar",markdown(r))

    def test_missing_period_is_not_omitted(self):
        tmp,path=self._folder()
        with tmp:
            (path/f"xau_pa_quality_{DAYS[0]}.json").unlink()
            with self.assertRaisesRegex(ValueError,"Missing or ambiguous"):
                aggregate(path)

    def test_quarantine_an_entire_source_day(self):
        tmp,path=self._folder()
        with tmp:
            day=DAYS[0]
            (path/f"xau_pa_quality_{day}.json").unlink()
            (path/f"quarantine_{day}.json").write_text(json.dumps({
                "day":day,"whole_day_quarantined":True,
                "reason":"crossed bid/ask quote",
                "trades_included":0,
            }))
            v=aggregate(path)
            self.assertEqual(len(v["valid_dates"]["july"]),9)
            self.assertEqual(len(v["quarantined"]),1)

    def test_cannot_claim_live_broker_validation(self):
        tmp,path=self._folder()
        with tmp:
            file=path/f"xau_pa_quality_{DAYS[0]}.json"
            v=json.loads(file.read_text())
            v["approved_for_live"]=True
            file.write_text(json.dumps(v))
            with self.assertRaisesRegex(ValueError,"Source cannot support"):
                aggregate(path)

    def test_cannot_overcount_filtered_signals(self):
        tmp,path=self._folder()
        with tmp:
            file=path/f"xau_pa_quality_{DAYS[0]}.json"
            v=json.loads(file.read_text())
            v["modes"]["M1"]["quality_v1"]["signals"]=3
            file.write_text(json.dumps(v))
            with self.assertRaisesRegex(ValueError,"invented"):
                aggregate(path)

    def test_run_rejects_unplanned_dates_before_source_access(self):
        with self.assertRaisesRegex(ValueError,"Only fixed dates"):
            run_day("not-a-real-quote-file.csv","20260101")


if __name__=="__main__":
    unittest.main()
