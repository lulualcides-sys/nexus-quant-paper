"""Read-only MT5 WIN collector tested with injected quotes; no live MT5 access."""
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace

from research.mt5_readonly_collector import canonicalize_mt5_rates,collect_from_terminal,run_research

UTC=timezone.utc


def sample(day=datetime(2026,11,9,12,10,tzinfo=UTC),n=130):
    return [{"time":int((day+timedelta(minutes=i)).timestamp()),
             "open":100000.0,"high":100010.0,"low":99990.0,
             "close":100000.0,"tick_volume":160,"real_volume":50,
             "spread":2} for i in range(n)]


class ReadOnlyMt5:
    TIMEFRAME_M1 = 1
    def __init__(self, candles, *, tick_size=5.0, connected=True):
        self.history=candles
        self.tick_size=tick_size
        self.connected=connected
        self.calls=[]
    def terminal_info(self):
        self.calls.append("terminal_info")
        return SimpleNamespace(connected=self.connected)
    def symbol_info(self,symbol):
        self.calls.append("symbol_info")
        return SimpleNamespace(name=symbol,trade_tick_size=self.tick_size)
    def symbol_select(self,symbol,select):
        self.calls.append("symbol_select")
        return True
    def copy_rates_range(self,symbol,timeframe,start,end):
        self.calls.append("copy_rates_range")
        return self.history
    def last_error(self):
        return (0,"")
    def order_send(self,*args,**kwargs):
        raise AssertionError("Trading method MUST NOT be called")


class Mt5CollectorTests(unittest.TestCase):
    def test_timestamp_is_utc_and_source_remains_private(self):
        with tempfile.TemporaryDirectory() as td:
            dest=Path(td)/"WINZ26_M1.csv"
            now=datetime(2026,11,9,19,tzinfo=UTC)
            history=sample()
            data,audit=canonicalize_mt5_rates(history,symbol="WINZ26",now_utc=now,destination=dest)
            self.assertEqual(len(data["bars"]),130)
            self.assertEqual(audit["candles_complete"],130)
            self.assertTrue(audit["start_local"].startswith("2026-11-09T09:10"))
            self.assertTrue(audit["no_orders_sent"])
            self.assertFalse(audit["broker_fills_verified"])
            self.assertEqual(audit["days_with_session_candles"],1)
            self.assertEqual(data["bars"][0]["volume"],50.0)
            self.assertTrue(dest.exists())

    def test_incomplete_current_minute_is_discarded(self):
        history=sample(n=130)
        now=datetime.fromtimestamp(history[-1]["time"]+10,UTC)
        with tempfile.TemporaryDirectory() as td:
            _,audit=canonicalize_mt5_rates(history,symbol="WINZ26",now_utc=now,
                                            destination=Path(td)/"WINZ26_M1.csv")
            self.assertEqual(audit["discarded_incomplete_current_bar"],1)
            self.assertEqual(audit["candles_complete"],129)

    def test_absent_minute_is_reported_not_invented(self):
        history=sample()
        del history[30]
        with tempfile.TemporaryDirectory() as td:
            _,audit=canonicalize_mt5_rates(history,symbol="WINZ26",
                                            now_utc=datetime(2026,11,9,20,tzinfo=UTC),
                                            destination=Path(td)/"WINZ26_M1.csv")
            self.assertEqual(audit["same_day_gap_events"],1)
            self.assertEqual(audit["same_day_missing_minutes"],1)

    def test_tick_volume_cannot_replace_real_volume(self):
        history=sample()
        history[10]["real_volume"]=0
        with tempfile.TemporaryDirectory() as td:
            dest=Path(td)/"WINZ26_M1.csv"
            with self.assertRaisesRegex(ValueError,"real_volume"):
                canonicalize_mt5_rates(history,symbol="WINZ26",
                                        now_utc=datetime(2026,11,9,20,tzinfo=UTC),
                                        destination=dest)
            self.assertFalse(dest.exists())

    def test_duplicates_are_fatal(self):
        history=sample()
        history[8]["time"]=history[7]["time"]
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError,"duplicate/out-of-order"):
                canonicalize_mt5_rates(history,symbol="WINZ26",
                                        now_utc=datetime(2026,11,9,20,tzinfo=UTC),
                                        destination=Path(td)/"a.csv")

    def test_wrong_tick_product_rejected_by_terminal(self):
        backend=ReadOnlyMt5(sample(),tick_size=0.5)
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError,"not WIN"):
                collect_from_terminal(backend,symbol="WINZ26",days=30,
                                      now_utc=datetime(2026,11,9,20,tzinfo=UTC),
                                      destination=Path(td)/"a.csv")
        self.assertNotIn("copy_rates_range",backend.calls)

    def test_disconnected_terminal_rejected_without_queries(self):
        backend=ReadOnlyMt5(sample(),connected=False)
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError,"not connected"):
                collect_from_terminal(backend,symbol="WINZ26",days=30,
                                      now_utc=datetime(2026,11,9,20,tzinfo=UTC),
                                      destination=Path(td)/"a.csv")
        self.assertEqual(backend.calls,["terminal_info"])

    def test_readonly_mt5_api_never_routes_orders(self):
        backend=ReadOnlyMt5(sample())
        with tempfile.TemporaryDirectory() as td:
            history,audit=collect_from_terminal(backend,symbol="WINZ26",days=30,
                                         now_utc=datetime(2026,11,9,20,tzinfo=UTC),
                                         destination=Path(td)/"WINZ26_M1.csv")
            self.assertEqual(len(history["bars"]),130)
            self.assertEqual(audit["requested_days"],30)
        self.assertEqual(backend.calls,
                         ["terminal_info","symbol_info","symbol_select","copy_rates_range"])

    def test_chronological_readonly_report_never_claims_profit(self):
        bars=[]
        # All four fixture sessions must be in the actual past when CI runs.
        for day in (2,3,4,5):
            bars.extend(sample(day=datetime(2026,11,day,12,10,tzinfo=UTC)))
        with tempfile.TemporaryDirectory() as td:
            data,_=canonicalize_mt5_rates(bars,symbol="WINZ26",
                                           now_utc=datetime(2026,11,6,21,tzinfo=UTC),
                                           destination=Path(td)/"WINZ26_M1.csv")
            report=run_research(data["bars"],contract="WINZ26")
        self.assertFalse(report["approved_live"])
        self.assertEqual(report["contracts_at_once"],1)
        self.assertEqual(report["daily_loss_lockout"],False)
        self.assertEqual(len(report["results"]),2)
        for window in report["results"].values():
            for row in window.values():
                self.assertEqual(row["trades"],0)
                self.assertEqual(row["net_brl"],0)
        self.assertEqual(report["chronological_split_day"],"2026-11-04")

    def test_research_fee_is_explicit_and_bounded(self):
        with self.assertRaisesRegex(ValueError,"Need at least"):
            run_research(sample(),contract="WINZ26")
        # Date count three or more triggers costs validation first.
        rows=[]
        for day in (9,10,11,12):
            rows+=sample(day=datetime(2026,11,day,12,10,tzinfo=UTC))
        with self.assertRaisesRegex(ValueError,"Invalid modeled fee"):
            run_research(rows,contract="WINZ26",fee_roundtrip_brl=-1)


if __name__ == "__main__":
    unittest.main()
