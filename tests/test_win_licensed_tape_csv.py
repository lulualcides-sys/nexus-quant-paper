"""Independent licensed Profit CSV flow importer unit tests, synthetic only.

No paid Nelogica data or other people's trade tapes are fetched/redistributed.
"""
import csv
import json
import tempfile
import unittest
from datetime import datetime,timedelta
from pathlib import Path

from research.win_licensed_tape_csv import (
    side,parse_brazil_number,parse_event_time,safe_trade_rows,
    build_minutes,private_output,source_hash
)
from research.win_flow_public_label_comparison import independent_signals

HEADER=("Ativo","Data","Tempo","Número do negócio","Preço","Quantidade",
        "Volume","Agente comprador","Agente vendedor","Agressor","After")

def make_rows():
    root=datetime(2026,11,3,9,10,0)
    result=[]
    for minute in range(21):
        for i in range(25):
            t=root+timedelta(minutes=minute,milliseconds=2000+i*2300)
            if minute==20:
                price=(100020 if i==0 else 100090 if i==1 else
                       99985 if i==2 else 100050 if i==24 else 100035)
                aggressor="3" if i<20 else "2"
                size=6
            else:
                price=(100050 if i==0 or i==24 else
                       100100 if i==1 else 100000 if i==2 else 100040)
                aggressor="2" if i<12 else "3"
                size=4
            result.append(("WINZ26",t.strftime("%d/%m/%Y"),t.strftime("%H:%M:%S.%f")[:-3],
                           str(minute*25+i+1),f"{price:,}".replace(",","X").replace(".",",").replace("X",".")+",00",
                           str(size),"0","BUY_AGENT_SECRET","SELL_AGENT_SECRET",aggressor,"N"))
    return result

def create_csv(path,rows,separator=";"):
    with open(path,"w",encoding="utf-8-sig",newline="") as fp:
        writer=csv.writer(fp,delimiter=separator)
        writer.writerow(HEADER)
        writer.writerows(rows)

class LicensedTapeTests(unittest.TestCase):
    def test_portuguese_headers_and_brazil_decimal(self):
        self.assertEqual(parse_brazil_number("100.005,00"),100005)
        self.assertEqual(parse_brazil_number("6"),6)
        self.assertEqual(parse_brazil_number("100005.0"),100005)
        self.assertRaises(ValueError,parse_brazil_number,"NaN")

    def test_official_trade_type_only_accepts_buy_two_sell_three(self):
        self.assertEqual(side("2"),1)
        self.assertEqual(side("3"),-1)
        self.assertEqual(side("COMPRA"),1)
        self.assertEqual(side("VENDA"),-1)
        self.assertEqual(side("RLP"),0)
        self.assertEqual(side("13"),0)
        self.assertEqual(side("leilão"),0)
        self.assertEqual(side("desconhecido"),0)

    def test_timestamp_is_real_sao_paulo_local_and_keeps_milliseconds(self):
        ms=parse_event_time("03/11/2026","09:10:02.300")
        self.assertEqual(ms,int(datetime(2026,11,3,12,10,2,300000).timestamp()*1000))
        self.assertRaises(ValueError,parse_event_time,"03/11/2026","23:60:00")

    def test_exact_synthetic_tape_yields_causal_buy_without_magic_threshold_fitting(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"licensed_sample.csv"
            create_csv(path,make_rows())
            events=list(safe_trade_rows(path,"WINZ26","2026-11-03"))
            self.assertEqual(len(events),525)
            minutes,quality=build_minutes(events)
            self.assertEqual(quality["minute_bars"],21)
            self.assertEqual(quality["valid_flow_minutes"],21)
            self.assertTrue(all(r["independent_m1_volume_crosscheck_performed"] is False for r in minutes))
            self.assertEqual(minutes[-1]["real_volume"],150)
            self.assertEqual(minutes[-1]["buy_volume"],30)
            self.assertEqual(minutes[-1]["sell_volume"],120)
            self.assertEqual(minutes[-1]["delta"],-90)
            signals,stats=independent_signals(minutes)
            self.assertEqual(len(signals),1)
            self.assertEqual(stats["price_candidates"],1)
            self.assertEqual(signals[0]["side"],1)
            self.assertEqual(signals[0]["minute"],9*60+31)
            self.assertEqual(signals[0]["source"],"NQ_INDEPENDENT_EXHAUSTION_NOT_TRACKER")
            out=Path(td)/"private_mt5"/"test.json"
            digest=private_output({"quality":quality,"minutes":minutes,"signals":signals},out)
            saved=out.read_text(encoding="utf-8")
            self.assertEqual(len(digest),64)
            self.assertEqual(len(source_hash(path)),64)
            self.assertNotIn("BUY_AGENT_SECRET",saved)
            self.assertNotIn("SELL_AGENT_SECRET",saved)

    def test_missing_aggressor_always_reduces_coverage(self):
        rows=make_rows()
        rows[-1]=(*rows[-1][:-2],"32",rows[-1][-1])
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"test.csv"
            create_csv(path,rows)
            events=list(safe_trade_rows(path,"WINZ26","2026-11-03"))
            minutes,_=build_minutes(events)
            self.assertEqual(minutes[-1]["unknown_volume"],6)
            self.assertEqual(minutes[-1]["classified_trade_count"],24)
            self.assertFalse(minutes[-1]["valid_flow"])
            signals,_=independent_signals(minutes)
            self.assertEqual(signals,[])

    def test_duplicate_trade_id_is_fatal_not_double_counted(self):
        rows=make_rows()
        rows[1]=(*rows[1][:3],rows[0][3],*rows[1][4:])
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"test.csv";create_csv(path,rows)
            with self.assertRaisesRegex(ValueError,"duplicate trade"):
                list(safe_trade_rows(path,"WINZ26","2026-11-03"))

    def test_mixed_contract_is_fatal_even_if_related_to_WIN(self):
        rows=make_rows()
        rows[-1]=("WINV26",*rows[-1][1:])
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"test.csv";create_csv(path,rows)
            with self.assertRaisesRegex(ValueError,"Unexpected contract"):
                list(safe_trade_rows(path,"WINZ26","2026-11-03"))

    def test_reject_continuous_contract_and_future_day_and_off_grid_prices(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"test.csv";create_csv(path,make_rows())
            with self.assertRaises(ValueError):
                list(safe_trade_rows(path,"WINFUT","2026-11-03"))
            rows=make_rows()
            rows[0]=(*rows[0][:4],"100.002,00",*rows[0][5:])
            create_csv(path,rows)
            with self.assertRaisesRegex(ValueError,"Off-grid"):
                list(safe_trade_rows(path,"WINZ26","2026-11-03"))
            with self.assertRaises(ValueError):
                list(safe_trade_rows(path,"WINZ26","2026-11-05"))

    def test_out_of_order_timestamp_is_fatal(self):
        rows=make_rows()
        rows[1]=(*rows[1][:2],rows[0][2],*rows[1][3:])
        rows[2]=(*rows[2][:2],"09:10:00.000",*rows[2][3:])
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"test.csv";create_csv(path,rows)
            with self.assertRaisesRegex(ValueError,"Out-of-order"):
                list(safe_trade_rows(path,"WINZ26","2026-11-03"))

    def test_missing_candle_minute_fails_first_after_gap(self):
        ticks=make_rows()
        kept=[r for r in ticks if not r[2].startswith("09:15:")]
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"test.csv";create_csv(path,kept)
            minutes,_=build_minutes(safe_trade_rows(path,"WINZ26","2026-11-03"))
            self.assertIn("m1_gap_before",minutes[5]["reject_reasons"])
            self.assertFalse(minutes[5]["valid_flow"])
            signals,_=independent_signals(minutes)
            self.assertEqual(signals,[])

    def test_zero_price_zero_quantity_and_negative_and_non_numeric_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"test.csv"
            for changed_index,value in [(4,"0"),(5,"0"),(5,"-1"),(4,"abc")]:
                rows=make_rows()
                r=list(rows[0]);r[changed_index]=value;rows[0]=tuple(r)
                create_csv(path,rows)
                with self.assertRaises(ValueError):
                    list(safe_trade_rows(path,"WINZ26","2026-11-03"))

    def test_cannot_write_private_signal_results_outside_ignored_folder(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                private_output({"signals":[]},Path(td)/"public.json")

if __name__=="__main__":
    unittest.main()
