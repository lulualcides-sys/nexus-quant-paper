"""No-lookahead, state-transition, manual-mark and session tests for v3.

These synthetic prices TEST code behavior only. They are NOT XAU profits.
"""
from datetime import datetime,timezone
from pathlib import Path
import json
import math
import tempfile
import unittest
from unittest.mock import patch

from research.xau_pa_manual_rules_v3 import (
    Trendline,MarkedZones,closed_pivots,proxy_line,parse_mark_file,
    sideways,line_crossed,retest_signal,range_signal,causal_signals,
    one_day,utc_ms,DAYS,
)
from research.xau_price_action_m1m5 import Settings


T0=int(datetime(2026,11,2,9,tzinfo=timezone.utc).timestamp())


def bar(i,*,close=100.,op=None,low=98.9,high=101.1,tf=60):
    return {"time":T0+i*tf,"open":close if op is None else op,
            "close":close,"low":low,"high":high,"quote_updates":25}


def breakout_bars(side=1):
    bars=[bar(i) for i in range(52)]
    if side==1:
        # Descending LTD from (10,103) to (30,101); line(45) = 99.5
        bars[44]=bar(44,close=99.55,op=99.5,high=100.,low=98.9)
        bars[45]=bar(45,close=100.4,op=99.7,high=100.6,low=99.55)
        bars[46]=bar(46,close=100.05,op=99.65,high=100.2,low=99.35)
        line=Trendline("LTD",10,103.,30,101.,(T0+40*60)*1000,"user")
    else:
        # Ascending LTA from (10,97) to (30,99); line(45) = 100.5
        bars[44]=bar(44,close=100.45,op=100.5,high=101.1,low=100.2)
        bars[45]=bar(45,close=99.6,op=100.3,high=100.5,low=99.5)
        bars[46]=bar(46,close=99.95,op=100.30,high=100.65,low=99.7)
        line=Trendline("LTA",10,97.,30,99.,(T0+40*60)*1000,"user")
    return bars,line


def zoning_bars():
    # Close crosses center repeatedly, broad range vs average true range.
    series=[100,101,102,101,100,99,98,99]*7
    bars=[bar(i,close=float(v),op=v-.05,
              high=v+.22,low=v-.22)
          for i,v in enumerate(series)]
    bars[48]=bar(48,op=98.12,close=98.88,high=99.0,low=97.9)
    return bars


class ManualPriceActionStateTests(unittest.TestCase):
    def test_buy_waits_break_then_separate_retest(self):
        bars,line=breakout_bars()
        self.assertTrue(line_crossed(bars[44],bars[45],line,45,2.))
        a,diag=causal_signals(bars[:47],60,(T0+40*60)*1000,
                              (T0+51*60)*1000,
                              marking_mode="manual",manual_lines=[line])
        self.assertEqual(a,[],"A breakout candle must never be an entry")
        signals,diag=causal_signals(bars,60,(T0+40*60)*1000,
                             (T0+51*60)*1000,
                             marking_mode="manual",manual_lines=[line])
        self.assertEqual(len(signals),1)
        x=signals[0]
        self.assertEqual(x["setup"],"break_retest")
        self.assertEqual(x["side"],1)
        self.assertEqual(x["line_kind"],"LTD")
        self.assertEqual(x["breakout_ms"],bars[45]["time"]*1000)
        self.assertEqual(x["eligible_ms"],(bars[46]["time"]+60)*1000)
        self.assertGreaterEqual(diag["breakout_waiting_retest"],1)

    def test_sell_waits_lta_break_and_separate_retest(self):
        bars,line=breakout_bars(-1)
        self.assertTrue(line_crossed(bars[44],bars[45],line,45,2.))
        sigs,_=causal_signals(bars,60,(T0+40*60)*1000,
                       (T0+51*60)*1000,
                       marking_mode="manual",manual_lines=[line])
        self.assertEqual(len(sigs),1)
        self.assertEqual(sigs[0]["side"],-1)
        self.assertEqual(sigs[0]["line_kind"],"LTA")
        self.assertGreater(sigs[0]["stop"],bars[46]["high"])

    def test_false_break_not_entered_when_close_falls_back_through_line(self):
        bars,line=breakout_bars()
        bars[46]=bar(46,close=98.5,op=99.8,low=98.3,high=100.)
        sigs,diag=causal_signals(bars,60,(T0+40*60)*1000,
                         (T0+51*60)*1000,
                         marking_mode="manual",manual_lines=[line])
        self.assertEqual(sigs,[])
        self.assertGreaterEqual(diag.get("false_breakout",0),1)

    def test_user_marks_required_no_automatic_range_entry_under_manual_mode(self):
        bars=zoning_bars()
        sigs,diag=causal_signals(bars,60,(T0+40*60)*1000,
                         (T0+56*60)*1000,marking_mode="manual")
        self.assertEqual(sigs,[])
        self.assertIn("missing_user_marks",diag)

    def test_user_marked_range_only_if_sideways(self):
        bars=zoning_bars()
        zones=MarkedZones(97.8,98.2,101.8,102.2,
                          (T0+40*60)*1000,"user")
        r=atr_for_test(bars,48)
        self.assertTrue(sideways(bars,48,r))
        signal=range_signal(bars,48,60,zones)
        self.assertIsNotNone(signal)
        self.assertEqual(signal["side"],1)
        self.assertEqual(signal["setup"],"range_rejection")
        self.assertEqual(signal["marks_source"],"user")
        self.assertGreater(signal["room_limit"],signal["stop"])
        trend=[bar(i,close=100+.32*i,op=100+.32*i-.05,
                   high=100+.32*i+.3,low=100+.32*i-.3)
               for i in range(54)]
        self.assertFalse(sideways(trend,48,atr_for_test(trend,48)))
        self.assertIsNone(range_signal(trend,48,60,zones))

    def test_lta_ltd_must_have_correct_slope_and_preopen_creation(self):
        with self.assertRaisesRegex(ValueError,"LTD must descend"):
            Trendline("LTD",2,100.,10,101.,0,"user").assert_valid(100,60)
        with self.assertRaisesRegex(ValueError,"after trading"):
            Trendline("LTA",2,99.,10,100.,3000,"user").assert_valid(2000,60)

    def test_marks_from_future_rejected(self):
        bars,line=breakout_bars()
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/"marks.json"
            f.write_text(json.dumps({
                "symbol":"XAUUSD","day":"20261102",
                "created_ms":(T0+45*60)*1000,
                "by_timeframe":{"M1":{"range":{
                    "support_low":98.,"support_high":98.3,
                    "resistance_low":101.,"resistance_high":102.}},
                    "M5":{}}
            }))
            with self.assertRaisesRegex(ValueError,"must precede"):
                parse_mark_file(f,"20261102",60,(T0+40*60)*1000,bars)

    def test_manual_line_utc_anchor_maps_to_array_index_not_unix_bar_epoch(self):
        bars,line=breakout_bars()
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/"marks.json"
            f.write_text(json.dumps({
                "symbol":"XAUUSD","day":"20261102",
                "created_ms":(T0+40*60)*1000,
                "by_timeframe":{"M1":{"trendlines":[{
                    "kind":"LTD","x1_ms":bars[10]["time"]*1000,"y1":103.,
                    "x2_ms":bars[30]["time"]*1000,"y2":101.
                }]}}
            }))
            lines,z=parse_mark_file(f,"20261102",60,(T0+41*60)*1000,bars)
            self.assertEqual(len(lines),1)
            self.assertEqual(lines[0].x1,10)
            self.assertEqual(lines[0].x2,30)
            self.assertAlmostEqual(lines[0].value(45),99.5)
            empty,_=parse_mark_file(f,"20261102",300,(T0+41*60)*1000,bars)
            self.assertEqual(empty,[])

    def test_mark_line_cannot_reference_unseen_future_candle(self):
        bars,line=breakout_bars()
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/"marks.json"
            f.write_text(json.dumps({
                "symbol":"XAUUSD","day":"20261102",
                "created_ms":(T0+40*60)*1000,
                "by_timeframe":{"M1":{"trendlines":[{
                    "kind":"LTD",
                    "x1_ms":bars[10]["time"]*1000,"y1":103.,
                    "x2_ms":bars[46]["time"]*1000,"y2":101.
                }]}}
            }))
            with self.assertRaisesRegex(ValueError,"predating"):
                parse_mark_file(f,"20261102",60,(T0+41*60)*1000,bars)

    def test_proxy_mark_is_never_labeled_user_drawn(self):
        bars=zoning_bars()
        zone=__import__("research.xau_pa_manual_rules_v3",
                        fromlist=["proxy_zones"]).proxy_zones(bars[:40],(T0+40*60)*1000)
        self.assertEqual(zone.source,"proxy")
        self.assertNotEqual(zone.source,"user")
        self.assertRaisesRegex(
            ValueError,"Proxy zones presented as manual",
            causal_signals,bars,60,(T0+40*60)*1000,(T0+56*60)*1000,
            marking_mode="manual",manual_zones=zone
        )

    def test_disallows_undocumented_ema_signal(self):
        bars=[bar(i) for i in range(65)]
        out,diag=causal_signals(
            bars,60,(T0+40*60)*1000,(T0+60*60)*1000,
            marking_mode="manual",manual_lines=()
        )
        self.assertFalse(out)
        self.assertNotIn("ema_pullback",str(diag))

    def test_real_quote_run_no_manual_file_fails_closed_before_any_trade(self):
        with self.assertRaisesRegex(ValueError,"No user-supplied drawing"):
            one_day("missing.csv",DAYS[0],marking_mode="manual")


def atr_for_test(bars,i):
    from research.xau_price_action_m1m5 import atr
    return atr(bars,i,14)


if __name__=="__main__":
    unittest.main()
