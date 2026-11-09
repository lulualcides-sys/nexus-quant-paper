"""Unit tests for LOCAL read-only WIN M1 + trade-tick provenance.

No actual broker data, network, credentials or orders in CI. Strict synthetic
inputs prove the quality gate; they do NOT show original Tracker equivalence.
"""
import unittest
import tempfile
from pathlib import Path
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace

from research.win_mt5_tick_provenance import (
    local_window,valid_symbol,canonical_m1,aggregate_trade_ticks,
    attach_quality,extract_day,save_private,FLAG_BUY,FLAG_SELL,FLAG_VOLUME,FLAG_LAST
)

START=datetime(2026,11,3,12,0,tzinfo=timezone.utc)

def rate(n,volume=50):
    return {"time":int((START+timedelta(minutes=n)).timestamp()),
            "open":100000.,"high":100010.,"low":99990.,"close":100005.,
            "real_volume":volume}

def trades(n,*,include_side=True,volume=2):
    result=[]
    minute=int((START+timedelta(minutes=n)).timestamp())*1000
    for i in range(25):
        side=FLAG_SELL if i<20 else FLAG_BUY
        flags=FLAG_LAST|FLAG_VOLUME|(side if include_side else 0)
        result.append({"time_msc":minute+1300+i*2300,"flags":flags,
                       "volume_real":volume,"last":100005.})
    return result

class MockMT5:
    TIMEFRAME_M1=1
    COPY_TICKS_TRADE=1
    def __init__(self,rate_count=60):
        self.rates=[rate(i) for i in range(rate_count)]
        self.all_ticks=[t for i in range(rate_count) for t in trades(i)]
        self.called=[]
    def terminal_info(self):
        self.called.append("terminal_info")
        return SimpleNamespace(connected=True)
    def symbol_info(self,symbol):
        self.called.append("symbol_info")
        return SimpleNamespace(trade_tick_size=5)
    def symbol_select(self,symbol,enabled):
        self.called.append("symbol_select")
        return enabled
    def copy_rates_range(self,symbol,timeframe,start,end):
        self.called.append("copy_rates_range")
        return self.rates
    def copy_ticks_range(self,symbol,start,end,flags):
        self.called.append("copy_ticks_range")
        a=start.timestamp()*1000
        b=end.timestamp()*1000
        return [t for t in self.all_ticks if a<=t["time_msc"]<=b]
    def last_error(self):
        return (0,"")
    def order_send(self,*args,**kwargs):
        raise AssertionError("Broker order methods must NEVER be called")

class FlowProvenanceTests(unittest.TestCase):
    def test_local_sp_day_mapped_to_utc_no_guessed_timezone(self):
        a,b=local_window("2026-11-03")
        self.assertEqual(a,datetime(2026,11,3,12,tzinfo=timezone.utc))
        self.assertEqual(b,datetime(2026,11,3,22,tzinfo=timezone.utc))
    def test_only_single_WIN_contract(self):
        self.assertEqual(valid_symbol("winz26"),"WINZ26")
        for s in ("WINFUT","WIND26","WINZ2026","WDOZ26"):
            with self.assertRaises(ValueError):valid_symbol(s)
    def test_valid_25_trades_yield_genuine_delta_minus_30(self):
        aggregate,count=aggregate_trade_ticks(trades(0),START,START+timedelta(minutes=1))
        self.assertEqual(count,25)
        d=attach_quality([rate(0)],aggregate)
        self.assertTrue(d[0]["valid_flow"])
        self.assertEqual(d[0]["buy_volume"],10)
        self.assertEqual(d[0]["sell_volume"],40)
        self.assertEqual(d[0]["delta"],-30)
        self.assertEqual(d[0]["tick_volume_agreement_pct"],0.)
        self.assertEqual(d[0]["classified_share"],1.)
    def test_unknown_side_not_assumed_as_buy_or_sell(self):
        aggregate,_=aggregate_trade_ticks(trades(0,include_side=False),
                                         START,START+timedelta(minutes=1))
        d=attach_quality([rate(0)],aggregate)
        self.assertFalse(d[0]["valid_flow"])
        self.assertEqual(d[0]["unknown_volume"],50)
        self.assertEqual(d[0]["delta"],0)
        self.assertIn("insufficient_aggressor_classification",d[0]["reject_reasons"])
    def test_zero_volume_fake_quote_never_becomes_trade(self):
        ticks=trades(0)
        for t in ticks:
            t["volume_real"]=0
        aggregate,_=aggregate_trade_ticks(ticks,START,START+timedelta(minutes=1))
        d=attach_quality([rate(0)],aggregate)
        self.assertFalse(d[0]["valid_flow"])
        self.assertIsNone(d[0]["delta"])
    def test_disagreement_between_real_volume_and_tick_volume_rejected(self):
        aggregate,_=aggregate_trade_ticks(trades(0),START,START+timedelta(minutes=1))
        d=attach_quality([rate(0,volume=250)],aggregate)
        self.assertFalse(d[0]["valid_flow"])
        self.assertIn("m1_vs_tick_volume_mismatch",d[0]["reject_reasons"])
    def test_duplicate_price_only_tick_cannot_double_count_trades(self):
        original=trades(0)
        quote={"time_msc":original[8]["time_msc"]+1,
               "flags":2,"volume_real":500,"last":100005.}
        agg,_=aggregate_trade_ticks(sorted(original+[quote],key=lambda x:x['time_msc']),START,START+timedelta(minutes=1))
        self.assertEqual(agg[rate(0)["time"]]["buy"]+
                         agg[rate(0)["time"]]["sell"],50.)
    def test_both_aggressor_flags_are_unknown(self):
        rows=trades(0)
        rows[0]["flags"]=FLAG_LAST|FLAG_VOLUME|FLAG_BUY|FLAG_SELL
        agg,_=aggregate_trade_ticks(rows,START,START+timedelta(minutes=1))
        out=attach_quality([rate(0)],agg)
        self.assertEqual(out[0]["unknown_volume"],2)
        self.assertEqual(out[0]["classified_trade_count"],24)
        self.assertFalse(out[0]["valid_flow"])
    def test_official_last_trade_bit_eight_is_not_ask_quote_bit_four(self):
        self.assertEqual(FLAG_LAST,8)
        ticks=trades(0)
        for tick in ticks:
            tick["flags"]=8|(FLAG_BUY if tick["flags"]&FLAG_BUY else FLAG_SELL)
        aggregate,_=aggregate_trade_ticks(ticks,START,START+timedelta(minutes=1))
        self.assertTrue(attach_quality([rate(0)],aggregate)[0]["valid_flow"])
        only_quote=trades(0)
        for tick in only_quote:
            tick["flags"]=4|(FLAG_BUY if tick["flags"]&FLAG_BUY else FLAG_SELL)
        a,_=aggregate_trade_ticks(only_quote,START,START+timedelta(minutes=1))
        self.assertFalse(attach_quality([rate(0)],a)[0]["valid_flow"])

    def test_missing_tick_minutes_are_not_filled(self):
        agg,_=aggregate_trade_ticks(trades(0),START,START+timedelta(minutes=1))
        out=attach_quality([rate(0),rate(1)],agg)
        self.assertFalse(out[1]["valid_flow"])
        self.assertIn("no_real_trade_ticks",out[1]["reject_reasons"])
    def test_gap_m1_never_stays_valid_after_gap(self):
        t=trades(0)+trades(2)
        agg,_=aggregate_trade_ticks(t,START,START+timedelta(minutes=3))
        out=attach_quality([rate(0),rate(2)],agg)
        self.assertTrue(out[0]["valid_flow"])
        self.assertFalse(out[1]["valid_flow"])
        self.assertIn("missing_m1_before",out[1]["reject_reasons"])
    def test_out_of_order_m1_rejected(self):
        with self.assertRaises(ValueError):
            canonical_m1([rate(0),rate(0)],START,START+timedelta(hours=1))
    def test_out_of_order_ticks_rejected(self):
        t=trades(0)
        t[3]["time_msc"]=t[2]["time_msc"]-1
        with self.assertRaises(ValueError):
            aggregate_trade_ticks(t,START,START+timedelta(minutes=1))
    def test_read_only_mt5_interface_end_to_end_mock(self):
        mock=MockMT5()
        out,quality=extract_day(mock,symbol="WINZ26",date_string="2026-11-03",
                                now_utc=datetime(2026,11,9,tzinfo=timezone.utc))
        self.assertEqual(quality["candles"],60)
        self.assertEqual(quality["valid_flow_minutes"],60)
        self.assertEqual(quality["orders_sent"],0)
        self.assertNotIn("order_send",mock.called)
        with tempfile.TemporaryDirectory() as td:
            receipt=save_private([{"minutes":out,"quality":quality}],
                                 output_directory=td)[0]
            self.assertTrue(Path(receipt["file"]).exists())
            self.assertEqual(len(receipt["sha256"]),64)
    def test_no_future_data_extraction(self):
        with self.assertRaisesRegex(ValueError,"future or incomplete"):
            extract_day(MockMT5(),symbol="WINZ26",date_string="2026-11-03",
                        now_utc=datetime(2026,11,3,13,tzinfo=timezone.utc))
    def test_source_has_no_broker_orders_or_uploads(self):
        code=Path("research/win_mt5_tick_provenance.py").read_text(encoding="utf-8")
        for banned in ("order_send(", "requests.post(", "account_info(",
                       "login(", "github.com/api", "ftp://"):
            self.assertNotIn(banned,code)

if __name__=="__main__":
    unittest.main()
