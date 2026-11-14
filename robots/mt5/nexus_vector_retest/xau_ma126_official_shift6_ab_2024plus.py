#!/usr/bin/env python3
"""Frozen A/B research: original MA12/6 vs structure, liquidity and volatility.

All entries are causal at the NEXT candle's OPEN, relying only on that open
and prior fully CLOSED OHLCV. Price points assume 0.01 USD/oz; costs hypothetical.
MetaQuotes Moving Average 1.00: previous candle OPEN/CLOSE crosses
iMA(period=12, shift=6, MODE_SMA, PRICE_CLOSE) as read using CopyBuffer(0,0).
Its current visible value corresponds to MA of CLOSES shifted 6 candles
into chart future; CopyBuffer(0) returns the MA calculated 6 bars earlier.
The exact built-in EA uses reverse crossings and no TP or SL by default.
We retain separate baseline replicas with and without our 1ATR protection.
The comparison keeps the SAME original 1*ATR14 stop and opposite-MA-cross
exit for ALL configurations, so exit differences cannot fake an entry edge.

The historical price feed is NOT MetaTrader broker Bid/Ask tick data.
"""
from __future__ import annotations
import json,math
from pathlib import Path
import numpy as np
import pandas as pd
from research_oos import prepared,bars_for,download as source_2026

ALLOWED=(1,5,15,30)
MODELS=("A_METAQUOTES_NO_SL","A_MA12_ATR_STOP",
        "B_MA12_STRUCTURE_BREAK","C_SWEEP_CONFIRM",
        "D_VOLATILITY_EXPANSION")
POINT=0.01
COSTS=(0.8,1.2,1.6)
OUT=Path(__file__).resolve().parent/"xau_ma126_structure_sweep_results"
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
    f=prepared(raw if tf==1 else bars_for(raw,tf))
    open_=f.open
    close=f.close
    h=f.high
    l=f.low
    tr=pd.concat([h-l,(h-close.shift(1)).abs(),(l-close.shift(1)).abs()],axis=1).max(axis=1)
    # The ACTUAL MetaQuotes example creates iMA(12,6,SMA,CLOSE)
    # and reads CopyBuffer(handle,0,0,...). A +6 plot shift means the
    # current chart location holds an average of closes from 6 bars AGO.
    # The previous v1.10 Nexus port incorrectly used NEW_OPEN + 11 closes.
    current_sma=sum(close.shift(k) for k in range(6,18))/12.
    f["ma_at_open"]=current_sma
    f["cross_buy"]=(open_.shift(1)<current_sma)&(close.shift(1)>current_sma)
    f["cross_sell"]=(open_.shift(1)>current_sma)&(close.shift(1)<current_sma)
    f["atr_pre"]=f.atr.shift(1)
    f["prior12_hi"]=h.shift(2).rolling(12,min_periods=12).max()
    f["prior12_lo"]=l.shift(2).rolling(12,min_periods=12).min()
    f["prior14_before_sweep_hi"]=h.shift(3).rolling(14,min_periods=14).max()
    f["prior14_before_sweep_lo"]=l.shift(3).rolling(14,min_periods=14).min()
    f["ema12_pre"]=close.ewm(span=12,adjust=False).mean().shift(1)
    f["ema55_pre"]=close.ewm(span=55,adjust=False).mean().shift(1)
    f["prev_body"]=(close.shift(1)-open_.shift(1))/(
        h.shift(1)-l.shift(1)).replace(0,np.nan)
    f["tr_prev"]=tr.shift(1)
    f["atr14_before"]=tr.ewm(alpha=1/14,adjust=False).mean().shift(2)
    f["atr50_before"]=tr.ewm(alpha=1/50,adjust=False).mean().shift(2)
    # C: Candle 2 sweeps fully known earlier 14-bar extrema and CLOSES BACK
    # INSIDE; candle 1 confirms with body direction & price past midpoint.
    pprev_open=open_.shift(2)
    pprev_high=h.shift(2)
    pprev_low=l.shift(2)
    pprev_close=close.shift(2)
    f["sweep_long"]=(pprev_low<f.prior14_before_sweep_lo-.05*f.atr14_before)&(
        pprev_close>f.prior14_before_sweep_lo)&(
        close.shift(1)>(pprev_high+pprev_low)/2)&(f.prev_body>.22)
    f["sweep_short"]=(pprev_high>f.prior14_before_sweep_hi+.05*f.atr14_before)&(
        pprev_close<f.prior14_before_sweep_hi)&(
        close.shift(1)<(pprev_high+pprev_low)/2)&(f.prev_body<-.22)
    # D: A new volatility regime is recognized from completed bar and older ATR.
    f["prior12_closed_hi"]=h.shift(2).rolling(12,min_periods=12).max()
    f["prior12_closed_lo"]=l.shift(2).rolling(12,min_periods=12).min()
    f["expansion"]=(f.tr_prev>=1.45*f.atr14_before)&(
        f.atr14_before>=1.05*f.atr50_before)
    return f


def signal_pairs(f):
    buy=f.cross_buy.to_numpy(dtype=bool)
    sell=f.cross_sell.to_numpy(dtype=bool)
    c=f.close.shift(1).to_numpy(dtype=float)
    atr=f.atr_pre.to_numpy(dtype=float)
    body=f.prev_body.to_numpy(dtype=float)
    structure_buy=buy&(c>f.prior12_hi.to_numpy(dtype=float)+.03*atr)&(body>.18)
    structure_sell=sell&(c<f.prior12_lo.to_numpy(dtype=float)-.03*atr)&(body<-.18)
    sweep_buy=f.sweep_long.to_numpy(dtype=bool)
    sweep_sell=f.sweep_short.to_numpy(dtype=bool)
    vol_buy=f.expansion.to_numpy(dtype=bool)&(body>.48)&(
        c>f.prior12_closed_hi.to_numpy(dtype=float)+.05*atr)&(
        f.ema12_pre.to_numpy(dtype=float)>f.ema55_pre.to_numpy(dtype=float))
    vol_sell=f.expansion.to_numpy(dtype=bool)&(body<-.48)&(
        c<f.prior12_closed_lo.to_numpy(dtype=float)-.05*atr)&(
        f.ema12_pre.to_numpy(dtype=float)<f.ema55_pre.to_numpy(dtype=float))
    return {
     "A_METAQUOTES_NO_SL":np.where(buy,1,np.where(sell,-1,0)).astype(np.int8),
     "A_MA12_ATR_STOP":np.where(buy,1,np.where(sell,-1,0)).astype(np.int8),
     "B_MA12_STRUCTURE_BREAK":np.where(structure_buy,1,np.where(structure_sell,-1,0)).astype(np.int8),
     "C_SWEEP_CONFIRM":np.where(sweep_buy,1,np.where(sweep_sell,-1,0)).astype(np.int8),
     "D_VOLATILITY_EXPANSION":np.where(vol_buy,1,np.where(vol_sell,-1,0)).astype(np.int8)
    }


def sim_quarter(f,signal,lo,hi,cost,protective_stop=True):
    """Non-overlapping positions, one per symbol, same stops/exits for all.

    SL-first in OHLC, worse-than-SL opens for gaps, exits on original opposite
    MA cross at NEW candle open; no optimized profit taking. Quarter positions
    liquidated at last closed price for separately comparable stress screens.
    """
    o=f.open.to_numpy(dtype=float)
    high=f.high.to_numpy(dtype=float)
    low=f.low.to_numpy(dtype=float)
    close=f.close.to_numpy(dtype=float)
    atr=f.atr_pre.to_numpy(dtype=float)
    cb=f.cross_buy.to_numpy(dtype=bool)
    cs=f.cross_sell.to_numpy(dtype=bool)
    result=[]
    active=False
    side=0
    entry=stop=0.
    entry_index=0
    Nsignals=int(np.count_nonzero(signal[lo:hi]))
    for i in range(lo,hi):
        if active:
            # First tick of new bar exits on opposite MA crossover.
            if (side>0 and cs[i]) or (side<0 and cb[i]):
                net_price=side*(o[i]-entry)-cost
                result.append(dict(pts=net_price/POINT,R=net_price/abs(entry-stop),
                    entry_index=entry_index,exit_index=i,reason="opposite_cross"))
                active=False
                continue  # same-bar close/reentry forbidden, matches EA v1.10
        if not active and i<hi-1 and signal[i]!=0 and np.isfinite(atr[i]) and atr[i]>POINT:
            side=int(signal[i])
            entry=float(o[i])
            stop=float(entry-side*atr[i]) # stopATR=1.00, same as EA original
            if not np.isfinite([entry,stop]).all():continue
            active=True
            entry_index=i
        if not active:continue
        slhit=(low[i]<=stop if side>0 else high[i]>=stop) if protective_stop else False
        if slhit:
            fill=min(o[i],stop) if side>0 else max(o[i],stop)
            net_price=side*(fill-entry)-cost
            result.append(dict(pts=net_price/POINT,R=net_price/abs(entry-stop),
                     entry_index=entry_index,exit_index=i,reason="stop"))
            active=False
    if active:
        net_price=side*(close[hi-1]-entry)-cost
        result.append(dict(pts=net_price/POINT,R=net_price/abs(entry-stop),
               entry_index=entry_index,exit_index=hi-1,reason="quarter_boundary"))
    points=np.array([r["pts"] for r in result],dtype=float)
    rmult=np.array([r["R"] for r in result],dtype=float)
    wins=points[points>0].sum() if len(points) else 0.
    loss=-points[points<0].sum() if len(points) else 0.
    winR=rmult[rmult>0].sum() if len(rmult) else 0.
    lossR=-rmult[rmult<0].sum() if len(rmult) else 0.
    eq=np.r_[0.,np.cumsum(points)]
    eqR=np.r_[0.,np.cumsum(rmult)]
    return {
      "N":len(result),"signals_raw":Nsignals,
      "green":int(np.sum(points>0)),"red":int(np.sum(points<0)),
      "gross_positive_pts":round(float(wins),3),
      "gross_negative_pts":round(float(loss),3),
      "gross_positive_R":round(float(winR),4),
      "gross_negative_R":round(float(lossR),4),
      "net_pts":round(float(points.sum()),1),
      "net_R":round(float(rmult.sum()),4),
      "PF":round(float(wins/loss),3) if loss>0 else None,
      "PF_R":round(float(winR/lossR),3) if lossR>0 else None,
      "win_pct":round(100.*float(np.mean(points>0)),2) if len(points) else 0.,
      "closed_trade_MDD_pts":round(float(np.max(np.maximum.accumulate(eq)-eq)),1),
      "closed_trade_MDD_R":round(float(np.max(np.maximum.accumulate(eqR)-eqR)),3),
      "reasons":{name:sum(x["reason"]==name for x in result)
                 for name in ("stop","opposite_cross","quarter_boundary")}
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
                metrics={str(cost):sim_quarter(f,signs[model],lo,hi,cost,
                                  protective_stop=(model!="A_METAQUOTES_NO_SL"))
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
    rows=[]
    for tf in ALLOWED:
        for model in MODELS:
            all_years=[x for x in cases if x["timeframe"]==f"M{tf}" and x["model"]==model]
            if len(all_years)<3:continue
            periods={x["year"]:x["metrics"]["1.2"] for x in all_years}
            stress={x["year"]:x["metrics"]["1.6"] for x in all_years}
            # Strict snapshot screen, no in-sample tuning.
            pass_=bool(model not in ("A_METAQUOTES_NO_SL","A_MA12_ATR_STOP") and all(
                periods[y]["net_pts"]>0 and periods[y]["net_R"]>0
                and stress[y]["net_R"]>0 and (
                    periods[y]["N"]>= (30 if y=="2026_partial" else 60))
                and periods[y]["PF"] is not None and periods[y]["PF"]>1.15
                and periods[y]["positive_quarters"]>=(
                    1 if y=="2026_partial" else 3)
                for y in ("2024","2025","2026_partial")))
            rows.append(dict(model=model,timeframe=f"M{tf}",
                counts={y:periods[y]["N"] for y in periods},
                net_points={y:periods[y]["net_pts"] for y in periods},
                net_R={y:periods[y]["net_R"] for y in periods},
                stress_R={y:stress[y]["net_R"] for y in periods},
                PF={y:periods[y]["PF"] for y in periods},
                win_rate={y:periods[y]["win_pct"] for y in periods},
                quarters_positive={y:periods[y]["positive_quarters"] for y in periods},
                tentative_screen=pass_))
    return rows


def main():
    all_q=[]
    for year in ("2024","2025","2026_partial"):
        raw=load_gold_year(int(year)) if year!="2026_partial" else source_2026()
        print("NQ_AB_SOURCE",json.dumps(dict(year=year,
          minute_candles=len(raw),from_date=str(raw.index.min()),
          to_date=str(raw.index.max()))),flush=True)
        all_q+=year_cases(raw,year)
    annual=aggregate(all_q)
    rankings=screen(annual)
    selected=[r for r in rankings if r["tentative_screen"]]
    out=dict(symbol="XAUUSD",version="MA126_AB_STRUCTURE_SWEEP_VOLATILITY_1",
      allowed_tf=["M1","M5","M15","M30"],costs_usd_per_oz_roundtrip=COSTS,
      points_price_change_usd_oz=POINT,
      opening_formula="MetaQuotes iMA(12,6,MODE_SMA,PRICE_CLOSE) with CopyBuffer shift0: average of closes from chart candle -6 to -17",
      exit_assumption="Original MetaQuotes sample A has reverse-cross exit and NO stop/TP, plus A_ATR and B/C/D use 1ATR protective stop, all use reverse-cross exit, 1 position per symbol",
      quarter_boundary="flatten at quarter final closed price; next quarter independent",
      source_2024_2025="pinned XAUUSD M1 OHLCV archived files",
      source_2026="separate partial Q2/Q3 2026 OHLCV sha256 verified",
      limitations=["OHLC proxy not broker MT5 tick execution",
      "2025 and 2026 partial heavily reused in earlier studies",
      "CAUTION: original MetaQuotes sample uses margin-and-history lot sizing, not included; reference points not original USD account profit",
      "2024 retrospective check (not forward validation)",
      "fixed assumed costs exclude dynamic Bid/Ask, commission, swap, real fills",
      "official baseline SIGNAL models iMA shifted6 as documented; lot sizing/decreasefactor and real bid/ask not modeled",
      "performance in price units/R not real monetary equity",
      "filters must not be selected or tuned after reading these results"],
      quarters=all_q,year_summaries=annual,screen=rankings,
      tentative_shortlist=selected,production_approved=False)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"ALL_RESULTS.json").write_text(json.dumps(out,indent=2)+"\n")
    lines=["# MetaQuotes MA12/6 SHIFT6 vs structure, liquidity, volatility (XAUUSD)",
      "","Original A_NO_SL no stop, other four 1xATR protective stop; all opposite MA-cross exit.",
      "2024/2025 full and 2026 partial, hypothetical 1.2 USD/oz costs.",
      "No tick-level MT5 real broker backtest. R is not percentage.",
      "",
      "| Model | TF | Year | N | Net pts | PF | Win % | Net R | Positive quarters |",
      "|---|---|---|---:|---:|---:|---:|---:|---:|"]
    for row in annual:
        x=row["metrics"]["1.2"]
        lines.append(f"| {row['model']} | {row['timeframe']} | {row['year']} | {x['N']} | {x['net_pts']} | {x['PF']} | {x['win_pct']} | {x['net_R']} | {x['positive_quarters']}/{x['tested_quarters']} |")
    lines.extend(["","## Tentative screen",str(selected),
       "","Do NOT promote historical candidates to live or modify original EA."])
    (OUT/"REPORT.md").write_text("\n".join(lines)+"\n")
    print("NQ_AB_COMPLETE",json.dumps(dict(quarter_rows=len(all_q),
       year_summaries=len(annual),comparisons=len(rankings),
       tentative_shortlist=selected)),flush=True)


if __name__=="__main__":
    main()
