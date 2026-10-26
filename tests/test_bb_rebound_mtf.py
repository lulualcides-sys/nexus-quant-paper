"""Network-free safety checks for the USD/CAD BB20 H1 -> M15 paper bot."""
import copy
import unittest
from statistics import mean
from datetime import datetime, timezone

from src.bb_rebound_mtf import (
    TICKER, CAPITAL, TRAIL_POLICY, NET_GREEN_BUFFER_PIPS,
    digest, exit_position, advance_trailing_stop, h1_rejection, parse_15m,
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


def minutes(up=True):
    out = []
    direction = 1 if up else -1
    for hour in range(60):
        base = 1.30 + direction * 0.0002 * hour
        for q in range(4):
            close = base + direction * 0.00004 * q
            op = close - direction * 0.00003
            out.append({
                "time": 3600 * hour + 900 * q,
                "open": op,
                "high": max(op, close) + (0.003 if q == 0 and not up else 0.00005),
                "low": min(op, close) - (0.003 if q == 0 and up else 0.00005),
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

    def test_first_run_is_clean_and_m15_pullback_not_breakout(self):
        bars = minutes()
        state = update(None, bars)
        self.assertIsNone(state["position"])
        self.assertEqual(state["closed"], [])
        self.assertEqual(state["equity"], CAPITAL)
        middle = mean(x["close"] for x in to_h1(bars)[-20:])
        # Price returns down to the H1 BB middle, then prints a small bullish
        # M15 rebound. It stays BELOW the prior M15 high (no breakout).
        bars.append({
            "time": 60 * 3600, "open": bars[-1]["close"],
            "high": bars[-1]["close"] + 0.00015,
            "low": middle - 0.00003, "close": middle + 0.00002,
        })
        bars.append({
            "time": 60 * 3600 + 900, "open": middle + 0.00002,
            "high": middle + 0.00025,
            "low": middle - 0.00002, "close": middle + 0.00020,
        })
        self.assertLess(bars[-1]["close"], bars[-2]["high"])  # NOT a breakout
        bars.append({
            "time": 60 * 3600 + 1800, "open": middle + 0.00020,
            "high": middle + 0.00025,
            "low": middle + 0.00013, "close": middle + 0.00021,
        })
        state = update(state, bars)
        self.assertIsNotNone(state["position"])
        self.assertEqual(state["position"]["side"], 1)
        self.assertEqual(state["position"]["entry_ts"], 60 * 3600 + 1800)
        self.assertEqual(state["position"]["entry_rule"], "bb20_h1_m15_pullback_v2")
        self.assertEqual(state["position"]["stop_policy"], TRAIL_POLICY)
        self.assertIsNone(state["position"]["target"])
        self.assertLessEqual(state["position"]["qty_usd"], CAPITAL)
        self.assertEqual(state["closed"], [])
        watermark = state["watermark_m15"]
        again = update(state, bars)
        self.assertEqual(again["watermark_m15"], watermark)
        self.assertEqual(again["last_entry_h1"], 59 * 3600)

    def test_bearish_m15_rebound_triggers_sell_without_low_breakout(self):
        bars = minutes(up=False)
        state = update(None, bars)
        middle = mean(x["close"] for x in to_h1(bars)[-20:])
        bars.append({
            "time": 60 * 3600, "open": bars[-1]["close"],
            "high": middle + 0.00003,
            "low": bars[-1]["close"] - 0.00015, "close": middle - 0.00002,
        })
        bars.append({
            "time": 60 * 3600 + 900, "open": middle - 0.00002,
            "high": middle + 0.00002,
            "low": middle - 0.00025, "close": middle - 0.00020,
        })
        self.assertGreater(bars[-1]["close"], bars[-2]["low"])
        bars.append({
            "time": 60 * 3600 + 1800, "open": middle - 0.00020,
            "high": middle - 0.00013, "low": middle - 0.00025,
            "close": middle - 0.00021,
        })
        state = update(state, bars)
        self.assertIsNotNone(state["position"])
        self.assertEqual(state["position"]["side"], -1)
        self.assertEqual(state["position"]["entry_ts"], 60 * 3600 + 1800)

    def test_no_entry_when_return_candle_does_not_reject_mean(self):
        bars = minutes()
        state = update(None, bars)
        middle = mean(x["close"] for x in to_h1(bars)[-20:])
        bars.append({
            "time": 60 * 3600, "open": bars[-1]["close"],
            "high": bars[-1]["close"] + 0.00015,
            "low": middle - 0.00003, "close": middle + 0.00002,
        })
        bars.append({
            "time": 60 * 3600 + 900, "open": middle + 0.00002,
            "high": middle + 0.00005,
            "low": middle - 0.00025, "close": middle - 0.00020,
        })
        bars.append({
            "time": 60 * 3600 + 1800, "open": middle - 0.00020,
            "high": middle - 0.0001, "low": middle - 0.00030,
            "close": middle - 0.00022,
        })
        state = update(state, bars)
        self.assertIsNone(state["position"])
        self.assertEqual(state["closed"], [])

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


    @staticmethod
    def trailing_book(side=1, stop_policy=TRAIL_POLICY):
        entry, risk = 1.4, 0.01
        return {
            "equity": CAPITAL,
            "position": {
                "side": side, "entry": entry, "entry_ts": 0,
                "qty_usd": 1000, "stop": entry-side*risk,
                "initial_r": risk, "best_close": entry,
                "stop_policy": stop_policy, "target": None,
                "green_protected": False, "stop_updates": 0,
            },
            "closed": [], "last_reason": "",
        }

    def test_unlimited_green_long_monotone_close_trail_no_tp_or_timeout(self):
        book = self.trailing_book()
        # Stops are checked with the level that existed BEFORE this candle.
        first = {"time": 900, "open": 1.4, "high": 1.45,
                 "low": 1.395, "close": 1.412}
        self.assertFalse(exit_position(book, first))
        self.assertFalse(book["position"]["green_protected"])
        self.assertTrue(advance_trailing_stop(book, first))
        self.assertAlmostEqual(book["position"]["stop"], 1.402)
        self.assertTrue(book["position"]["green_protected"])
        # An arbitrarily large uptrend does not hit a take-profit.
        second = {"time": 1800, "open": 1.412, "high": 1.46,
                  "low": 1.409, "close": 1.455}
        self.assertFalse(exit_position(book, second))
        advance_trailing_stop(book, second)
        self.assertAlmostEqual(book["position"]["stop"], 1.445)
        self.assertEqual(book["closed"], [])
        # Stop may NEVER retreat as price retreats, even after >8h.
        retrace = {"time": 100 * 900, "open": 1.451, "high": 1.453,
                   "low": 1.448, "close": 1.449}
        self.assertFalse(exit_position(book, retrace))
        self.assertFalse(advance_trailing_stop(book, retrace))
        self.assertEqual(book["position"]["stop"], 1.445)
        exit_bar = {"time": 101 * 900, "open": 1.449, "high": 1.451,
                    "low": 1.44, "close": 1.441}
        self.assertTrue(exit_position(book, exit_bar))
        self.assertEqual(book["closed"][0]["exit_type"], "TRAIL_STOP")
        self.assertAlmostEqual(book["closed"][0]["exit"], 1.445)
        self.assertGreater(book["closed"][0]["net_usd"], 0)

    def test_short_stop_monotone_without_fixed_profit_cap(self):
        book = self.trailing_book(-1)
        first = {"time": 900, "open": 1.4, "high": 1.405,
                 "low": 1.36, "close": 1.386}
        self.assertFalse(exit_position(book, first))
        self.assertTrue(advance_trailing_stop(book, first))
        self.assertAlmostEqual(book["position"]["stop"], 1.396)
        second = {"time": 1800, "open": 1.386, "high": 1.390,
                  "low": 1.33, "close": 1.340}
        self.assertFalse(exit_position(book, second))
        self.assertTrue(advance_trailing_stop(book, second))
        self.assertAlmostEqual(book["position"]["stop"], 1.35)
        self.assertFalse(advance_trailing_stop(book, {
            "time": 2700, "open": 1.343, "high": 1.345,
            "low": 1.341, "close": 1.344,
        }))
        self.assertAlmostEqual(book["position"]["stop"], 1.35)
        self.assertTrue(exit_position(book, {
            "time": 3600, "open": 1.344, "high": 1.355,
            "low": 1.343, "close": 1.354,
        }))
        self.assertEqual(book["closed"][0]["exit_type"], "TRAIL_STOP")
        self.assertGreater(book["closed"][0]["net_usd"], 0)

    def test_no_same_bar_lookahead_green_from_intrabar_wick(self):
        book = self.trailing_book()
        # An intrabar peak is NOT enough to tighten. The closing value
        # improves by only 0.2R; the former stop did not get hit.
        volatile = {"time": 900, "open": 1.4, "high": 1.460,
                    "low": 1.391, "close": 1.402}
        self.assertFalse(exit_position(book, volatile))
        advance_trailing_stop(book, volatile)
        self.assertAlmostEqual(book["position"]["stop"], 1.392)
        self.assertFalse(book["position"]["green_protected"])
        self.assertEqual(book["closed"], [])

    def test_gap_below_stop_can_lose_even_after_stop_protects_green(self):
        book = self.trailing_book()
        bar = {"time": 900, "open": 1.4, "high": 1.42,
               "low": 1.395, "close": 1.415}
        self.assertFalse(exit_position(book, bar))
        advance_trailing_stop(book, bar)
        self.assertTrue(book["position"]["green_protected"])
        gap = {"time": 10000, "open": 1.38, "high": 1.386,
               "low": 1.378, "close": 1.382}
        self.assertTrue(exit_position(book, gap))
        self.assertAlmostEqual(book["closed"][0]["exit"], 1.38)
        self.assertLess(book["closed"][0]["net_usd"], 0)

    def test_trailing_stop_loss_after_return_without_first_green(self):
        book = self.trailing_book()
        decline = {"time": 900, "open": 1.4, "high": 1.401,
                   "low": 1.389, "close": 1.393}
        self.assertTrue(exit_position(book, decline))
        self.assertEqual(book["closed"][0]["exit_type"], "STOP")
        self.assertLess(book["closed"][0]["net_usd"], 0)

    def test_legacy_position_keeps_target_and_time_policy(self):
        legacy = self.trailing_book(stop_policy="legacy_fixed")
        legacy["position"]["target"] = 1.42
        self.assertTrue(exit_position(legacy, {
            "time": 900, "open": 1.4, "high": 1.43,
            "low": 1.399, "close": 1.422,
        }))
        self.assertEqual(legacy["closed"][0]["exit_type"], "TARGET")
        again = self.trailing_book(stop_policy="legacy_fixed")
        self.assertTrue(exit_position(again, {
            "time": 34*900, "open": 1.4, "high": 1.41,
            "low": 1.399, "close": 1.405,
        }))
        self.assertEqual(again["closed"][0]["exit_type"], "TIME")

    def test_report_shows_live_trailing_stop_level(self):
        book = self.trailing_book()
        book["last_reason"] = "Em posição"
        body = "\n".join(digest(book, "2026-10-26"))
        self.assertIn("stop móvel", body)
        self.assertIn("sem TP", body)
        self.assertIn("1.39000", body)

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

    def test_combined_report_contains_eleventh_and_independent_capital(self):
        from src.daily_digest import digest as full_digest
        from src.gold_forward import update as gold_update
        from src.leveraged_gold import update as leveraged_update
        rows = []
        price = 2750.0
        for i in range(1100):
            close = price + 0.25
            rows.append({
                "time": 1729728000 + i * 3600,
                "open": price, "high": close + 1.0,
                "low": price - 1.0, "close": close,
            })
            price = close
        report = full_digest(
            "2026-10-26", gold_update(None, rows),
            leveraged_update(None, rows), mtf=update(None, minutes())
        )
        self.assertIn("11 robôs", report)
        self.assertIn("BB20 Pullback H1/M15", report)
        self.assertIn("51,000", report)
        self.assertIn("Sem operações reais", report)
        self.assertLess(len(report), 4000)

    def test_digest_names_eleventh_without_claiming_real_fills(self):
        state = update(None, minutes())
        lines = digest(state, "2026-10-26")
        self.assertIn("11º ROBÔ", lines[0])
        self.assertTrue(any("virtual" in line for line in lines))


if __name__ == "__main__":
    unittest.main()
