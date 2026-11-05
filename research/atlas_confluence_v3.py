"""Frozen ex-ante ATLAS v3 hypotheses, not the proprietary Tracker model.

The Tracker educator alleges confluence among liquidity, structure and Fibonacci
but provides no anchors, parameters, or source. Here we define falsifiable,
fully documented proxies and test them on WINQ26 without training on holdout.

All functions depend ONLY on bars through i (confirmed candle); pivots are
confirmed using at least TWO right-hand bars completed by i-1.
"""
from __future__ import annotations

from statistics import mean

from src.atlas_vector import signal as baseline, vector_levels
from research.atlas_tracker_v2 import candidate as v2_candidate

VARIANTS = ("baseline", "exhaustion_v2", "exhaustion_direction_v2",
            "fib_confluence_v3", "fib_confluence_obstacle_v3")
WINDOW=48
MIN_CLOSE_LOCATION=0.65
MAX_ATR_RATIO=2.0
MIN_ATR_RATIO=0.65


def confirmed_pivots(prior, kind, width=2):
    """No future knowledge: the trailing 2 bars precede today's signal."""
    result=[]
    if kind not in ("high","low"):
        raise ValueError("Invalid pivot direction")
    for j in range(width, len(prior)-width):
        center=prior[j][kind]
        left=[prior[k][kind] for k in range(j-width,j)]
        right=[prior[k][kind] for k in range(j+1,j+width+1)]
        if kind=="high" and center>max(left+right):
            result.append(center)
        elif kind=="low" and center<min(left+right):
            result.append(center)
    return result


def v3_signal(bars, i, variant="fib_confluence_v3"):
    if variant not in VARIANTS:
        raise ValueError("Unknown frozen candidate")
    if i < 75 or i >= len(bars):
        return 0
    if variant=="baseline":
        return baseline(bars,i)
    if variant in ("exhaustion_v2","exhaustion_direction_v2"):
        return v2_candidate(bars,i,variant)
    s=baseline(bars,i)
    if not s:
        return 0
    bar=bars[i]
    span=bar["high"]-bar["low"]
    if span<=0:
        return 0
    pos=(bar["close"]-bar["low"])/span
    # Confirmation: rebound closes in upper region; sell rejection in lower.
    if (s==1 and (bar["close"]<=bar["open"] or pos<MIN_CLOSE_LOCATION)) or (
        s==-1 and (bar["close"]>=bar["open"] or pos>1-MIN_CLOSE_LOCATION)
    ):
        return 0
    recent=bars[i-WINDOW:i]
    prev_close=bars[i-WINDOW-1]["close"]
    tr=[]
    for row in recent:
        tr.append(max(row["high"]-row["low"],abs(row["high"]-prev_close),
                      abs(row["low"]-prev_close)))
        prev_close=row["close"]
    atr=mean(tr[-14:])
    if atr<=0 or not (MIN_ATR_RATIO*atr <= span <= MAX_ATR_RATIO*atr):
        return 0
    hi=max(x["high"] for x in recent)
    lo=min(x["low"] for x in recent)
    if hi<=lo:
        return 0
    relative_location=(bar["close"]-lo)/(hi-lo)
    # Predeclared Fibonacci-inspired extreme zone, NOT the Tracker anchors.
    if s==1 and relative_location>0.382:
        return 0
    if s==-1 and relative_location<0.618:
        return 0
    if variant=="fib_confluence_obstacle_v3":
        levels=vector_levels(bar,s)
        entry,target=levels["entry"],levels["target"]
        side_kind="high" if s==1 else "low"
        peaks=confirmed_pivots(recent,side_kind)
        # Opposite liquidity clusters: at least 2 confirmed pivots near each
        # other (tolerance: 15% of the prior ATR) between entry and target.
        tolerance=0.15*atr
        blockers=[p for p in peaks if (entry<p<target if s==1 else target<p<entry)]
        for j,p in enumerate(blockers):
            if any(abs(p-q)<=tolerance for q in blockers[j+1:]):
                return 0
    return s
