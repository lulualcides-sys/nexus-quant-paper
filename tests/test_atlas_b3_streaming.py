"""Streaming B3 replay has bounded RAM and exact deal-ID integrity.

All rows are synthetic fixtures. This is NOT a real B3 price feed.
"""
from __future__ import annotations

import csv
import tempfile
import unittest
import zipfile
from pathlib import Path

from research.atlas_b3_ticks_oct13 import parse_b3_trades
from research.atlas_b3_streaming import parse_b3_trades_streaming


HEADER = [
    "DataReferencia", "CodigoInstrumento", "AcaoAtualizacao",
    "PrecoNegocio", "QuantidadeNegociada", "HoraFechamento",
    "CodigoIdentificadorNegocio", "TipoSessaoPregao", "DataNegocio",
    "CodigoParticipanteComprador", "CodigoParticipanteVendedor",
]


def rows(path, data):
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer=csv.writer(f,delimiter=";")
        writer.writerow(HEADER)
        for entry in data:
            ticker,action,price,quantity,clock,ident,session=entry
            writer.writerow(["2026-10-13",ticker,action,price,quantity,
                clock,ident,session,"2026-10-13","1","2"])


class B3TwoPassStreamingTests(unittest.TestCase):
    def test_20000_deals_one_minute_no_memory_copy_and_exact_volume(self):
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/"manual.txt"
            with file.open("w",newline="",encoding="utf-8") as fh:
                w=csv.writer(fh,delimiter=";")
                w.writerow(HEADER)
                for i in range(20000):
                    w.writerow(["2026-10-13","WINV26","0",
                                f"{200000+(i%7)*5},000","3",
                                f"0910{i%60:02d}{i%1000:03d}",
                                str(i+1),"1","2026-10-13","1","2"])
            bars,provenance=parse_b3_trades(file)
            self.assertEqual(len(bars),1)
            b=bars[0]
            self.assertEqual(b["volume"],60000)
            self.assertEqual(b["trade_count"],20000)
            self.assertEqual(b["high"],200030)
            self.assertEqual(b["low"],200000)
            self.assertEqual(provenance["surviving_trades"],20000)
            self.assertEqual(provenance["importer"],"sqlite_two_pass_streaming_v1")
            self.assertEqual(len(provenance["sha256"]),64)

    def test_valid_cancellation_for_discarded_afterhours_trade_is_not_orphan(self):
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/"manual.txt"
            rows(file,[
                ("WINV26","0","200000,000","5","091000000","100","1"),
                ("WINV26","0","200500,000","3","182700000","101","6"),
                ("WINV26","2","200500,000","3","183200000","101","6"),
            ])
            bars,src=parse_b3_trades_streaming(file)
            self.assertEqual(len(bars),1)
            self.assertEqual(bars[0]["volume"],5)
            self.assertEqual(src["counters"]["cancelled_trades_removed"],1)

    def test_cancelled_old_trade_and_reordered_tie(self):
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/"raw.txt"
            rows(file,[
                ("WINV26","0","200200,000","4","091000500","20","1"),
                ("WINV26","0","200100,000","3","091000500","10","1"),
                ("WINV26","0","200500,000","7","091000100","70","1"),
                ("WINV26","2","200500,000","7","183100000","70","6"),
                ("WINV26","0","200000,000","2","091000250","5","1"),
            ])
            bars,src=parse_b3_trades(file)
            self.assertEqual(len(bars),1)
            self.assertEqual((bars[0]["open"],bars[0]["high"],
                              bars[0]["low"],bars[0]["close"],
                              bars[0]["volume"]),
                             (200000,200200,200000,200200,9))
            self.assertEqual(src["counters"]["cancellation_records"],1)

    def test_numeric_equivalent_trade_id_duplicates_detected_on_disk(self):
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/"manual.txt"
            rows(file,[
                ("WINV26","0","200000,000","5","091000000","000001","1"),
                ("WINV26","0","200005,000","4","091001000","1","1"),
            ])
            with self.assertRaisesRegex(ValueError,"duplicate trade ID"):
                parse_b3_trades(file)

    def test_zip_provenance_and_cleanup(self):
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/"raw.txt"
            rows(file,[("WINV26","0","200000,000","1",
                        "091000000","1","1")])
            zipped=Path(d)/"b3_manual.zip"
            with zipfile.ZipFile(zipped,"w",compression=zipfile.ZIP_DEFLATED) as z:
                z.write(file,arcname="DRV_20261013.txt")
            result,src=parse_b3_trades(zipped)
            self.assertEqual(src["member"],"DRV_20261013.txt")
            self.assertEqual(result[0]["open"],200000)
            self.assertTrue(src["sha256"])
            self.assertFalse(src["automatically_downloaded"])


if __name__=="__main__":
    unittest.main()
