"""No network: MT5 export input hardening and real-volume guarantee."""
import tempfile
import unittest
from datetime import datetime,timedelta
from pathlib import Path

from research.win_mt5_history_import import import_mt5_bars


def mt5_sample(n=150):
    first=datetime(2026,11,9,9,10,0)
    h="<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n"
    bars=[f"{t:%Y.%m.%d}\t{t:%H:%M:%S}\t100000\t100010\t99990\t100005\t120\t50\t2"
          for t in [first+timedelta(minutes=i) for i in range(n)]]
    return h,bars


class Mt5ImporterTests(unittest.TestCase):
    def test_native_bars_import_with_explicit_timezone(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/"WINZ26_M1.csv"
            h,rows=mt5_sample()
            src.write_text(h+"\n".join(rows)+"\n",encoding="utf-8")
            output=Path(td)/"norm.csv"
            audit=import_mt5_bars(src,output,expected_symbol="WINZ26",
                                  server_utc_offset_hours=-3)
            self.assertEqual(audit["candles_m1"],150)
            self.assertEqual(audit["intraday_gaps"],0)
            self.assertEqual(audit["trading_days_with_session_quotes"],1)
            self.assertEqual(audit["source_format"],
                             "MT5 native Bars CSV real volume, no adjusted continuous futures")
            self.assertTrue(output.read_text(encoding="utf-8").startswith("Ativo;Data;Hora"))
            self.assertEqual(output.read_text(encoding="utf-8").splitlines()[1].split(";")[7],"50")

    def test_drop_m1_bar_records_hole_without_faking_prices(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/"WINZ26_M1.csv"
            h,rows=mt5_sample()
            del rows[22]
            src.write_text(h+"\n".join(rows)+"\n")
            audit=import_mt5_bars(src,Path(td)/"out.csv",
                                  expected_symbol="WINZ26",server_utc_offset_hours=-3)
            self.assertEqual(audit["intraday_gaps"],1)
            self.assertEqual(audit["intraday_missing_minutes"],1)

    def test_rejects_missing_real_contract_volume(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/"WINZ26_M1.csv"
            h,rows=mt5_sample()
            rows[10]=rows[10].replace("\t50\t2","\t0\t2")
            src.write_text(h+"\n".join(rows)+"\n")
            with self.assertRaisesRegex(ValueError,"real_volume"):
                import_mt5_bars(src,Path(td)/"out.csv",
                                expected_symbol="WINZ26",server_utc_offset_hours=-3)

    def test_rejects_wrong_ticker_filename(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/"WINV26_M1.csv"
            h,rows=mt5_sample()
            src.write_text(h+"\n".join(rows)+"\n")
            with self.assertRaisesRegex(ValueError,"filename"):
                import_mt5_bars(src,Path(td)/"out.csv",
                                expected_symbol="WINZ26",server_utc_offset_hours=-3)

    def test_timezone_must_be_supplied_cannot_infer(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/"WINZ26_M1.csv"
            h,rows=mt5_sample()
            src.write_text(h+"\n".join(rows)+"\n")
            with self.assertRaisesRegex(ValueError,"Confirm exact"):
                import_mt5_bars(src,Path(td)/"out.csv",
                                expected_symbol="WINZ26",server_utc_offset_hours=None)

    def test_duplicate_m1_timestamps_are_refused(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/"WINZ26_M1.csv"
            h,rows=mt5_sample()
            rows.insert(33,rows[32])
            src.write_text(h+"\n".join(rows)+"\n")
            with self.assertRaisesRegex(ValueError,"chronological"):
                import_mt5_bars(src,Path(td)/"out.csv",
                                expected_symbol="WINZ26",server_utc_offset_hours=-3)

    def test_cannot_overwrite_source(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/"WINZ26_M1.csv"
            h,rows=mt5_sample()
            src.write_text(h+"\n".join(rows)+"\n")
            with self.assertRaisesRegex(ValueError,"overwrite"):
                import_mt5_bars(src,src,
                                expected_symbol="WINZ26",server_utc_offset_hours=-3)


if __name__=="__main__":
    unittest.main()
