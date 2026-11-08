"""Isolated deterministic test suite; no exchange calls or live state."""
import csv
import hashlib
import io
import math
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from research.nexus_m1m5.data import (Bar, aggregate_closed_m15, get_month,
                                       month_range, normalize_time, parse_rows)
from research.nexus_m1m5.engine import (PortfolioGate, SCENARIOS, _summary, replay)
from research.nexus_m1m5.run import judgement, split_folds
from research.nexus_m1m5.strategies import Signal, SPECS, build_features, signal


def sample(step=60_000, n=340):
    return [Bar(i * step, 100., 100.1, 99.9, 100., 100., 60.) for i in range(n)]


def binance_row(t_micro=1735689600000000, step_micro=60_000_000):
    return [str(t_micro), "100", "102", "99", "101", "12",
            str(t_micro + step_micro - 1), "1200", "100", "6", "600", "0"]


class DataTests(unittest.TestCase):
    def test_epoch_scale(self):
        self.assertEqual(normalize_time("1735689600000000"), (1735689600000, 1000))
        self.assertEqual(normalize_time("1704067200000"), (1704067200000, 1))
        with self.assertRaises(ValueError):
            normalize_time("0")

    def test_spot_microseconds_and_taker_volume(self):
        b = parse_rows([binance_row()], "1m", expected_month="2025-01")[0]
        self.assertEqual((b.t, b.c, b.taker), (1735689600000, 101, 6))

    def test_duplicate_gap_reorder_and_wrong_month_fail(self):
        first = binance_row()
        second = binance_row(1735689600000000 + 2 * 60_000_000)
        for rows in ([first, first], [first, second], [second, first]):
            with self.subTest(rows=rows):
                with self.assertRaises(ValueError):
                    parse_rows(rows, "1m")
        with self.assertRaises(ValueError):
            parse_rows([first], "1m", expected_month="2025-02")

    def test_ohlc_zero_volume_spot_time_and_taker_guard(self):
        row = binance_row()
        row[3] = "103"
        with self.assertRaises(ValueError):
            parse_rows([row], "1m")
        row = binance_row()
        row[9] = "13"
        with self.assertRaises(ValueError):
            parse_rows([row], "1m")
        row = binance_row()
        row[0] = "1735689600000"  # incorrect milliseconds in 2025 public zip
        with self.assertRaises(ValueError):
            parse_rows([row], "1m")

    def test_checksum_rejects_modified_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "BTCUSDT" / "1m"
            d.mkdir(parents=True)
            name = "BTCUSDT-1m-2025-01.zip"
            (d / name).write_bytes(b"tampered")
            (d / (name + ".CHECKSUM")).write_text("f" * 64 + "  " + name)
            with self.assertRaises(ValueError):
                get_month("BTCUSDT", "1m", "2025-01", Path(tmp))

    def test_15m_no_future_or_invented_candles(self):
        bars = sample(300_000, 10)
        h = aggregate_closed_m15(bars)
        self.assertEqual([x.t for x in h], [0, 900_000, 1_800_000])
        broken = bars[:]
        broken[1] = Bar(301_000, 100, 101, 99, 100, 100, 50)
        h2 = aggregate_closed_m15(broken)
        self.assertEqual([x.t for x in h2], [900_000, 1_800_000])

    def test_month_windows(self):
        self.assertEqual(list(month_range("2026-10", 3)), ["2026-08", "2026-09", "2026-10"])
        with self.assertRaises(ValueError):
            list(month_range("2026-13", 1))


class StrategiesTests(unittest.TestCase):
    def test_six_distinct_configurations(self):
        self.assertEqual(set(SPECS), {"sweep", "vwap", "trend", "breakout", "squeeze", "flow"})
        self.assertEqual(sum(v["tf"] == "1m" for v in SPECS.values()), 2)
        self.assertEqual(sum(v["tf"] == "5m" for v in SPECS.values()), 4)

    def test_no_future_information_changes_signal(self):
        bars = sample(n=400)
        feats = build_features(bars)
        extended = bars + [
            Bar((400 + k) * 60_000, 100, 120, 10, 20, 1e7, 1e7) for k in range(10)]
        extended_feats = build_features(extended)
        for name in ("sweep", "vwap", "breakout", "squeeze", "flow"):
            self.assertEqual(
                signal(name, bars, feats, 330),
                signal(name, extended, extended_feats, 330),
                name)

    def test_m15_never_uses_unclosed_higher_candle(self):
        bars = sample(step=300_000, n=1200)
        features = build_features(bars)
        h = aggregate_closed_m15(bars)
        hf = build_features(h)
        times = [x.t + 900_000 for x in h]
        i = 900
        original = signal("trend", bars, features, i, higher=h,
                          higher_features=hf, higher_closes=times)
        # Distort later M15 candle only; decision at i must be identical.
        changed = h[:]
        last = changed[-1]
        changed[-1] = Bar(last.t, last.o, last.h + 100, last.l,
                          last.c + 100, last.v, last.taker)
        changed_f = build_features(changed)
        result = signal("trend", bars, features, i, higher=changed,
                        higher_features=changed_f,
                        higher_closes=[x.t + 900_000 for x in changed])
        self.assertEqual(original, result)

    def test_unknown_breakout_mode_rejected(self):
        bars = sample(n=240)
        with self.assertRaises(ValueError):
            signal("breakout", bars, build_features(bars), 220, breakout_mode="random")


class ExecutionTests(unittest.TestCase):
    @staticmethod
    def deterministic_signal(name, bars, features, i, **kwargs):
        if i == 210:
            return Signal("sweep", 1.25, 2.0, 99.8, "test_signal")
        return None

    def test_next_open_and_stop_before_target(self):
        bars = sample()
        bars[211] = Bar(211 * 60_000, 100, 102, 98, 100, 100, 60)
        feat = build_features(bars)
        with patch("research.nexus_m1m5.engine.signal", side_effect=self.deterministic_signal):
            report, records = replay(bars, feat, "sweep", start=210, stop=230)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["signal_t"], bars[210].t)
        self.assertEqual(records[0]["entry_t"], bars[211].t)
        self.assertEqual(records[0]["exit_reason"], "stop")
        self.assertLess(records[0]["pnl_usd"], 0)

    def test_double_cost_and_adverse_are_not_cheaper(self):
        bars, feat = sample(), None
        feat = build_features(bars)
        stats = []
        for scenario in ("base", "double_cost", "adverse"):
            with patch("research.nexus_m1m5.engine.signal", side_effect=self.deterministic_signal):
                r, trades = replay(bars, feat, "sweep", scenario, start=210, stop=230)
            self.assertEqual(len(trades), 1)
            stats.append(r)
        self.assertLess(stats[1]["net_usd"], stats[0]["net_usd"])
        self.assertLess(stats[2]["net_usd"], stats[0]["net_usd"])
        self.assertEqual(SCENARIOS["base"]["fee"], .001)

    def test_gap_down_cannot_fill_at_old_stop(self):
        bars = sample()
        bars[212] = Bar(212 * 60_000, 97, 98, 96, 97, 100, 60)
        feat = build_features(bars)
        with patch("research.nexus_m1m5.engine.signal", side_effect=self.deterministic_signal):
            report, trades = replay(bars, feat, "sweep", start=210, stop=230)
        self.assertEqual(trades[0]["exit_reason"], "gap_stop")
        self.assertLess(trades[0]["exit"], trades[0]["stop"])

    def test_daily_loss_lock_blocks_new_entries(self):
        # Large down gap forces daily-loss lock (stop cannot eliminate gap loss).
        bars = sample()
        bars[212] = Bar(212 * 60_000, 90, 90.1, 89, 90, 100, 50)
        feat = build_features(bars)
        def many_signals(name, bars, features, i, **kw):
            if i in (210, 213):
                return Signal("sweep", 1.25, 2.0, 99.8, "test")
        with patch("research.nexus_m1m5.engine.signal", side_effect=many_signals):
            r, trades = replay(bars, feat, "sweep", start=210, stop=230)
        self.assertEqual(r["signals"], 1)
        self.assertEqual(len(trades), 1)

    def test_portfolio_lock_correlation_stale_and_capacity(self):
        g = PortfolioGate()
        g.opened("x", "BTCUSDT", 2000, 10000)
        self.assertFalse(g.can_open("y", "BTCUSDT", 1000, 10000))
        self.assertFalse(g.can_open("y", "ETHUSDT", 2000, 10000, stale=True))
        self.assertFalse(g.can_open("y", "ETHUSDT", 2000, 10000, sync_ok=False))
        g.opened("y", "ETHUSDT", 2000, 10000)
        self.assertFalse(g.can_open("z", "ETHUSDT", 500, 10000))
        self.assertFalse(g.can_open("z", "BTCUSDT", 500, 10000))
        g.closed("x")
        self.assertEqual(len(g.positions), 1)

    def test_no_lookahead_on_fold_boundary(self):
        bars = sample()
        f = build_features(bars)
        with patch("research.nexus_m1m5.engine.signal", side_effect=self.deterministic_signal):
            a, _ = replay(bars, f, "sweep", start=211, stop=230)
        self.assertEqual(a["trades_closed"], 0)


class EvaluationTests(unittest.TestCase):
    def test_three_walkforward_windows_and_final_not_in_validation(self):
        folds, final = split_folds(list(month_range("2026-10", 12)))
        self.assertEqual(len([k for k in folds if k.startswith("walkforward")]), 3)
        self.assertEqual(folds["validation"][1], final[0])
        self.assertEqual(folds["final_intocado_primeiro_uso"], final)

    def test_negative_profit_is_rejected(self):
        r = {"trades_closed": 100, "net_usd": -10}
        other = {"net_usd": -20}
        self.assertEqual(judgement(r, other, other, [r, r, r])[0], "REPROVADO")

    def test_zero_sample_is_inconclusive(self):
        self.assertEqual(judgement({"trades_closed": 0}, {}, {}, [])[0],
                         "INCONCLUSIVO")

    def test_bootstrap_does_not_fabricate_small_sample_confidence(self):
        summary = _summary([], daily=[10000] * 100)
        self.assertIsNone(summary["ci95_expectancy_day_bootstrap_usd"])
        self.assertIsNone(summary["winrate"])


if __name__ == "__main__":
    unittest.main()
