"""One fixed time-causal H1 entry filter, shared by research and forward paper.

No broker access, no fitting of parameters, no live optimization.
H1 signal at bar i can lead only to entry at i+1 OPEN.
"""
from __future__ import annotations

from math import isfinite

COVERAGE_MULTIPLE=4.0
TREND_SEPARATION_ATR=1.5


def allow_signal(raw, candles, indicators, i, *, fee_bps):
    """Return original direction only if the last CLOSED bar satisfies all gates."""
    if raw not in (-1,0,1):
        raise ValueError("invalid signal direction")
    if raw==0:
        return 0
    if i<0 or i>=len(candles) or i>=len(indicators):
        raise ValueError("invalid completed candle index")
    p=indicators[i]
    close=candles[i]["close"]
    atr=p["atr"]
    e50=p["e50"]
    e200=p["e200"]
    if not all(isinstance(v,(int,float)) and isfinite(v) for v in
               (close,atr,e50,e200,fee_bps)):
        return 0
    if close<=0 or atr<=0 or fee_bps<0:
        return 0
    atr_bps=10000.0*atr/close
    trend_separation=abs(e50-e200)/atr
    if atr_bps < COVERAGE_MULTIPLE*fee_bps:
        return 0
    if trend_separation<TREND_SEPARATION_ATR:
        return 0
    if raw==1 and e50<=e200:
        return 0
    if raw==-1 and e50>=e200:
        return 0
    return raw
