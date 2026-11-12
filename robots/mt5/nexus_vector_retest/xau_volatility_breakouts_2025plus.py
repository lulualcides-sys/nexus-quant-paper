#!/usr/bin/env python3
"""Independent XAUUSD intraday volatility structures, all MT5 minute TFs 2025+.

NR7 here explicitly means narrowest of last seven *intraday bars*, not
Toby Crabel's classical NR7 daily session. These are hypotheses, not profit.
No indicator can repaint a CLOSED candle; fills occur on NEXT OPEN, with
historical stop-first OHLC execution. No MT5 broker ticks or actual orders.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from points10k import events as frozen_ema_events, WARM, POINT
from research_oos import prepared, bars_for, download
from points10k_2025 import source as load_2025
from alpha_xau_mtf_2025plus import (
    CUTOFF, TF_MINUTES, COST_GRID, horizon_bars,
    replay_one, summarize, windows_by_quarter)

MODELS = ("EMA21_BASE", "NR7_BAR_BREAK", "INSIDE_MOTHER_BREAK",
          "VOL_COMPRESSION_RELEASE", "EFFICIENCY_ER20_BREAK")
OUT=Path(__file__).resolve().parent / "xau_volatility_breakouts_2025plus_results"


def feature_frame(frame):
    """Compute only trailing, never centered, indicators and levels."""
    f=frame.copy()
    c=f.close.astype(float)
    hi=f.high.astype(float)
    lo=f.low.astype(float)
    tr=pd.concat([
        hi-lo, (hi-c.shift(1)).abs(), (lo-c.shift(1)).abs()],
        axis=1).max(axis=1)

    span=hi-lo
    f["nr7_prev"]=(span.shift(1)<=span.shift(1).rolling(
        7,min_periods=7).min()) & (span.shift(1)>0)

    # Entire completed bar i-1 inside mother bar i-2.
    f["inside_prev"]=(hi.shift(1)<hi.shift(2)) & (lo.shift(1)>lo.shift(2))
    f["prev_mother_hi"]=hi.shift(2)
    f["prev_mother_lo"]=lo.shift(2)
    f["prev_hi"]=hi.shift(1)
    f["prev_lo"]=lo.shift(1)

    # Compare six *previous* bars to the 20 immediately before those six.
    f["short_tr6"]=tr.shift(1).rolling(6,min_periods=6).mean()
    f["old_tr20"]=tr.shift(7).rolling(20,min_periods=20).mean()
    f["prior8_hi"]=hi.shift(1).rolling(8,min_periods=8).max()
    f["prior8_lo"]=lo.shift(1).rolling(8,min_periods=8).min()
    f["prior12_hi"]=hi.shift(1).rolling(12,min_periods=12).max()
    f["prior12_lo"]=lo.shift(1).rolling(12,min_periods=12).min()
    erpath=c.diff().abs().rolling(20,min_periods=20).sum()
    f["er20"]=(c-c.shift(20)).abs()/erpath.replace(0,np.nan)
    return f


def make_signals(frame, model, reference=None):
    """Build signal-bar events; only i and earlier candles enter decision.

    Future NEXT open i+1 is used only to reject a nonsensical stop distance
    when submitting at that open, never to decide the breakout or direction.
    """
    if model not in MODELS:
        raise ValueError(f"unsupported setup: {model}")
    if model=="EMA21_BASE":
        return list(reference if reference is not None
                    else frozen_ema_events(frame,"EMA21_PULLBACK"))
    n=len(frame)
    op=frame.open.to_numpy(dtype=float)
    hi=frame.high.to_numpy(dtype=float)
    lo=frame.low.to_numpy(dtype=float)
    cl=frame.close.to_numpy(dtype=float)
    atr=frame.atr.to_numpy(dtype=float)
    body=(cl-op)/np.maximum(hi-lo,1e-9)
    side=np.zeros(n,dtype=np.int8)
    reference_level=np.full(n,np.nan)
    stop_level=np.full(n,np.nan)

    if model=="NR7_BAR_BREAK":
        nr=frame.nr7_prev.to_numpy(dtype=bool)
        ph=frame.prev_hi.to_numpy(dtype=float)
        pl=frame.prev_lo.to_numpy(dtype=float)
        long=nr&(cl>ph+0.08*atr)&(body>.22)
        short=nr&(cl<pl-0.08*atr)&(body<-.22)
        side=np.where(long,1,np.where(short,-1,0))
        reference_level=np.where(long,ph,pl)
        stop_level=np.where(long,pl,np.where(short,ph,np.nan))
    elif model=="INSIDE_MOTHER_BREAK":
        inside=frame.inside_prev.to_numpy(dtype=bool)
        top=frame.prev_mother_hi.to_numpy(dtype=float)
        bottom=frame.prev_mother_lo.to_numpy(dtype=float)
        long=inside&(cl>top+.05*atr)&(body>.18)
        short=inside&(cl<bottom-.05*atr)&(body<-.18)
        side=np.where(long,1,np.where(short,-1,0))
        reference_level=np.where(long,top,bottom)
        stop_level=np.where(long,bottom,np.where(short,top,np.nan))
    elif model=="VOL_COMPRESSION_RELEASE":
        small=frame.short_tr6.to_numpy(dtype=float)
        large=frame.old_tr20.to_numpy(dtype=float)
        top=frame.prior8_hi.to_numpy(dtype=float)
        bottom=frame.prior8_lo.to_numpy(dtype=float)
        compact=(small<=.72*large)&(small>0)
        impulse=(hi-lo)>=1.4*small
        long=compact&impulse&(cl>top+.08*atr)&(body>.34)
        short=compact&impulse&(cl<bottom-.08*atr)&(body<-.34)
        side=np.where(long,1,np.where(short,-1,0))
        reference_level=np.where(long,top,bottom)
        stop_level=np.where(long,top,np.where(short,bottom,np.nan))
    elif model=="EFFICIENCY_ER20_BREAK":
        er=frame.er20.to_numpy(dtype=float)
        top=frame.prior12_hi.to_numpy(dtype=float)
        bottom=frame.prior12_lo.to_numpy(dtype=float)
        long=(er>=.38)&(cl>top+.10*atr)&(body>.30)
        short=(er>=.38)&(cl<bottom-.10*atr)&(body<-.30)
        side=np.where(long,1,np.where(short,-1,0))
        reference_level=np.where(long,top,bottom)
        stop_level=np.where(long,top,np.where(short,bottom,np.nan))

    results=[]
    for i in np.flatnonzero(side):
        if i<WARM or i>=n-1:
            continue
        direction=int(side[i])
        a=float(atr[i])
        pivot=float(stop_level[i])
        if not np.isfinite([a,pivot,op[i+1],hi[i],lo[i],reference_level[i]]).all() or a<=0:
            continue
        stop=(min(lo[i],pivot)-.12*a if direction>0
              else max(hi[i],pivot)+.12*a)
        risk=direction*(op[i+1]-stop)
        if .12*a<=risk<=4.0*a:
            results.append((int(i),direction,float(stop),
                             float(min(1.,abs(body[i])))))
    return results


def evaluate_year(raw,year,tf):
    if raw.empty or raw.index.min()<CUTOFF:
        raise ValueError("only 2025+ permitted")
    f=feature_frame(prepared(raw if tf==1 else bars_for(raw,tf)))
    if f.empty or f.index.min()<CUTOFF:
        raise ValueError("pre-2025 data or empty window")
    original=frozen_ema_events(f,"EMA21_PULLBACK")
    signals={m:make_signals(f,m,reference=original) for m in MODELS}
    if signals["EMA21_BASE"]!=original:
        raise AssertionError("baseline EMA21 mutated")
    trades={m:[] for m in MODELS}
    windows=[]
    for quarter,first,last in windows_by_quarter(f,horizon_bars(tf)):
        if first is None:
            windows.append(dict(quarter=quarter,status="INSUFFICIENT_BARS"))
            continue
        models={}
        for m in MODELS:
            replay=replay_one(f,signals[m],first,last,tf,"RUNNER_96H")
            trades[m].extend(replay)
            models[m]={str(cost):summarize(replay,cost) for cost in COST_GRID}
        windows.append(dict(quarter=quarter,first=str(f.index[first]),
                            last=str(f.index[last-1]),models=models))
        print("VOL_QUARTER",json.dumps({
          "year":year,"tf":f"M{tf}","quarter":quarter,
          "models":{k:models[k]["0.8"] for k in MODELS}}),flush=True)
    result=dict(year=year,tf=f"M{tf}",raw_bars=len(f),
       signal_count={m:len(v) for m,v in signals.items()},quarters=windows,
       summary={m:{str(c):summarize(trades[m],c) for c in COST_GRID} for m in MODELS})
    print("VOL_YEAR",json.dumps(dict(year=year,tf=f"M{tf}",
                    summary=result["summary"])),flush=True)
    return result


def screening(cases):
    """Frozen pre-read threshold; no real out-of-sample validation implied."""
    compare=[]
    for tf in TF_MINUTES:
        a=next(x for x in cases if x["year"]=="2025" and x["tf"]==f"M{tf}")
        b=next(x for x in cases if x["year"]=="2026" and x["tf"]==f"M{tf}")
        for model in MODELS:
            x=a["summary"][model]["1.2"]
            y=b["summary"][model]["1.2"]
            positive25=sum(q["models"][model]["1.2"]["net_pts"]>0
                           for q in a["quarters"] if "models" in q)
            positive26=sum(q["models"][model]["1.2"]["net_pts"]>0
                           for q in b["quarters"] if "models" in q)
            passed=(x["N"]>=100 and y["N"]>=50
                 and x["PF"] is not None and y["PF"] is not None
                 and x["PF"]>1.1 and y["PF"]>1.1
                 and x["net_pts"]>0 and y["net_pts"]>0
                 and positive25>=3 and positive26>=1)
            compare.append(dict(tf=f"M{tf}",model=model,
                trades_2025=x["N"],trades_2026_partial=y["N"],
                net_2025_cost1_2=x["net_pts"],net_2026_partial_cost1_2=y["net_pts"],
                pf_2025_cost1_2=x["PF"],pf_2026_partial_cost1_2=y["PF"],
                positive_quarters_2025=positive25,
                positive_quarters_2026_partial=positive26,
                screened=bool(passed)))
    return compare


def main():
    raw25,_=load_2025()
    raw26=download()
    if raw25.index.min()<CUTOFF or raw26.index.min()<CUTOFF:
        raise ValueError("2025 date boundary")
    cases=[]
    for tf in TF_MINUTES:
        for year,raw in (("2025",raw25),("2026",raw26)):
            cases.append(evaluate_year(raw,year,tf))
    compared=screening(cases)
    selected=[x for x in compared if x["screened"]]
    data=dict(symbol="XAUUSD",date_start="2025-01-01",
      models=MODELS,timeframes=[f"M{x}" for x in TF_MINUTES],
      method="non-repainting completed intraday bars, next open, stop first; same original Runner96h",
      costs_usd_per_ounce=COST_GRID,point_assumed=POINT,
      warnings=["NR7 here is intraday BAR NR7, not classic daily NR7.",
         "2026 only Q2 Q3; years 2025/26 already researched and feeds differ.",
         "55 comparisons create selection bias; no untouched OOS.",
         "No broker real ticks, Bid/Ask, variable spread, commission, swap or slippage.",
         "DD only on closed trade results, not intratrade equity.",
         "Not a native MT5 strategy tester, not real account return.",
         "Research only; previous four user-selected candidates unchanged."],
      cases=cases,comparison=compared,preliminary_shortlist=selected,
      approved_for_live=False)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"VOLATILITY_BREAKOUT_RESULTS.json").write_text(
      json.dumps(data,indent=2,ensure_ascii=False)+"\n")
    table=["# XAUUSD volatility compression / NR7-bar / inside-bar, 2025+",
       "","Only research OHLC; no live MT5. Four new independent structures.",
       "All official M1–M30 minute frames. 2026 source is partial.",
       "NR7 means intraday 7 bars, NOT classical 7 trading days.",
       "Costs 0.8/1.2/1.6 USD/oz assumed; stop-first, next open.",
       "","| TF | Model | Trades 2025 | Net 2025 cost1.2 | PF25 | Trades 2026 partial | Net26 cost1.2 | PF26 | +quarters 2025/26 |",
       "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for row in compared:
        table.append("| "+" | ".join(str(row[k]) for k in
          ("tf","model","trades_2025","net_2025_cost1_2","pf_2025_cost1_2",
           "trades_2026_partial","net_2026_partial_cost1_2",
           "pf_2026_partial_cost1_2"))+
          f' | {row["positive_quarters_2025"]}/{row["positive_quarters_2026_partial"]} |')
    table += ["","## Frozen experimental screening", "",
         str(selected) if selected else "None passed; do not claim positive strategy.",
         "","No new bots approved for real trades. Data already explored; forward testing required."]
    (OUT/"VOLATILITY_BREAKOUT_REPORT.md").write_text("\n".join(table)+"\n")
    print("VOL_COMPLETE",json.dumps(dict(years=len(cases),
       comparisons=len(compared),shortlisted=selected)),flush=True)


if __name__=="__main__":
    main()
