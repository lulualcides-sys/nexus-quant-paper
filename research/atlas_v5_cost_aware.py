"""ATLAS V5 cost-aware research-only guard, frozen before cross-contract tests.

This DOES NOT replicate the closed Tracker algorithm. It starts from V1
(sweep/rejection) and rejects signals for which a full round-trip estimated
transaction cost is disproportionately large relative to the nominal target.

A distinct shock/noise variant adds only ex-ante ATR, session and traded-volume
guards. Neither rule looks at future candles or previous trade outcomes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import ceil, floor, isfinite
from statistics import mean

from research.atlas_v4_filters import CANDIDATES as V4_CANDIDATES, candidate as v4_candidate
from research.win_price_data import TZ, POINT_VALUE_BRL, WIN_TICK
from src.atlas_vector import vector_levels

V5_CANDIDATES=("v5_cost_guard","v5_cost_noise_guard")
ALL_MODELS=V4_CANDIDATES+V5_CANDIDATES
FEE_BRL=4.0
STRESS_SLIPPAGE_TICKS=2
MAX_COST_TO_GROSS_TARGET=0.12
ATR_MIN=0.65
ATR_MAX=1.80
VOLUME_BASE_LOOKBACK=20
VOLUME_RATIO_MIN=0.75
MIN_20BAR_AVG_QUANTITY=100

def _tick_levels(levels, side):
    """Matches conservative entry/target rounding of existing WIN simulator."""
    def up(x):return ceil(x/WIN_TICK-1e-9)*WIN_TICK
    def down(x):return floor(x/WIN_TICK+1e-9)*WIN_TICK
    return (up(levels["entry"]) if side==1 else down(levels["entry"]),
            down(levels["target"]) if side==1 else up(levels["target"]))

def cost_fraction(bar,side):
    if side not in (-1,1):
        raise ValueError("Invalid side")
    entry,target=_tick_levels(vector_levels(bar,side),side)
    gross=side*(target-entry)*POINT_VALUE_BRL
    cost=FEE_BRL+2*STRESS_SLIPPAGE_TICKS*WIN_TICK*POINT_VALUE_BRL
    if gross<=0:
        return float("inf")
    return cost/gross

def v5_candidate(bars,i,variant):
    if variant not in ALL_MODELS:
        raise ValueError("Unregistered ATLAS V5 research variant")
    if variant in V4_CANDIDATES:
        return v4_candidate(bars,i,variant)
    if i<100 or i>=len(bars):
        return 0
    side=v4_candidate(bars,i,"v1_reference")
    if not side or cost_fraction(bars[i],side)>MAX_COST_TO_GROSS_TARGET:
        return 0
    if variant=="v5_cost_guard":
        return side
    b=bars[i]
    d=datetime.fromtimestamp(b["time"],timezone.utc).astimezone(TZ)
    hm=d.hour*60+d.minute
    if not (9*60+35<=hm<16*60+30):
        return 0
    ranges=[]
    for j in range(i-14,i):
        old=bars[j]
        prior_close=bars[j-1]["close"]
        ranges.append(max(old["high"]-old["low"],abs(old["high"]-prior_close),
                          abs(old["low"]-prior_close)))
    atr=mean(ranges)
    span=b["high"]-b["low"]
    if not (atr>0 and ATR_MIN*atr<=span<=ATR_MAX*atr):
        return 0
    vols=[x.get("volume",0) for x in bars[i-VOLUME_BASE_LOOKBACK:i]]
    current=b.get("volume",0)
    if not all(isinstance(v,(int,float)) and isfinite(v) and v>0
               for v in vols+[current]):
        return 0
    prior_avg=mean(vols)
    if prior_avg<MIN_20BAR_AVG_QUANTITY or current<VOLUME_RATIO_MIN*prior_avg:
        return 0
    return side
