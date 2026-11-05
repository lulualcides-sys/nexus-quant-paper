"""No-network tests for fair ATLAS M5/M15/M30/H1 retrospective comparisons."""
import unittest
from unittest.mock import patch

from research.atlas_mtf_comparison import (
    MIN_M5_BARS, TIMEFRAMES, parse_5m, resample_m5, run, simulate,
)


def sample_m5(n=2500, *, missing_volume=False):
    base = 1791000000 // 3600 * 3600
    return [{"time": base + i * 300,
             "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0,
             **({} if missing_volume else {"volume": 100.0})}
            for i in range(n)]


class AtlasMultiTimeframeTests(unittest.TestCase):
    def test_all_timeframes_resample_closed_contiguous_groups(self):
        source = sample_m5(2400)
        for name, seconds in TIMEFRAMES.items():
            candles = resample_m5(source, seconds)
            self.assertEqual(len(candles), len(source) * 300 // seconds)
            self.assertEqual(candles[0]["time"] % seconds, 0)
            self.assertEqual(candles[0]["volume"], seconds / 300 * 100.0)
            self.assertEqual(candles[0]["high"], 101.0)
            self.assertEqual(candles[-1]["close"], 100.0)

    def test_gap_not_interpolated(self):
        data = sample_m5(36)
        data.pop(4)
        self.assertEqual(len(resample_m5(data, 900)), 11)
        self.assertEqual(len(resample_m5(data, 1800)), 5)
        self.assertEqual(len(resample_m5(data, 3600)), 2)

    def test_no_volume_yields_unavailable_winrate_not_zero(self):
        source = sample_m5(2500, missing_volume=True)
        for tf, seconds in TIMEFRAMES.items():
            result = simulate(resample_m5(source, seconds), timeframe=tf, cost_bps=7)
            self.assertEqual(result["status"], "insufficient_volume")
            self.assertIsNone(result["winrate_pct"])
            self.assertIsNone(result["net_usd"])

    def test_flat_price_data_no_fabricated_winrate(self):
        source = sample_m5(2500)
        study = run(source)
        self.assertEqual(set(study["timeframes"]), set(TIMEFRAMES))
        for frame in TIMEFRAMES:
            for scenario in (7, 14, 28):
                row = study["timeframes"][frame]["scenarios"][str(scenario)]
                self.assertEqual(row["closed"], 0)
                self.assertIsNone(row["winrate_pct"])
                self.assertEqual(row["net_usd"], 0)
                self.assertFalse(row["position_open_at_end"])

    def test_historical_parser_excludes_unfinished_and_broken_candles(self):
        ts = 1791000000 // 300 * 300
        n = MIN_M5_BARS + 1
        quote = {key: [value] * n for key, value in
                 (("open", 100), ("high", 102), ("low", 98), ("close", 101), ("volume", 125))}
        payload = {"chart": {"result": [{
            "timestamp": [ts + 300 * i for i in range(n)],
            "indicators": {"quote": [quote]}}]}}
        now = ts + n * 300 + 181
        results = parse_5m(payload, now)
        self.assertEqual(len(results), n)
        self.assertEqual(results[-1]["volume"], 125)
        # If final bar isn't closed, 500 valid bars remain.
        results = parse_5m(payload, ts + n * 300 + 100)
        self.assertEqual(len(results), n-1)

    def test_same_bar_stop_wins_over_target_in_historical_replay(self):
        # Replay uses the same core step as live-paper, without rewriting risk.
        source = sample_m5(2500)
        from src import atlas_vector as atlas
        last_signal_index = 60
        # At i=61 an order based on i-1 is created, then low touches stop and
        # high touches target; the conservative outcome must be a stopped trade.
        source[61] = {**source[61], "high": 108, "low": 92}
        with patch.object(atlas, "signal", side_effect=lambda bars, i: 1 if i == last_signal_index else 0):
            row = simulate(source, timeframe="M5", cost_bps=7)
        self.assertGreaterEqual(row["closed"], 1)
        self.assertGreaterEqual(row["uncertain_same_bar_exits"], 1)
        self.assertEqual(row["wins"], 0)
        self.assertLess(row["net_usd"], 0)


if __name__ == "__main__":
    unittest.main()
