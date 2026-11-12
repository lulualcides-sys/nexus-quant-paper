#!/usr/bin/env python3
"""XAUUSD statistical-regime experiment, 2025+, ONLY MT5 M1 M5 M15 M30.

Research hypotheses: standardized-price reentry, variance-ratio reversion,
one-bar shock exhaustion and choppiness-regime expansion. All features use
closed past/current candles, and entries are next-bar open, with unchanged
OHLC stop-first runner. Not MT5 tick execution or a future profit claim.

Source concepts: intraday precious metals periodicity / volatility clustering
(Batten et al., PLOS ONE 2017, doi:10.1371/journal.pone.0174232);
2025/2026 gold regime-shift evidence, Mathematics 14(20):3708 (2026).
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from points10k import events as reference_ema, WARM, POINT
from research_oos import bars_for, prepared, download
from points10k_2025 import source as load_2025
from alpha_xau_mtf_2025plus import (
    CUTOFF, COST_GRID, horizon_bars, replay_one, summarize,
    windows_by_quarter)

ALLOWED_TF=(1,5,15,30)
MODELS=("EMA21_BASE", "ZSCORE80_REENTRY", "VR5_REVERSION",
        "SHOCK_EXHAUSTION", "CHOP14_EXPANSION")
OUT=Path(__file__).resolve().parent/"xau_statistical_regimes_batch5_2025plus_results"


def features(frame):
    """Strict causal trailing features computed from closed bars at i or earlier."""
    f=frame.copy()
    c=f.close.astype(float)
    hi=f.high.astype(float)
    lo=f.low.astype(float)
    op=f.open.astype(float)
    atr=f.atr.astype(float)
    mean=c.rolling(80,min_periods=80).mean()
    dev=c.rolling(80,min_periods=80).std(ddof=0)
    f["z80"]=(c-mean)/dev.replace(0,np.nan)

    d1=c.diff()
    d5=c.diff(5)
    den=5*(d1*d1).rolling(80,min_periods=80).mean()
    f["vr5"]=(d5*d5).rolling(80,min_periods=80).mean()/den.replace(0,np.nan)

    tr=pd.concat([hi-lo,(hi-c.shift(1)).abs(),
                  (lo-c.shift(1)).abs()],axis=1).max(axis=1)
    span=hi.rolling(14,min_periods=14).max()-lo.rolling(14,min_periods=14).min()
    tr_sum=tr.rolling(14,min_periods=14).sum()
    ratio=(tr_sum/span.replace(0,np.nan)).where(span>0)
    # Choppiness stays in [0,100] on normal bars; no future swing bars.
    f["chop14"]=100.*np.log10(ratio.clip(lower=1.0))/np.log10(14.)
    f["prior14_hi"]=hi.shift(1).rolling(14,min_periods=14).max()
    f["prior14_lo"]=lo.shift(1).rolling(14,min_periods=14).min()
    f["prior_hi"]=hi.shift(1)
    f["prior_lo"]=lo.shift(1)
    f["prior_mid"]=(hi.shift(1)+lo.shift(1))*.5
    f["prev_atr"]=atr.shift(1)
    f["prev_body"]=(c.shift(1)-op.shift(1))/(
        hi.shift(1)-lo.shift(1)).replace(0,np.nan)
    f["prev_range"]=(hi-lo).shift(1)
    return f


def signals(frame, model, frozen=None):
    """Signals determined by candle i close or before; entry i+1 open.

    Next open is used only to validate the stop when filling, not to choose
    the breakout, direction or model parameters.
    """
    if model not in MODELS:
        raise ValueError("unsupported model")
    if model=="EMA21_BASE":
        return list(frozen if frozen is not None else
                    reference_ema(frame,"EMA21_PULLBACK"))
    n=len(frame)
    o=frame.open.to_numpy(dtype=float)
    h=frame.high.to_numpy(dtype=float)
    l=frame.low.to_numpy(dtype=float)
    c=frame.close.to_numpy(dtype=float)
    a=frame.atr.to_numpy(dtype=float)
    body=(c-o)/np.maximum(h-l,1e-10)
    sign=np.zeros(n,dtype=np.int8)
    stopref=np.full(n,np.nan,dtype=float)
    z=frame.z80.to_numpy(dtype=float)
    zprev=np.roll(z,1)
    zprev[0]=np.nan

    if model=="ZSCORE80_REENTRY":
        long=(zprev<=-1.8)&(z>-1.8)&(z<-.4)&(body>.1)
        short=(zprev>=1.8)&(z<1.8)&(z>.4)&(body<-.1)
        sign=np.where(long,1,np.where(short,-1,0))
        stopref=np.where(long,frame.prior_lo.to_numpy(dtype=float),
                        frame.prior_hi.to_numpy(dtype=float))

    elif model=="VR5_REVERSION":
        vr=frame.vr5.to_numpy(dtype=float)
        # Variance ratio below unity suggests sub-diffusive/reverting path,
        # but is NOT evidence of a stable trading advantage.
        long=(vr<.84)&(zprev<=-1.45)&(z>-1.45)&(z<-.3)&(body>.08)
        short=(vr<.84)&(zprev>=1.45)&(z<1.45)&(z>.3)&(body<-.08)
        sign=np.where(long,1,np.where(short,-1,0))
        stopref=np.where(long,frame.prior_lo.to_numpy(dtype=float),
                        frame.prior_hi.to_numpy(dtype=float))

    elif model=="SHOCK_EXHAUSTION":
        pa=frame.prev_atr.to_numpy(dtype=float)
        pb=frame.prev_body.to_numpy(dtype=float)
        pr=frame.prev_range.to_numpy(dtype=float)
        pm=frame.prior_mid.to_numpy(dtype=float)
        prevhi=frame.prior_hi.to_numpy(dtype=float)
        prevlo=frame.prior_lo.to_numpy(dtype=float)
        shock=(pr>=1.8*pa)&(pa>0)&np.isfinite(pa)
        long=shock&(pb<-.55)&(c>pm)&(body>.22)&(c>o)
        short=shock&(pb>.55)&(c<pm)&(body<-.22)&(c<o)
        sign=np.where(long,1,np.where(short,-1,0))
        stopref=np.where(long,prevlo,prevhi)

    elif model=="CHOP14_EXPANSION":
        chop=frame.chop14.to_numpy(dtype=float)
        before=np.roll(chop,1)
        before[0]=np.nan
        top=frame.prior14_hi.to_numpy(dtype=float)
        bottom=frame.prior14_lo.to_numpy(dtype=float)
        valid=(before>=58)&(chop<58)
        long=valid&(c>top+.08*a)&(body>.25)
        short=valid&(c<bottom-.08*a)&(body<-.25)
        sign=np.where(long,1,np.where(short,-1,0))
        stopref=np.where(long,top,bottom)

    out=[]
    for i in np.flatnonzero(sign):
        if i<WARM or i>=n-1:
            continue
        direction=int(sign[i])
        atr=float(a[i])
        pivot=float(stopref[i])
        if not np.isfinite([o[i+1],atr,pivot,h[i],l[i]]).all() or atr<=0:
            continue
        stop=(min(l[i],pivot)-.12*atr if direction>0
              else max(h[i],pivot)+.12*atr)
        risk=float(direction*(o[i+1]-stop))
        if .12*atr<=risk<=4.*atr:
            out.append((int(i),direction,float(stop),
                        float(min(1.,abs(body[i])))))
    return out


def run_year(raw,year,tf):
    """Same historical source, same runner and quarter embargo as prior studies."""
    if tf not in ALLOWED_TF:
        raise ValueError(f"disallowed timeframe: M{tf}")
    if raw.empty or raw.index.min()<CUTOFF:
        raise ValueError("only >=2025 XAUUSD candles allowed")
    f=features(prepared(raw if tf==1 else bars_for(raw,tf)))
    if f.empty or f.index.min()<CUTOFF:
        raise ValueError("invalid prepared history cutoff")
    baseline=reference_ema(f,"EMA21_PULLBACK")
    event_map={m:signals(f,m,baseline) for m in MODELS}
    if event_map["EMA21_BASE"]!=list(baseline):
        raise AssertionError("original EMA21 baseline changed")
    trade_map={m:[] for m in MODELS}
    quarters=[]
    for quarter,first,last in windows_by_quarter(f,horizon_bars(tf)):
        if first is None:
            quarters.append(dict(quarter=quarter,status="INSUFFICIENT_BARS"))
            continue
        parts={}
        for model in MODELS:
            replay=replay_one(f,event_map[model],first,last,tf,"RUNNER_96H")
            trade_map[model].extend(replay)
            parts[model]={str(cost):summarize(replay,cost) for cost in COST_GRID}
        quarters.append(dict(quarter=quarter,first=str(f.index[first]),
            last=str(f.index[last-1]),summary=parts))
        print("REGIME_QUARTER",json.dumps(dict(tf=f"M{tf}",year=year,
            quarter=quarter,summary={m:parts[m]["0.8"] for m in MODELS})),
            flush=True)
    answer=dict(tf=f"M{tf}",year=year,bars=len(f),
        signal_counts={m:len(v) for m,v in event_map.items()},
        quarters=quarters,
        summary={m:{str(cost):summarize(trade_map[m],cost)
                    for cost in COST_GRID} for m in MODELS})
    print("REGIME_YEAR",json.dumps(dict(tf=f"M{tf}",year=year,
        summary=answer["summary"])),flush=True)
    return answer


def screen(cases):
    """Predeclared research screen, not future validation or a guarantee."""
    comparisons=[]
    for tf in ALLOWED_TF:
        a=next(x for x in cases if x["tf"]==f"M{tf}" and x["year"]=="2025")
        b=next(x for x in cases if x["tf"]==f"M{tf}" and x["year"]=="2026")
        for model in MODELS:
            x=a["summary"][model]["1.2"]
            y=b["summary"][model]["1.2"]
            quarters25=sum(q["summary"][model]["1.2"]["net_pts"]>0
                for q in a["quarters"] if "summary" in q)
            quarters26=sum(q["summary"][model]["1.2"]["net_pts"]>0
                for q in b["quarters"] if "summary" in q)
            passed=(x["N"]>=100 and y["N"]>=50
                and x["PF"] is not None and y["PF"] is not None
                and x["net_pts"]>0 and y["net_pts"]>0
                and x["PF"]>1.10 and y["PF"]>1.10
                and quarters25>=3 and quarters26>=1)
            comparisons.append(dict(tf=f"M{tf}",model=model,
                 N_2025=x["N"],N_2026_partial=y["N"],
                 net_2025_cost_1_2=x["net_pts"],net_2026_cost_1_2=y["net_pts"],
                 PF_2025_cost_1_2=x["PF"],PF_2026_cost_1_2=y["PF"],
                 positive_quarters_2025=quarters25,
                 positive_quarters_2026_partial=quarters26,
                 preliminary_screen=bool(passed)))
    return comparisons


def main():
    a,_=load_2025()
    b=download()
    if a.index.min()<CUTOFF or b.index.min()<CUTOFF:
        raise ValueError("pre-2025 prohibited")
    allcases=[]
    for tf in ALLOWED_TF:
        for year,raw in (("2025",a),("2026",b)):
            allcases.append(run_year(raw,year,tf))
    comparisons=screen(allcases)
    shortlisted=[x for x in comparisons if x["preliminary_screen"]]
    result=dict(symbol="XAUUSD",
       from_utc="2025-01-01T00:00:00Z",
       allowed_tf=["M1","M5","M15","M30"],
       models=MODELS,
       data_2026_partial_Q2_Q3=True,
       point_price_assumed=POINT,
       costs_usd_per_ounce_roundtrip_assumed=COST_GRID,
       execution="closed candle + next open, stop-first, unfavorable OHLC gap, 96h trading bars runner",
       warnings=["Research only, no MT5 broker tick backtest.",
                 "2025 and 2026 partial already studied; NOT untouched OOS.",
                 "No real broker Bid/Ask, swap, slippage, commissions, dynamic spread, fills, cash PnL or intratrade DD.",
                 "4 timeframes and 5 models imply 20 comparisons, increasing selection bias.",
                 "All seven saved candidates remain intact; no live trading approval."],
       annual_cases=allcases,comparisons=comparisons,
       shortlisted=shortlisted,approved_for_live=False)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"BATCH5_ALL.json").write_text(
        json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    lines=["# XAUUSD — statistical regimes batch5; ONLY M1/M5/M15/M30",
       "","2025 complete and 2026 partial, both previously researched. Research OHLC only.",
       "Signals: EMA21 frozen, Z-score 80 reentry, variance ratio 5 fade, shock reversal and CHOP14 expansion.",
       "Costs assumed 0.8/1.2/1.6 USD/oz; no actual broker ticks or returns.",
       "","| TF | Model | N2025 | Net2025 cost1.2 | PF2025 | N2026 partial | Net2026 cost1.2 | PF2026 | Positive quarters 2025/2026 |",
       "|---|---|---:|---:|---:|---:|---:|---:|"]
    for row in comparisons:
        lines.append("| "+" | ".join(str(row[k]) for k in
          ("tf","model","N_2025","net_2025_cost_1_2","PF_2025_cost_1_2",
           "N_2026_partial","net_2026_cost_1_2","PF_2026_cost_1_2"))+
           f' | {row["positive_quarters_2025"]}/{row["positive_quarters_2026_partial"]} |')
    lines+=["","## Exploratory screen","",str(shortlisted),
      "","No real-trading promotion. Original seven user-selected candidates preserved."]
    (OUT/"BATCH5_REPORT.md").write_text("\n".join(lines)+"\n")
    print("REGIME_COMPLETE",json.dumps(dict(cases=len(allcases),
        comparisons=len(comparisons),shortlisted=shortlisted)),flush=True)


if __name__=="__main__":
    main()
