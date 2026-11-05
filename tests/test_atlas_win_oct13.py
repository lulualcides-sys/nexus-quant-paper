"""ATLAS Oct 13: reject unsupported claims and malformed Profit data."""
import csv
from datetime import datetime,timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from research.atlas_win_oct13 import analyze,convert_profit,labels_from_csv


def fixture(path,n=500,offtick=False,symbol="WINV26",duplicate=False):
    start=datetime(2026,10,13,9,10)
    with path.open("w",encoding="utf-8",newline="") as fp:
        w=csv.writer(fp,delimiter=";")
        w.writerow(["Ativo","Data","Hora","Abertura","Máximo","Mínimo","Fechamento",
                    "Volume","Quantidade"])
        for i in reversed(range(n)):
            dt=start+timedelta(minutes=i)
            openprice="208001,00" if i==100 and offtick else "208000,00"
            w.writerow([symbol,dt.strftime("%d/%m/%Y"),dt.strftime("%H:%M:%S"),
                        openprice,"208100,00","207900,00","208050,00",
                        "10000000,00","80"])
        if duplicate:
            w.writerow([symbol,"13/10/2026","09:10:00","208000,00",
                        "208100,00","207900,00","208050,00","10000000,00","80"])


class TrackerOctoberTests(unittest.TestCase):
    def test_full_day_without_labels_reports_unverified_not_winrate(self):
        with TemporaryDirectory() as td:
            file=Path(td)/"profit.csv";fixture(file)
            report=analyze(file)
            self.assertEqual(report["contract"],"WINV26")
            self.assertEqual(report["target_day_m1_candles"],500)
            self.assertTrue(report["session_complete"])
            self.assertEqual(report["status"],"awaiting_verified_video_labels")
            self.assertEqual(report["verified_video_labels"],0)
            self.assertIsNone(report["comparisons"])
            self.assertFalse(report["financial_performance_validated"])

    def test_financial_volume_not_confused_with_quantity(self):
        with TemporaryDirectory() as td:
            file=Path(td)/"profit.csv";canonical=Path(td)/"normalized.csv"
            fixture(file)
            data,meta=convert_profit(file,canonical)
            self.assertEqual(data["bars"][0]["volume"],80)
            self.assertEqual(data["bars"][0]["open"],208000)
            self.assertTrue(meta["quantity_is_traded_contract_count"])
            self.assertEqual(len(meta["sha256"]),64)

    def test_rejects_symbol_mismatch_tick_and_duplicate(self):
        for opts,error in (({"symbol":"WINZ26"},"WINV26"),({"offtick":True},"grade de 5 pontos"),
                           ({"duplicate":True},"Duplicate")):
            with self.subTest(opts=opts):
                with TemporaryDirectory() as td:
                    file=Path(td)/"profit.csv";fixture(file,**opts)
                    with self.assertRaisesRegex(ValueError,error):
                        convert_profit(file,Path(td)/"normalized.csv")

    def test_420_candles_are_not_a_complete_session(self):
        with TemporaryDirectory() as td:
            file=Path(td)/"profit.csv";fixture(file,n=420)
            result=analyze(file)
            self.assertEqual(result["target_day_m1_candles"],420)
            self.assertEqual(result["missing_session_minutes"],80)
            self.assertEqual(result["status"],"incomplete_session_no_signal_replay")
            self.assertFalse(result["session_complete"])
            self.assertIsNone(result["comparisons"])

    def test_partial_day_does_not_claim_winrate(self):
        with TemporaryDirectory() as td:
            file=Path(td)/"profit.csv";fixture(file,n=230)
            result=analyze(file)
            self.assertEqual(result["status"],"insufficient_m1_data")
            self.assertIsNone(result["comparisons"])

    def test_evidence_needs_market_time_and_post_close(self):
        with TemporaryDirectory() as td:
            file=Path(td)/"labels.csv"
            file.write_text("date,market_time,side,evidence_url,observed_after_close\n"
                            "2026-10-13,10:25:00,buy,https://example.org/video,yes\n",
                            encoding="utf-8")
            self.assertEqual(len(labels_from_csv(file)),1)
            file.write_text(file.read_text().replace(",yes",",unknown"))
            with self.assertRaisesRegex(ValueError,"Invalid video label"):
                labels_from_csv(file)

if __name__=="__main__":
    unittest.main()
