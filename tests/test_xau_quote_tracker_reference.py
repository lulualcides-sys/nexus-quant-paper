"""Adversarial offline XAUUSD quote-Tracker tests; synthetic candles != backtest."""
import csv
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from research.xau_quote_tracker_reference import (
    QuotePolicy, signal, fib_levels, scan_closed, scan_csv,
)

T0 = int(datetime(2026, 11, 9, 13, 0, tzinfo=timezone.utc).timestamp())
P = QuotePolicy()


def bars(n=26, tf=60):
    return [
        {"time": T0 + i*tf, "open": 2005.0, "high": 2010.0,
         "low": 2000.0, "close": 2005.0,
         "tick_volume": 100, "spread_points": 30}
        for i in range(n)
    ]


def buy_data():
    b = bars()
    b[22] = {**b[22], "open": 2002.0, "high": 2009.0,
             "low": 1998.5, "close": 2007.0,
             "tick_volume": 240, "spread_points": 35}
    return b


def sell_data():
    b = bars()
    b[22] = {**b[22], "open": 2008.0, "high": 2011.5,
             "low": 2001.5, "close": 2003.0,
             "tick_volume": 240, "spread_points": 35}
    return b


class QuoteTrackerTests(unittest.TestCase):
    def test_buy_is_closed_sweep_reclaim_with_quote_activity(self):
        b=buy_data()
        self.assertEqual(signal(b,22,24,P),1)
        arrows=scan_closed(b,24,P)
        self.assertEqual(len(arrows),1)
        self.assertEqual(arrows[0]["side"],"BUY")
        self.assertTrue(arrows[0]["quote_activity_only"])

    def test_sell_is_symmetric(self):
        b=sell_data()
        self.assertEqual(signal(b,22,24,P),-1)
        self.assertEqual(scan_closed(b,24,P)[0]["side"],"SELL")

    def test_never_emit_on_unconfirmed_candle(self):
        b=buy_data()
        self.assertEqual(signal(b,22,21,P),0)
        self.assertEqual(signal(b,25,24,P),0)
        self.assertEqual(scan_closed(b,21,P),[])
        self.assertEqual(scan_closed(b,24,P)[0]["side"],"BUY")

    def test_next_bar_changes_cannot_repaint(self):
        b=buy_data()
        baseline=signal(b,22,24,P)
        b[23]={**b[23],"high":4000.0,"close":4000.0,"low":2000.0}
        b[24]={**b[24],"high":6000.0,"close":6000.0,"low":2000.0}
        self.assertEqual(signal(b,22,24,P),baseline)

    def test_tick_volume_is_only_quote_activity_and_zero_rejected(self):
        b=buy_data()
        b[22]["tick_volume"]=0
        self.assertEqual(signal(b,22,24,P),0)
        b=buy_data()
        b[22]["tick_volume"]=105
        self.assertEqual(signal(b,22,24,P),0)

    def test_absent_spread_fails_closed_without_inventing_quotes(self):
        b=buy_data()
        b[22]["spread_points"]=0
        self.assertEqual(signal(b,22,24,P),0)

    def test_expensive_spread_rejected(self):
        b=buy_data()
        b[22]["spread_points"]=400
        self.assertEqual(signal(b,22,24,P),0)

    def test_wick_and_close_rejection_required(self):
        b=buy_data()
        b[22]["open"]=1998.6 # no lower wick
        self.assertEqual(signal(b,22,24,P),0)
        b=buy_data()
        b[22]["close"]=2001.0 # close location fails
        self.assertEqual(signal(b,22,24,P),0)

    def test_no_sweep_no_signal(self):
        b=buy_data()
        b[22]["low"]=2000.5
        self.assertEqual(signal(b,22,24,P),0)

    def test_oversized_candle_rejected_with_preceding_atr(self):
        b=buy_data()
        b[22]["low"]=1960.0
        self.assertEqual(signal(b,22,24,P),0)

    def test_weekend_or_missing_candles_rejects_instead_of_filling(self):
        b=buy_data()
        b[10]["time"]-=86400
        self.assertEqual(signal(b,22,24,P),0)

    def test_broker_quote_spread_is_not_contracts_or_aggression(self):
        b=buy_data()
        b[22]["volume_real"]=100000
        b[22]["aggressor_buy"]=9000
        # Neither field may influence result; gold reference uses only quote count.
        self.assertEqual(signal(b,22,24,P),1)

    def test_m5_and_broker_tick_size_rounding(self):
        b=buy_data()
        for i,row in enumerate(b): row["time"]=T0 + 300*i
        self.assertEqual(signal(b,22,24,QuotePolicy(timeframe_seconds=300)),1)
        levels=fib_levels(b[22],1,0.01)
        self.assertEqual(levels,{"0":1998.5,"50":2003.75,"100":2009.,
                                 "200":2019.5,"-100":1988.})
        levels=fib_levels(b[22],-1,0.05)
        self.assertEqual(levels["0"],2009.0)
        self.assertEqual(levels["50"],2003.75)

    def test_invalid_policy_does_not_silently_change_market(self):
        with self.assertRaises(ValueError):
            signal(buy_data(),22,24,QuotePolicy(timeframe_seconds=900))
        with self.assertRaises(ValueError):
            scan_closed(buy_data(),25,QuotePolicy(point=0))

    def test_strict_offline_csv_and_explicit_forming_last_row(self):
        data=buy_data()
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/"gold.csv"
            keys=["symbol","time_utc","open","high","low","close",
                  "tick_volume","spread_points"]
            with file.open("w",encoding="utf-8",newline="") as f:
                rd=csv.DictWriter(f,fieldnames=keys)
                rd.writeheader()
                for b in data:
                    rd.writerow({"symbol":"XAUUSD.a",
                        "time_utc":datetime.fromtimestamp(b["time"],timezone.utc).isoformat(),
                        **{k:b[k] for k in keys if k not in ("symbol","time_utc")}})
            result=scan_csv(file,P)
            self.assertEqual(result["closed_signals"],1)
            self.assertEqual(result["symbol"],"XAUUSD.a")
            self.assertFalse(result["real_aggressor_delta_available"])
            self.assertEqual(result["orders_sent"],0)
            self.assertFalse(result["profitability_tested"])
            self.assertTrue(result["last_row_excluded_as_forming"])
            s=file.read_text().replace("XAUUSD.a","WINZ26",1)
            file.write_text(s)
            with self.assertRaisesRegex(ValueError,"Only XAUUSD"):
                scan_csv(file,P)

    def test_optional_liquidity_zone_requires_repeated_previous_touches(self):
        b=buy_data()
        for old in b[2:22]:
            old["low"]=2001.0
        b[5]["low"]=2000.0
        # One old print at the extreme is not a verified zone.
        self.assertEqual(signal(b,22,24,P),1)
        self.assertEqual(signal(b,22,24,QuotePolicy(require_liquidity_zone=True)),0)
        b[12]["low"]=2000.05
        self.assertEqual(signal(b,22,24,QuotePolicy(require_liquidity_zone=True)),1)

    def test_optional_liquidity_zone_does_not_relabel_future_bars(self):
        b=sell_data()
        policy=QuotePolicy(require_liquidity_zone=True)
        self.assertEqual(signal(b,22,24,policy),-1)
        b[23]={**b[23],"low":1500.0,"high":2600.0,"close":2005.0}
        self.assertEqual(signal(b,22,24,policy),-1)

    def test_csv_wrong_timeframe_is_rejected_not_resampled(self):
        data=buy_data()
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/"gold_m5.csv"
            keys=["symbol","time_utc","open","high","low","close",
                  "tick_volume","spread_points"]
            with file.open("w",encoding="utf-8",newline="") as f:
                writer=csv.DictWriter(f,fieldnames=keys)
                writer.writeheader()
                for i,b in enumerate(data):
                    writer.writerow({"symbol":"XAUUSD.a",
                       "time_utc":datetime.fromtimestamp(T0+300*i,timezone.utc).isoformat(),
                       **{k:b[k] for k in keys if k not in ("symbol","time_utc")}})
            with self.assertRaisesRegex(ValueError,"no contiguous candles"):
                scan_csv(file,QuotePolicy(timeframe_seconds=60))
            self.assertEqual(scan_csv(file,QuotePolicy(timeframe_seconds=300))["closed_signals"],1)

    def test_chart_has_public_geometry_labels_and_reconnect_recovery(self):
        m=Path("indicators/mt5/NQ_XAU_Quote_Tracker_Research.mq5").read_text(encoding="utf-8")
        for expected in ("OBJ_TEXT", "ENTRADA 50%", "ALVO 200%",
                         "STOP -100%", "COMPRA", "VENDA",
                         "InpRequireLiquidityZone", "InpLiquidityToleranceATR",
                         "for(int i=oldestNew;i>=1;i--)"):
            self.assertIn(expected,m,expected)

    def test_source_contains_no_order_routing_or_fake_aggressor(self):
        m=Path("indicators/mt5/NQ_XAU_Quote_Tracker_Research.mq5").read_text(encoding="utf-8")
        self.assertIn("tick_volume",m)
        self.assertIn("BufferBuy[0]=EMPTY_VALUE",m)
        self.assertIn("gLastOpen!=time[0]",m)
        self.assertIn("InpMaxSpreadATR",m)
        self.assertIn("NOT original Tracker",m)
        for banned in ("CopyTicksRange(", "TICK_FLAG_BUY", "TICK_FLAG_SELL",
                       "OrderSend(", "OrderCheck(", "CTrade ", "trade.Buy(",
                       "WebRequest(", "FileOpen("):
            self.assertNotIn(banned,m)


if __name__ == "__main__":
    unittest.main()
