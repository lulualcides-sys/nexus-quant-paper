"""V5 research-only, causal H4 trend gate for ORIGINAL V4 H1 fixed-exit signals.

The aim is signal quality and cost coverage, NOT to manufacture a positive
historical P&L. 2024–June/2026 were examined in preceding projects and
are never described as untouched holdouts. No broker orders.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass

from .data import Bar

HOUR_MS = 3_600_000
H4_MS = 4 * HOUR_MS


@dataclass(frozen=True)
class H4Policy:
    name: str
    min_trend_efficiency: float
    min_atr_pct: float
    require_ema200_slope: bool
    max_distance_to_ema20_atr: float


# Two causal hypotheses frozen before the first V5 historical run.
H4_POLICIES = (
    H4Policy("h4_alignment", .16, .005, False, 2.5),
    H4Policy("h4_directional", .30, .008, True, 1.8),
)


def aggregate_closed_h4(hours):
    """Only complete aligned groups of four contiguous H1 candlesticks."""
    output = []
    for i in range(len(hours) - 3):
        a = hours[i]
        if a.t % H4_MS:
            continue
        quartet = hours[i:i + 4]
        if any(quartet[k].t != a.t + k * HOUR_MS for k in range(4)):
            continue
        output.append(Bar(
            a.t, a.o, max(x.h for x in quartet),
            min(x.l for x in quartet), quartet[-1].c,
            sum(x.v for x in quartet), sum(x.taker for x in quartet),
            sum(x.qv for x in quartet), sum(x.trades for x in quartet),
        ))
    return output


def last_closed_h4_index(signal_closed_ms, h4_closes):
    """At entry M5 open use H4 whose CLOSE <= that exact timestamp."""
    return bisect_right(h4_closes, signal_closed_ms) - 1


def _efficiency(bars, h, lookback=12):
    denom = sum(abs(bars[k].c - bars[k - 1].c)
                for k in range(h - lookback + 1, h + 1))
    return ((bars[h].c - bars[h - lookback].c) / denom
            if denom else 0.0)


def h4_rejection_reason(*, entry_open_ms, entry_ref_price,
                        h4, features, h4_closes, policy):
    """Return None to approve or one auditable veto reason.

    Does NOT inspect current M5 high/low/close nor future H4 prices.
    Keep this decision independent of execution fee scenario.
    """
    if policy not in H4_POLICIES:
        raise ValueError("V5 gate must be a frozen H4Policy")
    if entry_open_ms < 0 or entry_ref_price <= 0:
        return "invalid_reference"
    if not h4 or not features or not h4_closes:
        return "missing_closed_h4"
    h = last_closed_h4_index(entry_open_ms, h4_closes)
    if h < 250 or h >= len(h4):
        return "insufficient_h4_history"
    if h4_closes[h] > entry_open_ms or entry_open_ms - h4_closes[h] >= H4_MS:
        return "stale_or_future_h4"
    c, atr = h4[h].c, features.atr[h]
    if not (c > 0 and atr > 0 and .004 < atr / c < .065):
        return "h4_invalid_volatility"
    if atr / c < policy.min_atr_pct:
        return "h4_below_fee_hurdle"
    if not (
        features.ema20[h] > features.ema50[h] > features.ema200[h] and
        features.ema50[h] > features.ema50[h - 6] and
        c > features.ema50[h] and
        entry_ref_price > features.ema50[h]
    ):
        return "h4_trend_not_aligned"
    if policy.require_ema200_slope and not (
        features.ema200[h] > features.ema200[h - 12]
    ):
        return "h4_slow_trend_not_rising"
    if _efficiency(h4, h) < policy.min_trend_efficiency:
        return "h4_directional_efficiency_too_low"
    if entry_ref_price > features.ema20[h] + (
        policy.max_distance_to_ema20_atr * atr
    ):
        return "h4_too_extended"
    return None
