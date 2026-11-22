#!/usr/bin/env python3
"""NY Gold Trend Breakout vs Pullback. 2025 calibration, 2026 partial check.

Objective, closed-candle signals only; next candle OPEN execution, SL-first OHLC,
costs in USD/oz not account currency. No profit guarantee or tick validation.
Parameters are fixed before looking at results; no data from before 2025 used.
"""
from __future__ import annotations
import json,math
from pathlib import Path
import numpy as np
import pandas as pd
from research_oos import prepared,bars_for,download as source_2026

ALLOWED=(1,5,15,30)
MODELS=("BREAK_BOTH","BREAK_LONG","PULL_BOTH","PULL_LONG")
POINT=0.01
COSTS=(0.8,1.2,1.6)
OUT=Path(__file__).resolve().parent/"xau_ny_momentum_results"
ROOT=Path("thirdparty/gold")
OHLC=("open","high","low","close","volume")


def load_gold_year(year):
    paths=sorted(ROOT.glob(f"XAUUSD/1m/{year}/*/*.csv"))
    if len(paths)<255:raise ValueError(f"{year} pinned source incomplete: {len(paths)} csv")
    frames=[]
    for path in paths:
        x=pd.read_csv(path,usecols=["datetime_utc","open","high","low","close","volume"])
        x["datetime"]=pd.to_datetime(x.pop("datetime_utc"),utc=True)
        frames.append(x)
    df=pd.concat(frames,ignore_index=True).sort_values("datetime").set_index("datetime")
    for c in OHLC:df[c]=pd.to_numeric(df[c],errors="raise")
    if df.index.has_duplicates or not (
      (df.high>=df[["open","close","low"]].max(axis=1)) &
      (df.low<=df[["open","close","high"]].min(axis=1)) &
      (df.volume>=0)
    ).all():raise ValueError("invalid source OHLCV")
    return df


def features(raw,tf):
    if tf not in ALLOWED:raise ValueError(f"Unauthorized TF {tf}")
    f=(raw.copy() if tf==1 else bars_for(raw,tf))
    c=f.close;h=f.high;l=f.low;v=f.volume
    tr=pd.concat([h-l,(h-c.shift(1)).abs(),(l-c.shift(1)).abs()],axis=1).max(axis=1)
    f["atr"]=tr.ewm(alpha=1/14,adjust=False).mean()
    for n in (21,55,200):
        f["ema"+str(n)]=c.ewm(span=n,adjust=False).mean()
    f["prior_hi"]=h.shift(1).rolling(20,min_periods=20).max()
    f["prior_lo"]=l.shift(1).rolling(20,min_periods=20).min()
    f["rvol"]=v/v.shift(1).rolling(20,min_periods=20).mean().replace(0,np.nan)
    days=f.index.floor("D")
    weighted=(h+l+c)/3*v
    f["vwap"]=weighted.groupby(days).cumsum()/v.groupby(days).cumsum().replace(0,np.nan)
    f["body"]=(c-f.open)/(h-l).replace(0,np.nan)
    return f

def signal_pairs(f):
    # Output at index i: entry at bar i OPEN, based exclusively on bar i-1
    prev=f.shift(1)
    c=prev.close.to_numpy(dtype=float);o=prev.open.to_numpy(dtype=float)
    h=prev.high.to_numpy(dtype=float);l=prev.low.to_numpy(dtype=float)
    atr=prev.atr.to_numpy(dtype=float);vwap=prev.vwap.to_numpy(dtype=float)
    e21=prev.ema21.to_numpy(dtype=float);e55=prev.ema55.to_numpy(dtype=float)
    e200=prev.ema200.to_numpy(dtype=float);rvol=prev.rvol.to_numpy(dtype=float)
    body=prev.body.to_numpy(dtype=float)
    # A signal at i is from bar i-1, so use the LAST CLOSED bar hour.
    tf_minutes=int((f.index[1]-f.index[0]).total_seconds()/60)
    hour=(f.index-pd.Timedelta(minutes=tf_minutes)).hour.to_numpy()
    active=(hour>=12)&(hour<=17)
    up=(e21>e55)&(e55>e200);down=(e21<e55)&(e55<e200)
    hi=prev.prior_hi.to_numpy(dtype=float);lo=prev.prior_lo.to_numpy(dtype=float)
    buy_break=active&up&(c>vwap)&(body>.30)&(rvol>=.90)&(c>hi+.12*atr)
    sell_break=active&down&(c<vwap)&(body<-.30)&(rvol>=.90)&(c<lo-.12*atr)
    buy_pull=active&up&(c>vwap)&(body>.20)&(l<=e21+.18*atr)&(c>e21+.10*atr)&(c>np.r_[np.nan,c[:-1]])
    sell_pull=active&down&(c<vwap)&(body<-.20)&(h>=e21-.18*atr)&(c<e21-.10*atr)&(c<np.r_[np.nan,c[:-1]])
    def code(b,s):
        return np.where(b,1,np.where(s,-1,0)).astype(np.int8)
    return {
       "BREAK_BOTH":code(buy_break,sell_break),
       "BREAK_LONG":code(buy_break,np.zeros_like(sell_break,dtype=bool)),
       "PULL_BOTH":code(buy_pull,sell_pull),
       "PULL_LONG":code(buy_pull,np.zeros_like(sell_pull,dtype=bool))
    }

def sim_quarter(f,signal,lo,hi,cost,protective_stop=True):
    """1.5 ATR risk, 2R target, 24-bar timeout, stop-first; no overlap."""
    op=f.open.to_numpy(dtype=float);cl=f.close.to_numpy(dtype=float)
    high=f.high.to_numpy(dtype=float);low=f.low.to_numpy(dtype=float)
    atr=f.atr.to_numpy(dtype=float)
    results=[]
    i=max(lo,250)
    while i<hi-1:
        side=int(signal[i])
        risk=1.5*float(atr[i-1]); entry=float(op[i])
        if side==0 or not np.isfinite(risk) or risk<=0:
            i+=1;continue
        stop=entry-side*risk;tp=entry+side*2.0*risk
        exit_i=min(hi-1,i+24);fill=float(cl[exit_i]);reason="timeout"
        for j in range(i,exit_i+1):
            if low[j]<=stop if side>0 else high[j]>=stop:
                fill=min(op[j],stop) if side>0 else max(op[j],stop)
                exit_i=j;reason="stop";break
            if high[j]>=tp if side>0 else low[j]<=tp:
                fill=tp;exit_i=j;reason="target";break
        net_price=side*(fill-entry)-cost
        results.append(dict(pts=net_price/POINT,R=net_price/risk,entry_index=i,
                            exit_index=exit_i,reason=reason))
        i=exit_i+1
    points=np.array([x["pts"] for x in results],dtype=float)
    rmult=np.array([x["R"] for x in results],dtype=float)
    wins=float(points[points>0].sum()) if len(points) else 0.
    losses=float(-points[points<0].sum()) if len(points) else 0.
    winR=float(rmult[rmult>0].sum()) if len(rmult) else 0.
    lossR=float(-rmult[rmult<0].sum()) if len(rmult) else 0.
    eq=np.r_[0.,np.cumsum(points)];eqR=np.r_[0.,np.cumsum(rmult)]
    dd=lambda v:float(np.max(np.maximum.accumulate(v)-v))
    return {"N":len(results),"signals_raw":int(np.count_nonzero(signal[lo:hi])),
      "green":int(np.sum(points>0)),"red":int(np.sum(points<0)),
      "gross_positive_pts":round(wins,3),"gross_negative_pts":round(losses,3),
      "gross_positive_R":round(winR,4),"gross_negative_R":round(lossR,4),
      "net_pts":round(float(points.sum()),1),"net_R":round(float(rmult.sum()),3),
      "PF":round(wins/losses,3) if losses else None,
      "PF_R":round(winR/lossR,3) if lossR else None,
      "win_pct":round(float(100*np.mean(points>0)),2) if len(points) else 0.,
      "closed_trade_MDD_pts":round(dd(eq),1),"closed_trade_MDD_R":round(dd(eqR),3),
      "reasons":{name:sum(x["reason"]==name for x in results)
                      for name in ("stop","target","timeout","quarter_boundary")}
    }

def year_cases(raw,year):
    cases=[]
    # Avoid repeated 1m resampling: each TF calculated once each year.
    for tf in ALLOWED:
        f=features(raw,tf)
        signs=signal_pairs(f)
        quarters=f.index.to_period("Q").astype(str)
        distinct=pd.unique(quarters)
        for q in distinct:
            idx=np.flatnonzero(quarters==q)
            lo=max(int(idx[0]),240)
            hi=int(idx[-1])+1
            if hi-lo<300:continue
            for model in MODELS:
                metrics={str(cost):sim_quarter(f,signs[model],lo,hi,cost)
                         for cost in COSTS}
                case=dict(year=year,quarter=q,model=model,timeframe=f"M{tf}",
                      candles=int(hi-lo),metrics=metrics)
                cases.append(case)
                print("NQ_AB_QUARTER",json.dumps(case),flush=True)
    return cases


def aggregate(cases):
    allcases=[]
    for year in sorted({x["year"] for x in cases}):
        for tf in ALLOWED:
            for model in MODELS:
                qt=[x for x in cases if x["year"]==year and
                        x["timeframe"]==f"M{tf}" and x["model"]==model]
                if not qt:continue
                metrics={}
                for cost in COSTS:
                    curr=[x["metrics"][str(cost)] for x in qt]
                    count=sum(x["N"] for x in curr)
                    pts=round(sum(x["net_pts"] for x in curr),1)
                    rn=round(sum(x["net_R"] for x in curr),4)
                    positives=sum(x["net_pts"]>0 for x in curr)
                    gross_gain=sum(x["gross_positive_pts"] for x in curr)
                    gross_loss=sum(x["gross_negative_pts"] for x in curr)
                    gross_gain_R=sum(x["gross_positive_R"] for x in curr)
                    gross_loss_R=sum(x["gross_negative_R"] for x in curr)
                    metrics[str(cost)]={"N":count,"net_pts":pts,"net_R":rn,
                     "PF":round(gross_gain/gross_loss,3) if gross_loss>0 else None,
                     "PF_R":round(gross_gain_R/gross_loss_R,3) if gross_loss_R>0 else None,
                     "wins":sum(x["green"] for x in curr),
                     "losses":sum(x["red"] for x in curr),
                     "win_pct":round(100.*sum(x["green"] for x in curr)/count,2) if count else 0.,
                     "positive_quarters":positives,"tested_quarters":len(curr),
                     "gross_positive_pts":round(gross_gain,2),
                     "gross_negative_pts":round(gross_loss,2),
                     "max_quarter_closed_MDD_pts":max(x["closed_trade_MDD_pts"] for x in curr)}
                entry=dict(model=model,timeframe=f"M{tf}",year=year,metrics=metrics)
                allcases.append(entry)
                print("NQ_AB_YEAR",json.dumps(entry),flush=True)
    return allcases


def screen(cases):
    candidates=[]
    for tf in ALLOWED:
        for model in MODELS:
            a=next((x for x in cases if x["year"]=="2025" and x["timeframe"]==f"M{tf}" and x["model"]==model),None)
            b=next((x for x in cases if x["year"]=="2026_partial" and x["timeframe"]==f"M{tf}" and x["model"]==model),None)
            if not a or not b:continue
            x=a["metrics"]["1.2"];y=b["metrics"]["1.2"];stress=b["metrics"]["1.6"]
            passed=bool(x["N"]>=40 and y["N"]>=20 and
               x["PF"] is not None and x["PF"]>1.10 and
               y["PF"] is not None and y["PF"]>1.10 and
               x["net_pts"]>0 and y["net_pts"]>0 and stress["net_pts"]>0 and
               x["positive_quarters"]>=3)
            candidates.append(dict(model=model,timeframe=f"M{tf}",year2025=x,
                     year2026_partial=y,passed_gate=passed))
    return candidates

def main():
    allq=[];sources=[]
    for year in ("2025","2026_partial"):
        raw=load_gold_year(2025) if year=="2025" else source_2026()
        source=dict(year=year,n=len(raw),start=str(raw.index.min()),
                  end=str(raw.index.max()))
        sources.append(source)
        print("NY_SOURCE",json.dumps(source),flush=True)
        allq+=year_cases(raw,year)
    annual=aggregate(allq)
    rankings=screen(annual)
    candidates=[r for r in rankings if r["passed_gate"]]
    OUT.mkdir(parents=True,exist_ok=True)
    results=dict(symbol="XAUUSD",scope="2025 full + 2026 available partial",
        models=MODELS,timeframes=ALLOWED,cost_usd_per_ounce=COSTS,
        point_price=0.01,source=sources,quarters=allq,annual=annual,
        screening=rankings,passed_gate=candidates,approved_for_live=False,
        regime="NY UTC 12-17, EMA21/55/200 aligned, VWAP volume-weighted",
        exits="1.5ATR risk; 2R TP; 24 bars max; stop first on OHLC",
        warnings=["OHLC surrogate, no MT5 real tick fills",
                  "2025 and 2026 partial previously observed, not pristine OOS",
                  "2026 feed is pinned and does not include November 2026",
                  "Costs fixed, no actual broker spread/swap/commission/dynamic lot",
                  "No assurance of future profit"])
    (OUT/"RESULTS.json").write_text(json.dumps(results,indent=2)+"\n")
    lines=["# XAUUSD NY Breakout vs Pullback — fixed 2025/2026 partial","",
           "| Model | TF | Year | N | Net pts | PF | Win % | Net R | Positive quarters |",
           "|---|---|---|---:|---:|---:|---:|---:|---:|"]
    for row in annual:
        x=row["metrics"]["1.2"]
        lines.append(f"| {row['model']} | {row['timeframe']} | {row['year']} | {x['N']} | {x['net_pts']} | {x['PF']} | {x['win_pct']} | {x['net_R']} | {x['positive_quarters']}/{x['tested_quarters']} |")
    lines+=["","Candidates passing fixed gate: "+str(candidates),
            "No MetaEditor or broker tick backtest; no live approval."]
    (OUT/"REPORT.md").write_text("\n".join(lines)+"\n")
    print("NY_DONE",json.dumps(dict(quar=len(allq),annual=len(annual),
                                passed=candidates)),flush=True)

if __name__=="__main__":
    main()
