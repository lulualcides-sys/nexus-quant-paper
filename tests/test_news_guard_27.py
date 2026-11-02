"""Deterministic, offline, causality and entry/exits tests for official macro filter."""
import json
import os
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from math import sin
from pathlib import Path
from unittest.mock import patch

from src import news_guard as guard
from src import gold_forward as gold
from src import leveraged_gold as lev
from src import experimental_h1 as h1
from src import bb_rebound_mtf as m15
from src import momentum60_shadow as mom
from src.strategies import make_indicators
from research.screen_v2 import aggregate_hourly_to_h4


def epoch(s):
    return int(datetime.fromisoformat(s.replace("Z","+00:00")).timestamp())


T0 = epoch("2026-09-15T00:00:00Z")


def hourly(n=1300):
    rows=[]
    for i in range(n):
        p=2500+i*.15+sin(i/17)*3
        rows.append({"time":T0+3600*i,"open":p,"high":p+2,
                     "low":p-2,"close":p+.1})
    return rows


def quarter(n=280):
    rows=[]
    for i in range(n):
        p=1.37+sin(i/19)*.001
        rows.append({"time":T0+900*i,"open":p,"high":p+.001,
                     "low":p-.001,"close":p+.00005})
    return rows


class NewsGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=json.loads(guard.CALENDAR.read_text(encoding="utf-8"))

    def test_calendar_all_official_sources_and_coverage(self):
        parsed=guard.validate(self.raw)
        self.assertGreaterEqual(len(parsed["intervals"]),10)
        for e in parsed["intervals"]:
            self.assertEqual(e["scope"],guard.MARKETS)
            self.assertTrue(e["source"].startswith("https://"))
            self.assertLess(e["start"],e["end"])

    def test_nfp_0830_eastern_is_1330_utc_after_dst_switch(self):
        market="XAUUSD"
        before=guard.evaluate(market,epoch("2026-11-06T12:29:59Z"),calendar=self.raw)
        first=guard.evaluate(market,epoch("2026-11-06T12:30:00Z"),calendar=self.raw)
        on=guard.evaluate(market,epoch("2026-11-06T13:30:00Z"),calendar=self.raw)
        after=guard.evaluate(market,epoch("2026-11-06T14:15:00Z"),calendar=self.raw)
        self.assertEqual(before["status"],"clear")
        self.assertEqual(first["status"],"blocked_high_impact")
        self.assertEqual(on["status"],"blocked_high_impact")
        self.assertEqual(after["status"],"clear")
        self.assertIn("bls-nfp-2026-11-06",on["event_ids"])

    def test_no_calendar_time_travel_historical_replay(self):
        old=guard.evaluate("EURUSD",epoch("2026-07-01T14:00:00Z"),calendar=self.raw)
        self.assertEqual(old["status"],"unknown")
        self.assertFalse(old["allowed"])

    def test_fomc_full_et_day_no_invented_time(self):
        raw=deepcopy(self.raw)
        raw["fresh_until_utc"]="2026-12-15T00:00:00Z"
        status=guard.evaluate("USDJPY",epoch("2026-12-09T20:00:00Z"),calendar=raw)
        self.assertEqual(status["status"],"blocked_high_impact")
        self.assertIn("fed-fomc-2026-12-09",status["event_ids"])
        after=guard.evaluate("USDJPY",epoch("2026-12-10T05:00:00Z"),calendar=raw)
        self.assertEqual(after["status"],"clear")

    def test_stale_and_unavailable_fail_closed_only_if_enabled(self):
        now=epoch("2026-11-17T14:00:00Z")
        r=guard.evaluate("EURUSD",now,calendar=self.raw)
        self.assertEqual(r["status"],"unknown")
        self.assertFalse(r["allowed"])
        self.assertTrue(guard.entry_permission("EURUSD",now,enabled=False,calendar=None))
        self.assertFalse(guard.entry_permission("EURUSD",now,enabled=True,calendar=self.raw))
        with patch.object(guard,"load",side_effect=FileNotFoundError("missing")):
            self.assertFalse(guard.entry_permission("EURUSD",now,enabled=True))

    def test_source_id_time_and_market_validation(self):
        cases=[]
        bad=deepcopy(self.raw);bad["events"][0]["source"]="http://trading.example.com";cases.append(bad)
        bad=deepcopy(self.raw);bad["events"][0]["source"]=None;cases.append(bad)
        bad=deepcopy(self.raw);bad["events"].append(deepcopy(bad["events"][0]));cases.append(bad)
        bad=deepcopy(self.raw);bad["events"][0]["time_et"]="25:99";cases.append(bad)
        bad=deepcopy(self.raw);bad["events"][0]["affected_markets"]=["UNKNOWN"];cases.append(bad)
        bad=deepcopy(self.raw);bad["observed_at_utc"]="2027-01-01T00:00:00Z";cases.append(bad)
        for raw in cases:
            with self.assertRaises(ValueError):
                guard.validate(raw)

    def test_only_new_gold_h4_entries_guarded(self):
        h4=aggregate_hourly_to_h4(hourly())
        ind=make_indicators(h4)
        i=len(h4)-2
        row=h4[i]
        book={"equity":gold.CAPITAL,"closed":[],"position":None}
        def signal(rule,bars,inds,j):
            return 1 if j==i-1 else 0
        with patch.object(gold,"sign",side_effect=signal), \
             patch.object(gold,"entry_permission",return_value=False):
            gold.evaluate_bar(book,"channel20",h4,ind,i)
        self.assertIsNone(book["position"])
        # A protective stop remains enforceable even if calendar unavailable.
        book["position"]={"side":1,"entry":row["open"]+4,"qty":1,
                          "stop":row["open"]+3,"target":row["open"]+20,
                          "held_bars":2,"start":row["time"]-14400}
        with patch.object(gold,"entry_permission",return_value=False):
            gold.evaluate_bar(book,"channel20",h4,ind,i)
        self.assertIsNone(book["position"])
        self.assertEqual(len(book["closed"]),1)

    def test_only_new_leveraged_entries_guarded(self):
        h4=aggregate_hourly_to_h4(hourly())
        ind=make_indicators(h4)
        i=len(h4)-2
        b=lev.fresh(h4)["books"]["lev_channel20"]
        with patch.object(lev,"sign",side_effect=lambda rule,bars,inds,j:1 if j==i-1 else 0), \
             patch.object(lev,"entry_permission",return_value=False):
            lev.one_bar(b,"lev_channel20",h4,ind,i,mode=lev.LIVE_POLICY)
        self.assertIsNone(b["position"])
        price=h4[i]["open"]
        b["position"]={"side":1,"entry":price+3,"start":h4[i]["time"]-14400,
                       "qty":1,"stop":price+1,"target":None,
                       "borrowed":1,"held_bars":0,"notional_leverage":1,
                       "mode":lev.LIVE_POLICY}
        with patch.object(lev,"entry_permission",return_value=False):
            lev.one_bar(b,"lev_channel20",h4,ind,i,mode=lev.LIVE_POLICY)
        self.assertIsNone(b["position"])
        self.assertEqual(len(b["closed"]),1)

    def test_h1_signal_blocked_but_active_stop_exits(self):
        rows=hourly(400)
        inds=make_indicators(rows)
        i=350
        book=h1.book()
        with patch.object(h1,"setup",return_value=1), \
             patch.object(h1,"entry_permission",return_value=False):
            h1.step(book,"EURUSD","rsi50",rows,inds,i)
        self.assertIsNone(book["position"])
        self.assertIn("calendário",book["last_reason"])
        p=rows[i]["open"]
        book["position"]={"side":1,"entry":p+5,"start":rows[i]["time"]-3600,
                          "qty":1,"stop":p+3,"initial_r":2,
                          "best_close":p+5,"held_bars":2}
        with patch.object(h1,"entry_permission",return_value=False):
            h1.step(book,"EURUSD","rsi50",rows,inds,i)
        self.assertIsNone(book["position"])
        self.assertEqual(len(book["closed"]),1)

    def test_m15_and_momentum60_block_eligible_new_entry(self):
        rows=quarter()
        hourly_bars=m15.to_h1(rows)
        h1ind=make_indicators(hourly_bars)
        m15ind=make_indicators(rows)
        book=m15.initial(rows)
        with patch.object(m15,"h1_trend_confirmation",return_value=1), \
             patch.object(m15,"m15_sma20_pullback",return_value=True), \
             patch.object(m15,"entry_permission",return_value=False):
            m15.step(book,rows,275,hourly_bars,h1ind,m15ind)
        self.assertIsNone(book["position"])
        self.assertIn("calendário",book["last_reason"])

        h4=aggregate_hourly_to_h4(hourly())
        momind=make_indicators(h4)
        i=len(h4)-2
        shadow=mom.fresh(h4)
        with patch.object(mom,"candidate_signal",side_effect=lambda rule,bars,inds,j:1 if j==i-1 else 0), \
             patch.object(mom,"entry_permission",return_value=False):
            mom.step(shadow,h4,momind,i)
        self.assertEqual(len(shadow["entries"]),0)
        self.assertIsNone(shadow["position"])


    def test_simultaneous_bea_gdp_and_pce_block_together(self):
        stamp=epoch("2026-11-25T13:30:00Z")
        # Snapshot fresh only through Nov 16. Model a new audited snapshot
        # (NOT a historical backfill) to test the future multi-event overlap.
        audited=deepcopy(self.raw)
        audited["fresh_until_utc"]="2026-11-27T00:00:00Z"
        result=guard.evaluate("USDCAD",stamp,calendar=audited)
        self.assertEqual(result["status"],"blocked_high_impact")
        self.assertEqual(set(result["event_ids"]),
                         {"bea-gdp-2026-11-25","bea-pce-2026-11-25"})

    def test_each_market_covered_and_planned_bot_census_is_27(self):
        from research.backtest_27 import all_ids
        ids=all_ids()
        self.assertEqual(len(ids),27)
        for _,(_,market) in ids.items():
            self.assertIn("USDCAD" if market=="USDCAD" else market,
                          guard.MARKETS)

    def test_existing_m15_stop_still_exits_when_news_is_blocked(self):
        rows=quarter()
        hourly_bars=m15.to_h1(rows)
        h1ind=make_indicators(hourly_bars)
        m15ind=make_indicators(rows)
        i=275
        price=rows[i]["open"]
        b=m15.initial(rows)
        b["position"]={"side":1,"entry":price+0.003,
                       "entry_ts":rows[i]["time"]-900,
                       "qty_usd":1000,"stop":price+0.001,
                       "initial_r":0.002,"stop_policy":"legacy_fixed",
                       "target":price+0.01,"best_close":price+0.003}
        with patch.object(m15,"entry_permission",return_value=False):
            m15.step(b,rows,i,hourly_bars,h1ind,m15ind)
        self.assertIsNone(b["position"])
        self.assertEqual(len(b["closed"]),1)

    def test_existing_momentum60_stop_still_exits_when_news_is_blocked(self):
        h4=aggregate_hourly_to_h4(hourly())
        ind=make_indicators(h4)
        i=len(h4)-2
        price=h4[i]["open"]
        b=mom.fresh(h4)
        b["position"]={"side":1,"entry":price+3,
                       "start":h4[i]["time"]-14400,"qty":1,
                       "stop":price+1,"target":price+40,
                       "held_bars":2}
        with patch.object(mom,"entry_permission",return_value=False):
            mom.step(b,h4,ind,i)
        self.assertIsNone(b["position"])
        self.assertEqual(len(b["closed"]),1)

    def test_off_by_default_regression_for_old_backtests(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertTrue(guard.entry_permission("XAUUSD",epoch("2026-04-01T00:00:00Z")))
        with patch.dict(os.environ,{"NEXUS_NEWS_GUARD_ENABLED":"1"}):
            self.assertFalse(guard.entry_permission("XAUUSD",epoch("2026-04-01T00:00:00Z")))


if __name__=="__main__":
    unittest.main()
