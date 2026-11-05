"""No-network regression tests for ATLAS V5 stress ranking and cost guards.

Artificial quotes and fake statements are strictly synthetic fixtures.
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch

from research.atlas_v5_cost_aware import (
    ALL_MODELS, V5_CANDIDATES, cost_fraction, v5_candidate,
    MAX_COST_TO_GROSS_TARGET,
)
from research.atlas_v5_loss_ranking import (
    WINDOWS,canonicalize_q26_m5,rank,_loss_analysis,_month_cut,_coverage,
    RESEARCH_CAPITAL_BRL,
)
from research.win_price_data import TZ


def fabricated_bars(n=140):
    origin=datetime(2026,5,18,0,0,tzinfo=TZ)
    return [{
        "time":int((origin+timedelta(minutes=5*k)).astimezone(timezone.utc).timestamp()),
        "open":200000.0,"high":200150.0,"low":199850.0,
        "close":200050.0,"volume":500.0,
    } for k in range(n)]


class AtlasV5ResearchTests(unittest.TestCase):
    def test_cost_floor_is_based_on_nominal_target_not_past_profit(self):
        big={"open":200000,"high":200250,"low":199750,"close":200100}
        small={"open":200000,"high":200040,"low":199960,"close":200010}
        self.assertLess(cost_fraction(big,1),MAX_COST_TO_GROSS_TARGET)
        self.assertGreater(cost_fraction(small,1),MAX_COST_TO_GROSS_TARGET)
        self.assertGreater(cost_fraction(small,-1),MAX_COST_TO_GROSS_TARGET)

    def test_no_future_lookahead_and_freeze_variants(self):
        candles=fabricated_bars()
        with patch("research.atlas_v5_cost_aware.v4_candidate",return_value=1):
            a=[v5_candidate(candles,125,variant) for variant in V5_CANDIDATES]
            self.assertEqual(a,[1,1])
            candles[126]={**candles[126],"close":100000,
                          "high":900000,"low":10000,"volume":99999999}
            self.assertEqual(a,[v5_candidate(candles,125,v) for v in V5_CANDIDATES])
        self.assertEqual(len(ALL_MODELS),8)
        with self.assertRaisesRegex(ValueError,"Unregistered"):
            v5_candidate(candles,125,"curve_fitted_strategy")

    def test_risk_veto_thin_market_and_out_of_session(self):
        candles=fabricated_bars()
        with patch("research.atlas_v5_cost_aware.v4_candidate",return_value=1):
            candles[125]["volume"]=1
            self.assertEqual(v5_candidate(candles,125,"v5_cost_noise_guard"),0)
            candles[125]["volume"]=500
            candles[125]["time"]=int(datetime(2026,5,18,18,10,tzinfo=TZ).timestamp())
            self.assertEqual(v5_candidate(candles,125,"v5_cost_noise_guard"),0)
            # The pure cost filter doesn't use speculative time-of-day improvements.
            self.assertEqual(v5_candidate(candles,125,"v5_cost_guard"),1)

    def test_q26_import_uses_contract_count_not_money_and_sorts(self):
        with tempfile.TemporaryDirectory() as td:
            raw=Path(td)/"q26.txt"
            normalized=Path(td)/"q26_m5.csv"
            records=[]
            start=datetime(2026,5,4,9,10)
            day=start
            while len(records)<1080:
                if day.weekday()<5:
                    for i in range(90):
                        t=day+timedelta(minutes=5*i)
                        records.append(f"WINQ26;{t:%d/%m/%Y};{t:%H:%M:%S};"
                                       "200000,00;200100,00;199900,00;"
                                       "200010,00;10.000.000,00;73")
                day+=timedelta(days=1)
            raw.write_text("\n".join(reversed(records))+"\n",encoding="utf-8")
            output=canonicalize_q26_m5(raw,normalized)
            self.assertEqual(output["symbol"],"WINQ26")
            self.assertEqual(output["timeframe_seconds"],300)
            self.assertEqual(output["bars"][0]["volume"],73)
            self.assertEqual(len(output["bars"]),1080)
            self.assertGreaterEqual(_coverage(output["bars"],"2026-05-01","2026-06-01")["days_with_65_m5"],12)
            self.assertIsNone(_month_cut(output["bars"],"2026-05-01","2026-06-01"))
            damaged=raw.read_text().replace("200000,00","200001,00",1)
            raw.write_text(damaged)
            with self.assertRaisesRegex(ValueError,"grade de 5 pontos"):
                canonicalize_q26_m5(raw,normalized)

    def test_loss_attribution_uses_closed_ledger_and_cannot_fake_profit(self):
        start=int(datetime(2026,4,14,10,0,tzinfo=TZ).timestamp())
        x={"closed_ledger":[
           {"signal_ts":start,"reason":"STOP","net_brl":-36.0,
            "estimated_cost_brl":8.0,"side":1,"contracts":1},
           {"signal_ts":start+3600,"reason":"TARGET","net_brl":54.0,
            "estimated_cost_brl":8.0,"side":-1,"contracts":1},
           {"signal_ts":start+7200,"reason":"STOP_SAME_BAR","net_brl":-54.0,
            "estimated_cost_brl":8.0,"side":1,"contracts":1},
        ],"uncertain_same_bar_exits":1}
        attribution=_loss_analysis(x)
        self.assertEqual(attribution["closed_trades"],3)
        self.assertEqual(attribution["stop_count"],2)
        self.assertEqual(attribution["total_estimated_cost_brl"],24.0)
        self.assertEqual(attribution["gross_before_estimated_costs_brl"],-12.0)
        self.assertEqual(attribution["net_brl"],-36.0)
        self.assertEqual(attribution["worst_5_losses"][0]["net_brl"],-54.0)

    def test_worst_to_best_rank_rejects_silent_model(self):
        example={"closed":15,"net_brl":-100.0,"profit_factor":0.6,
                 "open_at_end":False,"pending_at_end":False,
                 "max_realized_drawdown_pct":1.0}
        output={"periods":{}}
        for key,contract,a,b,full in WINDOWS:
            def make(net,closed):
                return {**example,"net_brl":net,"closed":closed}
            output["periods"][key]={"full_calendar_month":full,"status":"BACKTESTED",
                "variants":{m:{"1":make(20,15),"2":make(
                    -100 if m=="v1_reference" else 50 if m=="v5_cost_guard" else 0,
                    0 if m=="v5_cost_noise_guard" else 15)}
                    for m in ALL_MODELS},
                "attribution":{m:{"total_estimated_cost_brl":100} for m in ALL_MODELS}}
        positions=rank(output)
        self.assertEqual(positions[0]["variant"],"v1_reference")
        self.assertEqual(positions[-1]["variant"],"v5_cost_guard")
        silent=next(x for x in positions if x["variant"]=="v5_cost_noise_guard")
        self.assertFalse(silent["meaningful_descriptive_rank"])
        self.assertFalse(any(x["promoted"] for x in positions))
        self.assertEqual(positions[-1]["completed_months_backtested"],4)
        self.assertEqual(RESEARCH_CAPITAL_BRL,30000.0)

if __name__=="__main__":
    unittest.main()
