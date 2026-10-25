import math
import unittest
from unittest.mock import patch
from research.screen_v2 import aggregate_hourly_to_h4
from src.strategies import make_indicators
from src.gold_forward import update as update_regular, initial as initial_regular, evaluate_bar as regular_step
from src.leveraged_gold import (
    update as update_leveraged, one_bar, fresh, blocked,
    CONFIG, MAX_NOTIONAL_LEVERAGE, RISK_FRACTION, stats,
    DAILY_ENTRY_LOSS_LIMIT
)
from src.daily_digest import digest

START=1729728000

def candles(n=1150):
    price=2750.
    result=[]
    for i in range(n):
        end=price+0.5+0.18*math.sin(i/7)
        result.append({"time":START+3600*i,"open":price,
           "high":max(price,end)+1.0,"low":min(price,end)-1.0,"close":end})
        price=end
    return result

class LeveragedCohortTests(unittest.TestCase):
    def test_independent_five_and_five_no_backfill(self):
        hourly=candles()
        regular=update_regular(None,hourly)
        lever=update_leveraged(None,hourly)
        self.assertEqual(len(regular["books"]),5)
        self.assertEqual(len(lever["books"]),5)
        self.assertEqual(len(set(regular["books"])|set(lever["books"])),10)
        self.assertEqual(lever["h4_watermark"],regular["h4_watermark"])
        self.assertTrue(lever["paper_only"])
        self.assertTrue(all(b["equity"]==5000 and not b["closed"] and b["position"] is None for b in lever["books"].values()))
        self.assertEqual(lever,update_leveraged(lever,hourly))
        newer=candles(1200)
        advanced=update_leveraged(lever,newer)
        self.assertGreater(advanced["h4_watermark"],regular["h4_watermark"])
        self.assertEqual(advanced,update_leveraged(advanced,newer))

    def test_risk_leverage_capped_and_standard_max_one(self):
        h4=aggregate_hourly_to_h4(candles())
        feats=make_indicators(h4)
        i=250
        book=fresh(h4)["books"]["lev_channel20"]
        with patch("src.leveraged_gold.sign",side_effect=[1,0]):
            one_bar(book,"lev_channel20",h4,feats,i)
        pos=book["position"]
        self.assertIsNotNone(pos)
        self.assertGreater(RISK_FRACTION,0.0075)
        self.assertLessEqual(pos["notional_leverage"],MAX_NOTIONAL_LEVERAGE+1e-9)
        self.assertLessEqual(pos["qty"]*(pos["entry"]-pos["stop"]),5000*RISK_FRACTION+1e-6)
        conventional=initial_regular(h4)["books"]["channel20"]
        with patch("src.gold_forward.sign",side_effect=[1,0]):
            regular_step(conventional,"channel20",h4,feats,i)
        old=conventional["position"]
        self.assertLessEqual(old["qty"]*old["entry"]/5000,1.0+1e-9)

    def test_daily_limit_and_frozen_account_pause_new_entries(self):
        book=fresh(aggregate_hourly_to_h4(candles()))["books"]["lev_channel20"]
        book["today"]="2024-10-24"
        book["day_start_equity"]=5000
        book["equity"]=5000*(1-DAILY_ENTRY_LOSS_LIMIT)-0.01
        self.assertTrue(blocked(book))
        book["equity"]=5000
        book["frozen"]=True
        self.assertTrue(blocked(book))

    def test_closed_leverage_pnl_includes_fees_and_funding(self):
        h4=aggregate_hourly_to_h4(candles())
        features=make_indicators(h4)
        book=fresh(h4)["books"]["lev_channel20"]
        row=h4[250]
        entry=row["open"]
        book["position"]={"side":1,"entry":entry,"start":h4[247]["time"],
            "qty":1.0,"stop":row["high"]+1,"target":row["high"]+1000,
            "held_bars":4,"borrowed":1500.,"notional_leverage":1.4}
        one_bar(book,"lev_channel20",h4,features,250)
        self.assertEqual(len(book["closed"]),1)
        last=book["closed"][0]
        self.assertGreater(last["transaction_cost"],0)
        self.assertGreater(last["funding_cost"],0)
        self.assertAlmostEqual(last["net_usd"], last["gross_usd"]-last["transaction_cost"]-last["funding_cost"],places=3)

    def test_report_names_ten_and_never_claims_fbs_fills(self):
        h4=candles()
        normal=update_regular(None,h4)
        leveraged=update_leveraged(None,h4)
        msg=digest("2026-10-26",normal,leveraged,unavailable=[])
        self.assertIn("10 robôs",msg)
        self.assertIn("1×",msg)
        self.assertIn("3×",msg)
        self.assertIn("RESULTADOS VIRTUAIS",msg)
        self.assertIn("Sem operações reais",msg)
        self.assertLess(len(msg),4000)
        for v in CONFIG.values():
            self.assertIn(v[1],msg)

if __name__=="__main__":unittest.main()
