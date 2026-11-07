"""B3 M1 coverage gate: synthetic candles only; never evidence of actual WINV26."""
import unittest
from datetime import datetime, timedelta, timezone

from research.atlas_b3_ticks_oct13 import match_signals
from research.win_price_data import TZ


def bars(count=500, omitted=None, date="2026-10-13"):
    omitted=set(omitted or ())
    start=datetime.fromisoformat(date+"T09:10:00").replace(tzinfo=TZ)
    return [{"time":int((start+timedelta(minutes=i)).astimezone(timezone.utc).timestamp()),
             "open":200000,"high":200050,"low":199950,"close":200000,
             "volume":1} for i in range(count) if i not in omitted]


class B3GapGateTests(unittest.TestCase):
    def test_full_500_minute_session_waits_for_labels(self):
        r=match_signals(bars(),{"sha256":"SYNTHETIC"})
        self.assertEqual(r["session_observed_m1"],500)
        self.assertEqual(r["missing_session_minutes"],0)
        self.assertTrue(r["session_complete"])
        self.assertEqual(r["status"],"awaiting_verified_tracker_labels")
        self.assertIsNone(r["net_brl"])

    def test_499_real_bars_cannot_pass_400_threshold(self):
        r=match_signals(bars(500,omitted={121}),{"sha256":"SYNTHETIC"})
        self.assertEqual(r["session_observed_m1"],499)
        self.assertEqual(r["missing_first_20"],["11:11"])
        self.assertEqual(r["status"],"incomplete_session_no_signal_replay")
        self.assertFalse(r["session_complete"])
        self.assertIsNone(r["matches"])

    def test_420_contiguous_is_incomplete_not_label_replay(self):
        r=match_signals(bars(420),{"sha256":"SYNTHETIC"})
        self.assertEqual(r["missing_session_minutes"],80)
        self.assertEqual(r["status"],"incomplete_session_no_signal_replay")

    def test_399_is_insufficient(self):
        r=match_signals(bars(399),{"sha256":"SYNTHETIC"})
        self.assertEqual(r["status"],"insufficient_win_v26_m1_coverage")
        self.assertEqual(r["missing_session_minutes"],101)

    def test_wrong_day_candles_do_not_count(self):
        r=match_signals(bars(500,date="2026-10-12"),{"sha256":"SYNTHETIC"})
        self.assertEqual(r["session_observed_m1"],0)
        self.assertEqual(r["status"],"insufficient_win_v26_m1_coverage")

if __name__=="__main__":
    unittest.main()
