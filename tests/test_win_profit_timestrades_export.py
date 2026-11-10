"""Cross-platform tests for a local Profit Times&Trades-like CSV profile.

All rows are synthetic. This test DOES NOT verify a real Profit-exported file,
Rico live data, original Greenhouse source, profit, fills, or licensing.
"""
import csv
import tempfile
import unittest
from datetime import datetime,timedelta
from pathlib import Path

from research.win_profit_timestrades_export import (
    iter_profit_export,analyze_profit_export
)

COLS=["Ativo","Data","Hora","Valor","Quantidade","Agressor"]

def synthetic():
    rows=[]
    zero=datetime(2026,11,3,9,10)
    for k in range(21):
        for j in range(25):
            dt=zero+timedelta(minutes=k,milliseconds=1000+j*2300)
            if k==20:
                px=100020 if j==0 else 100090 if j==1 else 99985 if j==2 else 100050 if j==24 else 100035
                aggressor="Vendedor" if j<20 else "Comprador"
                qty=6
            else:
                px=100050 if j in (0,24) else 100100 if j==1 else 100000 if j==2 else 100040
                aggressor="Comprador" if j<12 else "Vendedor"
                qty=4
            rows.append(["WINZ26",dt.strftime("%d/%m/%Y"),
                         dt.strftime("%H:%M:%S.%f")[:-3],
                         f"{px//1000}.{px%1000:03},00",str(qty),aggressor])
    return rows

def create(path,rows,header=COLS,delimiter=";"):
    with open(path,"w",encoding="utf-8-sig",newline="") as fh:
        writer=csv.writer(fh,delimiter=delimiter)
        writer.writerow(header)
        writer.writerows(rows)

class ProfitTimesTradesAdapterTests(unittest.TestCase):
    def test_525_real_shaped_synthetic_trades_and_causal_m1_signal(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"profit.csv";create(path,synthetic())
            result=analyze_profit_export(path,target_contracts=100)
            self.assertEqual(result["trade_events"],525)
            self.assertEqual(result["symbol"],"WINZ26")
            self.assertEqual(result["day"],"2026-11-03")
            self.assertEqual(result["m1_quality"]["minute_bars"],21)
            self.assertEqual(result["m1_quality"]["valid_flow_minutes"],21)
            self.assertEqual(result["exchange_trade_ids_available"],False)
            self.assertEqual(len(result["m1_signals"]),1)
            self.assertEqual(result["m1_signals"][0]["side"],1)
            self.assertEqual(result["m1_signals"][0]["minute"],9*60+31)
            self.assertGreater(len(result["volume_bars"]),0)
            self.assertTrue(result["no_live_order_approval"])

    def test_explicit_columns_buy_and_sell_labels_only(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"buy.csv";create(path,synthetic()[:2])
            events=list(iter_profit_export(path))
            self.assertEqual([x["aggressor"] for x in events],[1,1])
            self.assertTrue(all(x["has_exchange_trade_id"] is False for x in events))

    def test_unknown_aggressor_is_kept_unknown_not_synthetic_buy(self):
        rows=synthetic()
        rows[-1][-1]="RLP"
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"unknown.csv";create(path,rows)
            result=analyze_profit_export(path,target_contracts=100)
            self.assertGreater(result["m1_quality"]["unclassified_trade_rows"],0)
            self.assertLess(result["m1_quality"]["valid_flow_minutes"],21)

    def test_nonstandard_names_are_rejected_not_guessed(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"bad.csv"
            create(path,[x[:5] for x in synthetic()[:2]],header=COLS[:5])
            with self.assertRaisesRegex(ValueError,"explicit aggressor"):
                list(iter_profit_export(path))

    def test_no_implicit_symbol_or_day_without_source(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"missing.csv"
            header=["Hora","Valor","Quantidade","Agressor"]
            rows=[[x[2],x[3],x[4],x[5]] for x in synthetic()[:2]]
            create(path,rows,header)
            with self.assertRaisesRegex(ValueError,"date"):
                list(iter_profit_export(path))
            with self.assertRaisesRegex(ValueError,"contract"):
                list(iter_profit_export(path,day="2026-11-03"))
            e=list(iter_profit_export(path,symbol="WINZ26",day="2026-11-03"))
            self.assertEqual(len(e),2)

    def test_full_datetime_single_column_works(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"datetime.csv"
            header=["Ativo","DataHora","Preço","Qtd","Tipo Agressão"]
            rows=[[x[0],x[1]+" "+x[2],x[3],x[4],x[5]] for x in synthetic()[:3]]
            create(path,rows,header)
            events=list(iter_profit_export(path))
            self.assertEqual(len(events),3)
            self.assertEqual(events[0]["quantity"],4)

    def test_mixed_contracts_and_dates_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"mixed.csv"
            rows=synthetic()[:3]
            rows[-1][0]="WINV26"
            create(path,rows)
            with self.assertRaisesRegex(ValueError,"Mixed expiry"):
                list(iter_profit_export(path))
            rows[-1][0]="WINZ26"
            rows[-1][1]="04/11/2026"
            create(path,rows)
            with self.assertRaisesRegex(ValueError,"Multiple sessions"):
                list(iter_profit_export(path))

    def test_non_monotonic_ticks_cannot_be_replayed_as_live(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"unordered.csv"
            rows=synthetic()[:3]
            rows[2][2]="09:10:00.000"
            create(path,rows)
            with self.assertRaisesRegex(ValueError,"Out-of-order"):
                list(iter_profit_export(path))

    def test_bad_tick_price_and_contract_quantity_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"wrong.csv"
            rows=synthetic()[:2]
            rows[0][3]="100.002,00"
            create(path,rows)
            with self.assertRaisesRegex(ValueError,"tick price"):
                list(iter_profit_export(path))
            rows[0][3]="100.005,00"
            rows[0][4]="0"
            create(path,rows)
            with self.assertRaisesRegex(ValueError,"quantity"):
                list(iter_profit_export(path))

    def test_duplicate_explicit_trade_id_is_rejected_but_same_price_noid_not_dropped(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"duplicate.csv"
            rows=synthetic()[:2]
            rows[1]=list(rows[0])
            create(path,rows)
            self.assertEqual(len(list(iter_profit_export(path))),2)
            header=COLS+["Número do Negócio"]
            trades=[x+[str(i)] for i,x in enumerate(rows)]
            trades[1][-1]=trades[0][-1]
            create(path,trades,header)
            with self.assertRaisesRegex(ValueError,"duplicate trade ID"):
                list(iter_profit_export(path))

    def test_non_numeric_side_unknown_and_no_broker_account(self):
        path=Path("research/win_profit_timestrades_export.py")
        s=path.read_text(encoding="utf-8")
        for forbidden in ("order_send(","OrderSend(","account_info(","login(",
                          "WinDLL(","requests.post(","subprocess."):
            self.assertNotIn(forbidden,s)

if __name__=="__main__":
    unittest.main()
