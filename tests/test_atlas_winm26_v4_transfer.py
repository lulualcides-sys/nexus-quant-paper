"""No-network tests for independent WINM26 M5 Profit export validation."""
from __future__ import annotations
import tempfile
import unittest
from datetime import datetime,timedelta
from pathlib import Path
from research.atlas_winm26_v4_transfer import canonicalize,SYMBOL,SOURCE_GIT_SHA,_cut,_quality,MONTHS
from research.win_price_data import read_win_csv

def sample(path, *,bad_symbol=False,off_tick=False):
    start=datetime(2026,3,2,9,10)
    rows=[]
    day=start
    while len(rows)<1200:
        if day.weekday()<5:
            for i in range(100):
                t=day+timedelta(minutes=5*i)
                o="200001,00" if off_tick and not rows else "200000,00"
                symbol="WINZ26" if bad_symbol and not rows else SYMBOL
                rows.append(
                    f"{symbol};{t:%d/%m/%Y};{t:%H:%M:%S};{o};200020,00;"
                    "199980,00;200000,00;10.000.000,00;200"
                )
        day+=timedelta(days=1)
    path.write_text("\n".join(reversed(rows))+"\n",encoding="utf-8")

class CrossContractImportTests(unittest.TestCase):
    def test_pinned_source_is_a_distinct_contract(self):
        self.assertEqual(SYMBOL,"WINM26")
        self.assertEqual(len(SOURCE_GIT_SHA),40)
        self.assertEqual(len(MONTHS),3)

    def test_profit_5m_contract_quantity_not_money(self):
        with tempfile.TemporaryDirectory() as d:
            raw=Path(d)/"profit.csv";out=Path(d)/"m5.csv"
            sample(raw)
            imported=canonicalize(raw,out)
            self.assertEqual(imported["symbol"],"WINM26")
            self.assertEqual(imported["timeframe_seconds"],300)
            self.assertEqual(imported["bars"][0]["volume"],200)
            self.assertEqual(len(imported["bars"]),1200)
            quality=_quality(imported["bars"],"2026-03-01","2026-04-01")
            self.assertEqual(quality["days_with_65_or_more_m5"],12)
            # No pre-period tradeable warmup in this synthetic input.
            self.assertIsNone(_cut(imported["bars"],"2026-03-01","2026-04-01"))

    def test_refuse_off_tick_or_mixed_contract(self):
        for opts,pattern in (({"off_tick":True},"grade de 5 pontos"),
                             ({"bad_symbol":True},"WINM26")):
            with self.subTest(opts=opts):
                with tempfile.TemporaryDirectory() as d:
                    raw=Path(d)/"profit.csv";out=Path(d)/"normalized.csv"
                    sample(raw,**opts)
                    with self.assertRaisesRegex(ValueError,pattern):
                        canonicalize(raw,out)

if __name__=="__main__":
    unittest.main()
