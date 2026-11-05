"""Research-only validation: signal isolation, no repaint, WIN tick + BRL math."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from research import atlas_tracker_v2 as v2
from research import atlas_win_backtest as win
from research.win_price_data import TZ, read_win_csv, resample
from src import atlas_vector as atlas


def gold_bars(n=100):
    return [{"time": i * 300, "open": 100.0, "close": 100.0,
             "high": 101.0, "low": 99.0, "volume": 100.0} for i in range(n)]


def win_bars(n=160):
    start = int(datetime(2026, 10, 29, 9, 0, tzinfo=TZ).timestamp())
    return [{"time": start + 60 * i, "open": 140000.0, "close": 140000.0,
             "high": 140005.0, "low": 139995.0, "volume": 100.0}
            for i in range(n)]


class TrackerEvidenceTests(unittest.TestCase):
    def test_v2_does_not_invent_missing_original_signal(self):
        data = gold_bars()
        for mode in v2.VARIANTS:
            self.assertEqual(v2.candidate(data, 80, mode), 0)

    def test_v2_rejection_and_atr_are_checked_using_past_only(self):
        data = gold_bars()
        data[60] = {**data[60], "open": 99.0, "close": 101.5,
                    "low": 98.5, "high": 102.0}
        with patch.object(v2, "ORIGINAL_SIGNAL", return_value=1):
            self.assertEqual(v2.candidate(data, 60, "original"), 1)
            self.assertEqual(v2.candidate(data, 60, "exhaustion_v2"), 1)
            self.assertEqual(v2.candidate(data, 60, "exhaustion_direction_v2"), 0)
            # Changing the NEXT candle cannot change signal on the closed one.
            data[61] = {**data[61], "close": 40000, "high": 40001}
            self.assertEqual(v2.candidate(data, 60, "exhaustion_v2"), 1)
            data[60] = {**data[60], "close": 99.0}
            self.assertEqual(v2.candidate(data, 60, "exhaustion_v2"), 0)

    def test_b3_worst_way_rounding_nominal_rr(self):
        buy = win._round_levels({"entry": 100002.5, "target": 100015.0, "stop": 99985.0}, 1)
        sell = win._round_levels({"entry": 100002.5, "target": 99985.0, "stop": 100015.0}, -1)
        self.assertEqual(buy, {"entry": 100005.0, "target": 100015.0, "stop": 99985.0})
        self.assertEqual(sell, {"entry": 100000.0, "target": 99985.0, "stop": 100015.0})

    def test_win_no_signal_not_fake_zero_winrate(self):
        data = win_bars()
        result = win.simulate(data, timeframe="M1", variant="original", fee_brl=4.0)
        self.assertEqual(result["closed"], 0)
        self.assertIsNone(result["winrate_pct"])
        self.assertEqual(result["net_brl"], 0)

    def test_win_stop_first_with_integer_contracts_and_brl_costs(self):
        data = win_bars()
        data[61] = {**data[61], "high": 140020.0, "low": 139980.0}
        with patch.object(win, "candidate", side_effect=lambda bars, i, var: 1 if i == 60 else 0):
            base = win.simulate(data, timeframe="M1", variant="original",
                                fee_brl=4.0, slip_ticks=0)
            higher = win.simulate(data, timeframe="M1", variant="original",
                                  fee_brl=4.0, slip_ticks=2)
        self.assertEqual(base["closed"], 1)
        self.assertEqual(base["wins"], 0)
        self.assertEqual(base["uncertain_same_bar_exits"], 1)
        trade = base["closed_ledger"][0]
        self.assertEqual(trade["contracts"], 3)
        self.assertEqual(trade["reason"], "STOP_SAME_BAR")
        self.assertEqual(trade["entry"], 140000)
        self.assertEqual(trade["exit"], 139985)
        self.assertAlmostEqual(base["net_brl"], -21.0)  # -9 points P&L BRL - R$12 fees
        self.assertLess(higher["net_brl"], base["net_brl"])

    def test_win_contract_csv_real_prices_and_volume_required(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "win.csv"
            start = datetime(2026, 10, 29, 9, 0)
            def write(spot=False, mixed=False):
                with path.open("w", encoding="utf-8") as f:
                    f.write("Ativo;Data;Hora;Open;High;Low;Close;Volume\n")
                    for i in range(130):
                        instant = start + timedelta(minutes=i)
                        ticker = "WINZ26" if mixed and i == 100 else "WINV26"
                        price = "140.002,50" if spot and i == 90 else "140.000"
                        f.write(f"{ticker};{instant:%d/%m/%Y};{instant:%H:%M};"
                                f"{price};140.005;139.995;140.000;1.000\n")
            write()
            dataset = read_win_csv(path, expected_symbol="WINV26")
            self.assertEqual(dataset["symbol"], "WINV26")
            self.assertEqual(dataset["timeframe_seconds"], 60)
            self.assertEqual(len(dataset["bars"]), 130)
            self.assertEqual(dataset["bars"][0]["open"], 140000)
            self.assertEqual(dataset["bars"][0]["volume"], 1000)
            self.assertEqual(len(resample(dataset["bars"], 300, base_seconds=60)), 26)
            write(spot=True)
            with self.assertRaisesRegex(ValueError, "grade de 5 pontos"):
                read_win_csv(path)
            write(mixed=True)
            with self.assertRaisesRegex(ValueError, "Múltiplos vencimentos"):
                read_win_csv(path)

    def test_win_csv_is_not_downloaded_silently(self):
        with self.assertRaises(FileNotFoundError):
            read_win_csv("/this/source/is/not/provided/real_win.csv")


if __name__ == "__main__":
    unittest.main()
