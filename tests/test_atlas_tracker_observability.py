"""ATLAS video-signal observability: artificial fixtures only, no Tracker claim."""
from __future__ import annotations

import csv
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from research.atlas_tracker_observability import (
    parse_coverage_csv, score_observable_intervals,
)
from research.atlas_confluence_v3 import VARIANTS
from research.win_price_data import TZ

DATE = "2026-10-13"
CONTRACT = "WINV26"
HEADER = [
    "date", "contract", "timeframe", "start_market_time",
    "end_market_time_exclusive", "evidence_url", "recording_continuous",
    "indicator_visible_throughout", "all_tracker_signals_labeled",
]


def bars_for_test(n=130, *, drop=None):
    start = datetime(2026, 10, 13, 9, 10, tzinfo=TZ)
    return [
        {
            "time": int((start + timedelta(minutes=i)).astimezone(
                timezone.utc).timestamp()),
            "open": 200000, "high": 200010, "low": 199990,
            "close": 200000, "volume": 10,
        }
        for i in range(n) if i != drop
    ]


def write_coverage(path, rows=None):
    rows = rows if rows is not None else [
        [DATE, CONTRACT, "M1", "10:25:00", "10:35:00",
         "https://example.com/continuous-unedited-recording", "yes",
         "yes", "yes"],
    ]
    with Path(path).open("w", encoding="utf-8", newline="") as f:
        writer=csv.writer(f)
        writer.writerow(HEADER)
        writer.writerows(rows)


class TrackerObservabilityTests(unittest.TestCase):
    def test_wrong_direction_counts_both_fp_and_fn(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"coverage.csv"
            write_coverage(p)
            windows=parse_coverage_csv(p)
            bars=bars_for_test()
            lookup={i:bar["time"] for i,bar in enumerate(bars)}
            labels=[(lookup[76],1),(lookup[78],1)]
            def model_signal(_,i,variant):
                return {76:1,78:-1,80:1}.get(i,0)
            with patch("research.atlas_tracker_observability.v3_signal",
                       side_effect=model_signal):
                result=score_observable_intervals(bars,labels,windows)
            self.assertTrue(result["claimed_full_observability_must_be_verified_by_human"])
            self.assertFalse(result["data_verified_by_auditor"])
            self.assertEqual(result["session_candles_scored"],10)
            for variant in VARIANTS:
                row=result["models"][variant]
                self.assertEqual(row["true_positive"],1)
                self.assertEqual(row["wrong_direction"],1)
                self.assertEqual(row["false_positive"],2)
                self.assertEqual(row["false_negative"],1)
                self.assertEqual(row["extra_unlabeled_in_complete_window"],1)
                self.assertEqual(row["precision_pct"],33.33)
                self.assertEqual(row["recall_pct"],50.0)
                self.assertEqual(row["f1_pct"],40.0)
            self.assertTrue(result["not_a_winrate"])
            self.assertIsNone(result["finance_results"])

    def test_no_labels_is_not_100percent_precision(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"coverage.csv"
            write_coverage(p)
            with patch("research.atlas_tracker_observability.v3_signal",
                       return_value=0):
                result=score_observable_intervals(bars_for_test(),[],
                    parse_coverage_csv(p))
            self.assertIsNone(result["models"]["baseline"]["precision_pct"])
            self.assertIsNone(result["models"]["baseline"]["recall_pct"])
            self.assertEqual(result["models"]["baseline"]["false_positive"],0)

    def test_missing_market_minute_must_fail_not_count_as_no_signal(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"coverage.csv"
            write_coverage(p)
            with self.assertRaisesRegex(ValueError,"Missing real M1 candle"):
                score_observable_intervals(bars_for_test(drop=80),[],
                                           parse_coverage_csv(p))

    def test_window_requires_all_three_completeness_attestations(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"coverage.csv"
            write_coverage(p)
            lines=p.read_text()
            for keyword in ("recording_continuous",
                            "indicator_visible_throughout",
                            "all_tracker_signals_labeled"):
                c=lines.replace("yes,yes,yes",
                                "no,yes,yes" if keyword=="recording_continuous"
                                else "yes,no,yes" if keyword=="indicator_visible_throughout"
                                else "yes,yes,no")
                p.write_text(c)
                with self.assertRaisesRegex(ValueError,"unobservable interval"):
                    parse_coverage_csv(p)
            p.write_text(lines)
            self.assertEqual(len(parse_coverage_csv(p)),1)

    def test_out_of_window_positive_labels_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"coverage.csv"
            write_coverage(p)
            bars=bars_for_test()
            with self.assertRaisesRegex(ValueError,"outside declared"):
                score_observable_intervals(bars,[(bars[100]["time"],1)],
                                           parse_coverage_csv(p))

    def test_overlapping_coverage_windows_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"coverage.csv"
            write_coverage(p,[
                [DATE,CONTRACT,"M1","10:25:00","10:35:00",
                 "https://example.org/record1","yes","yes","yes"],
                [DATE,CONTRACT,"M1","10:34:00","10:40:00",
                 "https://example.org/record2","yes","yes","yes"],
            ])
            with self.assertRaisesRegex(ValueError,"Overlapping"):
                parse_coverage_csv(p)

    def test_incomplete_history_is_not_scored(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"coverage.csv"
            write_coverage(p,[
                [DATE,CONTRACT,"M1","09:20:00","09:22:00",
                 "https://example.org/record1","yes","yes","yes"],
            ])
            with self.assertRaisesRegex(ValueError,"75 genuine historical"):
                score_observable_intervals(bars_for_test(),[],
                                           parse_coverage_csv(p))


if __name__=="__main__":
    unittest.main()
