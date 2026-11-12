#!/usr/bin/env python3
"""XAUUSD 2025+ second indicator batch: Supertrend, CCI, Williams %R, Hull MA.

Research-only; baseline frozen and no live order API. All decisions on the
signal candle close or earlier, execution on subsequent OPEN. This is NOT an
MT5 broker-tick backtest. Selection across already-viewed years is exploratory.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from points10k import events as frozen_ema_events, WARM, POINT
from points10k_2025 import source as get_2025
from research_oos import download, bars_for, prepared
from alpha_xau_mtf_2025plus import (
    TF_MINUTES, COST_GRID, CUTOFF, horizon_bars, replay_one, summarize,
    windows_by_quarter)

MODELS=("EMA21_BASE", "SUPERTREND_10_3", "CCI20_RECLAIM",
        "WILLIAMS_R14_RECLAIM", "HULL21_PULLBACK")
OUTPUT=Path(__file__).resolve().parent/"xau_indicator_batch2_2025plus_results"


def weighted_moving_average(values, n):
    """Trailing WMA aligned to candle t; never a centered or forward series."""
    x=np.asarray(values,dtype=float)
    y=np.full(len(x),np.nan)
    if len(x)>=n:
        w=np.arange(1,n+1,dtype=float)
        values=np.convolve(x,w[::-1],mode="valid")/w.sum()
        y[n-1:]=values
    return y


def supertrend_direction(close, high, low, atr, factor=3.):
    """ATR-band trend state, using only prior finalized bands and current close."""
    n=len(close)
    direction=np.zeros(n,dtype=np.int8)
    band=np.full(n,np.nan)
    if n==0:
        return direction,band
    mid=(high+low)*0.5
    upper=mid+factor*atr
    lower=mid-factor*atr
    last_upper=float(upper[0])
    last_lower=float(lower[0])
    prev_side=1
    for i in range(n):
        if i:
            if upper[i]<last_upper or close[i-1]>last_upper:
                last_upper=upper[i]
            if lower[i]>last_lower or close[i-1]<last_lower:
                last_lower=lower[i]
            if prev_side==1 and close[i]<last_lower:
                prev_side=-1
            elif prev_side==-1 and close[i]>last_upper:
                prev_side=1
        direction[i]=prev_side
        band[i]=last_lower if prev_side==1 else last_upper
    return direction,band


def indicators(frame):
    """All indicators causal; parameters deliberately frozen pre-evaluation."""
    d=frame.copy()
    close=d.close.to_numpy(dtype=float)
    high=d.high.to_numpy(dtype=float)
    low=d.low.to_numpy(dtype=float)
    atr=d.atr.to_numpy(dtype=float)
    tp=(high+low+close)/3.
    # CCI with trailing 20-bar mean absolute deviation (not std).
    s=pd.Series(tp,index=d.index)
    ma=s.rolling(20,min_periods=20).mean()
    mad=s.rolling(20,min_periods=20).apply(
        lambda q:float(np.mean(np.abs(q-q.mean()))),raw=True)
    d["cci20"]=(s-ma)/(0.015*mad.replace(0,np.nan))
    lower=d.low.rolling(14,min_periods=14).min()
    upper=d.high.rolling(14,min_periods=14).max()
    d["willr14"]=-100.*(upper-d.close)/(upper-lower).replace(0,np.nan)
    fast=weighted_moving_average(close,10)
    slow=weighted_moving_average(close,21)
    hull=weighted_moving_average(2*fast-slow,5)
    d["hma21"]=hull
    # Actual Supertrend ATR(10), separate from the frozen runner's ATR(14).
    prev_close=np.r_[close[0],close[:-1]]
    true_range=np.maximum(high-low,np.maximum(
        np.abs(high-prev_close),np.abs(low-prev_close)))
    atr10=pd.Series(true_range,index=d.index).ewm(
        alpha=1/10,adjust=False).mean().to_numpy()
    d["atr10_supertrend"]=atr10
    trend,stband=supertrend_direction(close,high,low,atr10,factor=3.)
    d["supertrend_side"]=trend
    d["supertrend_band"]=stband
    return d


def create_signals(frame,model,baseline=None):
    """Build original or new independent signals at closed candle i."""
    if model not in MODELS:
        raise ValueError(f"unsupported strategy: {model}")
    if model=="EMA21_BASE":
        return list(baseline if baseline is not None
                    else frozen_ema_events(frame,"EMA21_PULLBACK"))
    n=len(frame)
    close=frame.close.to_numpy(dtype=float)
    op=frame.open.to_numpy(dtype=float)
    high=frame.high.to_numpy(dtype=float)
    low=frame.low.to_numpy(dtype=float)
    atr=frame.atr.to_numpy(dtype=float)
    fast=frame.fema.to_numpy(dtype=float)
    slow=frame.sema.to_numpy(dtype=float)
    body=(close-op)/np.maximum(high-low,1e-10)
    side=np.zeros(n,dtype=np.int8)
    levels=np.full(n,np.nan,dtype=float)
    if model=="SUPERTREND_10_3":
        trend=frame.supertrend_side.to_numpy(dtype=np.int8)
        prev=np.roll(trend,1)
        prev[0]=0
        side=np.where((prev<0)&(trend>0)&(body>.12),1,
                      np.where((prev>0)&(trend<0)&(body<-.12),-1,0))
        levels=frame.supertrend_band.to_numpy(dtype=float)
    elif model=="CCI20_RECLAIM":
        cci=frame.cci20.to_numpy(dtype=float)
        old=np.roll(cci,1)
        old[0]=np.nan
        side=np.where((old<=-100)&(cci>-100)&(fast>slow)&(body>.08),1,
                      np.where((old>=100)&(cci<100)&(fast<slow)&(body<-.08),-1,0))
        levels=fast.copy()
    elif model=="WILLIAMS_R14_RECLAIM":
        wr=frame.willr14.to_numpy(dtype=float)
        prev=np.roll(wr,1)
        prev[0]=np.nan
        side=np.where((prev<=-80)&(wr>-80)&(fast>slow)&(body>.10),1,
                      np.where((prev>=-20)&(wr<-20)&(fast<slow)&(body<-.10),-1,0))
        levels=fast.copy()
    elif model=="HULL21_PULLBACK":
        hull=frame.hma21.to_numpy(dtype=float)
        old=np.roll(hull,1)
        old[0]=np.nan
        # Recent up/down slope and intrabar touch/reclaim, with EMA55 trend.
        side=np.where((hull>old)&(close>hull)&(low<hull)
                      &(close>slow)&(body>.15),1,
                      np.where((hull<old)&(close<hull)&(high>hull)
                      &(close<slow)&(body<-.15),-1,0))
        levels=hull.copy()
    signals=[]
    for i in np.flatnonzero(side):
        if i<WARM or i>=n-1:
            continue
        direction=int(side[i])
        level=float(levels[i])
        a=float(atr[i])
        if not np.isfinite([a,level,op[i+1],high[i],low[i]]).all() or a<=0:
            continue
        stop=(min(low[i],level)-.12*a if direction>0
              else max(high[i],level)+.12*a)
        risk=direction*(op[i+1]-stop)
        if .12*a<=risk<=3.0*a:
            signals.append((int(i),direction,float(stop),
                            float(min(1.,abs(body[i])))))
    return signals


def replay_year(raw,year,tf):
    if raw.empty or raw.index.min()<CUTOFF:
        raise ValueError("pre-2025 history is not allowed")
    prepared_frame=prepared(raw if tf==1 else bars_for(raw,tf))
    frame=indicators(prepared_frame)
    if frame.empty or frame.index.min()<CUTOFF:
        raise ValueError("date scope invalid")
    frozen=frozen_ema_events(frame,"EMA21_PULLBACK")
    signals={name:create_signals(frame,name,baseline=frozen)
             for name in MODELS}
    if signals["EMA21_BASE"]!=list(frozen):
        raise AssertionError("baseline differs from frozen strategy")
    hold=horizon_bars(tf)
    quarters=[]
    all_deals={name:[] for name in MODELS}
    for quarter,first,last in windows_by_quarter(frame,hold):
        if first is None:
            quarters.append(dict(quarter=quarter,status="INSUFFICIENT_BARS"))
            continue
        row=dict(quarter=quarter,first=str(frame.index[first]),
                 last=str(frame.index[last-1]),models={})
        for model in MODELS:
            trades=replay_one(frame,signals[model],first,last,tf,"RUNNER_96H")
            all_deals[model].extend(trades)
            row["models"][model]={str(cost):summarize(trades,cost)
                                  for cost in COST_GRID}
        quarters.append(row)
        print("BATCH2_QUARTER",json.dumps(dict(year=year,tf=f"M{tf}",
              quarter=quarter,
              results={m:row["models"][m]["0.8"]["net_pts"] for m in MODELS})),
              flush=True)
    results=dict(year=year,tf=f"M{tf}",
        source_candles=len(frame),signals={m:len(v) for m,v in signals.items()},
        quarters=quarters,
        summary={m:{str(c):summarize(all_deals[m],c) for c in COST_GRID}
                 for m in MODELS})
    print("BATCH2_YEAR",json.dumps(dict(year=year,tf=f"M{tf}",
        summary=results["summary"])),flush=True)
    return results


def screen(cases):
    """Descriptive screen only; historical exploration is NOT a true holdout."""
    shortlist=[]
    compared=[]
    for tf in TF_MINUTES:
        a=next(x for x in cases if x["tf"]==f"M{tf}" and x["year"]=="2025")
        b=next(x for x in cases if x["tf"]==f"M{tf}" and x["year"]=="2026")
        for model in MODELS:
            m=a["summary"][model]["1.2"]
            n=b["summary"][model]["1.2"]
            accept=(m["N"]>=100 and n["N"]>=50
               and m["PF"] is not None and n["PF"] is not None
               and m["PF"]>1.10 and n["PF"]>1.10
               and m["net_pts"]>0 and n["net_pts"]>0)
            row=dict(tf=f"M{tf}",model=model,
                n25=m["N"],n26=n["N"],net25=m["net_pts"],net26=n["net_pts"],
                pf25=m["PF"],pf26=n["PF"],screen_pass=bool(accept))
            compared.append(row)
            if accept:shortlist.append(row)
    return compared,shortlist


def main():
    raw25,_=get_2025()
    raw26=download()
    if raw25.index.min()<CUTOFF or raw26.index.min()<CUTOFF:
        raise ValueError("pre-2025 date")
    cases=[]
    for tf in TF_MINUTES:
        for year,raw in (("2025",raw25),("2026",raw26)):
            cases.append(replay_year(raw,year,tf))
    compared,short=screen(cases)
    result=dict(symbol="XAUUSD",from_utc=str(CUTOFF),
      timeframes=["M"+str(x) for x in TF_MINUTES],models=MODELS,
      backtest_model="OHLC stop-first on next open, same 96-hour runner",
      costs_roundtrip_usd_per_ounce_assumed=COST_GRID,
      point_value_price_assumed=POINT,
      code_test_status="RESEARCH_ONLY",
      warnings=["2025 and 2026 were already explored; results not untouched OOS.",
                "2026 is partial, sources differ across years.",
                "No broker Bid/Ask, swap, variable spread, tick slippage or intratrade DD.",
                "Screening 55 tf-model combinations creates multiple-testing bias.",
                "Only XAUUSD; new candidates are NOT live/MT5 validated."],
      cases=cases,comparison=compared,shortlisted=short,
      approved_for_live=False)
    OUTPUT.mkdir(parents=True,exist_ok=True)
    (OUTPUT/"BATCH2_RESULTS.json").write_text(
        json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    lines=["# XAUUSD — segunda leva de indicadores M1–M30 (2025+)",
      "","**Pesquisa OHLC; não é MT5 Strategy Tester nem trading real.**",
      "Modelos: "+", ".join(MODELS)+".",
      "RSI/MACD M30 salvo antes NÃO foi modificado nem substituído.",
      "Sinais em candle fechado; execução na próxima abertura; stops conservadores.",
      "Mesma saída e custo da referência EMA21 (0.8/1.2/1.6 USD/oz).",
      "2025 completo, 2026 parcial nas fontes disponíveis; ambos já vistos.",
      "","| TF | Modelo | N2025 | Net2025 custo1.2 | PF25 | N2026 parcial | Net2026 custo1.2 | PF26 |",
      "|---|---|---:|---:|---:|---:|---:|---:|"]
    for row in compared:
        keys=("tf","model","n25","net25","pf25","n26","net26","pf26")
        lines.append("| "+" | ".join(str(row[k]) for k in keys)+" |")
    lines += ["","## Triagem conservadora experimental","",
      ", ".join(f'{v["tf"]} {v["model"]}' for v in short) if short else
      "Nenhum candidato atingiu os requisitos de frequência, PF e custo.",
      "","**Sem aprovação para conta real.** Necessário teste futuro com broker.",
      ""]
    (OUTPUT/"BATCH2_REPORT.md").write_text("\n".join(lines))
    print("BATCH2_COMPLETE",json.dumps(dict(cases=len(cases),
        comparisons=len(compared),shortlisted=short)),flush=True)


if __name__=="__main__":
    main()
