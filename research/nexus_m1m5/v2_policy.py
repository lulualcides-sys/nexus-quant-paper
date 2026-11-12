"""Cost-aware V2 candidate gate. Never estimate an actual future price.

A target farther than fees is NECESSARY but not SUFFICIENT for positive
expected value: this module does not label those trades 'profitable'.
All inputs are from the already CLOSED signal bar or frozen fee assumptions.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Policy:
    name: str
    reward_to_cost: float
    target_r: float
    max_hold: int
    trend_gate: bool


def policies(timeframe):
    if timeframe not in ("1m", "5m"):
        raise ValueError("Only original lab timeframes")
    hold = 360 if timeframe == "1m" else 288
    return (
        Policy("v2_cost_floor", 2.0, 4.0, hold, False),
        Policy("v2_cost_plus_regime", 2.0, 4.0, hold, True),
    )


def approve_closed_signal(name, sig, bars, f, i, *, cost, reward_to_cost,
                          target_r, trend_gate):
    if i < 210 or i >= len(bars) or reward_to_cost < 1 or target_r <= 0:
        raise ValueError("Invalid signal gate inputs")
    b = bars[i]
    a = f.atr[i]
    if b.c <= 0 or a <= 0:
        return False
    # Same ATR/structure stop bound as executor, evaluated on closed signal
    # bar without looking at the NEXT bar's opening price.
    stop_distance = max(
        sig.stop_atr * a,
        min(2.5 * a, max(0, b.c - sig.structure_low + .10 * a)),
    )
    # Baseline round-trip fee + execution deviation. This is a hurdle,
    # not a forecast or a probability of target reaching.
    round_trip = 2 * (cost["fee"] + cost["slip"] + cost["impact"])
    target_pct = target_r * stop_distance / b.c
    if target_pct < reward_to_cost * round_trip:
        return False

    if trend_gate:
        # Cost-aware macro regime is different from original setup:
        # require sustained upward drift without using any future bar.
        if i < 222 or not (f.ema50[i] > f.ema200[i] and
                           f.ema50[i] > f.ema50[i - 12] and
                           b.c > f.ema50[i]):
            return False
        if name == "vwap":
            # VWAP mean-reversion original lateral regime must remain;
            # this only vetoes setups in prevailing downtrends.
            if abs(f.ema20[i] - f.ema50[i]) >= .70 * a:
                return False
    return True
