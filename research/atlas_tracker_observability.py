"""Evaluate ATLAS-vs-Tracker *only* in demonstrably observable chart intervals.

A list of visible Tracker arrows is a POSITIVE-ONLY sample. Comparing it
to ATLAS signals cannot establish precision, false-positive rate, or accuracy.

A separate, user-supplied coverage declaration must describe a continuous
recording where ALL Tracker arrows are visible and annotated. Never treat
untagged marketing screenshots as negative signals, or chart/player time as
the exchange's market time. This module does no trading and does not update
the ATLAS production/paper state.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from research.atlas_confluence_v3 import VARIANTS, v3_signal
from research.atlas_win_oct13 import DATE, SYMBOL
from research.win_price_data import TZ

START_MINUTE = 9 * 60 + 10
END_MINUTE = 17 * 60 + 30
NEEDED = {
    "date", "contract", "timeframe", "start_market_time",
    "end_market_time_exclusive", "evidence_url", "recording_continuous",
    "indicator_visible_throughout", "all_tracker_signals_labeled",
}


def _clock(value):
    try:
        dt = datetime.strptime(value.strip(), "%H:%M:%S")
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"Market clock HH:MM:SS required: {value!r}") from exc
    if dt.second:
        raise ValueError("Coverage intervals must align to exact M1 candle opens")
    return dt.hour * 60 + dt.minute


def _timestamp(minute):
    day = datetime.strptime(DATE, "%Y-%m-%d")
    return int(day.replace(hour=minute // 60, minute=minute % 60,
                           tzinfo=TZ).astimezone(timezone.utc).timestamp())


def parse_coverage_csv(path):
    """Parse self-declared full-observability windows, never independent proof."""
    windows = []
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not NEEDED.issubset(reader.fieldnames or []):
            raise ValueError("Required coverage fields: " + ", ".join(sorted(NEEDED)))
        for line, record in enumerate(reader, 2):
            if record["date"].strip() != DATE or record["contract"].strip() != SYMBOL:
                raise ValueError(f"Line {line}: wrong date or contract")
            if record["timeframe"].strip() != "M1":
                raise ValueError(f"Line {line}: coverage must be M1")
            for key in ("recording_continuous", "indicator_visible_throughout",
                        "all_tracker_signals_labeled"):
                if record[key].strip().lower() != "yes":
                    raise ValueError(f"Line {line}: cannot score unobservable interval ({key})")
            url = record["evidence_url"].strip()
            if not url.startswith("https://"):
                raise ValueError(f"Line {line}: recording requires verifiable HTTPS URL")
            lo = _clock(record["start_market_time"])
            hi = _clock(record["end_market_time_exclusive"])
            if lo < START_MINUTE or hi > END_MINUTE or hi <= lo:
                raise ValueError(f"Line {line}: invalid market interval")
            windows.append((lo, hi, url))
    if not windows:
        raise ValueError("No complete-observability windows provided")
    windows.sort()
    if any(windows[i][0] < windows[i-1][1] for i in range(1, len(windows))):
        raise ValueError("Overlapping observational windows are not allowed")
    return windows


def score_observable_intervals(bars, labels, windows):
    """Exact candle-and-direction matching; wrong-direction is FP plus FN.

    Candle timestamps are the OPEN of the signal candle. Signal formation
    occurs after that candle CLOSES. The last historical candle used for
    candidate calculation must be completely observed. A scoring warmup
    of 75 prior candles is mandatory for all variants.
    """
    by_time = {}
    for i, bar in enumerate(bars):
        ts = bar["time"]
        if ts in by_time:
            raise ValueError("Duplicate M1 timestamp in reconstructed market data")
        by_time[ts] = i
    if any(bars[i]["time"] <= bars[i - 1]["time"] for i in range(1, len(bars))):
        raise ValueError("M1 market candles must be chronological")
    evaluated = set()
    declared = []
    for start, end, _ in windows:
        for minute in range(start, end):
            ts = _timestamp(minute)
            if ts not in by_time:
                raise ValueError(f"Missing real M1 candle in declared recording coverage at {minute//60:02d}:{minute%60:02d}")
            index = by_time[ts]
            if index < 75:
                raise ValueError("At least 75 genuine historical candles are required before scored interval")
            evaluated.add(ts)
        declared.append({"start_market_time": f"{start//60:02d}:{start%60:02d}",
                         "end_market_time_exclusive": f"{end//60:02d}:{end%60:02d}"})
    ground_truth = {}
    for ts, side in labels:
        if side not in (-1, 1):
            raise ValueError("Unknown Tracker signal direction")
        if ts not in evaluated:
            raise ValueError("Tracker label outside declared continuously observed M1 interval")
        if ts in ground_truth:
            raise ValueError("Duplicate Tracker labels at same market candle")
        ground_truth[ts] = side
    records = {}
    for variant in VARIANTS:
        tp = fp = fn = wrong_direction = 0
        extra = 0
        for ts in sorted(evaluated):
            i = by_time[ts]
            predicted = v3_signal(bars, i, variant)
            observed = ground_truth.get(ts, 0)
            if predicted not in (-1, 0, 1):
                raise ValueError("Unexpected model output")
            if predicted and observed == predicted:
                tp += 1
            elif predicted and observed:
                wrong_direction += 1
                fp += 1
                fn += 1
            elif predicted:
                fp += 1
                extra += 1
            elif observed:
                fn += 1
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / (tp + fn) if tp + fn else None
        records[variant] = {
            "true_positive": tp, "false_positive": fp,
            "false_negative": fn, "wrong_direction": wrong_direction,
            "extra_unlabeled_in_complete_window": extra,
            "model_arrows_total": tp + fp,
            "tracker_arrows_labeled_total": tp + fn,
            "precision_pct": round(100 * precision, 2) if precision is not None else None,
            "recall_pct": round(100 * recall, 2) if recall is not None else None,
            "f1_pct": round(200 * precision * recall / (precision + recall), 2)
                      if precision is not None and recall is not None and precision + recall else None,
        }
    return {
        "status": "CONDITIONAL_ON_INDEPENDENT_VERIFICATION_OF_VIDEO_COVERAGE",
        "data_verified_by_auditor": False,
        "claimed_full_observability_must_be_verified_by_human": True,
        "session_candles_scored": len(evaluated),
        "coverage_windows": declared,
        "models": records,
        "finance_results": None,
        "not_a_winrate": True,
        "note": "Precision/recall only if recording truly includes EVERY signal, and labels/times are independently checked.",
    }
