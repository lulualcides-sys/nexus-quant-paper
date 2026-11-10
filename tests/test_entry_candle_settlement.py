"""Regression: paper execution must settle stops on the entry candle.

All OHLC here is synthetic test input, not a claimed market backtest.
Entries take place at the current candle OPEN. Its high/low happen after that
open (unknown ordering), so stop wins on ambiguous stop/target touches.
"""
import unittest
from unittest.mock import patch

from src.strategies import make_indicators
from src.gold_forward import evaluate_bar as gold_bar
from src.leveraged_gold import one_bar as leverage_bar
from src.experimental_h1 import step as h1_bar, book as h1_book
from src.momentum60_shadow import step as momentum_bar
from src.crypto_paper import step as crypto_bar, book as crypto_book


def bars(n=280, step=14400, *, low=70.0, high=130.0):
    start = 1760000000 // step * step
    data = [{"time": start + j * step, "open": 100.0,
             "high": 101.0, "low": 99.0, "close": 100.0} for j in range(n)]
    data[-1] = {"time": data[-1]["time"], "open": 100.0,
                "high": high, "low": low, "close": 100.0}
    return data


class EntryCandleFillTests(unittest.TestCase):
    def test_conventional_gold_stop_beats_target_on_entry_bar(self):
        data = bars()
        b = {"equity": 5000.0, "closed": [], "position": None}
        with patch("src.gold_forward.sign", side_effect=[1, 0]) as mock:
            gold_bar(b, "channel20", data, make_indicators(data), len(data)-1)
        self.assertEqual(mock.call_count, 2)
        self.assertIsNone(b["position"])
        self.assertEqual(len(b["closed"]), 1)
        self.assertEqual(b["closed"][0]["exit_type"], "STOP")
        self.assertEqual(b["closed"][0]["entry_ts"], b["closed"][0]["exit_ts"])
        self.assertLess(b["closed"][0]["net_usd"], 0)

    def test_conventional_gold_target_same_bar_when_stop_not_hit(self):
        data = bars(low=99)
        b = {"equity": 5000.0, "closed": [], "position": None}
        with patch("src.gold_forward.sign", side_effect=[1, 0]):
            gold_bar(b, "channel20", data, make_indicators(data), len(data)-1)
        self.assertEqual(b["closed"][0]["exit_type"], "TARGET")
        self.assertGreater(b["closed"][0]["net_usd"], 0)

    def test_leveraged_gold_entry_bar_stop_includes_fees(self):
        data = bars()
        b = {"equity": 5000.0, "peak_equity": 5000.0,
             "today": None, "day_start_equity": 5000.0,
             "frozen": False, "closed": [], "position": None}
        with patch("src.leveraged_gold.sign", side_effect=[1, 0]) as mock:
            leverage_bar(b, "lev_channel20", data, make_indicators(data),
                         len(data)-1, mode="green_runner")
        self.assertEqual(mock.call_count, 2)
        self.assertEqual(len(b["closed"]), 1)
        self.assertEqual(b["closed"][0]["exit_type"], "STOP")
        self.assertGreater(b["closed"][0]["transaction_cost"], 0)
        self.assertIsNone(b["position"])

    def test_h1_entry_bar_stop_keeps_entry_count(self):
        data = bars(step=3600)
        b = h1_book()
        called = []
        def signal(strategy, data, ind, i):
            called.append(i)
            return 1
        h1_bar(b, "EURUSD", "channel10", data, make_indicators(data),
               len(data)-1, signal_fn=signal)
        self.assertEqual(called, [len(data)-2])
        self.assertEqual(len(b["entries"]), 1)
        self.assertEqual(len(b["closed"]), 1)
        self.assertEqual(b["closed"][0]["exit_type"], "STOP")
        self.assertLess(b["closed"][0]["net_usd"], 0)
        self.assertIsNone(b["position"])

    def test_h1_negative_candle_cannot_become_nonexistent_hold(self):
        data = bars(step=3600)
        b = h1_book()
        h1_bar(b, "USDJPY", "ema20_retest", data, make_indicators(data),
               len(data)-1, signal_fn=lambda *_: 1)
        self.assertEqual(b["diagnostics"]["entered"], 1)
        self.assertEqual(b["diagnostics"]["exited"], 1)
        self.assertLess(b["closed"][0]["net_usd"], 0)

    def test_momentum60_entry_bar_stop(self):
        data = bars()
        b = {"equity": 5000.0, "position": None, "entries": [], "closed": []}
        with patch("src.momentum60_shadow.candidate_signal",
                   side_effect=[1, 0]) as mock:
            momentum_bar(b, data, make_indicators(data), len(data)-1)
        self.assertEqual(mock.call_count, 2)
        self.assertEqual(len(b["entries"]), 1)
        self.assertEqual(len(b["closed"]), 1)
        self.assertEqual(b["closed"][0]["exit_type"], "STOP")
        self.assertIsNone(b["position"])

    def test_crypto_entry_bar_stop_with_slippage_and_fees(self):
        data = bars(step=3600)
        b = crypto_book()
        with patch("src.crypto_paper.signal", return_value=True) as mock:
            crypto_bar(b, "channel20", data, make_indicators(data), len(data)-1)
        self.assertEqual(mock.call_count, 1)
        self.assertEqual(b["entries"], 1)
        self.assertEqual(len(b["closed"]), 1)
        self.assertEqual(b["closed"][0]["exit_type"], "STOP")
        self.assertLess(b["closed"][0]["net_usd"], 0)
        self.assertGreater(b["closed"][0]["cost_usdt"], 0)

    def test_no_backfill_if_no_signal(self):
        data = bars()
        b = {"equity": 5000.0, "closed": [], "position": None}
        with patch("src.gold_forward.sign", side_effect=[0, 0]):
            gold_bar(b, "channel20", data, make_indicators(data), len(data)-1)
        self.assertEqual(b["closed"], [])
        self.assertIsNone(b["position"])


if __name__ == "__main__":
    unittest.main()
