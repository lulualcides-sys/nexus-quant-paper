"""V3: hourly confirmed macro trend + movement size, opt-in research only.

No optimization to validation/historic final. 1H aggregation uses *complete*
contiguous 5-minute bars. Trade signal sees the last FULLY CLOSED 1H bar.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass

from .data import Bar


@dataclass(frozen=True)
class MacroPolicy:
    name: str
    mode: str
    min_stop_pct: float
    hourly_atr_multiplier: float
    target_r: float
    max_hold: int
    min_hourly_atr_pct: float
    require_200_slope: bool
    max_extension_atr: float


def policies(timeframe):
    if timeframe not in ("1m", "5m"):
        raise ValueError("Unsupported timeframe")
    hold_24h = 1440 if timeframe == "1m" else 288
    hold_48h = 2880 if timeframe == "1m" else 576
    return (
        MacroPolicy("v3_hourly_core", "v3", .006, .80, 2.0, hold_24h,
                    .0035, False, 2.0),
        MacroPolicy("v3_hourly_strict", "v3", .009, 1.20, 2.3, hold_48h,
                    .0050, True, 1.0),
    )


def aggregate_closed_h1(m5):
    """Build only full 12 x M5 H1 groups; reject misaligned or missing bars."""
    out = []
    for k in range(0, len(m5) - 11):
        first = m5[k]
        if first.t % 3_600_000:
            continue
        chunk = m5[k:k + 12]
        if any(chunk[j].t != first.t + j * 300_000 for j in range(12)):
            continue
        out.append(Bar(
            first.t, first.o, max(b.h for b in chunk), min(b.l for b in chunk),
            chunk[-1].c, sum(b.v for b in chunk), sum(b.taker for b in chunk),
            sum(b.qv for b in chunk), sum(b.trades for b in chunk),
        ))
    return out


def last_fully_closed_h1_index(bars, i, macro_closes):
    """Closed entry bar is known only at its END, not at its open timestamp."""
    if i < 0 or i >= len(bars) or not macro_closes:
        return -1
    # An M1/M5 bar opening 09:55 becomes known 10:00; H1 09:00
    # becomes known 10:00 too, so it is legal. Not legal at 09:55.
    step = 60_000 if (len(bars) > 1 and
                      bars[1].t - bars[0].t == 60_000) else 300_000
    signal_closed_at = bars[i].t + step
    return bisect_right(macro_closes, signal_closed_at) - 1


def approve_macro_signal(bars, i, macro, mf, closes, policy):
    if i < 210 or not macro or mf is None or closes is None:
        return False
    h = last_fully_closed_h1_index(bars, i, closes)
    if h < 240:
        return False
    # Avoid stale (e.g. unavailable) macro bars, must be <=1 H old
    signal_end = bars[i].t + (60_000 if bars[1].t - bars[0].t == 60_000 else 300_000)
    if signal_end - closes[h] >= 3_600_000:
        return False
    price = bars[i].c
    hourly_atr = mf.atr[h]
    if price <= 0 or hourly_atr <= 0:
        return False
    if hourly_atr / price < policy["min_hourly_atr_pct"]:
        return False
    if not (mf.ema20[h] >= mf.ema50[h] > mf.ema200[h] and
            mf.ema50[h] > mf.ema50[h - 12] and
            macro[h].c > mf.ema50[h] and
            price >= mf.ema50[h]):
        return False
    if policy["require_200_slope"] and not (
        mf.ema200[h] > mf.ema200[h - 24]
    ):
        return False
    if price > mf.ema20[h] + policy["max_extension_atr"] * hourly_atr:
        return False
    return True


def extra_stop_distance(bars, sign_i, macro, mf, closes, policy, ref_price):
    """Stop floor based exclusively on hourly ATR known at SIGNAL close."""
    h = last_fully_closed_h1_index(bars, sign_i, closes)
    if h < 0:
        raise ValueError("Macro ATR not available at signal close")
    return max(ref_price * policy["min_stop_pct"],
               mf.atr[h] * policy["hourly_atr_multiplier"])
