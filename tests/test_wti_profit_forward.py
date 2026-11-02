"""Prospective Channel20/55/WTI paper evidence tests: no historic fills."""
from __future__ import annotations

import json
import math
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from datetime import datetime,timezone

from src import wti_channel10_shadow as wti
from src import profit_watchlist as watch
from src import experimental_h1 as h1
from src import cost_aware_gate as gate


T0=int(datetime(2026,10,20,tzinfo=timezone.utc).timestamp())


def prices(n=220, start=T0):
    out=[]
    for i in range(n):
        p=75.+i*.04+math.sin(i/13)
        out.append({"time":start+i*3600,
                    "open":p,"high":p+.8,"low":p-.7,
                    "close":p+.2})
    return out


def trade(ts,net,fee,*,when=None):
    return {"entry_ts":ts,"exit_ts":when or ts+3600,
            "net_usd":net,"cost_usd":fee}


class WtiForwardProfitTests(unittest.TestCase):
    def test_wti_starts_with_exactly_zero_retro_trades(self):
        candles=prices()
        state=wti.update(None,candles)
        self.assertEqual(len(state["book"]["entries"]),0)
        self.assertEqual(len(state["book"]["closed"]),0)
        self.assertEqual(state["book"]["equity"],h1.CAPITAL)
        self.assertEqual(state["h1_watermark"],candles[-1]["time"])
        self.assertEqual(state["first_observation_ts"],candles[-1]["time"])
        self.assertEqual(state["no_historical_backfill"],True)

    def test_wti_signal_filters_match_predeclared_gate(self):
        candles=prices()
        i=160
        base={"atr":2.,"e50":73.,"e200":67.}
        indicators=[dict(base) for _ in candles]
        expected=gate.allow_signal(1,candles,indicators,i,
                                   fee_bps=h1.COST_BPS["XTIUSD"])
        with patch.object(h1,"setup",return_value=1):
            actual=wti.filtered_signal("channel10",candles,indicators,i)
        self.assertEqual(actual,expected)
        with self.assertRaises(ValueError):
            wti.filtered_signal("rsi50",candles,indicators,i)

    def test_clean_new_h1_candle_opens_at_next_open_only(self):
        candles=prices()
        original=wti.update(None,candles[:190])
        with patch.object(wti,"filtered_signal",return_value=1):
            updated=wti.update(original,candles[:191])
        self.assertEqual(updated["h1_watermark"],candles[190]["time"])
        self.assertEqual(len(updated["book"]["entries"]),1)
        self.assertEqual(updated["book"]["entries"][0]["entry_ts"],candles[190]["time"])
        self.assertIsNone(original["book"]["position"])
        with patch.object(wti,"filtered_signal",return_value=1):
            same=wti.update(updated,candles[:191])
        self.assertEqual(len(same["book"]["entries"]),1)
        self.assertEqual(same["h1_watermark"],updated["h1_watermark"])

    def test_new_shadows_close_and_never_rewrite_original_books(self):
        candles=prices()
        base=wti.update(None,candles[:190])
        with patch.object(wti,"filtered_signal",return_value=1):
            first=wti.update(base,candles[:191])
        revised=deepcopy(candles[:192])
        revised[-1]["low"]=revised[-1]["open"]-50
        with patch.object(wti,"filtered_signal",return_value=0):
            later=wti.update(first,revised)
        self.assertEqual(len(later["book"]["closed"]),1)
        self.assertEqual(later["book"]["position"],None)
        self.assertEqual(len(base["book"]["closed"]),0)
        self.assertEqual(len(first["book"]["closed"]),0)

    def test_watermark_gone_fails_closed_and_state_unchanged(self):
        rows=prices()
        state=wti.update(None,rows[:195])
        old=deepcopy(state)
        gap=rows[196:]+rows[:193]
        gap=sorted(gap,key=lambda x:x["time"])
        with self.assertRaisesRegex(ValueError,"watermark missing"):
            wti.update(state,gap)
        self.assertEqual(state,old)
        invalid=deepcopy(state);invalid["policy"]="optimized_on_holdout"
        with self.assertRaisesRegex(ValueError,"incompatible"):
            wti.update(invalid,rows)

    def test_repeated_file_run_never_backfills(self):
        rows=prices()
        with TemporaryDirectory() as tmp:
            file=Path(tmp)/"shadow.json"
            first=wti.process(rows,path=file)
            again=wti.process(rows,path=file)
            self.assertEqual(len(again["book"]["closed"]),0)
            self.assertEqual(first["h1_watermark"],again["h1_watermark"])
            self.assertTrue(file.exists())

    def test_prospective_cutoff_drops_old_trade_even_if_it_closed_today(self):
        cutoff=watch.CUTOFF_TS
        old=trade(cutoff-3600,50,2,when=cutoff+3600)
        new=trade(cutoff+3600,8,1)
        conventional={"paper_only":True,"books":{
            "channel20":{"equity":5010,"closed":[old,new]},
            "channel55":{"equity":5000,"closed":[]}}}
        state=wti.update(None,prices())
        future=deepcopy(state)
        future["book"]["closed"]=[trade(cutoff+3600,-3,1)]
        original=deepcopy(conventional)
        view=watch.build(now=cutoff+86400,conventional=conventional,wti=future)
        v=view["watchlist"]["gold_h4:channel20"]
        self.assertEqual(v["trades"],1)
        self.assertEqual(v["net_usd"],8)
        self.assertEqual(v["double_transaction_fee_fixed_fills_usd"],7)
        self.assertFalse(v["validated_real_money"])
        self.assertEqual(view["watchlist"]["wti_filtered:channel10"]["net_usd"],-3)
        self.assertEqual(conventional,original)
        self.assertIn("Evidência nova",watch.telegram_line(view))

    def test_missing_book_unknown_not_zero_and_stress_not_replay(self):
        view=watch.build(now=watch.CUTOFF_TS+86400,conventional={},wti=None)
        for item in view["watchlist"].values():
            self.assertIsNone(item["net_usd"])
            self.assertEqual(item["status"],"unavailable")
        self.assertIn("SAME logged fills",view["stress_warning"])

    def test_fee_stress_uses_only_transaction_cost_and_never_promotes(self):
        c=watch.CUTOFF_TS+7200
        b={"closed":[trade(c,10,4),trade(c+3600,-3,1)],"equity":5007}
        row=watch._watch(b,"H4","gold_h4",5000,cutoff=watch.CUTOFF_TS)
        self.assertEqual(row["gross_before_transaction_cost_usd"],12)
        self.assertEqual(row["net_usd"],7)
        self.assertEqual(row["transaction_cost_usd"],5)
        self.assertEqual(row["double_transaction_fee_fixed_fills_usd"],2)
        self.assertEqual(row["trades"],2)
        self.assertEqual(row["status"],"insufficient_sample")
        self.assertFalse(row["validated_real_money"])

    def test_no_extra_27th_bot_and_no_intraday_telegram(self):
        from research.backtest_27 import all_ids
        self.assertEqual(len(all_ids()),27)
        self.assertNotIn("wti_filtered:channel10",all_ids())


if __name__=="__main__":
    unittest.main()
