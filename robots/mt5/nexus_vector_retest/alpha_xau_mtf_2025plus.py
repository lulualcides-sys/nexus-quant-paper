#!/usr/bin/env python3
"""XAUUSD 2025+ EMA21 Pullback across all native MT5 minute TFs M1..M30.

Research only, no broker order API. Historic OHLC stop-first proxy, costs
hypothetical. No tuning / promotion against already inspected historical data.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from points10k import events, COST, POINT, WARM
from research_oos import prepared, bars_for, download
from points10k_2025 import source as load_2025
from alpha_xau_longhold import simulate_xau
from alpha_xau_entry_risk_2025plus import qualified_entry
from alpha_xau_adaptive import trend_masks as compute_trend_masks

TF_MINUTES = (1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30)
PROFILES = ("RUNNER_96H", "ENTRY_QUALITY", "BE_AFTER_TP2",
            "ENTRY_QUALITY_BE", "REVERSAL_BE", "CONDITIONAL_TREND_96H")
COST_GRID = (0.8, 1.2, 1.6)
CUTOFF = pd.Timestamp("2025-01-01",tz="UTC")
HORIZON_MINUTES = 384 * 15  # original M15 runner = 96h of TRADING candles
OUT = Path(__file__).resolve().parent/"alpha_xau_mtf_2025plus_results"


def horizon_bars(tf_minutes):
    if tf_minutes not in TF_MINUTES or HORIZON_MINUTES % tf_minutes:
        raise ValueError("invalid M1–M30 timeframe")
    return HORIZON_MINUTES//tf_minutes


def replay_one(df, signals, first, last, tf_minutes, profile, masks=None):
    """One position at a time, same signals/tail embargo per timeframe.

    Executions: next-bar-open signal, stop first in same OHLC candle, partial
    targets of 1R and 1.5R (one third each), final third as runner to SL or
    fixed 96h in *bars*. BE is armed only on the candle AFTER TP2. Adverse EMA
    reversal needs two completely closed bars after TP2.
    """
    if profile not in PROFILES or not 0 <= first < last <= len(df):
        raise ValueError("invalid replay range")
    hold = horizon_bars(tf_minutes)
    arr = {k:df[k].to_numpy(dtype=float) for k in
           ("open","high","low","close","fema","atr")}
    op,hi,lo,cl,ema,atr = (arr[k] for k in
                          ("open","high","low","close","fema","atr"))
    filter_entry = profile in ("ENTRY_QUALITY","ENTRY_QUALITY_BE")
    simple_be = profile in ("BE_AFTER_TP2","ENTRY_QUALITY_BE")
    reversal_be = profile == "REVERSAL_BE"
    conditional = profile == "CONDITIONAL_TREND_96H"
    if conditional and masks is None:
        masks = compute_trend_masks(df)
    base_hold = 720//tf_minutes
    trades=[]
    last_close = first-1
    for i, side, source_stop, quality in signals:
        if i<first:
            continue
        if i+hold+1>=last:
            break   # signals are chronologically sorted, common right-tail embargo
        entrybar=i+1
        if entrybar <= last_close+1:
            continue
        entry=float(op[entrybar])
        risk=float(side*(entry-source_stop))
        if not np.isfinite(risk) or risk<=0:
            continue
        if filter_entry and not qualified_entry(df,i,side,risk):
            continue
        stop=float(source_stop)
        targets=(entry+side*risk, entry+side*1.5*risk)
        remain=1.
        fills=0
        gross=0.
        reason="TIME"
        exitbar=entrybar+hold
        breakeven_armed=False
        for j in range(entrybar,entrybar+hold+1):
            # Only extend beyond 12 candle-hours when the last CLOSED bar
            # confirms microtrend or established strong trend, same direction.
            if conditional and j>=entrybar+base_hold:
                idx=0 if side>0 else 1
                micro,strong=masks
                if not (micro[idx,j-1] or strong[idx,j-1]):
                    gross+=remain*side*(op[j]-entry)
                    reason="TREND_OFF"
                    exitbar=j
                    break
            # Protection after TP2 starts at the NEXT OPEN, not within TP2 bar.
            if fills==2 and j>entrybar:
                if simple_be or (reversal_be and j>=entrybar+3
                     and np.isfinite([cl[j-1],cl[j-2],ema[j-1],
                                      ema[j-2],atr[j-1]]).all()
                     and atr[j-1]>0
                     and side*(cl[j-1]-ema[j-1]) < -0.25*atr[j-1]
                     and side*(cl[j-2]-ema[j-2]) < 0):
                    stop=max(stop,entry) if side>0 else min(stop,entry)
                    breakeven_armed=True
            # Preserve stop-first ordering including opening gaps.
            if (lo[j]<=stop if side>0 else hi[j]>=stop):
                fill=min(op[j],stop) if side>0 else max(op[j],stop)
                gross+=remain*side*(fill-entry)
                reason="SL_PROTECTED" if breakeven_armed else "SL"
                exitbar=j
                break
            for k in range(fills,2):
                hit=(hi[j]>=targets[k] if side>0 else lo[j]<=targets[k])
                if not hit:
                    break
                gross+=side*(targets[k]-entry)/3.
                remain-=1./3
                fills=k+1
            if j==entrybar+hold:
                gross+=remain*side*(cl[j]-entry)
                exitbar=j
                break
        trades.append(dict(signal=int(i),entry=int(entrybar),exit=int(exitbar),
            side=int(side),gross_pts=float(gross/POINT),
            protected=breakeven_armed,reason=reason))
        last_close=exitbar
    return trades


def summarize(trades, cost=COST):
    if not trades:
        return dict(N=0, gross_pts=0., net_pts=0., PF=None,
                    win_pct=None, mdd_pts=None, avg_hold=None)
    gross=np.asarray([t["gross_pts"] for t in trades],dtype=float)
    net=gross-cost/POINT
    gain=float(net[net>0].sum())
    loss=float(-net[net<0].sum())
    curve=np.r_[0.,np.cumsum(net)]
    return dict(N=len(trades),
        gross_pts=round(float(gross.sum()),1),
        net_pts=round(float(net.sum()),1),
        PF=round(gain/loss,3) if loss else None,
        win_pct=round(float((net>0).mean()*100),2),
        mdd_pts=round(float((np.maximum.accumulate(curve)-curve).max()),1),
        avg_hold=round(float(np.mean([t["exit"]-t["entry"] for t in trades])),1))


def windows_by_quarter(df, hold):
    # Use identical chronological calendar boundaries for all model variants
    # within a given timeframe, not 10k-bar blocks that represent varying dates.
    quarter=df.index.to_period("Q")
    for quarter_id in pd.unique(quarter):
        indices=np.flatnonzero(quarter==quarter_id)
        first=max(int(indices[0]),WARM)
        last=int(indices[-1])+1
        if last-first<=hold+50:
            yield str(quarter_id),None,None
        else:
            yield str(quarter_id),first,last


def run_period(raw, label, tf_minutes):
    if raw.empty or raw.index.min()<CUTOFF:
        raise ValueError("pre-2025 data prohibited")
    df=prepared(raw.copy() if tf_minutes==1 else bars_for(raw,tf_minutes))
    if df.index.min()<CUTOFF:
        raise ValueError("unexpected pre-2025 resampling")
    signals=events(df,"EMA21_PULLBACK")
    trend=compute_trend_masks(df)
    bars=horizon_bars(tf_minutes)
    quarters=[]
    all_deals={model:[] for model in PROFILES}
    for quarter,first,last in windows_by_quarter(df,bars):
        if first is None:
            quarters.append(dict(quarter=quarter,status="INSUFFICIENT_BARS",
                                  candles=int(sum(df.index.to_period("Q")==quarter))))
            continue
        models={}
        for model in PROFILES:
            trades=replay_one(df,signals,first,last,tf_minutes,model,masks=trend)
            all_deals[model].extend(trades)
            models[model]={str(c):summarize(trades,c) for c in COST_GRID}
        if tf_minutes==15:
            # Trade-by-trade parity with previously saved, unmodified Runner384.
            orig=simulate_xau(df,signals,first,last,384,runner=True)
            ours=replay_one(df,signals,first,last,15,"RUNNER_96H")
            if len(orig)!=len(ours):
                raise AssertionError("M15 baseline trade-count regression")
            for a,b in zip(orig,ours):
                if (a["entry"],a["exit"],a["side"])!=(b["entry"],b["exit"],b["side"]) or not np.isclose(
                    a["gross_pts"],b["gross_pts"],atol=1e-5,rtol=0):
                    raise AssertionError("M15 baseline P&L regression")
        q=dict(quarter=quarter,first=str(df.index[first]),
               last=str(df.index[last-1]),models=models)
        quarters.append(q)
        print("MTF_WINDOW",json.dumps(dict(source=label,tf="M"+str(tf_minutes),
               quarter=quarter,base=models["RUNNER_96H"]["0.8"],
               best_gate=models["ENTRY_QUALITY_BE"]["0.8"])),flush=True)
    sums={model:{str(c):summarize(all_deals[model],c) for c in COST_GRID}
          for model in PROFILES}
    return dict(year=label,tf="M"+str(tf_minutes),source_candles=len(df),
        signals=len(signals),hold_bars=bars,
        full_quarters=sum("models" in q for q in quarters),
        quarters=quarters,summary=sums)


def main():
    raw25,_=load_2025()
    raw26=download()
    years=(("2025",raw25),("2026",raw26))
    results=dict(symbol="XAUUSD",min_utc="2025-01-01",
       timeframes=["M"+str(n) for n in TF_MINUTES],
       horizon="96 hours of complete trading candles, not 96 wallclock hours",
       cost_grid_usd_oz=COST_GRID,
       models=PROFILES,point_assumption=POINT,
       data_model="OHLC proxy, next opening fills, stop first, gap-aware",
       warnings=[
         "Research only, historical periods already inspected, not untouched OOS.",
         "TP1=1R and TP2=1.5R; runner=last 1/3 at original stop or horizon.",
         "Trend-conditional exits use last fully closed bar, extend only beyond 12 candle-hours when trend is present.",
         "Only XAUUSD 2025+; date blocks are UTC calendar quarters.",
         "Hypothetical cost; no broker bid/ask, swap, slippage, commission or actual execution.",
         "Different timeframes have different signal counts; raw point totals not directly comparable.",
         "Risk/DD measured on completed trades, not intratrade equity."],
       cases=[])
    for tf in TF_MINUTES:
        for year,raw in years:
            result=run_period(raw,year,tf)
            results["cases"].append(result)
            print("MTF_SUMMARY",json.dumps({k:result[k] for k in
                ("year","tf","source_candles","signals","hold_bars",
                 "full_quarters","summary")}),flush=True)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"RESULTADOS_M1_M30_2025PLUS.json").write_text(
        json.dumps(results,indent=2,ensure_ascii=False)+"\n")
    table=["# XAUUSD EMA21 — pesquisa M1 a M30 (2025+)","",
       "**Replay OHLC, não MetaTrader 5 nem lucro real.**",
       "Timeframes MT5: "+", ".join(results["timeframes"])+".",
       "Data de início obrigatória: 2025-01-01 UTC; períodos agrupados em trimestres.",
       "Runner equivalente a 96 horas de CANDLES em qualquer timeframe;",
       "nunca equiparar esse horizonte a horas corridas incluindo fins de semana.",
       "Custo fixo assumido US$0.80/oz por trade (stress US$1.20 e US$1.60).",
       "Ponto assumido 0.01, corretora ainda não verificada.",
       "Os dados foram vistos durante pesquisa, não constituem OOS novo.","",
       "| TF | Ano | Trimestres válidos | Baseline trades | Baseline net pts | Baseline PF | MDD pts | Combinado BE+qualidade net pts |",
       "|---|---|---:|---:|---:|---:|---:|---:|"]
    for r in results["cases"]:
        a=r["summary"]["RUNNER_96H"]["0.8"]
        b=r["summary"]["ENTRY_QUALITY_BE"]["0.8"]
        table.append("| "+" | ".join(map(str,(r["tf"],r["year"],r["full_quarters"],
            a["N"],a["net_pts"],a["PF"],a["mdd_pts"],b["net_pts"])))+" |")
    table+=["","Nenhuma estratégia pode ser chamada de vencedora sem custos reais e",
       "avaliação futura com parâmetros congelados. Variantes que tiverem",
       "menos operações também devem ser avaliadas pelo custo de oportunidade.",""]
    (OUT/"RELATORIO_M1_M30.md").write_text("\n".join(table))
    print("MTF_COMPLETED",len(results["cases"]),flush=True)


if __name__=="__main__":
    main()
