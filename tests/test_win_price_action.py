"""Focused tests of new WIN price action research; synthetic bars are NOT backtests."""
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from research.win_price_action import (
    Settings, _m5_closed, _range_rejection, _regime, candidate, simulate
)

BR = ZoneInfo("America/Sao_Paulo")


def candles(n=140):
    start = datetime(2026, 11, 9, 9, 10, tzinfo=BR)
    return [{
        "time": int((start + timedelta(minutes=i)).timestamp()),
        "open": 100000.0, "high": 100015.0, "low": 99985.0,
        "close": 100000.0, "volume": 100.0
    } for i in range(n)]


class WinPriceActionTests(unittest.TestCase):
    def test_m5_never_uses_unclosed_bars(self):
        bars = candles()
        for i in (68, 69, 70, 71, 79, 129):
            complete = _m5_closed(bars, i)
            self.assertTrue(all(x["time"] + 300 <= bars[i]["time"] + 60
                                for x in complete))
            self.assertEqual(complete, _m5_closed(bars[:i + 1], i))

    def test_regime_direction_not_single_trendline_break(self):
        def block(high, low):
            return [{"high": high, "low": low, "close": (high + low) / 2}] * 6
        self.assertEqual(_regime(block(100200, 100000) + block(100400, 100100)), "up")
        self.assertEqual(_regime(block(100400, 100200) + block(100250, 100050)), "down")
        self.assertEqual(_regime(block(100400, 100000) + block(100400, 100000)), "range")
        self.assertEqual(_regime(block(100200, 100000)), "unknown")

    def test_range_requires_twice_touched_boundaries(self):
        history = [
            {"high": 100400.0, "low": 100000.0, "close": 100200.0}
            for _ in range(12)
        ]
        bars = candles()
        bars[-1].update(open=100040.0, low=100005.0,
                        close=100055.0, high=100070.0)
        setup = _range_rejection(bars, len(bars)-1, history, Settings())
        self.assertEqual(setup["setup"], "range_rejection")
        self.assertEqual(setup["side"], 1)
        self.assertEqual(setup["stop"], 100000.0)
        history[0]["high"] = 100300.0
        history[-1]["high"] = 100300.0
        self.assertIsNone(_range_rejection(bars, len(bars)-1, history, Settings()))

    def test_future_bars_do_not_change_old_candidate(self):
        bars = candles()
        self.assertEqual(candidate(bars, 120), candidate(bars + [{
            **bars[-1], "time": bars[-1]["time"] + 60, "open": 90000.0,
            "high": 150000.0, "close": 149000.0
        }], 120))

    def test_next_bar_entry_and_conservative_ambiguous_stop(self):
        bars = candles()
        bars[71].update(low=99940.0, high=100120.0)
        setup = {"setup": "break_retest", "side": 1, "stop": 99950.0,
                 "signal_time": bars[69]["time"]}
        with patch("research.win_price_action.candidate",
                   side_effect=lambda _bars, i, _cfg: setup if i == 69 else None):
            report = simulate(bars)
        self.assertEqual(report["closed"], 1)
        t = report["trades"][0]
        self.assertEqual(t["entry_time"], bars[70]["time"])
        self.assertEqual(t["exit_time"], bars[71]["time"])
        self.assertEqual(t["reason"], "STOP")
        self.assertTrue(t["ambiguous_same_candle"])
        self.assertEqual(t["net_brl"], -16.0)
        self.assertEqual(report["net_brl"], -16.0)
        self.assertTrue(report["one_contract_only"])

    def test_stop_size_includes_roundtrip_cost(self):
        bars = candles()
        setup = {"setup": "break_retest", "side": 1, "stop": 99920.0,
                 "signal_time": bars[69]["time"]}
        with patch("research.win_price_action.candidate",
                   side_effect=lambda _bars, i, _cfg: setup if i == 69 else None):
            report = simulate(bars)
        self.assertEqual(report["closed"], 0)
        self.assertFalse(report["open_at_end"])
        self.assertEqual(report["rejected"]["risk"], 1)

    def test_no_real_trade_or_fake_profit_without_csv(self):
        bars = candles()
        result = simulate(bars)
        self.assertEqual(result["status"], "EXPERIMENTAL_PAPER_NOT_VALIDATED")
        self.assertEqual(result["closed"], 0)
        self.assertIsNone(result["win_rate_pct"])
        self.assertEqual(result["net_brl"], 0.0)

    def test_rejects_bad_inputs(self):
        with self.assertRaisesRegex(ValueError, "100 real"):
            simulate(candles(20))
        with self.assertRaisesRegex(ValueError, "risk fractions"):
            simulate(candles(), Settings(risk_fraction=0.0))


if __name__ == "__main__":
    unittest.main()
