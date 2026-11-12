"""Tests of causal rolling S/R marks and independently audited M1/M5 fills.

Synthetic fixtures exercise chronology, source integrity and risk gates;
synthetic PnL is never presented as real backtest performance.
"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research.xau_pa_rolling_zones_v5 import (
    FEBRUARY,JULY,DAYS,ARMS,COSTS,rolling_confirmed_zones,
    signals_for,experiment_day,
)
from research.xau_pa_rolling_zones_v5_scorecard import audit,as_markdown
from research.xau_pa_manual_rules_v3 import (
    MarkedZones,causal_signals,
)


T0=1781280000


def marks_bars(tf=60,n=70):
    bars=[]
    for i in range(n):
        price=100.
        low=99.4;high=100.6
        if i in (8,23,39,55):
            low=96.;price=98.
        if i in (14,30,46,62):
            high=104.;price=102.
        bars.append({
            "time":T0+i*tf,"open":price,"close":price,
            "low":low,"high":high,"quote_updates":30,
        })
    return bars


def evidence_day(day):
    frames={}
    for tf in ("M1","M5","SHARED"):
        frames[tf]={}
        for mode in ARMS:
            frames[tf][mode]={
                "signals":2,
                "setups":{"break_retest":1,"range_rejection":1},
                "reasons":{},
                "costs":{},
            }
            for cost in COSTS:
                pnl=2.0 if mode=="v5_rolling" else -1.0
                row={
                    "signals":2,"filled":1,
                    "net_usd_per_oz":pnl,
                    "rejected":{"wide_spread":0},
                    "trades":[{"setup":"break_retest",
                               "reason":"TARGET" if pnl>0 else "STOP",
                               "net_usd_per_oz":pnl}],
                }
                if tf=="SHARED":
                    row["one_global_position_per_symbol"]=True
                frames[tf][mode]["costs"][cost]=row
    return {
        "day":day,
        "source":{"date_utc":day,"sha256":"d"*64,
                  "raw_quote_rows":15000},
        "source_mark_mode":"proxy",
        "manual_drawings_reproduced":False,
        "same_quotes_and_exec_for_both_arms":True,
        "one_shared_XAUUSD_position":True,
        "not_a_mt5_broker_feed":True,
        "approved_for_real_trades":False,
        "warming_period_utc":"09:00-12:00",
        "trading_period_utc":"12:00-21:00",
        "results":frames,
    }


class CausalZoneResearch(unittest.TestCase):
    def test_two_repeated_confirmed_swings_construct_region(self):
        bars=marks_bars()
        start=(bars[-1]["time"]+60)*1000
        z=rolling_confirmed_zones(tuple(bars),start,60)
        self.assertIsInstance(z,MarkedZones)
        self.assertEqual(z.source,"proxy")
        self.assertLess(z.support_high,z.resistance_low)
        self.assertEqual(z.created_ms,start)

    def test_one_spike_does_not_create_false_repeated_region(self):
        bs=marks_bars()
        for i,b in enumerate(bs):
            if i not in (15,):
                b["low"]=99.4
            if i not in (30,):
                b["high"]=100.6
        z=rolling_confirmed_zones(tuple(bs),(bs[-1]["time"]+60)*1000,60)
        self.assertIsNone(z)

    def test_provider_rejects_future_incomplete_candle(self):
        bs=marks_bars()
        with self.assertRaisesRegex(ValueError,"Future bar"):
            rolling_confirmed_zones(tuple(bs),bs[-1]["time"]*1000,60)

    def test_region_changes_only_on_future_closed_bars(self):
        bs=marks_bars()
        old=rolling_confirmed_zones(tuple(bs),(bs[-1]["time"]+60)*1000,60)
        # Future, unseen quote prices must not mutate an already-computed zone.
        bs.append({"time":bs[-1]["time"]+60,"open":10000.,
                   "close":10000.,"high":10001.,"low":1.})
        self.assertEqual(old,rolling_confirmed_zones(
            tuple(bs[:-1]),bs[-2]["time"]*1000+60000,60
        ))

    def test_stops_and_targets_unchanged_in_manual_mode(self):
        bs=marks_bars(n=80)
        z=MarkedZones(95.5,96.5,103.5,104.5,bs[39]["time"]*1000,"user")
        start=(bs[39]["time"]+60)*1000
        end=(bs[79]["time"]+60)*1000
        modes=signals_for(bs,60,start,end,mode="manual",lines=(),zones=z)
        self.assertEqual(modes["v4_fixed"][0],modes["v5_rolling"][0])

    def test_signal_candle_never_part_of_mark_provider(self):
        bs=marks_bars(n=85)
        start=(bs[39]["time"]+60)*1000
        end=(bs[81]["time"]+60)*1000
        seen=[]
        def forbidden_future_provider(past,candidate_start,tf):
            self.assertTrue(all((x["time"]+tf)*1000<=candidate_start
                                for x in past))
            self.assertTrue(all(x["time"]*1000<candidate_start for x in past))
            seen.append(candidate_start)
            return None
        causal_signals(bs,60,start,end,marking_mode="proxy",
                       proxy_dynamic_zone_fn=forbidden_future_provider)
        self.assertGreater(len(seen),30)

    def test_rejects_dates_chosen_after_results(self):
        with self.assertRaisesRegex(ValueError,"preregistered"):
            experiment_day("none.csv","20261212")

    def test_never_guess_manual_user_mark_files(self):
        with self.assertRaisesRegex(ValueError,"Manual drawings"):
            experiment_day("none.csv",DAYS[0],mode="manual")

    def fixture(self):
        tmp=tempfile.TemporaryDirectory();folder=Path(tmp.name)
        for day in DAYS:
            (folder/f"xau_pa_v5_{day}.json").write_text(json.dumps(evidence_day(day)))
        return tmp,folder

    def test_summary_records_both_costs_global_position_and_source(self):
        tmp,folder=self.fixture()
        with tmp:
            r=audit(folder)
            self.assertTrue(r["no_real_user_drawings_supplied"])
            self.assertFalse(r["approved_for_live"])
            self.assertTrue(r["one_global_symbol_lock"])
            self.assertEqual(len(r["clean_days"]["february"]),5)
            self.assertEqual(len(r["clean_days"]["july"]),5)
            self.assertEqual(r["results"]["SHARED"]["v5_rolling"]["double"]["february"]["net_usd_per_oz"],10.0)
            self.assertIn("Sem desenhos manuais reais",as_markdown(r))

    def test_missing_date_fails_closed(self):
        tmp,folder=self.fixture()
        with tmp:
            (folder/f"xau_pa_v5_{DAYS[0]}.json").unlink()
            with self.assertRaisesRegex(ValueError,"Missing or conflicting"):
                audit(folder)

    def test_whole_feed_excluded_after_bad_quote(self):
        tmp,folder=self.fixture()
        with tmp:
            day=DAYS[0]
            (folder/f"xau_pa_v5_{day}.json").unlink()
            (folder/f"quarantine_{day}.json").write_text(json.dumps({
                "day":day,"whole_source_quarantined":True,
                "included_fills":0,"reason":"invalid crossed BID/ASK"
            }))
            result=audit(folder)
            self.assertEqual(len(result["clean_days"]["february"]),4)
            self.assertEqual(len(result["quarantined_whole_sessions"]),1)

    def test_broker_claim_or_bad_ledger_cannot_pass_audit(self):
        tmp,folder=self.fixture()
        with tmp:
            p=folder/f"xau_pa_v5_{DAYS[0]}.json"
            original=json.loads(p.read_text())
            original["approved_for_real_trades"]=True
            p.write_text(json.dumps(original))
            with self.assertRaisesRegex(ValueError,"Unverifiable"):
                audit(folder)
            original["approved_for_real_trades"]=False
            original["results"]["M5"]["v5_rolling"]["costs"]["double"]["filled"]=99
            p.write_text(json.dumps(original))
            with self.assertRaisesRegex(ValueError,"Broken chronological"):
                audit(folder)


if __name__=="__main__":
    unittest.main()
