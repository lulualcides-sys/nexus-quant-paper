"""Deterministic offline tests; no fabricated real exchange fills."""
import copy
import json
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from src.crypto_paper import (
    CAPITAL, RISK, SYMBOLS, STRATEGIES, book, digest, fetch_klines,
    fresh, key, parse_klines, process, signal, step, update, WARMUP,
)
from src.market_quality import validate_bars
from src.strategies import make_indicators

T0 = 1800000000 - 1800000000 % 3600


def rows(n=265, start=T0, shift=0.0):
    values = []
    for i in range(n):
        p = 300.0 + shift + .05*i + math.sin(i/9)
        o = p - .15
        c = p + .12
        values.append({"time": start + i*3600, "open": o,
                       "high": max(o,c)+.3, "low": min(o,c)-.3,
                       "close": c})
    return values


class CryptoPaperTest(unittest.TestCase):
    def setUp(self):
        self.data = {"BTCUSDT": rows(265), "ETHUSDT": rows(265, shift=100)}

    def test_four_separate_books_no_retroactive_trades(self):
        state = update(None, self.data)
        self.assertTrue(state["paper_only"] and state["spot_only"])
        self.assertEqual(len(state["books"]), 4)
        self.assertEqual(len(state["watermarks"]), 2)
        self.assertTrue(all(b["position"] is None and not b["closed"]
                            and not b["entries"] for b in state["books"].values()))
        original = copy.deepcopy(state)
        self.assertEqual(update(state, self.data), original)

    def test_isolated_new_candle_and_no_leverage(self):
        state = update(None, self.data)
        extended = dict(self.data, BTCUSDT=rows(266))
        with patch("src.crypto_paper.signal", return_value=True) as patched:
            update(state, extended)
        self.assertEqual(state["watermarks"]["BTCUSDT"], extended["BTCUSDT"][-1]["time"])
        self.assertEqual(state["watermarks"]["ETHUSDT"], self.data["ETHUSDT"][-1]["time"])
        self.assertEqual(patched.call_count, 2)
        for strat in STRATEGIES:
            b = state["books"][key("BTCUSDT", strat)]
            p = b["position"]
            self.assertEqual(b["entries"], 1)
            self.assertLessEqual(p["qty"] * p["entry"] * 1.001,
                                 CAPITAL + 1e-7)
            self.assertLessEqual(p["qty"] * (p["entry"] - p["stop"]),
                                 CAPITAL * RISK + 1e-7)
        self.assertFalse(state["books"][key("ETHUSDT", "ema_pullback")]["position"])

    def test_stop_gap_pessimistic_and_no_same_bar_reentry(self):
        b = book()
        b["position"] = {"entry": 105.0, "start": T0, "qty": 1.0,
                         "stop": 100.0, "initial_r": 5.0,
                         "best_close": 105.0, "held": 0, "slip_cost": .05}
        candles = rows(266)
        candles[-1] = {"time": candles[-1]["time"], "open": 96,
                       "high": 98, "low": 95, "close": 97}
        with patch("src.crypto_paper.signal", return_value=True):
            step(b, "ema_pullback", candles, make_indicators(candles), 265)
        self.assertEqual(len(b["closed"]), 1)
        self.assertLess(b["closed"][0]["exit"], 96)
        self.assertLess(b["closed"][0]["net_usd"], -9)
        self.assertIsNone(b["position"])
        self.assertEqual(b["entries"], 0)

    def test_missing_watermark_fails_instead_of_inventing_backfill(self):
        state = update(None, self.data)
        with self.assertRaisesRegex(ValueError, "watermark perdido"):
            update(state, {"BTCUSDT": rows(265, start=T0+900*3600)})

    def test_partial_market_preserves_other_market(self):
        state = update(None, self.data)
        update(state, {"ETHUSDT": rows(266, shift=100)})
        self.assertIn("BTCUSDT", state["unavailable"])
        self.assertEqual(len(state["books"]), 4)
        self.assertEqual(state["watermarks"]["BTCUSDT"],
                         self.data["BTCUSDT"][-1]["time"])

    def test_binance_complete_candle_validation(self):
        candles = rows(265)
        payload = [[r["time"]*1000, str(r["open"]), str(r["high"]),
                    str(r["low"]), str(r["close"]), "10",
                    (r["time"]+3600)*1000-1] for r in candles]
        now = candles[-1]["time"]+3600+150
        good = parse_klines(payload, now)
        self.assertEqual(len(good), 265)
        with self.assertRaisesRegex(ValueError, "desatualizada"):
            parse_klines(payload, now+20000)
        partial = payload + [[(candles[-1]["time"]+3600)*1000, "101",
                    "102", "99", "100", "10",
                    (candles[-1]["time"]+7200)*1000-1]]
        self.assertEqual(len(parse_klines(partial, now)), 265)
        with self.assertRaisesRegex(ValueError, "lacuna"):
            parse_klines(payload[:250] + payload[251:], now)

    def test_cannot_fetch_unapproved_pair(self):
        with self.assertRaisesRegex(ValueError, "nao aprovado"):
            fetch_klines("DOGEUSDT", now=T0)

    def test_persist_and_only_virtual_daily_digest(self):
        with TemporaryDirectory() as folder:
            path = Path(folder)/"crypto.json"
            state = process(self.data, path=path)
            self.assertEqual(len(json.loads(path.read_text())["books"]), 4)
            message = digest(state, "2026-10-31")
            self.assertIn("BTCUSDT", message)
            self.assertIn("ETHUSDT", message)
            self.assertIn("SIMULACAO", message)
            self.assertNotIn("ordem real enviada", message)


if __name__ == "__main__":
    unittest.main()
