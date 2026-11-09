"""Isolated, paper-only CA/C1/C2 M5 research. NEVER submits broker orders.

CA/C1/C2 here is an explicit *research hypothesis*, not a claim to
reproduce any proprietary technique seen in a video. All bars must be
completed 5-minute UTC OHLC candles from a declared market/source.
"""
from __future__ import annotations

import bisect
import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, date, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
FIVE_MINUTES = 300
SESSION_START = time(8, 0)
LAST_ENTRY = time(12, 0)
SESSION_END = time(16, 0)


@dataclass(frozen=True)
class Settings:
    risk_fraction: float = 0.0025
    max_notional: float = 1.0
    target_r: float = 1.5
    fees_roundtrip_bps: float = 8.0
    slippage_each_side_bps: float = 2.0
    min_ca_atr: float = 0.6
    max_ca_atr: float = 3.0
    max_cost_fraction_of_r: float = 0.25

    def __post_init__(self):
        if not (0 < self.risk_fraction <= 0.01 and 0 < self.max_notional <= 1
                and self.target_r >= 1 and 0 < self.min_ca_atr < self.max_ca_atr
                and 0 < self.max_cost_fraction_of_r < 1
                and self.fees_roundtrip_bps > 0 and self.slippage_each_side_bps > 0):
            raise ValueError("Invalid risk/cost parameters; zero-cost modeling is prohibited")


def timestamp(value):
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise ValueError("Non-finite timestamp")
        return int(value)
    if isinstance(value, str):
        value = value.strip()
        if value.isdecimal():
            return int(value)
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError("Naive timestamps forbidden; provide UTC ISO-8601 or epoch")
        return int(dt.timestamp())
    raise ValueError("Unsupported timestamp")


def validate_bars(data):
    """Reject duplicates, bad OHLC, non-M5 timestamps; never manufacture candles."""
    rows = []
    seen = set()
    for row in data:
        ts = timestamp(row["time"])
        if ts in seen or ts % FIVE_MINUTES:
            raise ValueError("Duplicate or unaligned 5-minute candle timestamp")
        seen.add(ts)
        values = {k: float(row[k]) for k in ("open", "high", "low", "close")}
        if (not all(math.isfinite(v) and v > 0 for v in values.values())
                or values["high"] < max(values["open"], values["close"])
                or values["low"] > min(values["open"], values["close"])):
            raise ValueError("Invalid OHLC candle")
        rows.append({"time": ts, **values})
    rows.sort(key=lambda r: r["time"])
    return rows


def load_bars(path):
    path = Path(path)
    with path.open(encoding="utf8", newline="") as f:
        if path.suffix.lower() == ".csv":
            data = list(csv.DictReader(f))
        elif path.suffix.lower() == ".json":
            data = json.load(f)
            if isinstance(data, dict):
                data = data["bars"]
        else:
            raise ValueError("Supported formats: CSV or JSON")
    if not isinstance(data, list):
        raise ValueError("Expected a list of M5 candles")
    return validate_bars(data)


def indicators(bars):
    """Closed-bar ATR(14) and trend on complete, contiguous H1 candles only."""
    atr = []
    last = None
    for i, b in enumerate(bars):
        prev = bars[i - 1]["close"] if i else b["close"]
        tr = max(b["high"] - b["low"], abs(b["high"] - prev), abs(b["low"] - prev))
        last = tr if last is None else (last * 13 + tr) / 14
        atr.append(last)
    buckets = defaultdict(list)
    for b in bars:
        buckets[(b["time"] // 3600) * 3600].append(b)
    h1 = []
    for start in sorted(buckets):
        chunk = sorted(buckets[start], key=lambda b: b["time"])
        if len(chunk) != 12 or any(b["time"] != start + 300 * j for j, b in enumerate(chunk)):
            continue
        h1.append({"end": start + 3600, "close": chunk[-1]["close"]})
    e50 = e200 = None
    for j, h in enumerate(h1):
        v = h["close"]
        e50 = v if e50 is None else e50 + (2 / 51) * (v - e50)
        e200 = v if e200 is None else e200 + (2 / 201) * (v - e200)
        h["e50"], h["e200"] = e50, e200
        h["warm"] = j >= 204
    return atr, h1, [h["end"] for h in h1]


def trend_at(h1, ends, signal_end, side):
    """Uses only H1 bars whose close time is <= the completed M5 signal."""
    i = bisect.bisect_right(ends, signal_end) - 1
    if i < 204:
        return False
    cur, before = h1[i], h1[i - 4]
    return ((cur["e50"] > cur["e200"]
             and cur["close"] > cur["e50"] and cur["e50"] > before["e50"])
            if side == 1 else
            (cur["e50"] < cur["e200"]
             and cur["close"] < cur["e50"] and cur["e50"] < before["e50"]))


def complete_sessions(bars):
    """Require the entire 08:00-16:00 NY M5 session; no imputed missing bars."""
    dates = defaultdict(dict)
    for i, b in enumerate(bars):
        local = datetime.fromtimestamp(b["time"], timezone.utc).astimezone(NY)
        if SESSION_START <= local.time().replace(tzinfo=None) < SESSION_END:
            dates[local.date()][b["time"]] = i
    good = {}
    missing = {}
    for day, indices in dates.items():
        start = datetime.combine(day, SESSION_START, NY)
        expected = [int((start + timedelta(minutes=5 * j)).timestamp()) for j in range(96)]
        if all(ts in indices for ts in expected):
            good[day] = [indices[ts] for ts in expected]
        else:
            missing[day.isoformat()] = 96 - sum(ts in indices for ts in expected)
    return good, missing


def candidate_for_day(bars, indices, variant, atr, h1, ends, cfg):
    """Find the first confirmed C2. Entry on NEXT bar, never on signal candle."""
    seq = [bars[i] for i in indices]
    ca_high = max(b["high"] for b in seq[:4])
    ca_low = min(b["low"] for b in seq[:4])
    width = ca_high - ca_low
    if width <= 0:
        return None, "zero_ca"
    if variant == "SIMPLE":
        # Control: first confirmed CA close, same exposure/fees/stop/target.
        # NEVER crosses a signal with its own execution candle.
        for j in range(4, 47):
            b = seq[j]
            side = 1 if b["close"] > ca_high else (-1 if b["close"] < ca_low else 0)
            if not side:
                continue
            entry_i = indices[j + 1]
            entry = bars[entry_i]["open"]
            stop = ca_high if side == 1 else ca_low
            if (entry - stop) * side <= 0:
                return None, "gap_wrong_side"
            return {
                "entry_i": entry_i, "side": side, "stop": stop,
                "ca_high": ca_high, "ca_low": ca_low,
                "c1_edge": None, "signal_time": b["time"],
                "variant": "SIMPLE",
            }, "signal"
        return None, "no_ca_breakout"
    if variant == "C":
        channel_atr = atr[indices[3]]
        if channel_atr <= 0 or not cfg.min_ca_atr <= width / channel_atr <= cfg.max_ca_atr:
            return None, "ca_atr_filter"

    side = 0
    c1_edge = None
    for j in range(4, 47):  # the latest signal is 11:50; entry before 12:00 NY
        b = seq[j]
        if side == 0:
            if b["close"] > ca_high:
                side, c1_edge = 1, ca_high + width
                breakout_j = j
            elif b["close"] < ca_low:
                side, c1_edge = -1, ca_low - width
                breakout_j = j
            continue
        if j <= breakout_j:
            continue
        confirmed = b["close"] > c1_edge if side == 1 else b["close"] < c1_edge
        if not confirmed:
            continue
        if variant in ("B", "C") and not trend_at(h1, ends, b["time"] + 300, side):
            return None, "trend_filter"
        entry_i = indices[j + 1]
        entry = bars[entry_i]["open"]
        stop = ca_high if side == 1 else ca_low
        if (entry - stop) * side <= 0:
            return None, "gap_wrong_side"
        nominal_r = abs(entry - stop)
        if variant == "C":
            cost_per_unit = entry * (cfg.fees_roundtrip_bps + 2 * cfg.slippage_each_side_bps) / 10000
            if cost_per_unit / nominal_r > cfg.max_cost_fraction_of_r:
                return None, "cost_to_r_filter"
        return {
            "entry_i": entry_i, "side": side, "stop": stop,
            "ca_high": ca_high, "ca_low": ca_low, "c1_edge": c1_edge,
            "signal_time": b["time"], "variant": variant,
        }, "signal"
    return None, "no_c2_confirmation"


def simulate_trade(bars, indices, candidate, equity, cfg):
    entry_i, side = candidate["entry_i"], candidate["side"]
    bar = bars[entry_i]
    entry_raw = bar["open"]
    entry = entry_raw * (1 + side * cfg.slippage_each_side_bps / 10000)
    stop = candidate["stop"]
    risk_unit = side * (entry - stop)
    if risk_unit <= 0:
        return None
    fee_unit = entry * (cfg.fees_roundtrip_bps / 10000)
    adverse_exit_slip = entry * cfg.slippage_each_side_bps / 10000
    worst_unit = risk_unit + fee_unit + adverse_exit_slip
    qty = min(equity * cfg.risk_fraction / worst_unit,
              equity * cfg.max_notional / entry)
    if qty <= 0:
        return None
    target = entry + side * cfg.target_r * risk_unit
    fill = reason = exit_time = None
    # Stop/target are tested from NEXT opened bar. Stop wins ambiguous candles.
    start_pos = indices.index(entry_i)
    for j in range(start_pos, len(indices)):
        b = bars[indices[j]]
        stop_hit = b["low"] <= stop if side == 1 else b["high"] >= stop
        target_hit = b["high"] >= target if side == 1 else b["low"] <= target
        if stop_hit:
            fill = min(b["open"], stop) if side == 1 else max(b["open"], stop)
            reason = "STOP"
        elif target_hit:
            fill = target
            reason = "TARGET"
        if fill is not None:
            exit_time = b["time"] + 300
            break
    if fill is None:
        last = bars[indices[-1]]
        fill, reason, exit_time = last["close"], "SESSION_FLAT", last["time"] + 300
    exit_px = fill * (1 - side * cfg.slippage_each_side_bps / 10000)
    fee = qty * (entry + exit_px) / 2 * cfg.fees_roundtrip_bps / 10000
    pnl = side * (exit_px - entry) * qty - fee
    return {
        **candidate,
        "entry_time": bar["time"], "exit_time": exit_time,
        "entry": entry, "exit": exit_px, "target": target,
        "qty": qty, "fee_usd": fee, "net_usd": pnl,
        "net_r": pnl / (equity * cfg.risk_fraction),
        "exit_reason": reason,
    }


def run(bars, variant, cfg=None, initial_equity=5000.0):
    """One isolated virtual book per variant; no live state or broker access."""
    if variant not in ("A", "B", "C", "SIMPLE"):
        raise ValueError("Unknown variant")
    cfg = cfg or Settings()
    if initial_equity <= 0:
        raise ValueError("Equity must be positive")
    bars = validate_bars(bars)
    atr, h1, ends = indicators(bars)
    days, incomplete = complete_sessions(bars)
    equity = initial_equity
    trades, rejections = [], defaultdict(int)
    equity_curve = [equity]
    for day, indices in sorted(days.items()):
        candidate, reason = candidate_for_day(bars, indices, variant, atr, h1, ends, cfg)
        if candidate is None:
            rejections[reason] += 1
            continue
        trade = simulate_trade(bars, indices, candidate, equity, cfg)
        if trade is None:
            rejections["invalid_risk"] += 1
            continue
        trade["day"] = day.isoformat()
        trades.append(trade)
        equity += trade["net_usd"]
        equity_curve.append(equity)
    return {
        "variant": variant, "initial_equity": initial_equity,
        "final_equity": equity, "trades": trades,
        "equity_curve": equity_curve, "sessions": len(days),
        "skipped_incomplete_sessions": incomplete, "rejections": dict(rejections),
        "paper_only": True, "rules_version": "ca_c1_c2_hypothesis_v1",
    }


def metrics(trades, initial_equity=5000.0):
    realized = initial_equity
    peak = initial_equity
    max_dd = 0.0
    positives = negatives = 0.0
    for t in trades:
        net = t["net_usd"]
        positives += max(0, net)
        negatives += max(0, -net)
        realized += net
        peak = max(peak, realized)
        max_dd = max(max_dd, 100 * (peak - realized) / peak)
    n = len(trades)
    return {
        "trades": n, "net_usd": round(realized - initial_equity, 2),
        "hit_rate_pct": round(100 * sum(t["net_usd"] > 0 for t in trades) / n, 2) if n else None,
        "profit_factor": round(positives / negatives, 3) if negatives else None,
        "max_realized_drawdown_pct": round(max_dd, 2),
        "mean_net_r": round(sum(t["net_r"] for t in trades) / n, 4) if n else None,
        "has_enough_trades_for_review": n >= 50,
    }


def chronological_report(bars, cfg=None, source="user_supplied_M5", split=0.7):
    """Day-level chronological holdout; no optimization or retroactive selection."""
    cfg = cfg or Settings()
    if not 0.5 <= split <= 0.9:
        raise ValueError("Split outside supported range")
    bars = validate_bars(bars)
    days, _ = complete_sessions(bars)
    dates = sorted(days)
    split_at = min(len(dates), max(0, int(len(dates) * split)))
    cutoff = dates[split_at].isoformat() if split_at < len(dates) else None
    out = {
        "source": source,
        "data_type": "M5 OHLC, NOT bid/ask fills",
        "session": "08:00-16:00 America/New_York",
        "fee_roundtrip_bps_assumed": cfg.fees_roundtrip_bps,
        "slippage_each_side_bps_assumed": cfg.slippage_each_side_bps,
        "split": "chronological by NY trading date; 70% dev / 30% holdout",
        "split_day": cutoff,
        "historical_claim": False, "live_trading": False,
        "variants": {},
    }
    for code in ("A", "B", "C"):
        result = run(bars, code, cfg)
        dev = [t for t in result["trades"] if cutoff and t["day"] < cutoff]
        test = [t for t in result["trades"] if cutoff and t["day"] >= cutoff]
        out["variants"][code] = {
            "development": metrics(dev),
            "holdout": metrics(test),
            "all": metrics(result["trades"]),
            "sessions": result["sessions"],
            "incomplete_days": result["skipped_incomplete_sessions"],
            "rejections": result["rejections"],
        }
    doubled = Settings(**{**cfg.__dict__,
                          "fees_roundtrip_bps": cfg.fees_roundtrip_bps * 2,
                          "slippage_each_side_bps": cfg.slippage_each_side_bps * 2})
    for code in ("A", "B", "C"):
        stressed = run(bars, code, doubled)
        test = [t for t in stressed["trades"] if cutoff and t["day"] >= cutoff]
        out["variants"][code]["holdout_2x_cost"] = metrics(test)
    # Simple breakout benchmark: identical risk and fill assumptions.
    plain = run(bars, "SIMPLE", cfg)
    plain_stress = run(bars, "SIMPLE", doubled)
    out["benchmark_simple_ca_breakout"] = {
        "all": metrics(plain["trades"]),
        "development": metrics([t for t in plain["trades"] if cutoff and t["day"] < cutoff]),
        "holdout": metrics([t for t in plain["trades"] if cutoff and t["day"] >= cutoff]),
        "holdout_2x_cost": metrics([t for t in plain_stress["trades"]
                                   if cutoff and t["day"] >= cutoff]),
    }

    # Expanding-window evaluation, WITHOUT refitting any parameters.
    # Each test window is disjoint, dates are chronological, and no trade
    # from a later fold can affect any earlier fold's reported P&L.
    out["rolling_origin"] = []
    fractions = (0.4, 0.6, 0.8, 1.0)
    if len(dates) >= 10:
        for fold in range(3):
            left = int(len(dates) * fractions[fold])
            right = int(len(dates) * fractions[fold + 1])
            if not (0 < left < right):
                continue
            start_day, end_day = dates[left].isoformat(), (
                dates[right].isoformat() if right < len(dates) else None)
            fold_data = {"fold": fold + 1,
                         "training_days": left, "test_start": start_day,
                         "test_end_exclusive": end_day, "results": {}}
            for code in ("A", "B", "C", "SIMPLE"):
                observed = run(bars, code, cfg)["trades"]
                test_trades = [t for t in observed
                               if t["day"] >= start_day
                               and (end_day is None or t["day"] < end_day)]
                fold_data["results"][code] = metrics(test_trades)
            out["rolling_origin"].append(fold_data)
    out["rolling_origin_method"] = (
        "Expanding train window, sequential disjoint test windows; "
        "no parameter fitting, purging or independent broker feed; "
        "diagnostic only, not a completed validation.")

    out["valid_for_profit_claim"] = False
    out["limitations"] = [
        "A single chronological holdout is not a walk-forward or untouched independent test.",
        "No order book, broker bid/ask, market impact or financing observed.",
        "More out-of-sample observations and multiple market regimes are required.",
        "Do not treat GC=F futures as identical to XAUUSD spot/CFD."
    ]
    return out
