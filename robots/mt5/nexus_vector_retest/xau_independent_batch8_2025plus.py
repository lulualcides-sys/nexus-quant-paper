#!/usr/bin/env python3
"""XAUUSD independent signal discovery batch 8, closed bars 2025+, M1/M5/M15/M30 ONLY.

Four predeclared new hypotheses, fixed original 96 trading-candle-hour runner,
per-trade initial stop R, strict 2025 / partial-2026 cross-period screen. This
reuses repeatedly inspected historical OHLC: NOT untouched out-of-sample,
not a broker MT5 tick test, not a positive real account trading claim.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from points10k import POINT,WARM
from points10k_2025 import source as source2025
from research_oos import prepared,bars_for,download
from alpha_xau_mtf_2025plus import (
    CUTOFF,COST_GRID,horizon_bars,windows_by_quarter,replay_one,summarize)
from xau_exit_risk_batch6_2025plus import risk_stats
from xau_volatility_breakouts_2025plus import feature_frame, make_signals
from xau_statistical_regimes_batch5_2025plus import features as old_features, signals as old_signals

ALLOWED_TF=(1,5,15,30)
NEW_MODELS=("RSI2_EMA200_REBOUND","DONCHIAN24_FAILED_BREAK",
           "DAILY_VWAP_RECLAIM","MOMENTUM3_SHALLOW_RETRACE")
FROZEN_REFERENCES=(("ER20_M30_FROZEN",30),("SHOCK_M15_FROZEN",15))
OUT=Path(__file__).resolve().parent/"xau_batch8_independent_2025plus_results"


def feature_frame8(frame):
    d=frame.copy()
    cl=d.close.astype(float)
    op=d.open.astype(float)
    hi=d.high.astype(float)
    lo=d.low.astype(float)
    atr=d.atr.replace(0,np.nan)
    d["ema50"]=cl.ewm(span=50,adjust=False).mean()
    d["ema200"]=cl.ewm(span=200,adjust=False).mean()
    diff=cl.diff()
    gain=diff.clip(lower=0).ewm(alpha=.5,adjust=False,min_periods=2).mean()
    loss=(-diff.clip(upper=0)).ewm(alpha=.5,adjust=False,min_periods=2).mean()
    rsi=100-100/(1+gain/loss.replace(0,np.nan))
    d["rsi2"]=rsi.mask((loss==0)&(gain>0),100.).mask(
        (gain==0)&(loss>0),0.).mask((loss==0)&(gain==0),50.)
    d["prev_rsi2"]=d.rsi2.shift(1)
    d["prior24_hi"]=hi.shift(2).rolling(24,min_periods=24).max()
    d["prior24_lo"]=lo.shift(2).rolling(24,min_periods=24).min()
    d["prev_hi"]=hi.shift(1)
    d["prev_lo"]=lo.shift(1)
    d["prev_close"]=cl.shift(1)
    d["prev_open"]=op.shift(1)
    d["before_close"]=cl.shift(2)
    d["before_open"]=op.shift(2)
    d["body_fraction"]=(cl-op)/(hi-lo).replace(0,np.nan)
    d["prev_body_fraction"]=d.body_fraction.shift(1)
    d["before_body_fraction"]=d.body_fraction.shift(2)
    d["prev_range"]=(hi-lo).shift(1)
    d["prior_atr"]=atr.shift(1)
    d["vwap_prev"]=d.vwap.shift(1)
    d["prior_day"]=d.index.floor("D").to_series(index=d.index).shift(1)
    d["day_id"]=d.index.floor("D")
    # Only allow previous/current day's VWAP comparisons after 30 elapsed
    # minutes from UTC midnight. Tick volume is a proxy, not true exchange size.
    d["minutes_since_midnight"]=d.index.hour*60+d.index.minute
    return d


def emit(df,model):
    """Only closed candles decide direction; next opening validates stop risk."""
    if model not in NEW_MODELS:
        raise ValueError("unknown strategy")
    o=df.open.to_numpy(dtype=float)
    h=df.high.to_numpy(dtype=float)
    l=df.low.to_numpy(dtype=float)
    c=df.close.to_numpy(dtype=float)
    a=df.atr.to_numpy(dtype=float)
    ema50=df.ema50.to_numpy(dtype=float)
    ema200=df.ema200.to_numpy(dtype=float)
    body=df.body_fraction.to_numpy(dtype=float)
    side=np.zeros(len(df),dtype=np.int8)
    pivot=np.full(len(df),np.nan,dtype=float)
    if model=="RSI2_EMA200_REBOUND":
        r=df.rsi2.to_numpy(dtype=float)
        prev=df.prev_rsi2.to_numpy(dtype=float)
        above=(ema50>ema200)&(c>ema200)
        below=(ema50<ema200)&(c<ema200)
        long=above&(prev<12)&(r>12)&(r<65)&(body>.10)
        short=below&(prev>88)&(r<88)&(r>35)&(body<-.10)
        side=np.where(long,1,np.where(short,-1,0))
        pivot=np.where(long,df.prev_lo.to_numpy(dtype=float),
                       df.prev_hi.to_numpy(dtype=float))
    elif model=="DONCHIAN24_FAILED_BREAK":
        top=df.prior24_hi.to_numpy(dtype=float)
        bottom=df.prior24_lo.to_numpy(dtype=float)
        ph=df.prev_hi.to_numpy(dtype=float)
        pl=df.prev_lo.to_numpy(dtype=float)
        pc=df.prev_close.to_numpy(dtype=float)
        long=(pl<bottom-.10*a)&(pc<bottom)&(c>bottom)&(body>.18)
        short=(ph>top+.10*a)&(pc>top)&(c<top)&(body<-.18)
        side=np.where(long,1,np.where(short,-1,0))
        pivot=np.where(long,pl,ph)
    elif model=="DAILY_VWAP_RECLAIM":
        vw=df.vwap.to_numpy(dtype=float)
        pv=df.vwap_prev.to_numpy(dtype=float)
        prev=df.prev_close.to_numpy(dtype=float)
        mn=df.minutes_since_midnight.to_numpy(dtype=float)
        is_same_day=(df.day_id==df.prior_day).to_numpy(dtype=bool)
        long=is_same_day&(mn>=30)&(prev<pv-.12*a)&(c>vw+.08*a)&(body>.25)
        short=is_same_day&(mn>=30)&(prev>pv+.12*a)&(c<vw-.08*a)&(body<-.25)
        side=np.where(long,1,np.where(short,-1,0))
        pivot=np.where(long,df.prev_lo.to_numpy(dtype=float),
                       df.prev_hi.to_numpy(dtype=float))
    elif model=="MOMENTUM3_SHALLOW_RETRACE":
        prev=df.prev_body_fraction.to_numpy(dtype=float)
        before=df.before_body_fraction.to_numpy(dtype=float)
        pclose=df.prev_close.to_numpy(dtype=float)
        bclose=df.before_close.to_numpy(dtype=float)
        pb_open=df.prev_open.to_numpy(dtype=float)
        bb_open=df.before_open.to_numpy(dtype=float)
        prev_range=df.prev_range.to_numpy(dtype=float)
        prioratr=df.prior_atr.to_numpy(dtype=float)
        # Closed bars i-2 and i-1 progressed with trend. Current signal bar
        # retraces into an EMA50 band and closes back with trend.
        long=(ema50>ema200)&(before>.40)&(prev>.35)&(
            bclose>bb_open)&(pclose>pb_open)&(
            l<=ema50+.30*a)&(c>ema50)&(body>.20)&(
            prev_range<=2.4*prioratr)
        short=(ema50<ema200)&(before<-.40)&(prev<-.35)&(
            bclose<bb_open)&(pclose<pb_open)&(
            h>=ema50-.30*a)&(c<ema50)&(body<-.20)&(
            prev_range<=2.4*prioratr)
        side=np.where(long,1,np.where(short,-1,0))
        pivot=np.where(long,df.prev_lo.to_numpy(dtype=float),
                       df.prev_hi.to_numpy(dtype=float))
    ans=[]
    for i in np.flatnonzero(side):
        if i<WARM or i>=len(df)-1:
            continue
        s=int(side[i])
        stop=(min(float(l[i]),float(pivot[i]))-.12*float(a[i]) if s>0
              else max(float(h[i]),float(pivot[i]))+.12*float(a[i]))
        risk=s*(o[i+1]-stop)
        if not np.isfinite([stop,risk,a[i],body[i]]).all() or a[i]<=0:
            continue
        if .12*a[i]<=risk<=4.*a[i]:
            ans.append((int(i),s,float(stop),float(min(1.,abs(body[i])))))
    return ans


def input_model(raw,tf,model):
    if tf not in ALLOWED_TF or raw.empty or raw.index.min()<CUTOFF:
        raise ValueError("XAUUSD 2025+ in M1 M5 M15 M30 only")
    x=prepared(raw if tf==1 else bars_for(raw,tf))
    if x.empty or x.index.min()<CUTOFF:
        raise ValueError("invalid resampling")
    if model in NEW_MODELS:
        y=feature_frame8(x)
        return y,emit(y,model)
    if model=="ER20_M30_FROZEN" and tf==30:
        y=feature_frame(x)
        return y,make_signals(y,"EFFICIENCY_ER20_BREAK")
    if model=="SHOCK_M15_FROZEN" and tf==15:
        y=old_features(x)
        return y,old_signals(y,"SHOCK_EXHAUSTION")
    raise ValueError("invalid reference model/timeframe")


def calculate(raw,year,tf,model):
    frame,events=input_model(raw,tf,model)
    alltrades=[]
    quarters=[]
    for quarter,first,last in windows_by_quarter(frame,horizon_bars(tf)):
        if first is None:
            quarters.append(dict(quarter=quarter,status="INSUFFICIENT_BARS"))
            continue
        trades=replay_one(frame,events,first,last,tf,"RUNNER_96H")
        alltrades.extend(trades)
        metrics={str(cost):{**summarize(trades,cost),
                     **risk_stats(trades,events,frame,cost)}
                     for cost in COST_GRID}
        quarters.append(dict(quarter=quarter,
            first=str(frame.index[first]),last=str(frame.index[last-1]),
            metrics=metrics))
        print("B8_QUARTER",json.dumps(dict(model=model,tf=f"M{tf}",
               year=year,quarter=quarter,metrics=metrics["1.2"])),flush=True)
    full={str(cost):{**summarize(alltrades,cost),
                    **risk_stats(alltrades,events,frame,cost)}
                    for cost in COST_GRID}
    answer=dict(year=year,tf=f"M{tf}",model=model,
        source_bars=len(frame),emitted_signals=len(events),
        quarters=quarters,summary=full)
    print("B8_YEAR",json.dumps(dict(year=year,tf=f"M{tf}",
                model=model,metrics=full)),flush=True)
    return answer


def screen(panels):
    """Strict independent-like descriptive screen; not independent data."""
    models=[(m,tf) for m in NEW_MODELS for tf in ALLOWED_TF]+list(FROZEN_REFERENCES)
    comparisons=[]
    for m,tf in models:
        a=next(x for x in panels if x["model"]==m and x["tf"]==f"M{tf}" and x["year"]=="2025")
        b=next(x for x in panels if x["model"]==m and x["tf"]==f"M{tf}" and x["year"]=="2026")
        x=a["summary"]["1.2"];y=b["summary"]["1.2"]
        xstress=a["summary"]["1.6"];ystress=b["summary"]["1.6"]
        q25=[z["metrics"]["1.2"]["net_R"] for z in a["quarters"] if "metrics" in z]
        q26=[z["metrics"]["1.2"]["net_R"] for z in b["quarters"] if "metrics" in z]
        # Quarterly concentration metric checks largest positive quarter
        # share of sum of positive quarterly R, not share of annual net R.
        plus=[max(0.,z) for z in q25]
        share=max(plus)/sum(plus) if sum(plus)>0 else None
        passed=bool(m in NEW_MODELS and x["N"]>=100 and y["N"]>=50
            and x["net_R"]>0 and y["net_R"]>0
            and xstress["net_R"]>0 and ystress["net_R"]>0
            and x["PF_R"] is not None and y["PF_R"] is not None
            and x["PF_R"]>1.2 and y["PF_R"]>1.2
            and sum(q>0 for q in q25)>=3
            and sum(q>0 for q in q26)>=1
            and share is not None and share<=.65)
        comparisons.append(dict(model=m,tf=f"M{tf}",reference=m not in NEW_MODELS,
          N_2025=x["N"],N_2026_partial=y["N"],
          net_R_2025=x["net_R"],net_R_2026_partial=y["net_R"],
          PF_R_2025=x["PF_R"],PF_R_2026_partial=y["PF_R"],
          DD_R_2025=x["MDD_R"],DD_R_2026_partial=y["MDD_R"],
          net_R_stress_2025=xstress["net_R"],
          net_R_stress_2026_partial=ystress["net_R"],
          positive_quarters_2025=sum(q>0 for q in q25),
          positive_quarters_2026_partial=sum(q>0 for q in q26),
          largest_positive_quarter_share_2025=share,
          preliminary_screen=passed))
    return comparisons


def main():
    a,_=source2025()
    b=download()
    if a.index.min()<CUTOFF or b.index.min()<CUTOFF:
        raise ValueError("start date violation")
    jobs=[(m,tf) for m in NEW_MODELS for tf in ALLOWED_TF]+list(FROZEN_REFERENCES)
    results=[]
    for model,tf in jobs:
        for year,raw in (("2025",a),("2026",b)):
            results.append(calculate(raw,year,tf,model))
    ranked=screen(results)
    shortlist=[x for x in ranked if x["preliminary_screen"]]
    result=dict(symbol="XAUUSD",
      authorized_tfs=["M1","M5","M15","M30"],
      original_new_models=NEW_MODELS,
      frozen_controls=FROZEN_REFERENCES,
      from_utc="2025-01-01",source_2026="partial Q2/Q3, separate feed",
      assumed_cost_roundtrip_usd_per_ounce=COST_GRID,
      execution="next bar OPEN, full initial stop; stop-first and gap-aware conservative OHLC; TP1 1R third, TP2 1.5R third, final third original Runner96h; no orders",
      score="Per-trade normalized initial 1R return after assumed hypothetical roundtrip costs, not dollar PnL or account return",
      limitations=["Research years already repeatedly studied, not untouched out of sample.",
      "2026 is partial Q2/Q3 only; feeds from 2025 and 2026 differ.",
      "VWAP volume source is OHLCV proxy, not verified broker tick volume.",
      "Four new mechanics times four timeframes means 16 multiple comparisons.",
      "No Bid/Ask, broker real ticks, spread variation, swap, slippage, commission, lot rounding, equity funding, live execution or intra-trade DD.",
      "Never overwrite 10 saved candidates or deploy to real-money account."],
      annual_panels=results,comparisons=ranked,shortlist=shortlist,
      approved_for_live=False)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"BATCH8_ALL.json").write_text(json.dumps(result,indent=2)+"\n")
    lines=["# XAUUSD 2025+ batch8: RSI2, Donchian fake break, VWAP day, momentum 3 bars",
      "","Historical OHLC and hypothetical cost, not broker tick or real PnL.",
      "Only M1, M5, M15, M30. 4 new strategies and 2 unchanged references.",
      "All numbers in initial stop risk units (R), costs 1.2 per troy oz roundtrip.",
      "","| Strategy | TF | N25 | Net R25 | PF25 | N26 partial | Net R26 | PF26 | Stress R25 | Stress R26 | 2025 dominant positive quarter share | Screening |",
      "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for z in ranked:
        lines.append("| "+" | ".join(str(z[k]) for k in
            ("model","tf","N_2025","net_R_2025","PF_R_2025",
             "N_2026_partial","net_R_2026_partial","PF_R_2026_partial",
             "net_R_stress_2025","net_R_stress_2026_partial",
             "largest_positive_quarter_share_2025","preliminary_screen"))+" |")
    lines+=["","## Predefined screen",str(shortlist),"",
       "A preliminarily positive pattern is NOT approved for live. New data needed."]
    (OUT/"BATCH8_REPORT.md").write_text("\n".join(lines)+"\n")
    print("B8_COMPLETE",json.dumps(dict(panels=len(results),
        comparisons=len(ranked),shortlisted=shortlist)),flush=True)


if __name__=="__main__":
    main()
