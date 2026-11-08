"""Six distinct, long-only Binance SPOT research hypotheses.

All signal functions inspect the current CLOSED candle and earlier bars only.
A signal is NOT a fill. The next candle open is the earliest entry reference.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from math import sqrt


@dataclass(frozen=True, slots=True)
class Features:
    ema20: list
    ema50: list
    ema200: list
    atr: list
    sma20: list
    std20: list
    vol20: list
    high20: list
    low20: list
    vwap48: list
    squeeze: list


@dataclass(frozen=True, slots=True)
class Signal:
    name: str
    stop_atr: float
    target_r: float
    structure_low: float
    reason: str


SPECS = {
    "sweep": {"tf": "1m", "stop_atr": 1.25, "target_r": 2.0},
    "vwap": {"tf": "1m", "stop_atr": 1.15, "target_r": 1.6},
    "trend": {"tf": "5m", "stop_atr": 1.40, "target_r": 2.1},
    "breakout": {"tf": "5m", "stop_atr": 1.65, "target_r": 2.3},
    "squeeze": {"tf": "5m", "stop_atr": 1.40, "target_r": 2.0},
    "flow": {"tf": "5m", "stop_atr": 1.30, "target_r": 1.8},
}


def build_features(bars):
    n = len(bars)
    lists = [[] for _ in range(11)]
    ema20, ema50, ema200, atr, sma20, std20, vol20, high20, low20, vwap48, squeeze = lists
    if not n:
        return Features(*lists)
    e20 = e50 = e200 = bars[0].c
    a = max(1e-9, bars[0].h - bars[0].l)
    price_sum = price_sq = vol_sum = 0.0
    volume48 = dollar48 = 0.0
    for i, b in enumerate(bars):
        e20 += 2 / 21 * (b.c - e20)
        e50 += 2 / 51 * (b.c - e50)
        e200 += 2 / 201 * (b.c - e200)
        prev_c = bars[i - 1].c if i else b.c
        tr = max(b.h - b.l, abs(b.h - prev_c), abs(b.l - prev_c))
        a += (tr - a) / 14
        price_sum += b.c
        price_sq += b.c * b.c
        vol_sum += b.v
        typical = (b.h + b.l + b.c) / 3
        volume48 += b.v
        dollar48 += typical * b.v
        if i >= 20:
            old = bars[i - 20]
            price_sum -= old.c
            price_sq -= old.c * old.c
            vol_sum -= old.v
        if i >= 48:
            old = bars[i - 48]
            volume48 -= old.v
            dollar48 -= ((old.h + old.l + old.c) / 3) * old.v
        window = min(i + 1, 20)
        mid = price_sum / window
        sd = sqrt(max(0.0, price_sq / window - mid * mid))
        ema20.append(e20)
        ema50.append(e50)
        ema200.append(e200)
        atr.append(a)
        sma20.append(mid)
        std20.append(sd)
        vol20.append((vol_sum - b.v + bars[i - 20].v) / 20 if i >= 20 else 0.0)
        high20.append(max(x.h for x in bars[i - 20:i]) if i >= 20 else float("inf"))
        low20.append(min(x.l for x in bars[i - 20:i]) if i >= 20 else 0.0)
        vwap48.append(dollar48 / volume48 if volume48 > 0 else b.c)
        # BB inside KC using only fully observed (current + prior) data.
        squeeze.append(bool(i >= 200 and 2 * sd < 1.5 * a))
    return Features(*lists)


def _signal(name, i, f, bars, *, low=None, reason=None):
    b = bars[i]
    return Signal(name, SPECS[name]["stop_atr"], SPECS[name]["target_r"],
                  b.l if low is None else low, reason or name)


def _breakout_at(bars, f, i):
    if i < 210:
        return False
    b = bars[i]
    threshold = f.high20[i]
    return (b.c > threshold and bars[i - 1].c <= f.high20[i - 1] and
            b.c > b.o and b.v >= 1.15 * f.vol20[i] > 0 and
            f.atr[i] >= 1.10 * f.atr[i - 5] and
            0 < b.c - threshold <= 0.45 * f.atr[i])


def signal(name, bars, f, i, higher=None, higher_features=None, *, breakout_mode="immediate", higher_closes=None):
    """Return signal after bar i CLOSE, never a retroactive fill."""
    if name not in SPECS:
        raise ValueError("Unknown robot")
    if i < 210 or i + 1 >= len(bars):
        return None
    b, prev = bars[i], bars[i - 1]
    a = f.atr[i]
    if not (a > 0 and f.vol20[i] > 0 and b.v > 0):
        return None
    if name == "sweep":
        level = f.low20[i]
        lower_wick = min(b.o, b.c) - b.l
        body = abs(b.c - b.o)
        if (b.l < level and b.c > level and b.c > b.o and
            lower_wick >= max(0.30 * a, 1.5 * body) and
            b.v > 1.20 * f.vol20[i] and (b.c - level) <= 0.7 * a):
            return _signal(name, i, f, bars, low=b.l, reason="low_sweep_recovery")
    elif name == "vwap":
        # Mean reversion only when trend separation and recent slope are small.
        if (abs(f.ema20[i] - f.ema50[i]) < 0.70 * a and
            abs(f.ema50[i] - f.ema50[i - 8]) < 0.45 * a and
            f.std20[i] > 0 and f.std20[i - 1] > 0 and
            prev.c < f.vwap48[i - 1] - 1.6 * f.std20[i - 1] and
            b.c > prev.c and b.c < f.vwap48[i] - 0.55 * f.std20[i] and
            b.c > b.o):
            return _signal(name, i, f, bars, low=min(b.l, prev.l),
                           reason="oversold_rolling_vwap_recovery")
    elif name == "trend":
        if not higher or not higher_features:
            return None
        close_ms = b.t + 300_000
        # Higher timeframe features may be precomputed but ONLY an M15 whose
        # closing timestamp is <= this M5 signal's close can be referenced.
        h15 = bisect_right(higher_closes if higher_closes is not None else [x.t + 900_000 for x in higher], close_ms) - 1
        if h15 < 205:
            return None
        h = higher[h15]
        hf = higher_features
        if (h.t + 900_000 <= close_ms and
            h.c > hf.ema50[h15] > hf.ema200[h15] and
            hf.ema50[h15] > hf.ema50[h15 - 4] and
            f.ema20[i] > f.ema50[i] and
            prev.l <= f.ema20[i - 1] + 0.20 * a and
            b.c > f.ema20[i] and b.c > prev.h and b.c > b.o and
            0 < b.c - f.ema20[i] < 0.90 * a):
            return _signal(name, i, f, bars, low=min(prev.l, b.l),
                           reason="m5_ema20_pullback_closed_m15_confirmation")
    elif name == "breakout":
        if breakout_mode not in ("immediate", "retest"):
            raise ValueError("Invalid breakout mode")
        if breakout_mode == "immediate" and _breakout_at(bars, f, i):
            return _signal(name, i, f, bars, low=f.low20[i],
                           reason="donchian_atr_volume_confirm")
        if breakout_mode == "retest":
            for j in range(i - 1, max(209, i - 4), -1):
                if _breakout_at(bars, f, j):
                    level = f.high20[j]
                    if (b.l <= level + .25 * a and b.c > level and b.c > b.o
                        and b.c - level <= 0.65 * a and b.v > 0.8 * f.vol20[i]):
                        return _signal(name, i, f, bars, low=min(level, b.l),
                                       reason="prior_confirmed_breakout_retest")
    elif name == "squeeze":
        compressed = sum(f.squeeze[i - k] for k in range(1, 7))
        bb_upper = f.sma20[i] + 2 * f.std20[i]
        kc_upper = f.ema20[i] + 1.5 * a
        if (compressed >= 4 and not f.squeeze[i] and
            b.c > max(bb_upper, kc_upper) and
            prev.c <= f.sma20[i - 1] + 2 * f.std20[i - 1] and
            b.v >= 1.25 * f.vol20[i] and b.h - b.l >= 0.9 * a):
            return _signal(name, i, f, bars, low=min(b.l, prev.l),
                           reason="bb_keltner_compression_expansion")
    elif name == "flow":
        # Taker-buy candle volume is a trade-aggressor proxy, NOT L2/order book.
        ratios = [bars[j].taker / bars[j].v if bars[j].v else 0 for j in range(i - 2, i + 1)]
        if (ratios[-1] >= .59 and sum(ratios) / 3 >= .55 and
            b.v >= 1.35 * f.vol20[i] and
            f.ema20[i] > f.ema50[i] and
            b.c > f.ema20[i] and b.c > prev.h and b.c > b.o and
            a / b.c >= .0003):
            return _signal(name, i, f, bars, low=min(b.l, prev.l),
                           reason="taker_buy_ratio_with_trend_confirmation")
    return None
