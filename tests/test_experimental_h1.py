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
    bot_key, diagnostics, digest, process, setup, step, update,
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
