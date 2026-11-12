#!/usr/bin/env python3
"""XAUUSD 2025+ indicator lab, all 11 minute MT5 frames M1 through M30.

Exploratory public OHLC research, NOT broker MT5 tester or order execution.
Each signal is generated only from its COMPLETED candle; fills start at next
opening. Strategy params fixed BEFORE looking at this new comparison.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from research_oos import bars_for, prepared, download
from points10k_2025 import source as load_2025
from points10k import events as frozen_ema_events, POINT, WARM
from alpha_xau_mtf_2025plus import (
    TF_MINUTES, COST_GRID, horizon_bars, windows_by_quarter,
    replay_one, summarize, CUTOFF)

MODELS = (
    "EMA21_BASE",
    "EMA21_ADX_DI",
    "EMA21_RSI_MACD",
    "ADX_DONCHIAN24",
    "RSI_BOLLINGER20",
    "MACD_RSI_TREND",
    "KELTNER_SQUEEZE",
    "STOCH_REJECTION",
)
BASELINE = "EMA21_BASE"
PROFILE = "RUNNER_96H"
RESULTS = Path(__file__).resolve().parent / "xau_new_indicators_2025plus_results"


def indicators(frame):
    """Vectorized indicators on the current/past candle. No centered windows."""
    d=frame.copy()
    close=d.close.astype(float)
    high=d.high.astype(float)
    low=d.low.astype(float)
    prev_high=high.shift(1)
    prev_low=low.shift(1)
    up=high-prev_high
    down=prev_low-low
    plus_dm=up.where((up>down)&(up>0),0.)
    minus_dm=down.where((down>up)&(down>0),0.)
    atr=d.atr.replace(0,np.nan)
    plus_di=100.*plus_dm.ewm(alpha=1/14,adjust=False).mean()/atr
    minus_di=100.*minus_dm.ewm(alpha=1/14,adjust=False).mean()/atr
    dx=100.*(plus_di-minus_di).abs()/(plus_di+minus_di).replace(0,np.nan)
    d["adx"]=dx.ewm(alpha=1/14,adjust=False,min_periods=14).mean()
    d["plus_di"]=plus_di
    d["minus_di"]=minus_di

    delta=close.diff()
    for period in (14,):
        up_avg=delta.clip(lower=0).ewm(alpha=1/period,adjust=False,
                                       min_periods=period).mean()
        down_avg=(-delta.clip(upper=0)).ewm(alpha=1/period,adjust=False,
                                            min_periods=period).mean()
        rs=up_avg/down_avg.replace(0,np.nan)
        rsi=100.-100./(1.+rs)
        # Flat market = neutral; no sell-all RSI=100 false signal.
        rsi=rsi.mask((down_avg==0)&(up_avg>0),100.)
        rsi=rsi.mask((up_avg==0)&(down_avg>0),0.)
        rsi=rsi.mask((up_avg==0)&(down_avg==0),50.)
        d["rsi14"]=rsi

    mid=close.rolling(20,min_periods=20).mean()
    dev=close.rolling(20,min_periods=20).std(ddof=0)
    d["bb_mid"]=mid
    d["bb_upper"]=mid+2.*dev
    d["bb_lower"]=mid-2.*dev
    d["bb_width"]=4.*dev
    # Keltner width based on EMA(20) of last closed price and ATR(14).
    kc_mid=close.ewm(span=20,adjust=False).mean()
    d["kc_upper"]=kc_mid+1.5*atr
    d["kc_lower"]=kc_mid-1.5*atr
    d["squeeze"]=d.bb_width<(3.*atr)

    macd=close.ewm(span=12,adjust=False).mean()-close.ewm(span=26,adjust=False).mean()
    macd_signal=macd.ewm(span=9,adjust=False).mean()
    d["macd_hist"]=macd-macd_signal

    lo14=low.rolling(14,min_periods=14).min()
    hi14=high.rolling(14,min_periods=14).max()
    d["stoch_k"]=100.*(close-lo14)/(hi14-lo14).replace(0,np.nan)
    d["stoch_d"]=d.stoch_k.rolling(3,min_periods=3).mean()
    return d


def build_signals(frame, kind, baseline=None):
    """Create (signalbar, side, source_stop, quality) sorted by signal bar.

    All indicator signals use current candle i and prior states. Entry risk
    can be inspected on the next open i+1; no decision uses that bar's high,
    low, closing price, future trend, or future pivots.
    """
    if kind not in MODELS:
        raise ValueError(f"unknown indicator: {kind}")
    if kind==BASELINE:
        return list(baseline if baseline is not None
                    else frozen_ema_events(frame,"EMA21_PULLBACK"))

    if kind.startswith("EMA21_"):
        source=(baseline if baseline is not None
                else frozen_ema_events(frame,"EMA21_PULLBACK"))
        adx=frame.adx.to_numpy(dtype=float)
        pdi=frame.plus_di.to_numpy(dtype=float)
        mdi=frame.minus_di.to_numpy(dtype=float)
        rsi=frame.rsi14.to_numpy(dtype=float)
        hist=frame.macd_hist.to_numpy(dtype=float)
        return [(i,side,stop,quality) for i,side,stop,quality in source
            if (kind=="EMA21_ADX_DI" and np.isfinite([adx[i],pdi[i],mdi[i]]).all()
                and adx[i]>=23. and side*(pdi[i]-mdi[i])>0)
            or (kind=="EMA21_RSI_MACD" and np.isfinite([rsi[i],hist[i]]).all()
                and ((side>0 and 52.<rsi[i]<78. and hist[i]>0)
                     or (side<0 and 22.<rsi[i]<48. and hist[i]<0)))]

    o=frame.open.to_numpy(dtype=float)
    c=frame.close.to_numpy(dtype=float)
    h=frame.high.to_numpy(dtype=float)
    l=frame.low.to_numpy(dtype=float)
    a=frame.atr.to_numpy(dtype=float)
    fast=frame.fema.to_numpy(dtype=float)
    slow=frame.sema.to_numpy(dtype=float)
    rsi=frame.rsi14.to_numpy(dtype=float)
    hist=frame.macd_hist.to_numpy(dtype=float)
    adx=frame.adx.to_numpy(dtype=float)
    pdi=frame.plus_di.to_numpy(dtype=float)
    mdi=frame.minus_di.to_numpy(dtype=float)
    body=(c-o)/np.maximum(h-l,1e-8)
    n=len(frame)
    long=np.zeros(n,dtype=bool)
    short=np.zeros(n,dtype=bool)
    lvl_long=np.full(n,np.nan)
    lvl_short=np.full(n,np.nan)

    if kind=="ADX_DONCHIAN24":
        ceiling=frame.rhi.to_numpy(dtype=float)  # previous 24 high shifted one
        floor=frame.rlo.to_numpy(dtype=float)
        long=(c>ceiling+.08*a)&(adx>=22)&(pdi>mdi)&(body>.22)
        short=(c<floor-.08*a)&(adx>=22)&(mdi>pdi)&(body<-.22)
        lvl_long=ceiling
        lvl_short=floor
    elif kind=="RSI_BOLLINGER20":
        lower=frame.bb_lower.to_numpy(dtype=float)
        upper=frame.bb_upper.to_numpy(dtype=float)
        long=(l<lower)&(c>lower)&(rsi<43)&(body>.12)
        short=(h>upper)&(c<upper)&(rsi>57)&(body<-.12)
        lvl_long=lower
        lvl_short=upper
    elif kind=="MACD_RSI_TREND":
        prev_hist=np.roll(hist,1)
        prev_hist[0]=np.nan
        long=(prev_hist<=0)&(hist>0)&(fast>slow)&(rsi>=52)&(rsi<76)&(body>.1)
        short=(prev_hist>=0)&(hist<0)&(fast<slow)&(rsi<=48)&(rsi>24)&(body<-.1)
        lvl_long=fast
        lvl_short=fast
    elif kind=="KELTNER_SQUEEZE":
        squeeze=frame.squeeze.to_numpy(dtype=bool)
        prev_sq=np.roll(squeeze,1)
        prev_sq[0]=False
        upper=frame.bb_upper.to_numpy(dtype=float)
        lower=frame.bb_lower.to_numpy(dtype=float)
        prev_upper=np.roll(upper,1)
        prev_lower=np.roll(lower,1)
        prev_upper[0]=np.nan
        prev_lower[0]=np.nan
        ku=frame.kc_upper.to_numpy(dtype=float)
        kl=frame.kc_lower.to_numpy(dtype=float)
        long=prev_sq&(c>prev_upper)&(c>ku)&(fast>slow)&(body>.18)
        short=prev_sq&(c<prev_lower)&(c<kl)&(fast<slow)&(body<-.18)
        lvl_long=ku
        lvl_short=kl
    elif kind=="STOCH_REJECTION":
        k=frame.stoch_k.to_numpy(dtype=float)
        d=frame.stoch_d.to_numpy(dtype=float)
        pk=np.roll(k,1)
        pd_=np.roll(d,1)
        pk[0]=pd_[0]=np.nan
        long=(pk<=pd_)&(k>d)&(k>=12)&(k<=42)&(body>.14)&(c>fast-.5*a)
        short=(pk>=pd_)&(k<d)&(k>=58)&(k<=88)&(body<-.14)&(c<fast+.5*a)
        lvl_long=np.minimum(l,fast)
        lvl_short=np.maximum(h,fast)

    out=[]
    eligible=np.flatnonzero(long|short)
    for i in eligible:
        if i < WARM or i>=n-1:
            continue
        side=1 if long[i] else -1
        level=lvl_long[i] if side>0 else lvl_short[i]
        if not np.isfinite([a[i],o[i+1],level,h[i],l[i]]).all() or a[i]<=0:
            continue
        stop=(min(l[i],level)-.15*a[i] if side>0
              else max(h[i],level)+.15*a[i])
        risk=side*(o[i+1]-stop)
        if not .15*a[i]<=risk<=3.*a[i]:
            continue
        score=min(1.,abs(body[i]))
        out.append((int(i),int(side),float(stop),float(score)))
    return out


def run_year(raw, year, tf):
    if raw.empty or raw.index.min()<CUTOFF:
        raise ValueError(f"pre-2025 or missing {year} data")
    src=raw if tf==1 else bars_for(raw,tf)
    data=indicators(prepared(src))
    if data.empty or data.index.min()<CUTOFF:
        raise ValueError("pre-2025 prepared bars")
    base=frozen_ema_events(data,"EMA21_PULLBACK")
    signals={name:build_signals(data,name,baseline=base) for name in MODELS}
    horizon=horizon_bars(tf)
    results=[]
    closed_trades={name:[] for name in MODELS}
    for q,first,last in windows_by_quarter(data,horizon):
        if first is None:
            results.append(dict(quarter=q,status="INSUFFICIENT_BARS"))
            continue
        models={}
        for name in MODELS:
            trades=replay_one(data,signals[name],first,last,tf,PROFILE)
            closed_trades[name].extend(trades)
            models[name]={str(cost):summarize(trades,cost) for cost in COST_GRID}
        results.append(dict(quarter=q,first=str(data.index[first]),
                            last=str(data.index[last-1]),models=models))
        print("INDICATOR_QUARTER",json.dumps(dict(year=year,tf=f"M{tf}",quarter=q,
             baseline=models[BASELINE]["0.8"],
             alternatives={name:models[name]["0.8"]["net_pts"] for name in MODELS[1:]})),
             flush=True)
    result=dict(year=year,tf=f"M{tf}",bars=len(data),
        raw_signals={name:len(items) for name,items in signals.items()},
        valid_quarters=sum("models" in q for q in results),
        quarters=results)
    for name in MODELS:
        # Pool trades from non-overlapping quarters chronologically; drawdown
        # on the entire closing-equity curve, NOT added quarterly drawdowns.
        result.setdefault("summary",{})[name]={
            str(cost):summarize(closed_trades[name],cost) for cost in COST_GRID}
    print("INDICATOR_YEAR",json.dumps(dict(year=year,tf=f"M{tf}",
        signals=result["raw_signals"],summary=result["summary"])),flush=True)
    return result


def rank_models(cases):
    """A conservative SCREEN, not proof of out-of-sample profitability.

    Predefined criteria: positives in both 2025 and 2026 even at stressed
    cost 1.2, PF>1.10 each period, >=100 2025 and >=50 partial-2026 trades.
    Record all models that fail too. Years already seen in other research.
    """
    rows=[]
    for tf in TF_MINUTES:
        yr25=next(c for c in cases if c["tf"]==f"M{tf}" and c["year"]=="2025")
        yr26=next(c for c in cases if c["tf"]==f"M{tf}" and c["year"]=="2026")
        for name in MODELS:
            a=yr25["summary"][name]["0.8"]
            b=yr26["summary"][name]["0.8"]
            ast=yr25["summary"][name]["1.2"]
            bst=yr26["summary"][name]["1.2"]
            screen=(all([
                ast["net_pts"]>0,bst["net_pts"]>0,
                ast["PF"] is not None and ast["PF"]>1.1,
                bst["PF"] is not None and bst["PF"]>1.1,
                a["N"]>=100,b["N"]>=50]))
            rows.append(dict(tf=f"M{tf}",name=name,
                N2025=a["N"],N2026=b["N"],
                net2025=a["net_pts"],net2026=b["net_pts"],
                pf2025=a["PF"],pf2026=b["PF"],
                dd2025=a["mdd_pts"],dd2026=b["mdd_pts"],
                stress2025=ast["net_pts"],stress2026=bst["net_pts"],
                stress_pf2025=ast["PF"],stress_pf2026=bst["PF"],
                conservative_screen_pass=screen))
    return rows


def main():
    raw25,_=load_2025()
    raw26=download()
    if raw25.index.min()<CUTOFF or raw26.index.min()<CUTOFF:
        raise ValueError("2025 lower-bound violated")
    cases=[]
    for tf in TF_MINUTES:
        for year,raw in (("2025",raw25),("2026",raw26)):
            cases.append(run_year(raw,year,tf))
    selection=rank_models(cases)
    result=dict(symbol="XAUUSD",first_allowed_utc=str(CUTOFF),
       last_2026_timestamp=str(raw26.index.max()),
       timeframes=[f"M{x}" for x in TF_MINUTES],
       models=MODELS,runner_profile=PROFILE,
       point_assumed=POINT,costs_roundtrip_usd_oz=COST_GRID,
       indicator_params="ADX14/DI14, RSI14, BB20x2, MACD12-26-9, Stoch14-3, Keltner EMA20 +/- 1.5ATR, Donchian24",
       policy="Keep original untouched, same exits, no tuning during evaluation.",
       cautions=[
          "OHLC only, no broker bid-ask, tick slips, swap, real spread or commissions.",
          "2025 and 2026 were already seen in other XAU research; neither is fresh untouched OOS.",
          "2026 dataset partial; different feeds for 2025 and 2026.",
          "Closed-trade drawdown only; intratrade exposure unmeasured.",
          "Comparisons use same profile but strategy-specific stops and different entry sets.",
          "Selection screens are descriptive, no automated promotion or real orders."],
       cases=cases,comparisons=selection,
       screened_candidates=[x for x in selection if x["conservative_screen_pass"]],
       approved_for_live=False)
    RESULTS.mkdir(parents=True,exist_ok=True)
    (RESULTS/"RESULTADOS_INDICADORES_XAU_2025PLUS.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    lines=["# XAUUSD — laboratório de novos indicadores, M1–M30, 2025+",
       "", "**Pesquisa histórica, não backtest MT5 com ticks do broker.**",
       "Indicadores: "+", ".join(MODELS)+".",
       "Comparação com EMA21_BASE intacta. Entrada no open seguinte a sinal",
       "concluído; stop antes de alvo no OHLC ambíguo, 1/3 em 1R, 1/3 em",
       "1,5R, último 1/3 até stop ou máximo de 96 horas de candles.",
       "Custos 0,8 / 1,2 / 1,6 USD/oz estimados, POINT=0,01 assumido.",
       "2026 é PARCIAL e 2025/2026 já analisados previamente; não é OOS novo.","",
       "| TF | Modelo | N2025 | Net2025 pts | PF2025 | MDD2025 | N2026 parcial | Net2026 pts | PF2026 | MDD2026 | Stress2025 1.2 | Stress2026 1.2 |",
       "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for x in selection:
        vals=(x["tf"],x["name"],x["N2025"],x["net2025"],x["pf2025"],
              x["dd2025"],x["N2026"],x["net2026"],x["pf2026"],
              x["dd2026"],x["stress2025"],x["stress2026"])
        lines.append("| "+" | ".join(str(v) for v in vals)+" |")
    lines += ["","## Indicadores que passaram no filtro conservador experimental",""]
    found=result["screened_candidates"]
    if found:
        for c in found:
            lines.append(f'- {c["tf"]} {c["name"]} — {c["N2025"]} trades em 2025, {c["N2026"]} em 2026 parcial; conferir JSON detalhado.')
    else:
        lines.append("Nenhum. Não promover parâmetros nem reinterpretar perdas como lucro.")
    lines += ["","**Qualquer candidato segue sem homologação real.**",
       "Necessário feed do broker e forward prospectivo independente.",""]
    (RESULTS/"RELATORIO_INDICADORES_XAU_2025PLUS.md").write_text("\n".join(lines))
    print("INDICATORS_COMPLETE",json.dumps(dict(
        cases=len(cases),comparisons=len(selection),
        shortlisted=[(x["tf"],x["name"]) for x in found])),flush=True)


if __name__=="__main__":
    main()
