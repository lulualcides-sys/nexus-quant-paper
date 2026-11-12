#!/usr/bin/env python3
"""XAUUSD 2025+ independent market-structure/session experiments (MT5 M1-M30).

Exploratory stop-first OHLC replay, NOT an EA, tick tester or profitable claim.
Levels are formed entirely BEFORE signals can be emitted:
 - UTC previous completed trading-day high/low;
 - Asia 00:00-06:00 UTC range, traded only 07:00+ UTC;
 - New York 08:00-09:00 local opening range (DST via timezone database),
   traded 09:00-13:00 New York only after the hour is complete.
Sensible sessions are a research hypothesis, not guaranteed edge.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from points10k import events as ema_events, WARM, POINT
from points10k_2025 import source as get_2025
from research_oos import download, bars_for, prepared
from alpha_xau_mtf_2025plus import (
    TF_MINUTES,COST_GRID,CUTOFF,horizon_bars,windows_by_quarter,
    replay_one,summarize)

MODELS=("EMA21_BASE","YDAY_SWEEP_RECLAIM","ASIA_SWEEP_RECLAIM",
        "NY_ORB_BREAK_RETEST","YDAY_BREAK_HOLD")
OUT=Path(__file__).resolve().parent/"xau_liquidity_session_2025plus_results"


def session_levels(frame, tf):
    """No future intraday levels: mapped only to times AFTER interval completion."""
    idx=frame.index
    if idx.tz is None or str(idx.tz)!="UTC":
        raise ValueError("historical candles must be timezone-aware UTC")
    if tf not in TF_MINUTES:
        raise ValueError("unsupported timeframe")
    hour=idx.hour.to_numpy()
    close=frame.close.to_numpy(dtype=float)
    high=frame.high.to_numpy(dtype=float)
    low=frame.low.to_numpy(dtype=float)
    day=idx.strftime("%Y-%m-%d")
    daily=pd.DataFrame(dict(day=day,high=high,low=low)).groupby("day",sort=True).agg(
        high=("high","max"),low=("low","min"))
    prev_hi=daily["high"].shift(1)
    prev_lo=daily["low"].shift(1)
    day_series=pd.Series(day)
    yesterday_high=day_series.map(prev_hi).to_numpy(dtype=float)
    yesterday_low=day_series.map(prev_lo).to_numpy(dtype=float)

    asia_mask=(hour>=0)&(hour<6)
    asia=pd.DataFrame(dict(day=day[asia_mask],high=high[asia_mask],
         low=low[asia_mask])).groupby("day",sort=True).agg(
         hi=("high","max"),lo=("low","min"),count=("high","size"))
    # Incomplete historical session is explicitly unusable; bars_for enforces
    # completed TF bars, but public data may omit separate timestamps.
    asia=asia[asia["count"]==360//tf]
    asia_hi=day_series.map(asia.hi).to_numpy(dtype=float)
    asia_lo=day_series.map(asia.lo).to_numpy(dtype=float)
    asia_hi[hour<6]=np.nan
    asia_lo[hour<6]=np.nan

    ny=idx.tz_convert("America/New_York")
    nyhour=ny.hour.to_numpy()
    nyday=ny.strftime("%Y-%m-%d")
    opening=nyhour==8
    orb=pd.DataFrame(dict(day=nyday[opening],high=high[opening],
         low=low[opening])).groupby("day",sort=True).agg(
         hi=("high","max"),lo=("low","min"),count=("high","size"))
    orb=orb[orb["count"]==60//tf]
    local_series=pd.Series(nyday)
    orb_hi=local_series.map(orb.hi).to_numpy(dtype=float)
    orb_lo=local_series.map(orb.lo).to_numpy(dtype=float)
    orb_hi[nyhour<9]=np.nan
    orb_lo[nyhour<9]=np.nan
    return dict(utcday=day,utc_hour=hour,nyday=nyday,ny_hour=nyhour,
        yesterday_high=yesterday_high,yesterday_low=yesterday_low,
        asia_high=asia_hi,asia_low=asia_lo,
        ny_orb_high=orb_hi,ny_orb_low=orb_lo,
        ny_opening_count=int(len(orb)),asia_session_count=int(len(asia)))


def build_signals(frame, tf, kind, contexts=None, baseline=None):
    """One signal per complete session per strategy; next-open fills only."""
    if kind not in MODELS:
        raise ValueError("unknown strategy")
    if kind=="EMA21_BASE":
        return list(baseline if baseline is not None
            else ema_events(frame,"EMA21_PULLBACK"))
    ctx=session_levels(frame,tf) if contexts is None else contexts
    o=frame.open.to_numpy(dtype=float)
    h=frame.high.to_numpy(dtype=float)
    l=frame.low.to_numpy(dtype=float)
    c=frame.close.to_numpy(dtype=float)
    atr=frame.atr.to_numpy(dtype=float)
    body=(c-o)/np.maximum(h-l,1e-8)
    n=len(frame)
    out=[]
    used=set()

    def add_signal(i,side,ref,daykey):
        """Use last CLOSED bar's wick and level, next OPEN, no future OHLC."""
        if daykey in used or i<WARM or i>=n-1:
            return False
        a=float(atr[i])
        if not np.isfinite([a,ref,o[i+1],h[i],l[i]]).all() or a<=0:
            return False
        stop=(min(l[i],ref)-.12*a if side>0 else max(h[i],ref)+.12*a)
        risk=float(side*(o[i+1]-stop))
        if not .15*a<=risk<=4.*a:
            return False
        out.append((int(i),int(side),float(stop),float(min(1.,abs(body[i])))))
        used.add(daykey)
        return True

    if kind=="NY_ORB_BREAK_RETEST":
        # Loop through each day chronologically. Break first, then retest in
        # a LATER candle. The 08:00–09:00 NY range is complete at 09:00 NY.
        last_day=None
        pending_side=0
        pending_idx=-1
        max_bars=max(2,60//tf)
        for i in range(WARM,n-1):
            day=ctx["nyday"][i]
            if day!=last_day:
                last_day=day
                pending_side=0
                pending_idx=-1
            hour=ctx["ny_hour"][i]
            if hour<9 or hour>=13:
                continue
            hi=ctx["ny_orb_high"][i]
            lo=ctx["ny_orb_low"][i]
            a=atr[i]
            if not np.isfinite([hi,lo,a]).all() or a<=0:
                continue
            if day in used:
                continue
            if pending_side and i>pending_idx:
                if i-pending_idx<=max_bars:
                    level=hi if pending_side>0 else lo
                    touched=(l[i]<=level+.12*a if pending_side>0
                             else h[i]>=level-.12*a)
                    reclaimed=(c[i]>level+.03*a and body[i]>.12
                        if pending_side>0 else c[i]<level-.03*a and body[i]<-.12)
                    if touched and reclaimed:
                        if add_signal(i,pending_side,level,day):
                            pending_side=0
                            continue
                else:
                    pending_side=0
            # Breakout is a CLOSED candle beyond ORB; never enter that bar.
            if not pending_side:
                if c[i]>hi+.10*a and body[i]>.2:
                    pending_side=1
                    pending_idx=i
                elif c[i]<lo-.10*a and body[i]<-.2:
                    pending_side=-1
                    pending_idx=i
        return out

    for i in range(WARM,n-1):
        a=atr[i]
        if not np.isfinite(a) or a<=0:
            continue
        utc_hour=ctx["utc_hour"][i]
        day=ctx["utcday"][i]
        side=0
        reference=np.nan
        if kind=="YDAY_SWEEP_RECLAIM":
            if not 6<=utc_hour<20:
                continue
            hi=ctx["yesterday_high"][i]
            lo=ctx["yesterday_low"][i]
            if not np.isfinite([hi,lo]).all():
                continue
            if l[i]<lo-.08*a and c[i]>lo+.02*a and body[i]>.12:
                side=1;reference=lo
            elif h[i]>hi+.08*a and c[i]<hi-.02*a and body[i]<-.12:
                side=-1;reference=hi
        elif kind=="ASIA_SWEEP_RECLAIM":
            if not 7<=utc_hour<19:
                continue
            hi=ctx["asia_high"][i]
            lo=ctx["asia_low"][i]
            if not np.isfinite([hi,lo]).all():
                continue
            if l[i]<lo-.08*a and c[i]>lo+.03*a and body[i]>.14:
                side=1;reference=lo
            elif h[i]>hi+.08*a and c[i]<hi-.03*a and body[i]<-.14:
                side=-1;reference=hi
        elif kind=="YDAY_BREAK_HOLD":
            if not 9<=utc_hour<20 or i==0:
                continue
            hi=ctx["yesterday_high"][i]
            lo=ctx["yesterday_low"][i]
            if not np.isfinite([hi,lo]).all():
                continue
            if c[i]>hi+.12*a and c[i-1]<=hi and body[i]>.28:
                side=1;reference=hi
            elif c[i]<lo-.12*a and c[i-1]>=lo and body[i]<-.28:
                side=-1;reference=lo
        if side:
            add_signal(i,side,reference,day)
    return out


def run_period(raw,year,tf):
    if raw.empty or raw.index.min()<CUTOFF:
        raise ValueError("data earlier than 2025 are prohibited")
    df=prepared(raw if tf==1 else bars_for(raw,tf))
    if df.empty or df.index.min()<CUTOFF:
        raise ValueError("invalid prepared scope")
    ctx=session_levels(df,tf)
    frozen=ema_events(df,"EMA21_PULLBACK")
    signal={name:build_signals(df,tf,name,contexts=ctx,baseline=frozen)
            for name in MODELS}
    if frozen!=signal["EMA21_BASE"]:
        raise AssertionError("EMA baseline mutated")
    alltr={name:[] for name in MODELS}
    quarters=[]
    for quarter,first,last in windows_by_quarter(df,horizon_bars(tf)):
        if first is None:
            quarters.append(dict(quarter=quarter,status="INSUFFICIENT_BARS"))
            continue
        models={}
        for name in MODELS:
            trades=replay_one(df,signal[name],first,last,tf,"RUNNER_96H")
            alltr[name].extend(trades)
            models[name]={str(cost):summarize(trades,cost) for cost in COST_GRID}
        quarters.append(dict(quarter=quarter,first=str(df.index[first]),
                             last=str(df.index[last-1]),models=models))
        print("LIQ_QUARTER",json.dumps(dict(year=year,tf=f"M{tf}",
             quarter=quarter,summary={name:models[name]["0.8"]
                                      for name in MODELS})),flush=True)
    result=dict(year=year,tf=f"M{tf}",source_candles=len(df),
      signal_counts={x:len(y) for x,y in signal.items()},
      complete_asia_sessions=ctx["asia_session_count"],
      complete_ny_opening_ranges=ctx["ny_opening_count"],
      quarters=quarters,
      summary={name:{str(cost):summarize(alltr[name],cost)
            for cost in COST_GRID} for name in MODELS})
    print("LIQ_YEAR",json.dumps(dict(year=year,tf=f"M{tf}",
          summary=result["summary"])),flush=True)
    return result


def screen(cases):
    """Fixed screen, reporting ALL failures; not honest OOS or live approval."""
    out=[]
    for tf in TF_MINUTES:
        a=next(v for v in cases if v["year"]=="2025" and v["tf"]==f"M{tf}")
        b=next(v for v in cases if v["year"]=="2026" and v["tf"]==f"M{tf}")
        for model in MODELS:
            x=a["summary"][model]["1.2"]
            y=b["summary"][model]["1.2"]
            pos25=sum(q.get("models",{}).get(model,{}).get("1.2",{}).get("net_pts",0)>0
                       for q in a["quarters"] if "models" in q)
            pos26=sum(q.get("models",{}).get(model,{}).get("1.2",{}).get("net_pts",0)>0
                       for q in b["quarters"] if "models" in q)
            passed=(x["N"]>=80 and y["N"]>=30 and x["net_pts"]>0 and
                    y["net_pts"]>0 and x["PF"] is not None and y["PF"] is not None
                    and x["PF"]>1.10 and y["PF"]>1.10
                    and pos25>=3 and pos26>=1)
            out.append(dict(tf=f"M{tf}",model=model,
                 trades2025=x["N"],trades2026_partial=y["N"],
                 net2025=x["net_pts"],net2026_partial=y["net_pts"],
                 pf2025=x["PF"],pf2026_partial=y["PF"],
                 positive_quarters2025=pos25,
                 positive_quarters2026_partial=pos26,
                 screened=bool(passed)))
    return out


def main():
    raw25,_=get_2025()
    raw26=download()
    if raw25.index.min()<CUTOFF or raw26.index.min()<CUTOFF:
        raise ValueError("source date scope broken")
    cases=[]
    for tf in TF_MINUTES:
        for yr,raw in (("2025",raw25),("2026",raw26)):
            cases.append(run_period(raw,yr,tf))
    ranks=screen(cases)
    result=dict(symbol="XAUUSD",from_utc="2025-01-01",models=MODELS,
      timeframes=[f"M{i}" for i in TF_MINUTES],
      timeframe_convention="UTC for Asia/day, local America/New_York for 08-09 NY opening range with DST",
      year2026_is_partial=True,
      costs_usd_per_ounce_roundtrip_assumed=COST_GRID,
      point_price_assumed=POINT,
      method="next open / stop-first conservative OHLC/96h trading-candle runner",
      sources=["parshant65-lang/Gold-XAUUSD-1m-2020-2025-Historical-Data@b2cfdc571ffac9eff9f2132ea6946da559d29af2 2025 only",
        "getdata-finance/xauusd-1m-ohlcv-metals-historical-data pinned SHA256 2026 subset"],
      caveats=["Historical periods already explored, not true untouched OOS.",
        "One setup per day/session by design; cannot hit high-frequency targets.",
        "No bid/ask broker ticks, variable spread, slippage, swap or cash PnL.",
        "Intratrade drawdown not calculated.",
        "NY range use America/New_York DST; Asia and previous day anchored UTC.",
        "Session-level OHLC estimates do not prove trading edge.",
        "Model selection over 55 TF/model comparisons causes multiple testing bias.",
        "None approved for real account."],
      cases=cases,comparison=ranks,
      shortlisted=[r for r in ranks if r["screened"]],
      approved_for_live=False)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"LIQUIDITY_SESSION_ALL.json").write_text(
        json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    table=["# XAUUSD 2025+ — Liquidity/session research, M1 to M30",
       "","Experimental OHLC replay only. No MT5 tick backtest or claims of profitability.",
       "Four independent signal ideas plus untouched EMA21 benchmark.",
       "2026 is partial, seen research years are not untouched OOS.",
       "Cost 0.8,1.2,1.6 USD/oz assumed. Stop first on same bar.","",
       "| TF | Signal | N2025 | Net25 cost1.2 | PF25 | N2026 | Net26 cost1.2 | PF26 | Positive quarters 2025/2026 |",
       "|---|---|---:|---:|---:|---:|---:|---:|---|"]
    for v in ranks:
        table.append("| "+" | ".join(str(v[k]) for k in
          ("tf","model","trades2025","net2025","pf2025",
           "trades2026_partial","net2026_partial","pf2026_partial"))+
          f' | {v["positive_quarters2025"]}/{v["positive_quarters2026_partial"]} |')
    table += ["","## Preliminary screen only, no live promotion",""]
    if result["shortlisted"]:
        table += [str(v) for v in result["shortlisted"]]
    else:
        table += ["No new structure/session model passed the preregistered screen."]
    table += ["","All variants, even losing models, remain recorded in JSON.",""]
    (OUT/"LIQUIDITY_SESSION_REPORT.md").write_text("\n".join(table))
    print("LIQ_COMPLETE",json.dumps(dict(cases=len(cases),comparison=len(ranks),
            shortlisted=result["shortlisted"])),flush=True)


if __name__=="__main__":
    main()
