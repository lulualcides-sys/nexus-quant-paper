"""Independent XAUUSD MT5 Tracker-style *quote-activity* research model.

The Greenhouse Tracker is proprietary. This is NOT its source or a replica.
XAUUSD OTC/CFD quote tick counts are broker-dependent; they are NOT
exchange-trade volume, aggression, CVD or institutional absorption.
All decisions are made after a candle closes, using only earlier candles.
No account connection, order routing, profit claims or credential handling.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import csv
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone


@dataclass(frozen=True)
class QuotePolicy:
    timeframe_seconds: int = 60
    lookback: int = 20
    atr_period: int = 14
    min_tick_updates: int = 15
    activity_factor: float = 1.20
    min_range_atr: float = 0.60
    max_range_atr: float = 2.50
    min_wick_fraction: float = 0.28
    close_location: float = 0.62
    sweep_atr: float = 0.06
    max_spread_atr: float = 0.35
    point: float = 0.01
    tick_size: float = 0.01
    require_liquidity_zone: bool = False  # Optional, NOT proven Tracker rule
    liquidity_touch_tolerance_atr: float = 0.18
    liquidity_min_touches: int = 2

    def validate(self):
        if (self.timeframe_seconds not in (60, 300)
            or self.lookback < 5 or self.atr_period < 2
            or self.min_tick_updates < 1 or self.activity_factor < 1
            or not 0 < self.min_range_atr < self.max_range_atr
            or not 0 <= self.min_wick_fraction <= 1
            or not .5 <= self.close_location <= 1
            or self.sweep_atr < 0 or self.max_spread_atr <= 0
            or self.point <= 0 or self.tick_size <= 0
            or self.liquidity_touch_tolerance_atr < 0
            or self.liquidity_min_touches < 2):
            raise ValueError("Invalid XAU quote-research policy")


def _valid_bar(b):
    try:
        o, h, l, c = (float(b[k]) for k in ("open", "high", "low", "close"))
        volume = int(b["tick_volume"])
        spread = int(b["spread_points"])
        stamp = int(b["time"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    from math import isfinite
    return (all(isfinite(x) for x in (o, h, l, c))
            and l > 0 and l <= min(o, c) <= max(o, c) <= h
            and volume > 0 and spread >= 0 and stamp > 0)


def signal(bars: list[dict], index: int, closed_through: int,
           policy: QuotePolicy = QuotePolicy()) -> int:
    """+1 buy, -1 sell, 0 no research arrow.

    `closed_through` is the last fully CLOSED chronological candle index.
    Supplying a forming candle index as a candidate is always rejected.
    """
    policy.validate()
    required = max(policy.lookback, policy.atr_period) + 1
    if (index < required or index > closed_through
        or closed_through >= len(bars) or index >= len(bars)):
        return 0
    first = index - required
    relevant = bars[first:index + 1]
    if any(not _valid_bar(b) for b in relevant):
        return 0
    if any(not 0 < int(relevant[k]["time"]) - int(relevant[k-1]["time"])
           <= 2*policy.timeframe_seconds for k in range(1, len(relevant))):
        return 0
    # ATR14 is entirely PRIOR to the signal candle, no lookahead.
    tr = []
    for j in range(index-policy.atr_period, index):
        old, prior_close = bars[j], float(bars[j-1]["close"])
        tr.append(max(float(old["high"])-float(old["low"]),
                      abs(float(old["high"])-prior_close),
                      abs(float(old["low"])-prior_close)))
    atr = sum(tr) / len(tr)
    now = bars[index]
    span = float(now["high"]) - float(now["low"])
    if atr <= 0 or not policy.min_range_atr*atr <= span <= policy.max_range_atr*atr:
        return 0
    # OTC quote updates are only an activity proxy, NOT traded contracts.
    previous = bars[index-policy.lookback:index]
    activity = sum(int(b["tick_volume"]) for b in previous)/policy.lookback
    if (int(now["tick_volume"]) < policy.min_tick_updates
        or int(now["tick_volume"]) < policy.activity_factor*activity):
        return 0
    # A missing/zero historical spread must not be invented.
    spread = int(now["spread_points"])
    if spread <= 0 or spread*policy.point > policy.max_spread_atr*atr:
        return 0
    previous_high = max(float(b["high"]) for b in previous)
    previous_low = min(float(b["low"]) for b in previous)
    o, c, h, l = (float(now[k]) for k in ("open", "close", "high", "low"))
    location = (c-l)/span
    buy = (l <= previous_low-policy.sweep_atr*atr
           and c > previous_low and c > o
           and location >= policy.close_location
           and (min(o, c)-l)/span >= policy.min_wick_fraction)
    sell = (h >= previous_high+policy.sweep_atr*atr
            and c < previous_high and c < o
            and location <= 1-policy.close_location
            and (h-max(o, c))/span >= policy.min_wick_fraction)
    if policy.require_liquidity_zone:
        # Independent optional double-touch proxy; no undocumented Tracker claim.
        tolerance = policy.liquidity_touch_tolerance_atr*atr
        buy_touches = sum(abs(float(x["low"])-previous_low) <= tolerance for x in previous)
        sell_touches = sum(abs(float(x["high"])-previous_high) <= tolerance for x in previous)
        if buy and buy_touches < policy.liquidity_min_touches:
            buy = False
        if sell and sell_touches < policy.liquidity_min_touches:
            sell = False
    return 1 if buy and not sell else (-1 if sell and not buy else 0)


def fib_levels(candle: dict, side: int, tick_size: float) -> dict:
    """Public price geometry, not executable fills or a 2:1 RR promise."""
    if side not in (-1, 1) or tick_size <= 0:
        raise ValueError("Valid direction and positive broker tick_size required")
    low, high = float(candle["low"]), float(candle["high"])
    if not 0 < low < high:
        raise ValueError("Invalid candle")
    origin = low if side == 1 else high
    span = high-low
    def grid(value: float) -> float:
        step = Decimal(str(tick_size))
        return float((Decimal(str(value))/step).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP)*step)
    return {name: grid(origin+side*multiplier*span)
            for name, multiplier in (("0", 0), ("50", .5), ("100", 1),
                                     ("200", 2), ("-100", -1))}


def scan_closed(bars: list[dict], closed_through: int,
                policy: QuotePolicy = QuotePolicy()) -> list[dict]:
    """Never score the potentially open last candle."""
    policy.validate()
    if not 0 <= closed_through < len(bars):
        raise ValueError("Last CLOSED index must be supplied explicitly")
    result = []
    for i in range(max(policy.lookback, policy.atr_period)+1, closed_through+1):
        side = signal(bars, i, closed_through, policy)
        if side:
            result.append({"time_utc": datetime.fromtimestamp(
                int(bars[i]["time"]), timezone.utc).isoformat(),
                "side": "BUY" if side == 1 else "SELL",
                "quote_activity_only": True,
                "levels": fib_levels(bars[i], side, policy.tick_size)})
    return result


def _strict_gold_symbol(value: str) -> bool:
    return value.upper().startswith("XAUUSD") and len(value) <= 24


def scan_csv(path: str | Path, policy: QuotePolicy) -> dict:
    """Offline CSV from an authorized XAUUSD broker export. Signals, NOT P&L.

    Required: symbol,time_utc,open,high,low,close,tick_volume,spread_points.
    Times must be ISO 8601 WITH UTC offset; one forming candle is excluded.
    """
    policy.validate()
    path = Path(path)
    # Stream checksum instead of loading multi-GB authorized broker exports in RAM.
    with path.open("rb") as handle:
        h = hashlib.file_digest(handle, "sha256").hexdigest()
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        fields = {"symbol", "time_utc", "open", "high", "low",
                  "close", "tick_volume", "spread_points"}
        if not fields.issubset(rd.fieldnames or []):
            raise ValueError("Missing XAUUSD CSV required fields")
        selected_symbol = None
        for row in rd:
            sym = row["symbol"].strip()
            if not _strict_gold_symbol(sym):
                raise ValueError("Only XAUUSD broker symbols permitted")
            if selected_symbol is None:
                selected_symbol = sym
            elif sym != selected_symbol:
                raise ValueError("Mixed broker symbols")
            date = datetime.fromisoformat(row["time_utc"].replace("Z", "+00:00"))
            if date.tzinfo is None or date.utcoffset() is None:
                raise ValueError("Explicit timezone required")
            rows.append({
                "time": int(date.timestamp()),
                **{k: float(row[k]) for k in ("open", "high", "low", "close")},
                "tick_volume": int(row["tick_volume"]),
                "spread_points": int(row["spread_points"]),
            })
    if not rows or not all(_valid_bar(x) for x in rows):
        raise ValueError("Empty or invalid broker candle data")
    if any(rows[i]["time"] <= rows[i-1]["time"] for i in range(1, len(rows))):
        raise ValueError("Unordered/duplicate candles")
    # Reject a mistaken timeframe selection, not just a couple of sparse bars.
    # Weekends and data gaps are allowed, but the given timeframe must actually occur.
    gaps = [rows[i]["time"] - rows[i-1]["time"] for i in range(1, len(rows))]
    if any(gap % policy.timeframe_seconds for gap in gaps):
        raise ValueError("Candles not aligned to selected broker timeframe")
    if len(rows) >= 3 and policy.timeframe_seconds not in gaps:
        raise ValueError("Selected timeframe has no contiguous candles in CSV")
    # No external proof of server time/completeness or broker execution quality.
    # The last row may be forming; fail closed by excluding it.
    signals = scan_closed(rows, len(rows)-2, policy) if len(rows) >= 2 else []
    return {"symbol": selected_symbol, "sha256": h,
            "rows": len(rows), "last_row_excluded_as_forming": True,
            "timeframe_seconds": policy.timeframe_seconds,
            "research_signals": signals, "closed_signals": len(signals),
            "real_aggressor_delta_available": False,
            "orders_sent": 0, "profitability_tested": False}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Offline XAU quote-only Tracker research")
    ap.add_argument("--csv", required=True)
    ap.add_argument("--timeframe", choices=["M1", "M5"], default="M1")
    ns = ap.parse_args()
    result = scan_csv(ns.csv, QuotePolicy(timeframe_seconds=60 if ns.timeframe == "M1" else 300))
    print(json.dumps(result, ensure_ascii=False, indent=2))
