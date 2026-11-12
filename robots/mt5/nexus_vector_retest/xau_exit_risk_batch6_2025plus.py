#!/usr/bin/env python3
"""XAUUSD fixed-entry exit audit: 2025+, only M1/M5/M15/M30.

Compare EXACT original signals/stops, with three already-available exits
and two new fixed exits. This is conservative OHLC research, NOT a broker
MT5 test or profitable robot. Historical 2025/2026 already data-mined.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from points10k import events as ema_events, POINT
from research_oos import prepared, bars_for, download
from points10k_2025 import source as load2025
from alpha_xau_mtf_2025plus import (
    CUTOFF, COST_GRID, horizon_bars, windows_by_quarter,
    replay_one, summarize)
from xau_indicator_lab_2025plus import indicators, build_signals
from xau_volatility_breakouts_2025plus import feature_frame, make_signals
from xau_statistical_regimes_batch5_2025plus import features, signals

ALLOWED_TF=(1,5,15,30)
CANDIDATES=(
    ("EMA21_RUNNER_M15",15,"EMA21_BASE"),
    ("EMA21_RSI_MACD_M30",30,"EMA21_RSI_MACD"),
    ("ER20_BREAK_M30",30,"EFFICIENCY_ER20_BREAK"),
    ("SHOCK_EXHAUSTION_M5",5,"SHOCK_EXHAUSTION"),
    ("SHOCK_EXHAUSTION_M15",15,"SHOCK_EXHAUSTION"))
EXIT_MODES=("RUNNER_96H","BE_AFTER_TP2","REVERSAL_BE",
            "TRAIL_ATR2_AFTER_TP2","TIME_EXIT_24H")
OUTPUT=Path(__file__).resolve().parent/"xau_exit_risk_batch6_2025plus_results"


def entry_inputs(raw,tf,model):
    if tf not in ALLOWED_TF:
        raise ValueError("M1/M5/M15/M30 only")
    if raw.empty or raw.index.min()<CUTOFF:
        raise ValueError("only 2025+ source allowed")
    df=prepared(raw if tf==1 else bars_for(raw,tf))
    if df.empty or df.index.min()<CUTOFF:
        raise ValueError("invalid historic scope")
    if model=="EMA21_BASE":
        origin=ema_events(df,"EMA21_PULLBACK")
        return df,list(origin)
    if model=="EMA21_RSI_MACD":
        df=indicators(df)
        origin=ema_events(df,"EMA21_PULLBACK")
        sel=build_signals(df,model,origin)
        if not all(s in origin for s in sel):
            raise AssertionError("EMA RSI MACD entry inconsistent with frozen EMA baseline")
        return df,sel
    if model=="EFFICIENCY_ER20_BREAK":
        df=feature_frame(df)
        return df,make_signals(df,model)
    if model=="SHOCK_EXHAUSTION":
        df=features(df)
        return df,signals(df,model)
    raise ValueError("unrecognized entry model")


def replay_new_exit(df,events,first,last,tf,mode):
    """Keep the baseline simulator's entry/TP1/TP2/SL logic byte-equivalent;
    modify only last-third exit after TP2 or hard exit time at 24h.

    TP1 and TP2 are hit only from current OHLC. Trailing stop is updated at
    *next candle open*, from prices and ATR of FULLY completed prior bars.
    """
    if mode not in ("TRAIL_ATR2_AFTER_TP2","TIME_EXIT_24H"):
        raise ValueError("not a new exit mode")
    if tf not in ALLOWED_TF or not (0<=first<last<=len(df)):
        raise ValueError("invalid scope")
    hold=horizon_bars(tf)
    early=1440//tf
    o=df.open.to_numpy(dtype=float)
    h=df.high.to_numpy(dtype=float)
    l=df.low.to_numpy(dtype=float)
    c=df.close.to_numpy(dtype=float)
    atr=df.atr.to_numpy(dtype=float)
    trades=[]
    last_close=first-1
    for i,side,source_stop,quality in events:
        if i<first:
            continue
        if i+hold+1>=last:
            break
        entrybar=i+1
        if entrybar<=last_close+1:
            continue
        entry=float(o[entrybar])
        risk=float(side*(entry-source_stop))
        if not np.isfinite(risk) or risk<=0:
            continue
        stop=float(source_stop)
        tp1=entry+side*risk
        tp2=entry+side*1.5*risk
        remain=1.
        fills=0
        gross=0.
        reason="TIME"
        exitbar=entrybar+hold
        tp2_on_bar=None
        for j in range(entrybar,entrybar+hold+1):
            # The 24h exit executes at the first OPEN after 24h of bars,
            # before observing ANY high/low/close in the exit candle.
            if mode=="TIME_EXIT_24H" and j>=entrybar+early:
                gross+=remain*side*(o[j]-entry)
                reason="TIME24_OPEN"
                exitbar=j
                break
            # Nothing observed from candle j may change the stop on j.
            # After TP2 was filled, protect the final third at earliest j+1.
            if mode=="TRAIL_ATR2_AFTER_TP2" and fills==2 and (
                tp2_on_bar is not None and j>tp2_on_bar):
                prev=j-1
                if (prev>=entrybar and np.isfinite(atr[prev]) and atr[prev]>0):
                    start=max(entrybar,j-3)
                    if side>0:
                        v=float(np.max(h[start:j])-2.0*atr[prev])
                        stop=max(stop,entry,v)
                    else:
                        v=float(np.min(l[start:j])+2.0*atr[prev])
                        stop=min(stop,entry,v)
            if l[j]<=stop if side>0 else h[j]>=stop:
                fill=min(o[j],stop) if side>0 else max(o[j],stop)
                gross+=remain*side*(fill-entry)
                reason="TRAIL_SL" if mode=="TRAIL_ATR2_AFTER_TP2" and fills==2 else "SL"
                exitbar=j
                break
            for k,level in ((0,tp1),(1,tp2)):
                if k<fills:
                    continue
                if k>fills:
                    break
                crossed=h[j]>=level if side>0 else l[j]<=level
                if not crossed:
                    break
                gross+=side*(level-entry)/3.
                remain-=1./3
                fills=k+1
                if k==1:
                    tp2_on_bar=j
            if j==entrybar+hold:
                gross+=remain*side*(c[j]-entry)
                reason="TIME96"
                exitbar=j
                break
        trades.append(dict(signal=int(i),entry=int(entrybar),exit=int(exitbar),
             side=int(side),gross_pts=float(gross/POINT),
             protected=bool(mode=="TRAIL_ATR2_AFTER_TP2" and fills==2),
             reason=reason))
        last_close=exitbar
    return trades


def run_exit(df,events,first,last,tf,mode):
    if mode in ("RUNNER_96H","BE_AFTER_TP2","REVERSAL_BE"):
        return replay_one(df,events,first,last,tf,mode)
    return replay_new_exit(df,events,first,last,tf,mode)


def risk_stats(trades,events,df,cost):
    """Constant 1R sizing proxy, compare different stop lengths fairly.

    Returns cumulative R after roundtrip hypothetical cost; not currency,
    CAGR, annual return or real margin-aware portfolio equity.
    """
    by_signal={int(e[0]):(int(e[1]),float(e[2])) for e in events}
    op=df.open.to_numpy(dtype=float)
    rr=[]
    for t in trades:
        side,source_stop=by_signal[t["signal"]]
        risk=side*(float(op[t["entry"]])-source_stop)
        if not np.isfinite(risk) or risk<=0:
            raise AssertionError("unusable entry risk for R statistic")
        rr.append((float(t["gross_pts"])*POINT-float(cost))/risk)
    arr=np.asarray(rr,dtype=float)
    if not len(arr):
        return dict(N=0,net_R=0.,avg_R=None,PF_R=None,MDD_R=None,
                    win_R_pct=None)
    gain=arr[arr>0].sum()
    loss=-arr[arr<0].sum()
    curve=np.r_[0.,np.cumsum(arr)]
    return dict(N=len(arr),net_R=round(float(arr.sum()),3),
       avg_R=round(float(arr.mean()),4),
       PF_R=round(float(gain/loss),3) if loss else None,
       MDD_R=round(float(np.max(np.maximum.accumulate(curve)-curve)),3),
       win_R_pct=round(float((arr>0).mean()*100),2))


def eval_case(raw,year,name,tf,model):
    if tf not in ALLOWED_TF:
        raise ValueError("only supported native timeframes")
    df,events=entry_inputs(raw,tf,model)
    hold=horizon_bars(tf)
    cases={mode:[] for mode in EXIT_MODES}
    quarters=[]
    for q,first,last in windows_by_quarter(df,hold):
        if first is None:
            quarters.append(dict(quarter=q,status="INSUFFICIENT_BARS"))
            continue
        line={}
        for mode in EXIT_MODES:
            trades=run_exit(df,events,first,last,tf,mode)
            cases[mode].extend(trades)
            line[mode]={str(cost):{**summarize(trades,cost),
                 **risk_stats(trades,events,df,cost)}
                 for cost in COST_GRID}
        quarters.append(dict(quarter=q,first=str(df.index[first]),
                             last=str(df.index[last-1]),modes=line))
        print("EXIT_QUARTER",json.dumps(dict(year=year,candidate=name,
              quarter=q,original=line["RUNNER_96H"]["1.2"],
              variants={k:line[k]["1.2"] for k in EXIT_MODES[1:]})),flush=True)
    summary={mode:{str(cost):{**summarize(cases[mode],cost),
        **risk_stats(cases[mode],events,df,cost)} for cost in COST_GRID}
        for mode in EXIT_MODES}
    answer=dict(year=year,candidate=name,tf=f"M{tf}",model=model,bars=len(df),
       raw_signals=len(events),quarterly=quarters,summary=summary)
    print("EXIT_YEAR",json.dumps(dict(year=year,candidate=name,tf=f"M{tf}",
         summary=summary)),flush=True)
    return answer


def screening(cases):
    """Conservative preliminary screen, defined prior to CI execution.

    A profile must improve cumulative 1R-normalized net outcome vs frozen
    original in BOTH periods and preserve at least 100/50 trades, positive
    at stress 1.6, PF >1.10 under cost1.2 and controlled closed-trade DD.
    Results can only be research leads, NOT an untouched OOS validation.
    """
    checks=[]
    for name,tf,model in CANDIDATES:
        a=next(x for x in cases if x["candidate"]==name and x["year"]=="2025")
        b=next(x for x in cases if x["candidate"]==name and x["year"]=="2026")
        for mode in EXIT_MODES:
            x=a["summary"][mode]["1.2"]
            y=b["summary"][mode]["1.2"]
            xs=a["summary"][mode]["1.6"]
            ys=b["summary"][mode]["1.6"]
            base25=a["summary"]["RUNNER_96H"]["1.2"]
            base26=b["summary"]["RUNNER_96H"]["1.2"]
            pos25=sum(q["modes"][mode]["1.2"]["net_R"]>0
                for q in a["quarterly"] if "modes" in q)
            pos26=sum(q["modes"][mode]["1.2"]["net_R"]>0
                for q in b["quarterly"] if "modes" in q)
            improve=(x["net_R"]>base25["net_R"] and
                     y["net_R"]>base26["net_R"])
            floor=(x["N"]>=100 and y["N"]>=50 and
                    x["net_R"]>0 and y["net_R"]>0 and
                    xs["net_R"]>0 and ys["net_R"]>0 and
                    x["PF_R"] is not None and y["PF_R"] is not None and
                    x["PF_R"]>1.10 and y["PF_R"]>1.10 and
                    pos25>=3 and pos26>=1)
            dd25=base25["MDD_R"];dd26=base26["MDD_R"]
            dd_ok=(x["MDD_R"] is not None and y["MDD_R"] is not None
                and dd25 is not None and dd26 is not None
                and x["MDD_R"]<=1.10*dd25 and y["MDD_R"]<=1.10*dd26)
            passed=bool(mode!="RUNNER_96H" and floor and improve and dd_ok)
            checks.append(dict(candidate=name,tf=f"M{tf}",model=model,
                 exit_mode=mode,trades_2025=x["N"],trades_2026_partial=y["N"],
                 net_R_2025_cost1_2=x["net_R"],
                 net_R_2026_partial_cost1_2=y["net_R"],
                 baseline_net_R_2025_cost1_2=base25["net_R"],
                 baseline_net_R_2026_partial_cost1_2=base26["net_R"],
                 pf_R_2025=x["PF_R"],pf_R_2026_partial=y["PF_R"],
                 DD_R_2025=x["MDD_R"],DD_R_2026_partial=y["MDD_R"],
                 positive_quarters_2025=pos25,positive_quarters_2026_partial=pos26,
                 improved_in_both=bool(improve),stress_positive_both=bool(
                     xs["net_R"]>0 and ys["net_R"]>0),
                 preliminary_screen=passed))
    return checks


def main():
    raw25,_=load2025()
    raw26=download()
    if raw25.index.min()<CUTOFF or raw26.index.min()<CUTOFF:
        raise ValueError("pre2025 disallowed")
    evaluated=[]
    for name,tf,model in CANDIDATES:
        for year,raw in (("2025",raw25),("2026",raw26)):
            evaluated.append(eval_case(raw,year,name,tf,model))
    comparisons=screening(evaluated)
    shortlist=[c for c in comparisons if c["preliminary_screen"]]
    answer=dict(symbol="XAUUSD",from_utc="2025-01-01",
        allowed_tf=["M1","M5","M15","M30"],
        tested_candidates=CANDIDATES,exit_modes=EXIT_MODES,
        costs_roundtrip_usd_per_oz=COST_GRID,
        point_assumed_usd=POINT,
        risk_normalization="each trade same nominal 1R of initial stop distance, excluding lot constraints, funding and intratrade equity",
        reproducibility="exact historical input sources as prior research, same quarter embargo, same entry signals",
        caveats=["2025/2026 historical periods repeatedly examined; NO independent OOS.",
           "2026 partial Q2/Q3 from different feed.",
           "No broker Bid/Ask, spread dynamics, fees, swap, slippage or lot-size execution.",
           "No simultaneous-portfolio combination, correlation-adjusted leverage or real equity drawdown.",
           "TRAIl stop uses only previously closed candles, BE reuses original engine.",
           "Even if preliminary screen passes, never approve live without broker ticks/forward demo."],
        annual_evaluations:evaluated,
        comparisons=comparisons,
        shortlisted=shortlist,
        approved_for_live=False)
    OUTPUT.mkdir(parents=True,exist_ok=True)
    (OUTPUT/"EXIT_RISK_ALL.json").write_text(json.dumps(answer,indent=2)+"\n")
    rows=["# XAUUSD — frozen entries, exit/stop comparisons (M1 M5 M15 M30 only)",
      "","Historical OHLC research; hypothetical costs $0.8/$1.2/$1.6 per oz, no live or MT5 tick results.",
      "Five preserved candidates, same signals and stops; three existing exit methods and two new.",
      "2026 partial only, prior research years already studied; no untouched out-of-sample.",
      "The 1R normalized proxy is NOT a portfolio simulation. Do not equate raw point profit with real returns.",
      "","| Candidate | Exit | N2025 | Net R2025 cost1.2 | PF R2025 | Max DD R2025 | N2026 partial | Net R2026 cost1.2 | PF R2026 | Max DD R2026 | Same-year improvement |",
      "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for z in comparisons:
        rows.append("| "+" | ".join(str(z[v]) for v in
             ("candidate","exit_mode","trades_2025","net_R_2025_cost1_2",
              "pf_R_2025","DD_R_2025","trades_2026_partial",
              "net_R_2026_partial_cost1_2","pf_R_2026_partial",
              "DD_R_2026_partial","improved_in_both"))+" |")
    rows+=["","## Predeclared passes","",str(shortlist),
      "","Never alter original nine selected research records or deploy an experimental exit."]
    (OUTPUT/"EXIT_RISK_REPORT.md").write_text("\n".join(rows)+"\n")
    print("EXIT_COMPLETE",json.dumps(dict(evaluations=len(evaluated),
         comparisons=len(comparisons),shortlisted=shortlist)),flush=True)


if __name__=="__main__":
    main()
