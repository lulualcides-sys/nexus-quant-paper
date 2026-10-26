"""Network-free safety checks for the USD/CAD BB20 H1 -> M15 paper bot."""
import copy
import unittest
from datetime import datetime, timezone

from src.bb_rebound_mtf import (
    TICKER, CAPITAL, digest, exit_position, h1_rejection, parse_15m,
    to_h1, update,
)
from src.strategies import make_indicators


def hours(up=True, count=61):
    out = []
    for i in range(count):
        close = 1.30 + (1 if up else -1) * 0.0002 * i
        op = close - (0.0001 if up else -0.0001)
        out.append({
            "time": 3600 * i, "open": op,
            "high": max(op, close) + 0.003,
            "low": min(op, close) - 0.003,
            "close": close,
        })
    return out


def minutes():
    out = []
    for hour in range(60):
        base = 1.30 + 0.0002 * hour
        for q in range(4):
            close = base + 0.00004 * q
            op = close - 0.00003
            out.append({
                "time": 3600 * hour + 900 * q,
                "open": op, "high": close + 0.00005,
                "low": base - 0.003 if q == 0 else op - 0.00005,
                "close": close,
            })
    return out


class BB20BotTests(unittest.TestCase):
    def test_h1_confirmation_requires_trend_and_mean_touch(self):
        data = hours()
        inds = make_indicators(data)
        self.assertEqual(h1_rejection(data, inds, 59), 1)
        altered = copy.deepcopy(data)
        altered[59]["low"] = altered[59]["close"] - 0.00001
        self.assertEqual(h1_rejection(altered, make_indicators(altered), 59), 0)

        down = hours(up=False)
        self.assertEqual(h1_rejection(down, make_indicators(down), 59), -1)

    def test_first_run_is_clean_and_m15_confirmed_entry_is_incremental(self):
        bars = minutes()
        state = update(None, bars)
        self.assertIsNone(state["position"])
        self.assertEqual(state["closed"], [])
        self.assertEqual(state["equity"], CAPITAL)
        # A breakout M15 closes after the completed H1 rejection.
        breakout_open = bars[-1]["close"] + 0.00001
        breakout_close = breakout_open + 0.00040
        bars.append({
            "time": 60 * 3600, "open": breakout_open,
            "high": breakout_close + 0.00005,
            "low": breakout_open - 0.00005,
            "close": breakout_close,
        })
        bars.append({
            "time": 60 * 3600 + 900, "open": breakout_close,
            "high": breakout_close + 0.00005,
            "low": breakout_close - 0.00005,
            "close": breakout_close,
        })
        state = update(state, bars)
        self.assertIsNotNone(state["position"])
        self.assertEqual(state["position"]["side"], 1)
        self.assertEqual(state["position"]["entry_ts"], 60 * 3600 + 900)
        self.assertLessEqual(state["position"]["qty_usd"], CAPITAL)
        self.assertEqual(state["closed"], [])
        watermark = state["watermark_m15"]
        again = update(state, bars)
        self.assertEqual(again["watermark_m15"], watermark)
        self.assertEqual(again["last_entry_h1"], 59 * 3600)

    def test_missing_watermark_does_not_fabricate_orders(self):
        bars = minutes()
        state = update(None, bars)
        state["watermark_m15"] = -1
        with self.assertRaisesRegex(ValueError, "lacuna"):
            update(state, bars)

    def test_conservative_stop_takes_priority_and_converts_cad_to_usd(self):
        state = {
            "equity": 1000.0, "position": {
                "side": 1, "entry": 1.4, "entry_ts": 0,
                "qty_usd": 1000.0, "stop": 1.39, "target": 1.42,
            }, "closed": [], "last_reason": "",
        }
        exited = exit_position(state, {
            "time": 900, "open": 1.4, "low": 1.38, "high": 1.43, "close": 1.42,
        })
        self.assertTrue(exited)
        self.assertEqual(state["closed"][0]["exit_type"], "STOP")
        self.assertLess(state["equity"], 1000)
        self.assertIsNone(state["position"])

    def test_m15_feed_rejects_unfinished_bars(self):
        t = 1_800_000_000 - (1_800_000_000 % 900)
        payload = {
            "chart": {"result": [{
                "timestamp": [t-900, t],
                "indicators": {"quote": [{
                    "open": [1.4, 1.4],
                    "high": [1.41, 1.41],
                    "low": [1.39, 1.39],
                    "close": [1.4, 1.4],
                }]},
            }]}
        }
        with self.assertRaisesRegex(ValueError, "apenas 1 candles"):
            parse_15m(payload, now=t+1000)

    def test_digest_names_eleventh_without_claiming_real_fills(self):
        state = update(None, minutes())
        lines = digest(state, "2026-10-26")
        self.assertIn("11º ROBÔ", lines[0])
        self.assertTrue(any("virtual" in line for line in lines))


if __name__ == "__main__":
    unittest.main()
