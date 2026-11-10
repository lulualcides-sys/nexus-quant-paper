"""Dukascopy XAUUSD quote replay regression tests: no broker simulation claims."""
from datetime import datetime, timezone
from pathlib import Path
import csv
import json
import tempfile
import unittest

from research.xau_dukascopy_replay import aggregate_real_quotes, replay_historical_quotes

BASE = int(datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc).timestamp()*1000)


def write_ticks(file, *, n=65, reversed_time=False, crossed=False, repeated=False):
    with file.open("w", encoding="utf-8", newline="") as f:
        writer=csv.DictWriter(f,fieldnames=["timestamp", "askPrice", "bidPrice",
                                           "askVolume", "bidVolume"])
        writer.writeheader()
        rows=[]
        for m in range(n):
            for j in range(5):
                ts=BASE+m*60000+j*10000
                bid=2750.0 + (m % 4)*.01 + (j % 2)*.05
                ask=bid+0.16
                rows.append({"timestamp":ts,"askPrice":ask,"bidPrice":bid,
                             "askVolume":90.0,"bidVolume":120.0})
        if repeated:
            for k in range(50):
                rows.append({**rows[-1],"timestamp":rows[-1]["timestamp"]+k+1})
        if crossed:
            rows[4]["askPrice"]=rows[4]["bidPrice"]-0.01
        if reversed_time:
            rows[6]["timestamp"]=rows[0]["timestamp"]
        for row in rows:
            writer.writerow(row)


class DukascopyReplayTests(unittest.TestCase):
    def test_real_bid_ask_schema_produces_audited_bars(self):
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/"quotes.csv"
            write_ticks(file)
            bars,audit=aggregate_real_quotes(file)
            self.assertEqual(audit["source_rows"],65*5)
            self.assertEqual(len(bars),65)
            self.assertTrue(all(b["tick_volume"]==5 for b in bars))
            self.assertTrue(all(b["spread_points"]>=160 for b in bars))
            self.assertEqual(bars[0]["time"],BASE//1000)
            report=replay_historical_quotes(file)
            self.assertEqual(report["aggregated_closed_or_open_bars"],65)
            self.assertTrue(report["excluded_potentially_open_last_candle"])
            self.assertEqual(report["orders_sent"],0)
            self.assertTrue(report["bid_ask_quotes_not_trades"])
            self.assertTrue(report["profitability_untested"])
            self.assertFalse(report["exact_original_tracker_match_verified"])
            self.assertEqual(report["candidates_total"],0)  # 5 updates < 15 gate

    def test_no_volume_confusion(self):
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/"quotes.csv"
            write_ticks(file)
            bars,_=aggregate_real_quotes(file)
            original=bars[0]["tick_volume"]
            text=file.read_text()
            file.write_text(text.replace(",90.0,120.0",",999999.0,888888.0"))
            bars2,_=aggregate_real_quotes(file)
            self.assertEqual(original,bars2[0]["tick_volume"])

    def test_m5_aggregation_keeps_5_minute_boundaries(self):
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/"quotes.csv"
            write_ticks(file,n=70)
            bars,audit=aggregate_real_quotes(file,300)
            self.assertEqual(len(bars),14)
            self.assertEqual(bars[0]["tick_volume"],25)
            self.assertEqual(audit["timeframe_seconds"],300)

    def test_crossed_bid_ask_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/"quotes.csv"
            write_ticks(file,crossed=True)
            with self.assertRaisesRegex(ValueError,"crossed"):
                aggregate_real_quotes(file)

    def test_disordered_quotes_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/"quotes.csv"
            write_ticks(file,reversed_time=True)
            with self.assertRaisesRegex(ValueError,"Out-of-order"):
                aggregate_real_quotes(file)

    def test_duplicate_unchanged_price_is_not_recounted(self):
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/"quotes.csv"
            write_ticks(file,repeated=True)
            bars,audit=aggregate_real_quotes(file)
            self.assertEqual(audit["repeated_price_quotes_ignored"],50)
            self.assertEqual(bars[-1]["tick_volume"],5)

    def test_empty_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/"quotes.csv"
            file.write_text("")
            with self.assertRaisesRegex(ValueError,"Missing or oversized"):
                aggregate_real_quotes(file)

    def test_wrong_timeframe_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/"quotes.csv"
            write_ticks(file)
            with self.assertRaisesRegex(ValueError,"Invalid timeframe"):
                aggregate_real_quotes(file,900)

    def test_warmup_required(self):
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/"quotes.csv"
            write_ticks(file,n=15)
            with self.assertRaisesRegex(ValueError,"Insufficient"):
                aggregate_real_quotes(file)

    def test_fixed_report_does_not_include_raw_proprietary_ticks(self):
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/"quotes.csv"
            write_ticks(file)
            report=replay_historical_quotes(file)
            self.assertNotIn("raw_ticks",report)
            self.assertNotIn("broker_login",report)
            self.assertNotIn("account_number",report)
            self.assertEqual(report["activity_type"],
               "observed bid/ask quote-price changes (not traded contracts)")


if __name__=="__main__":
    unittest.main()
