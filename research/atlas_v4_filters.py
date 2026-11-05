"""ATLAS V4: independent, preregistered, falsifiable WIN M1 signal candidates.

Research only. Does NOT reverse engineer Greenhouse's proprietary Tracker.
Each decision at i uses closed bars <=i; the executor creates its order on i+1.
Parameters fixed BEFORE running June/July validation, with no optimization
on those months. Futures literature motivates trading-session, liquidity and
volatility regimes, but offers no evidence that these thresholds work on WIN.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from statistics import mean

from research.win_price_data import TZ, local_day

CANDIDATES = (
    "v1_reference",
    "v3_reference",
    "v4_sweep_quality",
    "v4_sweep_trend",
    "v4_sweep_vwap",
    "v4_breakout_retest",
)
LOOKBACK = 20
WARMUP = 100
TICK = 5.0

def _ema(values, period):
    alpha = 2 / (period + 1)
    out = float(values[0])
    for value in values[1:]:
        out += alpha * (float(value) - out)
    return out

def _clock(ts):
    d = datetime.fromtimestamp(ts, timezone.utc).astimezone(TZ)
    return d.hour * 60 + d.minute

def _tr14(bars, i):
    ranges=[]
    for j in range(i-14,i):
        p=bars[j-1]["close"]
        b=bars[j]
        ranges.append(max(b["high"]-b["low"],abs(b["high"]-p),abs(b["low"]-p)))
    return mean(ranges)

def _base(bars, i, *, volume_multiple, wick, bullish_close, break_mode):
    """Return -1/0/+1; only the last closed bar and 20 previous bars used."""
    if i < WARMUP or i>=len(bars):
        return 0
    b=bars[i]
    span=b["high"]-b["low"]
    if span < 2*TICK:
        return 0
    last=bars[i-LOOKBACK:i]
    volumes=[x.get("volume",0) for x in last]
    curr_volume=b.get("volume",0)
    if not all(isinstance(v,(float,int)) and isfinite(v) and v>0 for v in volumes+[curr_volume]):
        return 0
    avg_volume=sum(volumes)/len(volumes)
    # Liquidity floor excludes low-quantity distant expiries from experimentation.
    if avg_volume<100 or curr_volume<avg_volume*volume_multiple:
        return 0
    atr=_tr14(bars,i)
    if not (atr>0 and 0.55*atr<=span<=2.20*atr):
        return 0
    high=max(x["high"] for x in last)
    low=min(x["low"] for x in last)
    lower=min(b["open"],b["close"])-b["low"]
    upper=b["high"]-max(b["open"],b["close"])
    location=(b["close"]-b["low"])/span
    # Signal confirms a sweep rejection, or an independently observed breakout
    # with a limit retest order on the next bar. Neither uses future bars.
    if break_mode:
        if (b["close"]>high+TICK and b["close"]>b["open"]
                and location>=bullish_close):
            return 1
        if (b["close"]<low-TICK and b["close"]<b["open"]
                and location<=1-bullish_close):
            return -1
    else:
        if (b["low"]<low and b["close"]>low and b["close"]>b["open"]
                and lower/span>=wick and location>=bullish_close):
            return 1
        if (b["high"]>high and b["close"]<high and b["close"]<b["open"]
                and upper/span>=wick and location<=1-bullish_close):
            return -1
    return 0

def _session_vwap(bars,i):
    day=local_day(bars[i]["time"])
    turnover=quantity=0.0
    for j in range(i,-1,-1):
        b=bars[j]
        if local_day(b["time"])!=day:
            break
        v=b["volume"]
        turnover += ((b["high"]+b["low"]+b["close"])/3)*v
        quantity += v
    return turnover/quantity if quantity>0 else None

def candidate(bars,i,variant):
    if variant not in CANDIDATES:
        raise ValueError("Unregistered V4 variant")
    if i< WARMUP or i>=len(bars):
        return 0
    if variant == "v1_reference":
        from src.atlas_vector import signal
        return signal(bars,i)
    if variant == "v3_reference":
        from research.atlas_confluence_v3 import v3_signal
        return v3_signal(bars,i,"fib_confluence_v3")
    local_minute=_clock(bars[i]["time"])
    # Ignore first 25 minutes of opening volatility and late illiquid windows.
    if not (9*60+35<=local_minute<16*60+30):
        return 0
    if variant=="v4_breakout_retest":
        return _base(bars,i,volume_multiple=1.25,wick=0,
                     bullish_close=0.72,break_mode=True)
    side=_base(bars,i,volume_multiple=1.25,wick=0.25,
               bullish_close=0.62,break_mode=False)
    if not side:
        return 0
    if variant=="v4_sweep_quality":
        return side
    if variant=="v4_sweep_trend":
        prior=[x["close"] for x in bars[i-75:i]]
        fast=_ema(prior,20)
        slow=_ema(prior,50)
        return side if (fast>slow if side==1 else fast<slow) else 0
    # Same-session VWAP: only accumulated closed trade quantities, not future.
    vwap=_session_vwap(bars,i)
    if vwap is None:
        return 0
    # A return above/below session fair value may avoid fading strong trends.
    return side if (bars[i]["close"]>=vwap if side==1
                    else bars[i]["close"]<=vwap) else 0
