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
        for row in history:
            row["high"] = 100300.0
        history[5]["high"] = 100400.0
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

    def test_reenters_after_losses_beyond_old_daily_cap_and_hits_stop_win(self):
        # Four consecutive losses exceed former daily R$40 guard; fifth
        # valid signal must still open and close at the take-profit.
        bars = candles()
        stop_indices = (71, 81, 91, 101)
        for i in stop_indices:
            bars[i].update(low=99940.0, high=100015.0)
        bars[111].update(low=99985.0, high=100110.0)
        signals = {69, 79, 89, 99, 109}
        def setup(_bars, i, _cfg):
            return ({"setup": "break_retest", "side": 1,
                     "stop": 99950.0, "signal_time": bars[i]["time"]}
                    if i in signals else None)
        with patch("research.win_price_action.candidate", side_effect=setup):
            report = simulate(bars)
        self.assertEqual(report["closed"], 5)
        self.assertEqual([t["reason"] for t in report["trades"]],
                         ["STOP", "STOP", "STOP", "STOP", "TARGET"])
        self.assertEqual([t["net_brl"] for t in report["trades"]],
                         [-16.0, -16.0, -16.0, -16.0, 14.0])
        self.assertEqual(report["net_brl"], -50.0)
        self.assertEqual(report["rejected"].get("daily_stop"), None)
        self.assertFalse(report["daily_loss_limit_enabled"])
        self.assertTrue(report["stop_red_enabled"])
        self.assertTrue(report["stop_win_enabled"])

    def test_never_stacks_new_entries_while_trade_is_open(self):
        bars = candles()
        bars[75].update(low=99940.0, high=100015.0)
        def signal_while_open(_bars, i, _cfg):
            return ({"setup": "break_retest", "side": 1,
                     "stop": 99950.0, "signal_time": bars[i]["time"]}
                    if i in range(69, 75) else None)
        with patch("research.win_price_action.candidate", side_effect=signal_while_open):
            result = simulate(bars)
        self.assertEqual(result["closed"], 1)
        self.assertEqual(result["trades"][0]["entry_time"], bars[70]["time"])
        self.assertEqual(result["trades"][0]["exit_time"], bars[75]["time"])
        self.assertEqual(result["max_concurrent_positions"], 1)

    def test_gap_during_position_invalidates_quality_even_if_stop_not_visible(self):
        bars = candles()
        # Entry on M1 index 70; skip precisely one minute before 71.
        for bar in bars[71:]:
            bar["time"] += 60
        setup = {"setup": "break_retest", "side": 1, "stop": 99950.0,
                 "signal_time": bars[69]["time"]}
        with patch("research.win_price_action.candidate",
                   side_effect=lambda _bars, i, _cfg: setup if i == 69 else None):
            out = simulate(bars)
        self.assertEqual(out["closed"], 1)
        self.assertEqual(out["trades"][0]["reason"], "UNVERIFIABLE_DATA_GAP")
        self.assertEqual(out["unverifiable_position_gap_exits"], 1)
        self.assertEqual(out["status"], "BACKTEST_HAS_UNVERIFIABLE_POSITION_GAPS")
        self.assertEqual(out["net_brl"], -16.0)

    def test_unrealized_trade_is_marked_separately_from_closed_pnl(self):
        bars = candles()
        setup = {"setup": "break_retest", "side": 1, "stop": 99950.0,
                 "signal_time": bars[138]["time"]}
        with patch("research.win_price_action.candidate",
                   side_effect=lambda _bars, i, _cfg: setup if i == 138 else None):
            out = simulate(bars)
        self.assertEqual(out["closed"], 0)
        self.assertTrue(out["open_at_end"])
        self.assertEqual(out["net_brl"], 0.0)
        self.assertEqual(out["open_position_mark_to_market_net_brl"], -6.0)
        self.assertEqual(out["equity_including_open_mark_brl"], 1994.0)

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
