#!/usr/bin/env python3
"""XAUUSD session structure: batch9 research only, 2025+ M1/M5/M15/M30.

Four frozen session-based entries compared against original ER20 M30 and
Shock M15. UTC time windows are FIXED, not broker/local London/NY DST hours.
Causal session ranges use running intra-day maxima/minima, never full future
daily high/low. Historical OHLC proxy, not a MT5 broker real-tick backtest.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from points10k import WARM
from research_oos import prepared,bars_for,download
from points10k_2025 import source as load25
from alpha_xau_mtf_2025plus import CUTOFF,COST_GRID,horizon_bars,windows_by_quarter,replay_one,summarize
from xau_exit_risk_batch6_2025plus import risk_stats
from xau_independent_batch8_2025plus import input_model as frozen_input

ALLOWED=(1,5,15,30)
MODELS=("ASIA_SWEEP_RECLAIM","ASIA_TREND_BREAK","UTC13_RANGE_FAKEOUT","VWAP_EMA_RECLAIM")
FROZEN=(("ER20_M30_FROZEN",30),("SHOCK_M15_FROZEN",15))
OUT=Path(__file__).resolve().parent/"xau_session_batch9_results"


def features(src):
    """All features at candle i use only [0:i] inclusive, UTC-day reset."""
    d=src.copy()
    idx=d.index
    day=idx.floor("D")
    hours=idx.hour
    hi=d.high.astype(float)
    lo=d.low.astype(float)
    d["asia_hi"]=hi.where(hours<7).groupby(day).cummax().groupby(day).ffill()
    d["asia_lo"]=lo.where(hours<7).groupby(day).cummin().groupby(day).ffill()
    d["utc13_hi"]=hi.where(hours==13).groupby(day).cummax().groupby(day).ffill()
    d["utc13_lo"]=lo.where(hours==13).groupby(day).cummin().groupby(day).ffill()
    d["prev_close"]=d.close.shift(1)
    d["prev_low"]=d.low.shift(1)
    d["prev_high"]=d.high.shift(1)
    d["prev_vwap"]=d.vwap.shift(1)
    d["same_day"]=day==day.shift(1) if hasattr(day,"shift") else day==np.roll(day,1)
    d["utc_hour"]=hours
    d["body"]=(d.close-d.open)/(d.high-d.low).replace(0,np.nan)
    return d


def events(df,model):
    """Signal i only after candle i closes. Entry i+1 open checks risk."""
    if model not in MODELS:
        raise ValueError("unknown session strategy")
    o=df.open.to_numpy(dtype=float)
    hi=df.high.to_numpy(dtype=float)
    lo=df.low.to_numpy(dtype=float)
    c=df.close.to_numpy(dtype=float)
    a=df.atr.to_numpy(dtype=float)
    f=df.fema.to_numpy(dtype=float)
    slow=df.sema.to_numpy(dtype=float)
    vw=df.vwap.to_numpy(dtype=float)
    pvw=df.prev_vwap.to_numpy(dtype=float)
    prev=df.prev_close.to_numpy(dtype=float)
    body=df.body.to_numpy(dtype=float)
    ah=df.asia_hi.to_numpy(dtype=float)
    al=df.asia_lo.to_numpy(dtype=float)
    uh=df.utc13_hi.to_numpy(dtype=float)
    ul=df.utc13_lo.to_numpy(dtype=float)
    h=df.utc_hour.to_numpy(dtype=int)
    side=np.zeros(len(df),dtype=np.int8)
    stop_pivot=np.full(len(df),np.nan,dtype=float)
    if model=="ASIA_SWEEP_RECLAIM":
        active=(h>=7)&(h<13)
        long=active&(lo<al-.08*a)&(c>al+.04*a)&(body>.16)
        short=active&(hi>ah+.08*a)&(c<ah-.04*a)&(body<-.16)
        side=np.where(long,1,np.where(short,-1,0))
        stop_pivot=np.where(long,lo,hi)
    elif model=="ASIA_TREND_BREAK":
        active=(h>=7)&(h<13)
        long=active&(prev<=ah)&(c>ah+.10*a)&(f>slow)&(body>.25)
        short=active&(prev>=al)&(c<al-.10*a)&(f<slow)&(body<-.25)
        side=np.where(long,1,np.where(short,-1,0))
        stop_pivot=np.where(long,df.prev_low.to_numpy(dtype=float),
                         df.prev_high.to_numpy(dtype=float))
    elif model=="UTC13_RANGE_FAKEOUT":
        active=(h>=14)&(h<19)
        long=active&(lo<ul-.10*a)&(c>ul+.06*a)&(body>.18)
        short=active&(hi>uh+.10*a)&(c<uh-.06*a)&(body<-.18)
        side=np.where(long,1,np.where(short,-1,0))
        stop_pivot=np.where(long,lo,hi)
    elif model=="VWAP_EMA_RECLAIM":
        active=(h>=7)&(h<20)&df.same_day.to_numpy(dtype=bool)
        rv=df.rvol.to_numpy(dtype=float)
        long=active&(f>slow)&(prev<pvw-.08*a)&(c>vw+.06*a)&(body>.2)&(rv>=.7)
        short=active&(f<slow)&(prev>pvw+.08*a)&(c<vw-.06*a)&(body<-.2)&(rv>=.7)
        side=np.where(long,1,np.where(short,-1,0))
        stop_pivot=np.where(long,df.prev_low.to_numpy(dtype=float),
                         df.prev_high.to_numpy(dtype=float))
    out=[]
    for i in np.flatnonzero(side):
        if i<WARM or i>=len(df)-1:continue
        s=int(side[i])
        if not np.isfinite([o[i+1],a[i],stop_pivot[i],body[i]]).all() or a[i]<=0:
            continue
        stop=(min(lo[i],stop_pivot[i])-.12*a[i] if s>0
              else max(hi[i],stop_pivot[i])+.12*a[i])
        risk=s*(o[i+1]-stop)
        if .12*a[i]<=risk<=4.*a[i]:
            out.append((int(i),s,float(stop),float(min(1.,abs(body[i])))))
    return out


def source_events(raw,tf,model):
    if tf not in ALLOWED or raw.empty or raw.index.min()<CUTOFF:
        raise ValueError("2025+ XAUUSD only in M1 M5 M15 M30")
    if model in ("ER20_M30_FROZEN","SHOCK_M15_FROZEN"):
        return frozen_input(raw,tf,model)
    if model not in MODELS:raise ValueError("invalid model")
    source=raw if tf==1 else bars_for(raw,tf)
    d=features(prepared(source))
    return d,events(d,model)


def run_case(raw,year,tf,model):
    df,ev=source_events(raw,tf,model)
    trade_list=[]
    qs=[]
    hold=horizon_bars(tf)
    for q,first,last in windows_by_quarter(df,hold):
        if first is None:
            qs.append(dict(quarter=q,status="insufficient"))
            continue
        deals=replay_one(df,ev,first,last,tf,"RUNNER_96H")
        trade_list.extend(deals)
        metrics={str(cost):{**summarize(deals,cost),
                  **risk_stats(deals,ev,df,cost)} for cost in COST_GRID}
        qs.append(dict(quarter=q,metrics=metrics))
        print("B9_Q",json.dumps(dict(model=model,tf=f"M{tf}",year=year,
                                   quarter=q,summary=metrics["1.2"])),flush=True)
    totals={str(cost):{**summarize(trade_list,cost),
                **risk_stats(trade_list,ev,df,cost)} for cost in COST_GRID}
    answer=dict(model=model,tf=f"M{tf}",year=year,raw_signals=len(ev),
                quarters=qs,summary=totals)
    print("B9_YEAR",json.dumps(dict(model=model,tf=f"M{tf}",year=year,summary=totals)),flush=True)
    return answer


def summarize_screen(cases):
    plans=[(m,t) for m in MODELS for t in ALLOWED]+list(FROZEN)
    out=[]
    for model,tf in plans:
        a=next(x for x in cases if x["model"]==model and x["tf"]==f"M{tf}" and x["year"]=="2025")
        b=next(x for x in cases if x["model"]==model and x["tf"]==f"M{tf}" and x["year"]=="2026")
        x=a["summary"]["1.2"];y=b["summary"]["1.2"]
        sx=a["summary"]["1.6"];sy=b["summary"]["1.6"]
        q25=[z["metrics"]["1.2"]["net_R"] for z in a["quarters"] if "metrics" in z]
        q26=[z["metrics"]["1.2"]["net_R"] for z in b["quarters"] if "metrics" in z]
        pos=[max(0.,v) for v in q25]
        largest=max(pos)/sum(pos) if sum(pos)>0 else None
        passed=bool(model in MODELS and x["N"]>=100 and y["N"]>=50
            and x["net_R"]>0 and y["net_R"]>0
            and sx["net_R"]>0 and sy["net_R"]>0
            and x["PF_R"] is not None and y["PF_R"] is not None
            and x["PF_R"]>1.20 and y["PF_R"]>1.20
            and sum(v>0 for v in q25)>=3 and sum(v>0 for v in q26)>=1
            and largest is not None and largest<=.65)
        out.append(dict(model=model,tf=f"M{tf}",reference=model not in MODELS,
          N25=x["N"],N26partial=y["N"],points25=x["net_pts"],
          points26partial=y["net_pts"],PF_points25=x["PF"],PF_points26partial=y["PF"],
          netR25=x["net_R"],netR26partial=y["net_R"],
          PF_R25=x["PF_R"],PF_R26partial=y["PF_R"],
          stressed_points25=sx["net_pts"],stressed_points26partial=sy["net_pts"],
          stressed_netR25=sx["net_R"],stressed_netR26partial=sy["net_R"],
          DD_points25=x["mdd_pts"],DD_points26partial=y["mdd_pts"],
          positive_quarters_2025=sum(v>0 for v in q25),
          positive_quarters_2026_partial=sum(v>0 for v in q26),
          largest_positive_quarter_share_2025=largest,
          net_points_positive_both=x["net_pts"]>0 and y["net_pts"]>0,
          net_R_positive_both=x["net_R"]>0 and y["net_R"]>0,
          predeclared_screen=passed))
    return out


def main():
    x,_=load25()
    y=download()
    if x.index.min()<CUTOFF or y.index.min()<CUTOFF:
        raise ValueError("source date invalid")
    pairs=[(m,t) for m in MODELS for t in ALLOWED]+list(FROZEN)
    cases=[]
    for model,tf in pairs:
        for year,raw in (("2025",x),("2026",y)):
            cases.append(run_case(raw,year,tf,model))
    compared=summarize_screen(cases)
    shortlist=[z for z in compared if z["predeclared_screen"]]
    payload=dict(symbol="XAUUSD",from_utc="2025-01-01",
      permitted_timeframes=["M1","M5","M15","M30"],
      new_models=MODELS,frozen_references=FROZEN,
      costs_assumed_usd_oz_roundtrip=COST_GRID,
      assumed_point_price_change_usd=0.01,
      data_sources="2025 and 2026 partial Q2/Q3 different historical feeds, previously examined",
      time_sessions="All session windows fixed UTC, not daylight-saving-aware named markets",
      execution="Original Runner96h; candle i closed signal, next bar open, stop-first ambiguous OHLC, adverse gaps, partials 1R and 1.5R, final third runner",
      important_limits=["OHLC not broker MT5 real ticks, fees dynamic spread etc.",
        "No untouched out of sample, previously inspected both years.",
        "R-based simulated results not real account returns or percent.",
        "No data snooping correction; four mechanics x four TF.",
        "Do not merge production or change ten saved candidates."],
      annual_cases=cases,comparison=compared,shortlist=shortlist,approved_for_live=False)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"ALL_RESULTS.json").write_text(json.dumps(payload,indent=2)+"\n")
    lines=["# XAUUSD Session Batch9 — ONLY 2025+, M1 M5 M15 M30",
           "","Historical OHLC estimates, NOT broker ticks or real returns.",
           "Net points assume 0.01 USD/oz price movement per point, cost USD 1.20/oz.",
           "","| Model | TF | N25 | Net pts25 | PF25 | Net R25 | N26 partial | Net pts26 | PF26 | Net R26 | Screen |",
           "|---|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    for z in compared:
        keys=("model","tf","N25","points25","PF_points25","netR25",
              "N26partial","points26partial","PF_points26partial",
              "netR26partial","predeclared_screen")
        lines.append("| "+" | ".join(str(z[k]) for k in keys)+" |")
    lines+=["","## Predeclared shortlist",str(shortlist),"",
            "Positive points are NOT sufficient for risk-normalized profitability. No live approval."]
    (OUT/"REPORT.md").write_text("\n".join(lines)+"\n")
    print("B9_DONE",json.dumps(dict(panels=len(cases),comparisons=len(compared),
                  shortlist=shortlist)),flush=True)


if __name__=="__main__":
    main()
