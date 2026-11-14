#!/usr/bin/env python3
"""Price-only Donchian XAUUSD XAU experiment, 2025+ (no profit guarantees).

Four pre-declared models, M1/M5/M15/M30, two distinct data periods.
Reuses pinned public 2025 1-minute and pinned partial 2026 1-minute data.
No volume/VWAP or broker-time dependencies.
Causal signals only at bar close; next bar open entry.
Stop 2 ATR14, TP 4 ATR14 (2R), one open position, no timeout.
Stop hit first if OHLC ambiguous; gap stop suffers adverse fills.
Costs: hypothetical $0.80/$1.20/$1.60 per oz per round trip.
Trades are continuous over a year (NOT reset at quarter boundaries).
Results in points (0.01 USD/oz per point), not account dollars.
"""
from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import pandas as pd
from research_oos import bars_for, download as load_pinned_2026

BASE=Path("thirdparty/gold/XAUUSD/1m/2025")
OUT=Path(__file__).resolve().parent/"xau_donchian_price_only_results"
MODELS=("DON20_LONG","DON20_BOTH","DON55_LONG","DON20_LONG_EMA200")
FRAMES=(1,5,15,30)
COSTS=(0.8,1.2,1.6)
POINT=0.01

def load_2025():
    files=sorted(BASE.glob("*/*.csv"))
    if len(files)<255:
        raise ValueError(f"pinned 2025 source incomplete: {len(files)} days")
    frames=[]
    for path in files:
        f=pd.read_csv(path,usecols=["datetime_utc","open","high","low","close","volume"])
        f["datetime"]=pd.to_datetime(f.pop("datetime_utc"),utc=True)
        frames.append(f)
    df=pd.concat(frames,ignore_index=True).sort_values("datetime").set_index("datetime")
    if df.index.has_duplicates:raise ValueError("duplicate historical timestamps")
    for col in ("open","high","low","close","volume"):
        df[col]=pd.to_numeric(df[col],errors="raise")
    if not ((df.high>=df[["open","low","close"]].max(axis=1))&
            (df.low<=df[["open","high","close"]].min(axis=1))).all():
        raise ValueError("OHLC invalid")
    return df

def features(raw,tf):
    if tf not in FRAMES:raise ValueError("frame outside M1/M5/M15/M30")
    df=raw.copy() if tf==1 else bars_for(raw,tf)
    c=df.close;h=df.high;l=df.low
    tr=pd.concat([h-l,(h-c.shift(1)).abs(),(l-c.shift(1)).abs()],axis=1).max(axis=1)
    df["atr"]=tr.ewm(alpha=1/14,adjust=False).mean()
    df["hi20"]=h.shift(1).rolling(20,min_periods=20).max()
    df["lo20"]=l.shift(1).rolling(20,min_periods=20).min()
    df["hi55"]=h.shift(1).rolling(55,min_periods=55).max()
    df["ema200"]=c.ewm(span=200,adjust=False).mean()
    return df

def directions(df):
    # signal realized at close of bar j and placed at OPEN of j+1,
    # so shift all columns by one in this decision series.
    prev=df.shift(1)
    close=prev.close.to_numpy(dtype=float)
    atr=prev.atr.to_numpy(dtype=float)
    prev20high=prev.hi20.to_numpy(dtype=float)
    prev20low=prev.lo20.to_numpy(dtype=float)
    prev55high=prev.hi55.to_numpy(dtype=float)
    ema=prev.ema200.to_numpy(dtype=float)
    up20=close>prev20high+0.05*atr
    down20=close<prev20low-0.05*atr
    up55=close>prev55high+0.05*atr
    return {
      "DON20_LONG": np.where(up20,1,0).astype(np.int8),
      "DON20_BOTH": np.where(up20,1,np.where(down20,-1,0)).astype(np.int8),
      "DON55_LONG":np.where(up55,1,0).astype(np.int8),
      "DON20_LONG_EMA200":np.where(up20&(close>ema),1,0).astype(np.int8)
    }

def simulate(df,signals,cost):
    """No timed closure except last available candle. One order at a time.

    Stops/TP evaluated each bar INCLUDING entry bar. Fill assumes first-bar
    open and pessimistic SL on both levels touched.
    """
    op=df.open.to_numpy(dtype=float)
    hi=df.high.to_numpy(dtype=float)
    lo=df.low.to_numpy(dtype=float)
    close=df.close.to_numpy(dtype=float)
    atr=df.atr.to_numpy(dtype=float)
    dates=df.index
    results=[]
    j=251
    size=len(df)
    while j<size-1:
        side=int(signals[j])
        if side==0 or not np.isfinite(atr[j-1]) or atr[j-1]<=0:
            j+=1;continue
        entry=float(op[j]);risk=2*float(atr[j-1])
        stop=entry-side*risk
        take=entry+side*2*risk
        k=j;exit_price=float(close[-1]);reason="end_of_data"
        while k<size:
            hitstop=(lo[k]<=stop if side>0 else hi[k]>=stop)
            hittp=(hi[k]>=take if side>0 else lo[k]<=take)
            if hitstop:
                exit_price=(min(float(op[k]),stop) if side>0 else max(float(op[k]),stop))
                reason="stop";break
            if hittp:
                exit_price=take;reason="tp";break
            k+=1
        if k>=size:k=size-1
        net_price=side*(exit_price-entry)-cost
        results.append(dict(entry_idx=j,exit_idx=k,exit_time=str(dates[k]),side=side,
             reason=reason,net_pts=net_price/POINT,net_R=net_price/risk))
        j=k+1
    return results

def summarize(rows):
    pts=np.array([x["net_pts"] for x in rows],dtype=float)
    rs=np.array([x["net_R"] for x in rows],dtype=float)
    gain=float(pts[pts>0].sum()) if len(rows) else 0
    loss=float(-pts[pts<0].sum()) if len(rows) else 0
    eq=np.r_[0.,np.cumsum(pts)]
    return dict(N=len(rows),win_count=int(np.sum(pts>0)),red_count=int(np.sum(pts<0)),
      net_pts=round(float(pts.sum()),1),net_R=round(float(rs.sum()),3),
      PF=(round(gain/loss,3) if loss>0 else None),
      win_rate=(round(float(100*np.mean(pts>0)),2) if len(rows) else 0),
      mdd_closed_pts=round(float(np.max(np.maximum.accumulate(eq)-eq)),1),
      gross_gain_pts=round(gain,2),gross_loss_pts=round(loss,2),
      exits={reason:sum(x["reason"]==reason for x in rows)
           for reason in ("stop","tp","end_of_data")})

def test_year(raw,name):
    out=[]
    for tf in FRAMES:
        f=features(raw,tf)
        signals=directions(f)
        for model in MODELS:
            records_by_cost={str(c):simulate(f,signals[model],c) for c in COSTS}
            metrics={str(c):summarize(records_by_cost[str(c)]) for c in COSTS}
            result=dict(model=model,tf=f"M{tf}",year=name,metrics=metrics)
            out.append(result)
            print("DON_YEAR",json.dumps(result),flush=True)
            # Quarterly net from FULL year paths, not independent quarter resets
            r=records_by_cost["1.2"]
            for quarter in pd.unique(f.index.to_period("Q")):
                selected=[x for x in r if pd.Period(pd.Timestamp(x["exit_time"]).tz_convert(None),freq="Q")==quarter]
                print("DON_QUARTER",json.dumps(dict(model=model,tf=f"M{tf}",year=name,
                      quarter=str(quarter),metrics=summarize(selected))),flush=True)
    return out

def main():
    out=[];periods=[]
    for name in ("2025","2026_partial"):
        raw=load_2025() if name=="2025" else load_pinned_2026()
        periods.append(dict(period=name,N=len(raw),start=str(raw.index.min()),end=str(raw.index.max())))
        print("DON_SOURCE",json.dumps(periods[-1]),flush=True)
        out.extend(test_year(raw,name))
    screen=[]
    for tf in FRAMES:
        for model in MODELS:
            a=next(x for x in out if x["tf"]==f"M{tf}" and x["model"]==model and x["year"]=="2025")
            b=next(x for x in out if x["tf"]==f"M{tf}" and x["model"]==model and x["year"]=="2026_partial")
            ac=a["metrics"]["1.2"];bc=b["metrics"]["1.2"];stress=b["metrics"]["1.6"]
            eligible=(ac["N"]>=35 and bc["N"]>=15 and ac["net_pts"]>0 and
                bc["net_pts"]>0 and stress["net_pts"]>0 and ac["PF"] is not None and
                bc["PF"] is not None and ac["PF"]>=1.2 and bc["PF"]>=1.1)
            screen.append(dict(tf=f"M{tf}",model=model,year2025=ac,year2026_partial=bc,
                               stress=stress,eligible=bool(eligible)))
    OUT.mkdir(parents=True,exist_ok=True)
    result=dict(periods=periods,all_models=out,screen=screen,costs=COSTS,
         timeframe=FRAMES,point_definition="1 pt = 0.01 USD/oz",
         note="OHLC-only; no broker ticks/BidAsk/commission/swaps; sample 2026 partial",
         approved_live=False)
    (OUT/"FULL_RESULT.json").write_text(json.dumps(result,indent=2)+"\n")
    lines=["# XAUUSD Donchian, resultados 2025+ com custos hipotéticos","",
      "| Modelo | TF | Ano | N | Pontos | PF | Acerto % | DD fechado |",
      "|---|---|---|---:|---:|---:|---:|---:|"]
    for row in out:
        m=row["metrics"]["1.2"]
        lines.append(f"| {row['model']} | {row['tf']} | {row['year']} | {m['N']} | {m['net_pts']} | {m['PF']} | {m['win_rate']} | {m['mdd_closed_pts']} |")
    lines+=["","**Candidatos que passaram no gate predefinido:**",
             json.dumps([x for x in screen if x["eligible"]],indent=2),
             "","Nenhuma garantia de lucro. Sem ticks do MetaTrader."]
    (OUT/"REPORT.md").write_text("\n".join(lines)+"\n")
    print("DON_DONE",json.dumps(dict(evaluations=len(out),
           gate=[dict(tf=x["tf"],model=x["model"]) for x in screen if x["eligible"]])),flush=True)

if __name__=="__main__":
    main()
