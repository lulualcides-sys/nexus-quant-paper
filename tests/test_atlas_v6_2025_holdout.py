"""Isolation tests for research-only WINFUT continuous source and V6 holdout."""
import csv
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from research.atlas_v6_2025_holdout import (
    parse_profit_continuous, run_study, PERIODS, SOURCE_BLOB, SOURCE_COMMIT
)
from research.win_price_data import TZ

def fixture(file, symbol="WINFUT", duplicate=False, offgrid=False, bad_quantity=False):
    with file.open("w", encoding="utf-8", newline="") as fp:
        out=csv.writer(fp,delimiter=";")
        out.writerow(["Ativo","Data","Hora","Abertura","Máximo","Mínimo","Fechamento",
                      "Volume","Quantidade"])
        start=datetime(2025,11,3,9,10)
        for i in reversed(range(102)):
            clock=start+timedelta(minutes=i*5)
            price="168.501" if offgrid and i==10 else "168.500"
            q="0" if bad_quantity and i==10 else "95"
            out.writerow([symbol,clock.strftime("%d/%m/%Y"),clock.strftime("%H:%M:%S"),
                          price,"168.550","168.450","168.500","125.000,00",q])
        if duplicate:
            out.writerow([symbol,"03/11/2025","09:10:00",
                          "168.500","168.550","168.450","168.500","125.000,00","95"])

class HoldoutTests(unittest.TestCase):
    def test_2025_periods_and_source_frozen(self):
        self.assertEqual([p[0] for p in PERIODS],["2025-09","2025-10","2025-11","2025-12"])
        self.assertEqual(len(SOURCE_BLOB),40)
        self.assertEqual(len(SOURCE_COMMIT),40)

    def test_profit_contract_quantity_not_monetary_volume(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/"profit.csv"
            fixture(f)
            rows=parse_profit_continuous(f)
            self.assertEqual(len(rows),102)
            self.assertEqual(rows[0][1:5],(168500,168550,168450,168500))
            self.assertEqual(rows[0][-1],95)
            self.assertLess(rows[0][0],rows[-1][0])

    def test_reject_mismatch_duplicate_tick_and_broken_volume(self):
        scenarios=[({"symbol":"WINV26"},"exact WINFUT"),
                   ({"duplicate":True},"Duplicate"),
                   ({"offgrid":True},"grade"),
                   ({"bad_quantity":True},"volume/quantity")]
        for options, expected in scenarios:
            with self.subTest(options=options):
                with tempfile.TemporaryDirectory() as td:
                    f=Path(td)/"profit.csv"
                    fixture(f,**options)
                    with self.assertRaisesRegex(ValueError,expected):
                        parse_profit_continuous(f)

    def test_empty_month_does_not_fabricate_performance(self):
        time=int(datetime(2024,1,3,9,10,tzinfo=TZ).astimezone(timezone.utc).timestamp())
        bars=[{"time":time+i*300,"open":168500,"high":168550,
               "low":168450,"close":168500,"volume":95} for i in range(200)]
        data=run_study({"bars":bars,"symbol":"WINFUT"},{"sha256":"SYNTHETIC"})
        self.assertTrue(all(p["status"]=="INSUFFICIENT_DATA" for p in data["periods"].values()))
        self.assertTrue(all(v["nmonths"]==0 and v["closed"]==0 for v in data["aggregate_stress"].values()))
        self.assertFalse(data["approved_for_paper_or_live"])
        self.assertFalse(data["prospective_forward_test"])
        self.assertTrue(data["contract_identity_unknown"])
        self.assertEqual(data["decision"],"REJECT_PROMOTION_MISSING_CONTRACT_AND_FILL_AUDIT")

if __name__=="__main__":
    unittest.main()
