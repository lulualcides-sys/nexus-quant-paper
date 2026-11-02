"""Synthetic forward-only and risk tests for unvalidated H1 paper experiments."""
import math
import unittest
from copy import deepcopy
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch

from src.feed import MARKETS
from src.experimental_h1 import (
    CAPITAL, RISK_FRACTION, STRATEGIES, NOTIONAL_CAP,
    bot_key, diagnostics, digest, process, scorecard, setup, step, update,
)
from src.strategies import make_indicators

T0 = 1791000000 - 1791000000 % 3600


def rows(n=120, start=T0, shift=0.0):
    out = []
    for i in range(n):
        v = 100 + shift + 0.04 * i + 0.4 * math.sin(i / 3)
        o = v - 0.15
        c = v + 0.13
        out.append({"time": start + i * 3600, "open": o, "high": max(o, c) + 0.2,
                    "low": min(o, c) - 0.2, "close": c})
    return out


class PaperH1Tests(unittest.TestCase):
    def setUp(self):
        self.data = {m: rows(120, shift=100 * j)
                     for j, m in enumerate(MARKETS)}

    def test_first_run_is_baseline_and_fifteen_books(self):
        s = update(None, self.data)
        self.assertEqual(len(s["books"]), 15)
        self.assertEqual(len(s["watermarks"]), 5)
        self.assertTrue(s["experimental_only"] and s["paper_only"])
        self.assertTrue(all(not b["position"] and not b["entries"] and not b["closed"]
                            for b in s["books"].values()))

    def test_replay_does_not_create_trades_or_change_watermark(self):
        s = update(None, self.data)
        before = deepcopy(s)
        update(s, self.data)
        self.assertEqual(before, s)

    def test_new_candle_can_open_on_previous_completed_bar(self):
        s = update(None, self.data)
        longer = dict(self.data, EURUSD=rows(121))
        with patch("src.experimental_h1.setup", return_value=1) as fn:
            update(s, longer)
        self.assertEqual(len(s["books"]["EURUSD:ema20_retest"]["entries"]), 1)
        self.assertEqual(len(s["books"]["EURUSD:channel10"]["entries"]), 1)
        self.assertEqual(len(s["books"]["EURUSD:rsi50"]["entries"]), 1)
        self.assertEqual(s["watermarks"]["EURUSD"], longer["EURUSD"][-1]["time"])
        self.assertEqual(s["watermarks"]["USDJPY"], self.data["USDJPY"][-1]["time"])
        self.assertTrue(all(x[0][3] == 119 for x in fn.call_args_list))
        for strat in STRATEGIES:
            position = s["books"][bot_key("EURUSD", strat)]["position"]
            self.assertGreater(position["qty"], 0)
            self.assertLessEqual(position["qty"] * position["entry"], CAPITAL * NOTIONAL_CAP + 1e-6)
            self.assertLessEqual(position["qty"] * position["initial_r"], CAPITAL * RISK_FRACTION + 1e-6)

    def test_usdjpy_sizing_and_quote_conversion(self):
        from src.experimental_h1 import _close, step, book
        candles = rows(121, shift=50.0)
        ind = make_indicators(candles)
        b = book()
        with patch("src.experimental_h1.setup", return_value=1):
            step(b, "USDJPY", "channel10", candles, ind, 120)
        self.assertIsNotNone(b["position"])
        p = b["position"]
        self.assertLessEqual(p["qty"], CAPITAL + 1e-6)  # USD base units
        self.assertLessEqual(p["qty"] * p["initial_r"] / p["entry"],
                             CAPITAL * RISK_FRACTION + 1e-6)
        b2 = book()
        b2["position"] = {"start": T0, "side": 1, "entry": 150.0,
                          "stop": 149.0, "qty": 100.0}
        candle = {"time": T0+3600, "open": 149.0, "high": 149.0,
                  "low": 148.0, "close": 148.5}
        _close(b2, "USDJPY", candle, 149.0, "STOP")
        # 100 yen gross loss = about 0.67 USD, plus fees, NOT US$100.
        self.assertGreater(b2["closed"][0]["net_usd"], -1)
        self.assertLess(b2["closed"][0]["net_usd"], -0.67)

    def test_old_position_stops_on_gap_at_worse_open(self):
        s = update(None, self.data)
        b = s["books"]["EURUSD:channel10"]
        old = self.data["EURUSD"][-1]["time"]
        b["position"] = {"side": 1, "entry": 100.0, "start": old,
                         "qty": 5.0, "stop": 99.0, "initial_r": 1.0,
                         "best_close": 100.0, "held_bars": 0, "stop_updates": 0}
        candles = rows(120)
        gap = {"time": old + 3 * 3600, "open": 96.0, "close": 95.5,
               "high": 97.0, "low": 95.0}
        updated = dict(self.data, EURUSD=candles + [gap])
        update(s, updated)
        trade = b["closed"][0]
        self.assertEqual(trade["exit"], 96.0)
        self.assertEqual(trade["exit_type"], "STOP")
        self.assertLess(trade["net_usd"], 0)
        self.assertEqual(b["diagnostics"]["entered"], 0)

    def test_missing_watermark_does_not_fill_history(self):
        s = update(None, self.data)
        from src.experimental_h1 import WARMUP
        with self.assertRaisesRegex(ValueError, "watermark perdido"):
            update(s, dict(self.data, EURUSD=rows(WARMUP + 80, start=T0 + 400*3600)))

    def test_isolation_quarantines_bad_wti_watermark_without_resetting_position(self):
        s = update(None, self.data)
        wti_key = "XTIUSD:channel10"
        old_wti_book = s["books"][wti_key]
        old_wti_book["position"] = {
            "side": 1, "entry": 105.0, "start": self.data["XTIUSD"][-2]["time"],
            "qty": 1.0, "stop": 103.0, "initial_r": 2.0,
            "best_close": 105.0, "stop_updates": 0, "held_bars": 0}
        # Production state has an odd timestamp with non-zero minutes.
        bad = s["watermarks"]["XTIUSD"] + 2631
        s["watermarks"]["XTIUSD"] = bad
        snapshot = deepcopy(s["books"][wti_key])
        expanded = {m: rows(121, shift=100*j)
                    for j,m in enumerate(MARKETS)}
        with patch("src.experimental_h1.setup",return_value=0):
            updated = update(s, expanded, isolate_errors=True)
        self.assertEqual(updated["watermarks"]["XTIUSD"], bad)
        self.assertEqual(updated["books"][wti_key], snapshot)
        self.assertIn("XTIUSD",updated["unavailable"])
        self.assertIn("No anchored evidence",updated["market_errors"]["XTIUSD"])
        for market in MARKETS:
            if market!="XTIUSD":
                self.assertEqual(updated["watermarks"][market],
                                 expanded[market][-1]["time"])
                self.assertNotIn(market,updated["unavailable"])

    def test_proven_wti_subhour_mark_resumes_only_existing_exits(self):
        s=update(None,self.data)
        oldmark=s["watermarks"]["XTIUSD"]
        key="XTIUSD:channel10"
        oldentry={
            "side":1,"entry":505.0,"start":oldmark,"qty":1.0,
            "stop":506.0,"initial_r":2.0,"best_close":505.0,
            "stop_updates":0,"held_bars":0}
        s["books"][key]["position"]=deepcopy(oldentry)
        s["books"][key]["entries"]=[{"entry_ts":oldmark,
                                     "side":1,"entry":105.0,"reason":"channel10",
                                     "risk_fraction":RISK_FRACTION}]
        s["watermarks"]["XTIUSD"]=oldmark+2631
        new={m:rows(124,shift=100*j) for j,m in enumerate(MARKETS)}
        with patch("src.experimental_h1.setup",return_value=1):
            result=update(s,new,isolate_errors=True)
        self.assertNotIn("XTIUSD",result["unavailable"])
        self.assertEqual(result["watermarks"]["XTIUSD"],new["XTIUSD"][-1]["time"])
        self.assertEqual(len(result["books"][key]["entries"]),1)
        self.assertEqual(result["books"][key]["entries"][0]["entry_ts"],oldmark)
        self.assertEqual(len(result["books"][key]["closed"]),1)
        self.assertEqual(result["books"][key]["closed"][0]["entry_ts"],oldmark)
        self.assertTrue(result["books"][key]["closed"][0]["reconciled_from_feed_gap"])
        from src.experimental_h1 import local_day
        closed_day=local_day(result["books"][key]["closed"][0]["exit_ts"])
        self.assertIn("0 saídas", next(line for line in digest(result,closed_day) if line.startswith("XTIUSD:")))
        self.assertIsNone(result["books"][key]["position"])
        self.assertEqual(result["watermark_repairs"][0]["from_ts"],oldmark+2631)
        self.assertEqual(result["watermark_repairs"][0]["anchored_closed_bar_ts"],oldmark)
        # Next genuinely fresh H1 candle is eligible for a new signal.
        next_rows={m:rows(125,shift=100*j) for j,m in enumerate(MARKETS)}
        # cooldown may intentionally block next bar; nevertheless no re-repair.
        update(result,next_rows,isolate_errors=True)
        self.assertEqual(len(result["watermark_repairs"]),1)

    def test_missing_proven_anchor_and_invalid_feed_stays_quarantined(self):
        from src.experimental_h1 import reconcile_subhour_watermark
        s=update(None,self.data)
        oldmark=s["watermarks"]["XTIUSD"]
        broken=oldmark+2631
        times=[bar["time"] for bar in self.data["XTIUSD"]]
        # The malformed mark must precede a genuinely observed later H1 candle;
        # otherwise feed freshness fails before journal-evidence validation.
        times.append(oldmark+3600)
        with self.assertRaisesRegex(ValueError,"No anchored evidence"):
            reconcile_subhour_watermark(s,"XTIUSD",times,broken)
        s["books"]["XTIUSD:channel10"]["entries"].append({
            "entry_ts":oldmark,"side":1})
        with self.assertRaisesRegex(ValueError,"not eligible"):
            reconcile_subhour_watermark(s,"XTIUSD",times[:-1],broken)
        with self.assertRaisesRegex(ValueError,"not eligible"):
            reconcile_subhour_watermark(s,"XTIUSD",times,oldmark+3600*20+2631)

    def test_isolated_market_failure_rolls_back_entire_market_and_rest_recovers(self):
        s = update(None,self.data)
        old = deepcopy(s["books"]["XAUUSD:channel10"])
        old_mark = s["watermarks"]["XAUUSD"]
        expanded = {m: rows(122, shift=100*j)
                    for j,m in enumerate(MARKETS)}
        # Raise only on the second candle after one successful virtual update.
        calls = {"XAUUSD":0}
        real_step = step
        def maybe_fails(book,market,strategy,bars,ind,index,*,signal_fn=None):
            if market=="XAUUSD":
                calls["XAUUSD"]+=1
                if calls["XAUUSD"]>=4:
                    raise ValueError("synthetic fatal market candle")
            return real_step(book,market,strategy,bars,ind,index,signal_fn=signal_fn)
        with patch("src.experimental_h1.step",side_effect=maybe_fails):
            updated=update(s,expanded,isolate_errors=True)
        self.assertEqual(updated["watermarks"]["XAUUSD"],old_mark)
        self.assertEqual(updated["books"]["XAUUSD:channel10"],old)
        self.assertIn("XAUUSD",updated["unavailable"])
        for market in MARKETS:
            if market!="XAUUSD":
                self.assertEqual(updated["watermarks"][market],expanded[market][-1]["time"])
        # Next healthy scan can resume without a reset and clears quarantine.
        with patch("src.experimental_h1.setup",return_value=0):
            resumed=update(s,expanded,isolate_errors=True)
        self.assertEqual(resumed["watermarks"]["XAUUSD"],expanded["XAUUSD"][-1]["time"])
        self.assertNotIn("market_errors",resumed)
        self.assertEqual(resumed["unavailable"],[])

    def test_scheduled_process_writes_isolated_healthy_states_even_if_wti_is_corrupt(self):
        with TemporaryDirectory() as td:
            file=Path(td)/"h1.json"
            current=process(self.data,path=file)
            prior=deepcopy(current["books"]["XTIUSD:channel10"])
            current["watermarks"]["XTIUSD"]+=2631
            file.write_text(__import__("json").dumps(current),encoding="utf-8")
            new={m:rows(121,shift=100*j) for j,m in enumerate(MARKETS)}
            with patch("src.experimental_h1.setup",return_value=0):
                saved=process(new,path=file)
            self.assertEqual(saved["books"]["XTIUSD:channel10"],prior)
            self.assertIn("XTIUSD",saved["unavailable"])
            self.assertEqual(saved["watermarks"]["EURUSD"],new["EURUSD"][-1]["time"])
            self.assertEqual(__import__("json").loads(file.read_text())["watermarks"],
                             saved["watermarks"])

    def test_partial_feed_keeps_other_markets_and_lists_unavailable(self):
        s = update(None, {"EURUSD": self.data["EURUSD"]})
        self.assertEqual(len(s["books"]), 3)
        self.assertIn("XAUUSD", s["unavailable"])
        update(s, self.data)
        self.assertEqual(len(s["books"]), 15)
        self.assertEqual(len(s["books"]["XAUUSD:rsi50"]["entries"]), 0)

    def test_persist_and_summary_are_virtual_and_auditable(self):
        with TemporaryDirectory() as td:
            f = Path(td) / "shadow.json"
            s = process(self.data, path=f)
            self.assertTrue(f.exists())
            self.assertIn("retroativas", s["books"]["EURUSD:rsi50"]["last_reason"])
            date = "2026-10-30"
            message = "\n".join(digest(s, date))
            self.assertIn("15 EXPERIMENTAIS", message)
            self.assertIn("NÃO VALIDADOS", message)
            self.assertIn("EURUSD", message)
            self.assertEqual(len(diagnostics(s)), 15)

    def test_net_cost_metrics_and_no_premature_promotion(self):
        s = update(None, self.data)
        b = s["books"]["EURUSD:channel10"]
        b["closed"] = [
            {"entry_ts": T0, "exit_ts": T0+3600, "net_usd": 2.0, "cost_usd": .1},
            {"entry_ts": T0+7200, "exit_ts": T0+10800, "net_usd": -1.0, "cost_usd": .1},
        ]
        b["equity"] = CAPITAL + 1.0
        report = scorecard(b)
        self.assertEqual(report["profit_factor"], 2.0)
        self.assertEqual(report["net_usd"], 1.0)
        self.assertEqual(report["win_rate_pct"], 50.0)
        self.assertEqual(report["fees_usd"], .2)
        self.assertFalse(report["validated"])
        self.assertFalse(report["sample_sufficient_for_review"])

    def test_combined_26_bot_report_fits_telegram(self):
        from src.daily_digest import digest as full_digest
        from src.gold_forward import STUDY
        from src.leveraged_gold import CONFIG
        shadow = update(None, self.data)
        gold = {"books": {k: {"equity": 5000, "closed": [], "position": None}
                          for k in STUDY}}
        leveraged = {"books": {k: {"equity": 5000, "peak_equity": 5000,
                                  "closed": [], "position": None, "frozen": False}
                               for k in CONFIG}}
        message = full_digest("2026-10-30", gold, leveraged, shadow=shadow,
                              mtf_error="Dados de USD/CAD temporariamente indisponíveis")
        self.assertIn("26 robôs", message)
        self.assertIn("15 EXPERIMENTAIS H1", message)
        self.assertLess(len(message), 4000)

    def test_signal_has_directions_or_no_signal(self):
        b = rows(130)
        ind = make_indicators(b)
        for strat in STRATEGIES:
            self.assertIn(setup(strat, b, ind, 120), {-1, 0, 1})
        with self.assertRaises(KeyError):
            setup("unknown", b, ind, 120)

    def test_no_reentry_same_bar_when_stopped(self):
        b = {"equity": CAPITAL, "position": {
            "side": 1, "entry": 110.0, "start": T0 + 118*3600,
            "qty": 1.0, "stop": 109.0, "initial_r": 1.0,
            "best_close": 110.0, "stop_updates": 0, "held_bars": 0,
        }, "closed": [], "entries": [], "last_exit_ts": None,
            "last_reason": "",
            "diagnostics": {"no_setup": 0, "gap": 0, "cooldown": 0,
                            "in_position": 0, "entered": 0, "exited": 0, "invalid": 0}}
        candles = rows(120)
        candles[119] = dict(candles[119], open=108.0, low=107.0, high=109.0, close=108.0)
        with patch("src.experimental_h1.setup", return_value=1):
            step(b, "EURUSD", "channel10", candles, make_indicators(candles), 119)
        self.assertIsNone(b["position"])
        self.assertEqual(len(b["closed"]), 1)
        self.assertFalse(b["entries"])


if __name__ == "__main__":
    unittest.main()
