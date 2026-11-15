#!/usr/bin/env python3
"""Nexus AlphaXAU v1.02 TECHNICAL-PLAN replay, NOT an Ollama backtest.

The actual EA has NO automatic entry and its model is consulted only on click.
Here we TEST TWO EXPLICIT RESEARCH HYPOTHESES inferred from ComputePlan:
 (A) EMA21/55 slope regime transitions, (B) same regime + BOS25 on closed bar.
These are NOT claims about actual model prompts, responses, UI confirmation,
pending entry behavior or fills. Avoid lookahead: signal at CLOSED j, enter OPEN j+1.
"""
from __future__ import annotations
from pathlib import Path
import argparse,json,math,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'robots'/'mt5'/'nexus_vector_retest'))
import numpy as np
import pandas as pd
from research_oos import download as partial_2026

PROJECT=Path(__file__).resolve().parent
OUT=PROJECT/"alphaxau_bt_results"
BASE=Path("thirdparty/gold/XAUUSD/1m/2025")
MODELS=("EMA21_55_REGIME_CHANGE","EMA21_55_BOS25")
COSTS=(0.8,1.2,1.6)
CONTRACT=100. # HYPOTHETICAL ounces/lot
INITIAL=10_000.0

def data_2025():
    paths=sorted(BASE.glob("*/*.csv"))
    if len(paths)<250:raise RuntimeError(f"2025 OHLCV source incomplete {len(paths)} days")
    buf=[]
    for p in paths:
        t=pd.read_csv(p,usecols=["datetime_utc","open","high","low","close","volume"])
        t["datetime"]=pd.to_datetime(t.pop("datetime_utc"),utc=True)
        buf.append(t)
    f=pd.concat(buf,ignore_index=True).sort_values("datetime").set_index("datetime")
    if f.index.has_duplicates:raise RuntimeError("duplicate M1 history")
    for col in ("open","high","low","close","volume"):
        f[col]=pd.to_numeric(f[col],errors="raise")
    return f

def aggregate_m15(raw):
    cnt=raw.close.resample("15min").count()
    f=raw.resample("15min").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"})
    f=f[cnt>=12].dropna().copy()
    c=f.close
    tr=pd.concat((f.high-f.low,(f.high-c.shift(1)).abs(),(f.low-c.shift(1)).abs()),axis=1).max(axis=1)
    f["atr"]=tr.ewm(alpha=1/14,adjust=False).mean()
    f["ema21"]=c.ewm(span=21,adjust=False).mean()
    f["ema55"]=c.ewm(span=55,adjust=False).mean()
    return f

def signals(f):
    # ComputePlan reads a CLOSED bar b[1], EMA21/55, EMA21 six candles back.
    e21=f.ema21;e55=f.ema55;c=f.close
    up=(e21>e55)&(e21>e21.shift(5))&(c>e21)
    down=(e21<e55)&(e21<e21.shift(5))&(c<e21)
    hi25=f.high.shift(1).rolling(25,min_periods=25).max()
    lo25=f.low.shift(1).rolling(25,min_periods=25).min()
    # No machine-learning signal exists in 1.02. These are hypothesis triggers.
    change_up=up&(~up.shift(1,fill_value=False))
    change_down=down&(~down.shift(1,fill_value=False))
    bos_up=up&(c>hi25)
    bos_down=down&(c<lo25)
    def event(bu,se):
        return pd.Series(np.where(bu,1,np.where(se,-1,0)),index=f.index,dtype=np.int8).shift(1,fill_value=0).to_numpy(dtype=np.int8)
    return {
      MODELS[0]:event(change_up,change_down),
      MODELS[1]:event(bos_up,bos_down)
    }

def evaluate(f,signal,cost,model):
    o=f.open.to_numpy(dtype=float)
    h=f.high.to_numpy(dtype=float)
    l=f.low.to_numpy(dtype=float)
    c=f.close.to_numpy(dtype=float)
    a=f.atr.to_numpy(dtype=float)
    ts=f.index
    last=-1
    equity=INITIAL;highwater=INITIAL;maxdd=0.
    day=None;daystart=INITIAL;daily_lock=0;rej_minlot=0
    trades=[];raw_count=int(np.count_nonzero(signal))
    i=110
    while i<len(f)-1:
        date=ts[i].date()
        if date!=day:
            day=date;daystart=equity
        if signal[i]==0:
            i+=1
            continue
        if equity<=0 or equity<=daystart*.98:
            daily_lock+=1
            i+=1
            continue
        side=int(signal[i])
        ep=float(o[i]);dist=1.50*float(a[i-1])   # InpStopATR=1.50
        if not np.isfinite(dist) or dist<=0:
            i+=1
            continue
        stop=ep-side*dist;target=ep+side*1.80*dist
        budget=equity*.005                   # InpRiskPerTradePct=0.50
        volume=math.floor(min(.50,budget/(CONTRACT*dist))/.01+1e-9)*.01
        if volume<.01:
            rej_minlot+=1
            i+=1
            continue
        # No Bid/Ask ticks; $ cost per ounce *100oz/lot*lot at close.
        # No slippage, swap, actual margin check (broker-dependent).
        ex=len(f)-1;xp=float(c[ex]);reason="END"
        for k in range(i,len(f)):
            if (l[k]<=stop if side==1 else h[k]>=stop):
                xp=min(float(o[k]),stop) if side==1 else max(float(o[k]),stop)
                ex=k;reason="SL";break
            if (h[k]>=target if side==1 else l[k]<=target):
                xp=target;ex=k;reason="TP";break
        pnl=(side*(xp-ep)-cost)*CONTRACT*volume
        equity+=pnl
        highwater=max(highwater,equity)
        maxdd=max(maxdd,(highwater-equity)/highwater)
        trades.append({"entry_time":str(ts[i]),"exit_time":str(ts[ex]),"side":side,
          "entry":round(ep,3),"stop":round(stop,3),"target":round(target,3),
          "exit":round(xp,3),"exit_type":reason,"lot":round(volume,2),
          "net_usd":round(pnl,2),"net_R":round(pnl/(dist*CONTRACT*volume),4)})
        # Advance calendar to AFTER the actual exit, so balance/daily risk
        # cannot be applied on bars that occur before a future close.
        last=ex
        i=ex+1
    prof=np.array([t["net_usd"] for t in trades])
    wins=float(prof[prof>0].sum()) if len(prof) else 0.
    losses=float(-prof[prof<0].sum()) if len(prof) else 0.
    months={}
    for t in trades:
        key=t["entry_time"][:7]
        if key not in months:months[key]={"N":0,"net_usd":0.}
        months[key]["N"]+=1;months[key]["net_usd"]+=t["net_usd"]
    for v in months.values():v["net_usd"]=round(v["net_usd"],2)
    losses_in_row=0;max_consecutive_losses=0
    for t in trades:
        losses_in_row=losses_in_row+1 if t["net_usd"]<0 else 0
        max_consecutive_losses=max(max_consecutive_losses,losses_in_row)
    summary={"model":model,"cost_usd_per_oz":cost,"bars":len(f),"raw_signal_bars":raw_count,
      "trades":len(trades),"win_pct":round(float((prof>0).mean()*100),2) if len(prof) else 0.,
      "net_usd":round(equity-INITIAL,2),"net_pct":round((equity-INITIAL)/INITIAL*100,2),
      "profit_factor":round(wins/losses,3) if losses>0 else None,
      "drawdown_closed_pct":round(maxdd*100,2),"max_consecutive_losses":max_consecutive_losses,
      "min_lot_rejected":rej_minlot,"new_entry_daily_locked":daily_lock,
      "months":months}
    return summary,trades

def synthetic_test():
    rng=np.random.default_rng(116)
    ix=pd.date_range("2025-02-02",periods=1400,freq="15min",tz="UTC")
    c=3000+np.cumsum(rng.normal(0,1.0,len(ix)))
    op=np.r_[c[0],c[:-1]]
    f=pd.DataFrame({"open":op,"high":np.maximum(op,c)+.3,"low":np.minimum(op,c)-.3,"close":c},index=ix)
    tr=pd.concat((f.high-f.low,(f.high-f.close.shift(1)).abs(),(f.low-f.close.shift(1)).abs()),axis=1).max(axis=1)
    f["atr"]=tr.ewm(alpha=1/14,adjust=False).mean()
    f["ema21"]=f.close.ewm(span=21,adjust=False).mean()
    f["ema55"]=f.close.ewm(span=55,adjust=False).mean()
    a=signals(f)
    mutant=f.copy()
    mutant.loc[ix[850]:,["close","high","low"]]+=500.
    mutant["ema21"]=mutant.close.ewm(span=21,adjust=False).mean()
    mutant["ema55"]=mutant.close.ewm(span=55,adjust=False).mean()
    b=signals(mutant)
    for m in MODELS:
        assert np.array_equal(a[m][:851],b[m][:851]),f"lookahead in {m}"
        assert set(np.unique(a[m])).issubset({-1,0,1})
        r,t=evaluate(f,a[m],1.2,m)
        assert r["trades"]>=0 and math.isfinite(r["net_usd"])
        assert all(x["lot"]>=.01 and x["lot"]<=.5 for x in t)
    print("ALPHA_UNIT_TESTS_PASS",len(MODELS),"causal signal models",flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--test",action="store_true")
    a=p.parse_args()
    synthetic_test()
    if a.test:return
    records=[];sources=[];alltrades={}
    for year in ("2025","2026_partial"):
        raw=data_2025() if year=="2025" else partial_2026()
        f=aggregate_m15(raw)
        s=signals(f)
        source={"year":year,"raw_minutes":len(raw),"M15_bars":len(f),"first":str(f.index.min()),"last":str(f.index.max())}
        sources.append(source)
        print("ALPHA_SOURCE",json.dumps(source),flush=True)
        for model in MODELS:
            for cost in COSTS:
                summary,trades=evaluate(f,s[model],cost,model)
                rec={"period":year,**summary}
                records.append(rec)
                alltrades[f"{year}_{model}_cost{cost}"]=trades
                print("ALPHA_RESULT",json.dumps(rec),flush=True)
    OUT.mkdir(parents=True,exist_ok=True)
    report={"name":"AlphaXAU technical plan signal proxy 1.02","valid_mt5_backtest":False,
      "ollama_tested":False,"underlying_EA_automatic_trades":0,
      "proposal_not_implemented_in_EA":["EMA regime change","EMA alignment + BOS25"],
      "source":sources,"results":records,"all_closed_trades":alltrades,
      "model_assumptions":{"symbol":"XAUUSD","tf":"M15","initial_usd":INITIAL,
        "contract_oz_per_lot":CONTRACT,"min_lot":0.01,"lot_step":0.01,
        "risk_equity_fraction":0.005,"stop_atr":1.5,"target_R":1.8,
        "daily_new_entry_brake_pct":2.0,"cost_usd_per_ounce":COSTS,
        "one_position_at_a_time":True,"last_closed_bar":True},
      "limitations":["Current EA has no auto-entry, Ollama is click-triggered text advice",
        "MT5 Strategy Tester blocks WebRequest, so this is NOT an Ollama AI performance test",
        "No historical Ollama prompts/responses/timestamped operator decisions available",
        "OHLC midpoint fills and hypothetical roundtrip costs, not broker real ticks",
        "Contract size and volume step approximated; margin/equity mark-to-market not simulated",
        "EMA and ATR differ slightly from MT5 warm-up; broker spreads, swap and slippage omitted",
        "Not a source of trading profitability or model probabilities"],
      "approved_live":False}
    (OUT/"results.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    lines=["# AlphaXAU v1.02 — replay de regras técnicas, **NÃO da IA Ollama**",
           "","## Importante",
           "No EA atual, OnTick() não abre ordens. A IA não gera instruções de execução nem é consultada pelo Strategy Tester. As entradas abaixo são hipóteses explícitas **criadas para pesquisa** a partir de ComputePlan(): (A) mudança de regime EMA21/55 + inclinação EMA21; (B) alinhamento de tendência + rompimento suporte/resistência anteriores de 25 candles.",
           "","## Hipóteses e parâmetros","- XAUUSD M15, 2025 completo e 2026 parcial; entrada no candle seguinte, apenas candles fechados",
           "- SL1,5 ATR14, TP1,8R, lote pelo risco 0,5%, banco US$10.000, 100oz por lote, mínimo 0,01 lote, cap0,50",
           "- Custos hipotéticos de 0,8/1,2/1,6 USD por onça ida+volta. Se candle toca SL e TP, conta SL primeiro",
           "","## Comparação",
           "| Período | Regra de entrada | Custo/oz | Trades | Lucro simulado USD | PF | Acerto | DD fechado |",
           "|---|---|---:|---:|---:|---:|---:|---:|"]
    for r in records:
        lines.append(f'| {r["period"]} | {r["model"]} | {r["cost_usd_per_oz"]} | {r["trades"]} | {r["net_usd"]:.2f} | {r["profit_factor"]} | {r["win_pct"]}% | {r["drawdown_closed_pct"]}% |')
    lines+=["","Resultados NÃO são do Llama: a imagem anterior era apenas uma ilustração de interface. A porcentagem de probabilidade vista na imagem não veio de um backtest. Ainda falta EA autônomo com sinais explícitos, compilação MT5 e ticks reais de corretora.","",
            "Relatório produzido sem otimização dos parâmetros."]
    (OUT/"REPORT_PTBR.md").write_text("\n".join(lines)+"\n")
    print("ALPHA_DONE",json.dumps({"rows":len(records),"sources":len(sources)}),flush=True)

if __name__=="__main__":
    main()
