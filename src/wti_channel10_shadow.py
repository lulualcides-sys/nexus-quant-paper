"""Forward-only WTI Channel10 + cost/trend gate PAPER experiment.

This is one additional experimental shadow, NOT a replacement or an additional
member of the 27 operational paper bots. It starts at observation time with
ZERO retroactive trades, no broker connection, independent virtual balance,
and exactly the fixed filter tested in research/cost_repair_lab.py.
"""
from __future__ import annotations

import json
from copy import deepcopy
from math import isfinite
from pathlib import Path

from src import experimental_h1 as h1
from src.cost_aware_gate import allow_signal
from src.strategies import make_indicators

FILE=Path("state/wti_channel10_filtered_shadow_v1.json")
SCHEMA=1
MARKET="XTIUSD"
STRATEGY="channel10"
POLICY="channel10_h1_cost_atr_4x_ema50_ema200_1p5atr"
TIMEFRAME_SECONDS=3600


def initial(bars):
    if len(bars)<=h1.WARMUP+2:
        raise ValueError("WTI H1: historical indicator warmup missing")
    marks=[b["time"] for b in bars]
    if marks!=sorted(set(marks)):
        raise ValueError("WTI H1: duplicated/unsorted timestamps")
    return {"schema":SCHEMA,"paper_only":True,"experimental_only":True,
            "source":"Yahoo CL=F H1 proxy, not FBS fills",
            "policy":POLICY,"market":MARKET,"strategy":STRATEGY,
            "h1_watermark":marks[-1],
            "book":h1.book(),
            "first_observation_ts":marks[-1],
            "no_historical_backfill":True,
            "last_run_reason":"Inicializado a partir do candle observado: ZERO entradas retroativas"}


def filtered_signal(strategy,bars,ind,i):
    if strategy!=STRATEGY:
        raise ValueError("Only WTI channel10 is supported")
    original=h1.setup(strategy,bars,ind,i)
    # The exact base fee is fixed. Under stress studies, only execution fees
    # change, not which closed-bar signals would have been selected.
    return allow_signal(original,bars,ind,i,fee_bps=h1.COST_BPS[MARKET])


def update(state,bars):
    if not isinstance(bars,list) or len(bars)<=h1.WARMUP+2:
        raise ValueError("WTI H1 feed insufficient")
    stamps=[b["time"] for b in bars]
    if stamps!=sorted(set(stamps)):
        raise ValueError("WTI feed timestamps invalid")
    if state is None:
        return initial(bars)
    if (state.get("schema")!=SCHEMA or state.get("paper_only") is not True
            or state.get("experimental_only") is not True
            or state.get("policy")!=POLICY or state.get("market")!=MARKET
            or state.get("strategy")!=STRATEGY
            or state.get("no_historical_backfill") is not True):
        raise ValueError("WTI shadow state incompatible; preserve existing book")
    mark=state.get("h1_watermark")
    if mark is None or mark not in stamps:
        raise ValueError("WTI watermark missing in price feed: refuse fabricated fills")
    if mark>stamps[-1]:
        raise ValueError("WTI price feed has moved backward")
    # Never mutate an incoming state on error.
    result=deepcopy(state)
    after=stamps.index(mark)+1
    if after>=len(bars):
        result["last_run_reason"]="Sem novo candle H1 fechado"
        return result
    inds=make_indicators(bars)
    for i in range(max(after,h1.WARMUP+1),len(bars)):
        h1.step(result["book"],MARKET,STRATEGY,bars,inds,i,
                signal_fn=filtered_signal)
        result["h1_watermark"]=stamps[i]
    result["last_run_reason"]=result["book"].get("last_reason","Sem sinal")
    if (result["book"]["equity"]<=0 or
        not isfinite(result["book"]["equity"])):
        raise ValueError("WTI shadow book equity invalid")
    return result


def process(bars, *, path=FILE):
    """Idempotent processing of observed candles; writes ONLY its own file."""
    path=Path(path)
    prior=json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    current=update(prior,bars)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(current,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return current
