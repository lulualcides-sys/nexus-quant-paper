"""No-network regression suite for public genuine WINQ26 and frozen ATLAS v3."""
from __future__ import annotations

from datetime import datetime,timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from research.atlas_winq26_public import canonicalize, SYMBOL, SOURCE_BLOB
from research.atlas_confluence_v3 import v3_signal, VARIANTS, confirmed_pivots
from research.atlas_winq26_validation import _period, TF


def sample_raw(path, *, duplicated=False):
    entries=[]
    day=datetime(2026,6,1,9,10)
    for d in range(4):
        open_day=day+timedelta(days=d)
        for i in range(350):
            t=open_day+timedelta(minutes=i)
            price=150000+5*((i+d)%5)
            entries.append((t,f"{SYMBOL};{t:%d/%m/%Y};{t:%H:%M:%S};"
                            f"{price},00;{price+10},00;{price-10},00;{price+5},00;"
                            f"10.000.000,00;73"))
    if duplicated:
        entries.append(entries[0])
    path.write_text("\n".join(x[1] for x in reversed(entries))+"\n",encoding="utf-8")


class AtlasWinq26ResearchTests(unittest.TestCase):
    def test_source_pinned_and_conversion_uses_qty_not_financial_volume(self):
        self.assertEqual(len(SOURCE_BLOB),40)
        with TemporaryDirectory() as td:
            a=Path(td)/"raw.csv";b=Path(td)/"normalized.csv"
            sample_raw(a)
            info=canonicalize(a,b)
            self.assertEqual(info["symbol"],"WINQ26")
            self.assertEqual(info["candles"],1400)
            self.assertTrue(info["simulator_uses_traded_contract_quantity"])
            from research.win_price_data import read_win_csv
            x=read_win_csv(b,expected_symbol="WINQ26")
            self.assertEqual(x["timeframe_seconds"],60)
            self.assertEqual(x["bars"][0]["volume"],73)
            self.assertEqual(x["bars"][-1]["volume"],73)
            self.assertEqual(x["bars"][0]["open"]%5,0)

    def test_source_rejects_duplicate_minute(self):
        with TemporaryDirectory() as td:
            a=Path(td)/"raw.csv";b=Path(td)/"normalized.csv"
            sample_raw(a,duplicated=True)
            with self.assertRaisesRegex(ValueError,"minutos duplicados"):
                canonicalize(a,b)

    def test_source_rejects_off_tick_prices(self):
        with TemporaryDirectory() as td:
            a=Path(td)/"raw.csv";b=Path(td)/"normalized.csv"
            sample_raw(a)
            c=a.read_text()
            a.write_text(c.replace("150000,00","150001,00",1))
            with self.assertRaisesRegex(ValueError,"grade de 5 pontos"):
                canonicalize(a,b)

    def test_v3_uses_only_closed_bars_no_future_leakage(self):
        bars=[]
        for i in range(110):
            bars.append({"time":i*60,"open":100.0,"high":102.0,
                         "low":98.0,"close":100.0,"volume":100.0})
        bars[85] = {**bars[85],"open":98.0,"high":100.0,
                    "low":97.0,"close":99.5,"volume":300.0}
        with patch("research.atlas_confluence_v3.baseline",return_value=1):
            a=v3_signal(bars,85,"fib_confluence_v3")
            bars[86]={**bars[86],"high":20000.0,"close":10000.0}
            self.assertEqual(a,v3_signal(bars,85,"fib_confluence_v3"))
            self.assertEqual(a,1)
        self.assertEqual(v3_signal(bars,0,"fib_confluence_v3"),0)

    def test_pivots_use_trailing_closed_confirmation(self):
        prior=[]
        for val in (2,3,9,3,2,1,8,2,3):
            prior.append({"high":val,"low":-val})
        self.assertEqual(confirmed_pivots(prior,"high"),[9,8])
        self.assertEqual(confirmed_pivots(prior,"low"),[-9,-8])

    def test_models_fixed_and_preperiod_60bar_warmup(self):
        self.assertEqual(len(VARIANTS),5)
        self.assertEqual(TF,{"M1":60,"M5":300,"M15":900,"M30":1800,"H1":3600})
        from research.win_price_data import TZ
        import datetime as dt
        start=int(dt.datetime(2026,6,1,9,10,tzinfo=TZ).timestamp())
        # 60 complete historical bars prior to the first June tradeable bar.
        bars=[{"time":start-86400-60*(60-i)} for i in range(60)]
        bars += [{"time":start+i*60} for i in range(540)]
        self.assertEqual(len(_period(bars,"2026-06-01","2026-07-01")),600)


if __name__=="__main__":
    unittest.main()
