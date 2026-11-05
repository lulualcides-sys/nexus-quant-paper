"""B3 tick replay tests use artificial FIXTURE ONLY, never market evidence."""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from research.atlas_b3_ticks_oct13 import parse_b3_trades, match_signals


HEADER = [
    "DataReferencia", "CodigoInstrumento", "AcaoAtualizacao",
    "PrecoNegocio", "QuantidadeNegociada", "HoraFechamento",
    "CodigoIdentificadorNegocio", "TipoSessaoPregao", "DataNegocio",
    "CodigoParticipanteComprador", "CodigoParticipanteVendedor", "TipoDoCanal",
]


def sample_file(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as stream:
        w = csv.writer(stream, delimiter=";")
        w.writerow(HEADER)
        for sym, action, price, qty, clock, ident, session in rows:
            w.writerow([
                "2026-10-13", sym, action, price, qty, clock, ident,
                session, "2026-10-13", "3", "4", "1",
            ])


class AtlasB3TicksTests(unittest.TestCase):
    def test_correct_time_and_id_sort_cancellation_and_no_fake_candles(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "drv.txt"
            sample_file(path, [
                ("DI1F27", "0", "14,150", "100", "090001000", "10", "1"),
                # Source is intentionally NOT in chronological order.
                ("WINV26", "0", "200050,000", "5", "090459999", "40", "1"),
                ("WINV26", "0", "200000,000", "30", "090055000", "10", "1"),
                ("WINV26", "0", "200100,000", "2", "090130500", "20", "1"),
                ("WINV26", "0", "199900,000", "1", "090130500", "30", "1"),
                ("WINV26", "2", "210000,000", "7", "101500000", "60", "1"),
                ("WINV26", "0", "200200,000", "4", "091000000", "50", "1"),
                ("WINV26", "0", "210000,000", "7", "091200000", "60", "1"),
                ("WINV26", "0", "200150,000", "1", "091459000", "70", "1"),
                ("WINV26", "0", "200500,000", "3", "182455000", "80", "1"),
                ("WINV26", "0", "200600,000", "10", "183120000", "90", "1"),
                ("WINZ26", "0", "202000,000", "3", "100000000", "10", "1"),
            ])
            bars, src = parse_b3_trades(path)
            self.assertEqual(len(bars), 3)
            first, second, third = bars
            self.assertEqual(
                (first["open"], first["high"], first["low"], first["close"],
                 first["volume"], first["trade_count"]),
                (200000, 200100, 199900, 200050, 38, 4)
            )
            self.assertEqual(
                (second["open"], second["high"], second["low"], second["close"],
                 second["volume"], second["trade_count"]),
                (200200, 200200, 200150, 200150, 5, 2)
            )
            self.assertEqual(third["volume"], 3)
            self.assertEqual(src["surviving_trades"], 7)
            self.assertEqual(src["counters"]["cancellation_records"], 1)
            self.assertTrue(src["sha256"])
            report = match_signals(bars, src)
            self.assertEqual(report["status"], "insufficient_win_v26_m1_coverage")
            self.assertIsNone(report["winrate"])
            self.assertFalse(report["trades_executed"])

    def test_zip_import_one_member(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "drv.csv"
            sample_file(path, [("WINV26", "0", "200000,000", "3", "090100000", "10", "1")])
            archive = Path(td) / "manual.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.write(path, arcname="DRV_20261013.csv")
            candles, provenance = parse_b3_trades(archive)
            self.assertEqual(len(candles), 1)
            self.assertEqual(provenance["member"], "DRV_20261013.csv")

    def test_off_tick_and_duplicate_trade_ids_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "drv.txt"
            sample_file(path, [("WINV26", "0", "200001,000", "1", "090100000", "10", "1")])
            with self.assertRaisesRegex(ValueError, "grade de 5 pontos"):
                parse_b3_trades(path)
            sample_file(path, [
                ("WINV26", "0", "200000,000", "1", "090100000", "10", "1"),
                ("WINV26", "0", "200050,000", "1", "090200000", "10", "1"),
            ])
            with self.assertRaisesRegex(ValueError, "duplicate trade ID"):
                parse_b3_trades(path)

    def test_orphan_cancellation_or_unknown_action_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "drv.txt"
            sample_file(path, [
                ("WINV26", "0", "200000,000", "3", "090100000", "10", "1"),
                ("WINV26", "2", "200000,000", "3", "090200000", "50", "1"),
            ])
            with self.assertRaisesRegex(ValueError, "Orphan cancellations"):
                parse_b3_trades(path)
            sample_file(path, [("WINV26", "1", "200000,000", "2", "090100000", "10", "1")])
            with self.assertRaisesRegex(ValueError, "unsupported trade action"):
                parse_b3_trades(path)

    def test_fixture_never_claims_trackers_27_executions(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "drv.txt"
            sample_file(path, [("WINV26", "0", "200000,000", "10", "091000000", "10", "1")])
            candles, src = parse_b3_trades(path)
            report = match_signals(candles, src)
            self.assertIsNone(report["net_brl"])
            self.assertIsNone(report["matches"])
            self.assertTrue(report["promotional_claim_27_signals_not_verified"])


if __name__ == "__main__":
    unittest.main()
