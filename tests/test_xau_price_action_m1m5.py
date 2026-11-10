"""Synthetic mechanical tests for XAUUSD PA, never evidence of trading profit."""
import csv
from dataclasses import replace
from datetime import datetime,timezone
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research.xau_price_action_m1m5 import (
    Settings, SourceQualityError, atr, backtest_session, candles_from_quotes,
    parse_quotes, range_rejection, resample_completed, scan_signals, simulate_ticks,
)

BASE=int(datetime(2026,6,8,12,0,tzinfo=timezone.utc).timestamp()*1000)


def signal(*,side=1,eligible=BASE+60000,atr_value=1.,stop=99.8,setup="break_retest"):
    return {"setup":setup,"side":side,"atr":atr_value,
            "stop":stop,"signal_ms":eligible-60000,
            "eligible_ms":eligible,"timeframe_seconds":60}


def write_csv(path,count=1800,invalid_at=None,reorder_at=None):
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f)
        w.writerow(["timestamp","askPrice","bidPrice","bidVolume","askVolume"])
        for n in range(count):
            ts=BASE+(n//6)*60000+(n%6)*9000
            bid=2000+math.sin(n/13)*.3+(n//300)*.2
            ask=bid+.14
            if n==invalid_at:ask=bid-.01
            if n==reorder_at:ts=BASE
            w.writerow([ts,ask,bid,300,200])


class XAUPriceActionTests(unittest.TestCase):
    def test_quotes_original_bid_ask_not_fake_aggressor_volume(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"quotes.csv"
            write_csv(p)
            quotes,src=parse_quotes(p,"20260608")
            self.assertEqual(len(quotes),1800)
            self.assertEqual(len(src["sha256"]),64)
            self.assertGreater(quotes[0][2],quotes[0][1])
            bars=candles_from_quotes(quotes,60)
            self.assertEqual(len(bars),300)
            self.assertEqual(bars[0]["quote_updates"],6)

    def test_cannot_clean_one_crossed_tick_then_keep_pnl(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"quotes.csv"
            write_csv(p,invalid_at=801)
            with self.assertRaisesRegex(SourceQualityError,"Invalid crossed"):
                parse_quotes(p,"20260608")

    def test_chronology_strict(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"quotes.csv"
            write_csv(p,reorder_at=700)
            with self.assertRaisesRegex(SourceQualityError,"reordered"):
                parse_quotes(p,"20260608")

    def test_no_incomplete_higher_tf_bar_peeking(self):
        bars=[{"time":BASE//1000+i*60,"open":10.,"close":10.+i,
               "high":11.+i,"low":9.,"quote_updates":5} for i in range(10)]
        c=resample_completed(bars,3,60,300)
        self.assertEqual(c,[])
        c=resample_completed(bars,4,60,300)
        self.assertEqual(len(c),1)
        self.assertEqual(c[0]["close"],bars[4]["close"])
        self.assertEqual(len(resample_completed(bars,8,60,300)),1)
        self.assertEqual(len(resample_completed(bars,9,60,300)),2)

    def test_no_last_unclosed_base_bar_signal(self):
        bars=[{"time":BASE//1000+i*60,"open":100.,"close":100.,
               "high":101.,"low":99.} for i in range(80)]
        with patch("research.xau_price_action_m1m5.candidate",
                   side_effect=lambda bs,i,tf,s: {"eligible_ms":i}):
            r=scan_signals(bars,60,Settings())
            self.assertEqual(len(r),79)
            self.assertEqual(r[-1]["eligible_ms"],78)

    def test_range_rejection_ported_to_dollars_not_win_points(self):
        context=[{"time":i*300,"open":104.,"close":104.,
                  "high":110. if i in (2,8) else 108.,
                  "low":100. if i in (0,7) else 102.}
                 for i in range(12)]
        bars=[{"time":3600,"open":101.3,"close":101.8,
               "high":102.1,"low":100.05}]
        r=range_rejection(bars,0,context,Settings(),2.)
        self.assertEqual(r["setup"],"range_rejection")
        self.assertEqual(r["side"],1)
        self.assertLess(r["stop"],100.05)

    def test_buy_market_ask_and_bid_target_not_ask_target(self):
        r=simulate_ticks([
            (BASE+59000,99.0,99.2),
            (BASE+60000,100.0,100.2), # Entry at 100.3 (ask + 0.1)
            (BASE+65000,101.1,101.4), # ASK above TP, BID still below
            (BASE+70000,101.3,101.5),
        ],[signal()],60,Settings())
        self.assertEqual(r["filled"],1)
        self.assertEqual(r["trades"][0]["entry"],100.3)
        self.assertEqual(r["trades"][0]["reason"],"TARGET")
        self.assertAlmostEqual(r["net_usd_per_oz"],.7)

    def test_sell_market_bid_ask_target(self):
        r=simulate_ticks([
            (BASE+60000,100.0,100.2),
            (BASE+62000,98.5,98.6)
        ],[signal(side=-1,stop=100.5)],60,Settings())
        self.assertEqual(r["trades"][0]["entry"],99.9)
        self.assertEqual(r["trades"][0]["reason"],"TARGET")
        self.assertAlmostEqual(r["net_usd_per_oz"],.9)

    def test_gap_through_stop_worsens_result(self):
        r=simulate_ticks([
            (BASE+60000,100.,100.2),
            (BASE+61000,99.3,99.6)
        ],[signal()],60,Settings())
        self.assertEqual(r["trades"][0]["reason"],"STOP")
        self.assertAlmostEqual(r["trades"][0]["exit"],99.2)
        self.assertAlmostEqual(r["net_usd_per_oz"],-1.4)

    def test_no_fills_before_bar_close_or_after_delay(self):
        early=simulate_ticks([(BASE+59000,100.,100.2)],
                             [signal()],60,Settings())
        self.assertEqual(early["filled"],0)
        late=simulate_ticks([(BASE+95000,100.,100.2)],
                            [signal()],60,Settings())
        self.assertEqual(late["filled"],0)
        self.assertEqual(late["rejected"]["delayed"],1)

    def test_wide_spread_blocks_market_entry(self):
        r=simulate_ticks([(BASE+60000,100.,102.)],
                         [signal()],60,Settings())
        self.assertEqual(r["filled"],0)
        self.assertEqual(r["rejected"]["wide_spread"],1)

    def test_unprofitable_rr_blocks_trade(self):
        settings=replace(Settings(),commission_roundtrip_usd_per_oz=4.)
        r=simulate_ticks([(BASE+60000,100.,100.2)],
                         [signal()],60,settings)
        self.assertEqual(r["filled"],0)
        self.assertEqual(r["rejected"]["uneconomic"],1)

    def test_one_position_at_a_time(self):
        a=signal()
        b=signal(eligible=BASE+120000)
        r=simulate_ticks([(BASE+60000,100.,100.2),
                          (BASE+120000,100.2,100.4),
                          (BASE+125000,101.3,101.5)],
                         [a,b],60,Settings())
        self.assertEqual(r["filled"],1)
        self.assertEqual(r["rejected"]["already_in_position"],1)

    def test_forced_last_tick_close_no_open_position_hidden(self):
        r=simulate_ticks([(BASE+60000,100.,100.2)],
                         [signal()],60,Settings())
        self.assertEqual(r["filled"],1)
        self.assertEqual(r["trades"][0]["reason"],"SESSION_END")

    def test_end_to_end_synthetic_quote_bar_warmup_no_broker_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"quotes.csv"
            write_csv(p)
            r=backtest_session(p,"20260608")
            self.assertFalse(r["approval_for_live"])
            self.assertFalse(r["is_actual_broker_backtest"])
            self.assertFalse(r["gold_contract_size_confirmed"])
            self.assertEqual(r["results"]["M1"]["candles"],300)
            self.assertEqual(r["results"]["M5"]["candles"],60)
            self.assertEqual(r["results"]["M5"]["context"],"M15")
            for tf in ("M1","M5"):
                self.assertLessEqual(r["results"][tf]["filled"],r["results"][tf]["signals"])


if __name__=="__main__":
    unittest.main()
