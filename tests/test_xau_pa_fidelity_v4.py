"""Causal v4 tests. All OHLC/quotes here are synthetic validation data."""
import json
from pathlib import Path
import tempfile
import unittest

from research.xau_pa_fidelity_v4 import (
    DAYS,ARMS,COSTS,proxy_zones_repeated,confirm_v4,gate_signals,
    experiment_day,
)
from research.xau_pa_fidelity_v4_scorecard import evaluate,markdown
from research.xau_pa_manual_rules_v3 import (
    Trendline,causal_signals
)

T0=1793610000  # only synthetic, no claims of real trade prices


def bars_v3():
    bs=[{"time":T0+i*60,"open":100.0,"high":101.1,
         "low":98.9,"close":100.0,"quote_updates":35}
        for i in range(52)]
    bs[44].update(open=99.5,high=100.,low=98.9,close=99.55)
    bs[45].update(open=99.7,high=100.6,low=99.55,close=100.4)
    bs[46].update(open=99.65,high=100.2,low=99.35,close=100.05)
    line=Trendline("LTD",10,103.,30,101.,
                   created_ms=(T0+40*60)*1000,source="user")
    return bs,line


def example_report(day):
    all_frames={}
    for tf in ("M1","M5","SHARED"):
        all_frames[tf]={}
        for arm in ARMS:
            all_frames[tf][arm]={
                "signals":2,"setup_signals":{"break_retest":2},
                "diagnostics":{"quality_veto_counts":{"qualified_break_retest":2}}
                    if tf!="SHARED" else {},
                "costs":{},
            }
            for cost in COSTS:
                pnl=-1 if cost=="standard" else -2
                out={"signals":2,"filled":1,"wins":0,"losses":1,
                     "net_usd_per_oz":pnl,
                     "trades":[{"net_usd_per_oz":pnl,"setup":"break_retest",
                                "reason":"STOP"}]}
                if tf=="SHARED":
                    out["one_global_position_per_symbol"]=True
                all_frames[tf][arm]["costs"][cost]=out
    return {
        "day":day,"source":{"date_utc":day,"sha256":"f"*64,
                            "raw_quote_rows":6000},
        "live_trading_approved":False,
        "same_quoted_bid_ask_execution":True,
        "one_position_globally":True,
        "market_feed_not_mt5_broker":True,
        "profits_usd_per_theoretical_ounce":True,
        "warmup_utc":"09:00-12:00","execution_utc":"12:00-21:00",
        "marking_mode":"proxy",
        "results":all_frames,
    }


class FidelityV4Tests(unittest.TestCase):
    def test_real_break_retest_comes_after_different_closed_candle(self):
        bs,line=bars_v3()
        signals,_=causal_signals(bs,60,(T0+40*60)*1000,(T0+51*60)*1000,
                                 marking_mode="manual",manual_lines=[line])
        self.assertEqual(len(signals),1)
        ok,reason=confirm_v4(bs,signals[0])
        self.assertTrue(ok,reason)
        self.assertEqual(signals[0]["line_source"],"user")
        self.assertGreater(signals[0]["signal_ms"],signals[0]["breakout_ms"])

    def test_weak_breakout_body_is_vetoed(self):
        bs,line=bars_v3()
        signals,_=causal_signals(bs,60,(T0+40*60)*1000,(T0+51*60)*1000,
                                 marking_mode="manual",manual_lines=[line])
        # Modify only previously completed breakout candle after signal
        # captured; tests the frozen quality gate, not a real backtest.
        bs[45]["open"]=100.1
        self.assertEqual(confirm_v4(bs,signals[0])[1],"weak_breakout_body")

    def test_cannot_leak_future_incomplete_candle(self):
        bs,line=bars_v3()
        sig={"timeframe_seconds":60,
             "signal_ms":bs[-1]["time"]*1000,
             "eligible_ms":(bs[-1]["time"]+60)*1000}
        with self.assertRaisesRegex(ValueError,"not closed"):
            confirm_v4(bs,sig)

    def test_same_marked_line_is_not_reused(self):
        bs,line=bars_v3()
        signals,_=causal_signals(bs,60,(T0+40*60)*1000,(T0+51*60)*1000,
                                 marking_mode="manual",manual_lines=[line])
        kept,reasons=gate_signals(bs,signals+signals,60)
        self.assertEqual(len(kept),1)
        self.assertEqual(reasons["repeated_same_marked_microtrend"],1)

    def test_proxy_zones_require_two_prior_confirmed_touches(self):
        # Strong repeated swing points, separated by >5 bars.
        bs=[]
        for i in range(65):
            x=100.0
            low=99.4;hi=100.6
            if i in (15,31,47):
                low=96.;x=98.
            if i in (22,38,54):
                hi=104.;x=102.
            bs.append({"time":T0+i*60,"open":x,"high":hi,
                       "low":low,"close":x,"quote_updates":30})
        zone=proxy_zones_repeated(bs,(T0+65*60)*1000)
        self.assertIsNotNone(zone)
        self.assertEqual(zone.source,"proxy")
        self.assertLess(zone.support_high,zone.resistance_low)
        # No two confirmed high/low swing touches.
        flat=[{**b,"high":100.8,"low":99.2} for b in bs]
        self.assertIsNone(proxy_zones_repeated(flat,(T0+65*60)*1000))

    def test_manual_mark_provenance_mandatory(self):
        with self.assertRaisesRegex(ValueError,"must be supplied"):
            experiment_day("absent.csv",DAYS[0],marking_mode="manual")

    def test_only_predeclared_historical_windows_allowed(self):
        with self.assertRaisesRegex(ValueError,"predeclared"):
            experiment_day("absent.csv","20260110")

    def fixture_dir(self):
        tmp=tempfile.TemporaryDirectory()
        folder=Path(tmp.name)
        for date in DAYS:
            (folder/f"xau_pa_v4_{date}.json").write_text(json.dumps(example_report(date)))
        return tmp,folder

    def test_scorecard_all_10_dates_and_global_position_gate(self):
        tmp,folder=self.fixture_dir()
        with tmp:
            r=evaluate(folder)
            self.assertFalse(r["approved_to_trade"])
            self.assertFalse(r["fidelity_to_user_manual_lines_verified"])
            self.assertTrue(r["one_shared_position_across_timeframes"])
            self.assertEqual(len(r["clean_dates"]["september"]),5)
            self.assertEqual(len(r["clean_dates"]["october"]),5)
            self.assertEqual(r["result"]["SHARED"]["v4_confirmed"]["double"]["september"]["net_usd_per_oz"],-10)
            self.assertIn("NÃO as linhas reais",markdown(r))

    def test_missing_source_day_rejected(self):
        tmp,folder=self.fixture_dir()
        with tmp:
            (folder/f"xau_pa_v4_{DAYS[0]}.json").unlink()
            with self.assertRaisesRegex(ValueError,"Missing/ambiguous"):
                evaluate(folder)

    def test_bad_data_day_must_be_quarantined_entirely(self):
        tmp,folder=self.fixture_dir()
        with tmp:
            date=DAYS[0]
            (folder/f"xau_pa_v4_{date}.json").unlink()
            (folder/f"quarantine_{date}.json").write_text(json.dumps({
                "day":date,"whole_source_excluded":True,
                "trades_included":0,"reason":"crossed ask/bid"
            }))
            r=evaluate(folder)
            self.assertEqual(len(r["clean_dates"]["september"]),4)
            self.assertEqual(len(r["quarantined_days"]),1)

    def test_claim_to_have_real_mt5_fills_is_not_accepted(self):
        tmp,folder=self.fixture_dir()
        with tmp:
            path=folder/f"xau_pa_v4_{DAYS[0]}.json"
            r=json.loads(path.read_text())
            r["market_feed_not_mt5_broker"]=False
            path.write_text(json.dumps(r))
            with self.assertRaisesRegex(ValueError,"Unverified source"):
                evaluate(folder)


if __name__=="__main__":
    unittest.main()
