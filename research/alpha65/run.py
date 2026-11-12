#!/usr/bin/env python3
"""ALPHA65 independent hypotheses, causal 1m+5m+15m+30m XAUUSD OHLC replay.

NOT a MetaTrader or broker-tick backtest. Spread schedule is ASSUMED not observed.
All signals come from fully closed candles; next M1 open is the first possible fill.
No martingale, grid, intrabar optimism, silent missing months or curve fitting on holdout.
"""
from __future__ import annotations
import hashlib,io,json,math,urllib.request
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"results"
URL=("https://raw.githubusercontent.com/getdata-finance/"
     "xauusd-1m-ohlcv-metals-historical-data/"
     "adcd99e7e0abee51e9a5eef123935e68a8d8aa30/XAUUSD_1m.csv")
SHA="a587597bbf88c2d868a00a4e0019cd705cee6ca4f20b0485d6b745f19fcc8225"
TRAIN=["2026-04","2026-05"]
VALID=["2026-06"]
HOLDOUT=["2026-07","2026-08"]  # already examined by earlier Nexus research; NOT virgin
MONTHS=TRAIN+VALID+HOLDOUT
MIN_TRADES=159
WIN_MIN=.65
PF_MIN=1.30
START_CASH=10000.
RISK=.0075
MIN_OZ=1.0       # ASSUMED broker 0.01 lots, 100 oz per lot
VOL_STEP_OZ=1.0
CONTRACT_OZ=100.
LEVERAGE=100.
MAX_HOLD_M1=75
COMMISSION_PER_OZ_ROUND=0.12  # hypothetical
SLIPPAGE_PER_SIDE_OZ=.10      # hypothetical price distance each side
SPREAD_STRESS=2.
SEED=20261112

def fetch():
    req=urllib.request.Request(URL,headers={"User-Agent":"Alpha65-Lab/1.0"})
    with urllib.request.urlopen(req,timeout=140) as res: content=res.read()
    actual=hashlib.sha256(content).hexdigest()
    if actual!=SHA: raise ValueError("XAUUSD source SHA mismatch: "+actual)
    df=pd.read_csv(io.BytesIO(content),parse_dates=["datetime"])
    df["datetime"]=pd.to_datetime(df["datetime"],utc=True)
    for k in ("open","high","low","close","volume"):
        df[k]=pd.to_numeric(df[k],errors="raise")
    if df["datetime"].duplicated().any():raise ValueError("Duplicate M1 minute")
    df=df.sort_values("datetime").set_index("datetime")
    if not ((df.high>=df[["open","close","low"]].max(axis=1))&
            (df.low<=df[["open","close","high"]].min(axis=1))&
            (df.volume>=0)).all():raise ValueError("Invalid XAUUSD OHLCV")
    return df

def aggregate(d,minutes):
    if minutes==1:return d
    counts=d.close.resample(str(minutes)+"min").count()
    x=d.resample(str(minutes)+"min").agg(
        {"open":"first","high":"max","low":"min","close":"last","volume":"sum"})
    return x[counts==minutes].dropna()

def enriched(d):
    x=d.copy()
    c=x.close
    prev=c.shift(1)
    tr=pd.concat([x.high-x.low,(x.high-prev).abs(),(x.low-prev).abs()],axis=1).max(axis=1)
    x["atr"]=tr.ewm(alpha=1/14,adjust=False).mean()
    x["ema21"]=c.ewm(span=21,adjust=False).mean()
    x["ema55"]=c.ewm(span=55,adjust=False).mean()
    x["ema200"]=c.ewm(span=200,adjust=False).mean()
    x["rvol"]=x.volume/x.volume.shift(1).rolling(20,min_periods=20).mean().replace(0,np.nan)
    x["prevhi"]=x.high.shift(1).rolling(12,min_periods=12).max()
    x["prevlo"]=x.low.shift(1).rolling(12,min_periods=12).min()
    x["prevhi24"]=x.high.shift(1).rolling(24,min_periods=24).max()
    x["prevlo24"]=x.low.shift(1).rolling(24,min_periods=24).min()
    x["prevclose"]=c.shift(1)
    x["prevema21"]=x.ema21.shift(1)
    x["mom5"]=c-c.shift(5)
    return x

def clip(z):return float(max(0,min(1,z)))

def emit_signal(events,x,i,side,model,tf,quality,level=None):
    r=x.iloc[i];a=float(r.atr)
    if not np.isfinite(a) or a<=0:return
    when=x.index[i]+pd.Timedelta(minutes=tf)
    # Current bar does NOT participate in next-bar execution.
    stop=float(min(r.low,level) - .10*a) if side>0 and level is not None else (
         float(max(r.high,level)+.10*a) if side<0 and level is not None else (
         float(r.low-.10*a) if side>0 else float(r.high+.10*a)))
    events.append({"signal_time":str(x.index[i]),"entry_time":when,
                   "direction":int(side),"model":model,"timeframe":tf,
                   "score":round(float(quality),4),"stop":stop,
                   "atr":a})

def signals_for(x,tf):
    events=[]
    state=None
    for i in range(220,len(x)-1):
        r=x.iloc[i]
        vals=[r.atr,r.rvol,r.ema21,r.ema55,r.prevhi,r.prevlo,
              r.prevhi24,r.prevlo24,r.prevclose,r.prevema21]
        if not all(np.isfinite(v) for v in vals):continue
        a=float(r.atr);rr=float(r.high-r.low)
        if a<=0 or rr<=0:continue
        body=(float(r.close)-float(r.open))/rr
        lower_wick=(min(r.open,r.close)-r.low)/rr
        upper_wick=(r.high-max(r.open,r.close))/rr
        vscore=clip(r.rvol/1.5)
        mscore=clip(abs(r.mom5)/max(2*a,1e-12))
        # 1) Sweep: level from PREVIOUS 12 confirmed bars; current candle rejects it.
        if r.low<r.prevlo-.08*a and r.close>r.prevlo+.02*a and body>.10 and lower_wick>.22:
            score=.30*clip(lower_wick/.65)+.25*clip((r.close-r.prevlo)/a)+.20*clip(body/.7)+.15*vscore+.10*mscore
            if score>=.40:emit_signal(events,x,i,1,"SWEEP",tf,score,float(r.prevlo))
        elif r.high>r.prevhi+.08*a and r.close<r.prevhi-.02*a and body<-.10 and upper_wick>.22:
            score=.30*clip(upper_wick/.65)+.25*clip((r.prevhi-r.close)/a)+.20*clip(-body/.7)+.15*vscore+.10*mscore
            if score>=.40:emit_signal(events,x,i,-1,"SWEEP",tf,score,float(r.prevhi))
        # 2) EMA pullback: candle crosses EMA21 on trend side and direction of 55.
        ema_up=r.ema21>r.ema55 and r.ema55>r.ema200
        ema_dn=r.ema21<r.ema55 and r.ema55<r.ema200
        if ema_up and r.low<r.ema21-.05*a and r.close>r.ema21+.03*a and body>.18:
            score=.30*clip((r.ema21-r.ema55)/a)+.25*clip(body/.8)+.20*clip((r.close-r.ema21)/a)+.15*vscore+.10*mscore
            if score>=.4:emit_signal(events,x,i,1,"EMA_PULLBACK",tf,score,float(r.ema21))
        elif ema_dn and r.high>r.ema21+.05*a and r.close<r.ema21-.03*a and body<-.18:
            score=.30*clip((r.ema55-r.ema21)/a)+.25*clip(-body/.8)+.20*clip((r.ema21-r.close)/a)+.15*vscore+.10*mscore
            if score>=.4:emit_signal(events,x,i,-1,"EMA_PULLBACK",tf,score,float(r.ema21))
        # 3) Structure break, then later retest of the PREVIOUS level; never
        # stamp signal back on breakout bar. Trade only after retest closes.
        if state is not None:
            age=i-state["i"]
            side=state["side"];lev=state["level"]
            if age>7:state=None
            elif age>=1:
                touched=(r.low<=lev+.15*a if side>0 else r.high>=lev-.15*a)
                recovered=(r.close>lev+.03*a and body>.10 if side>0 else r.close<lev-.03*a and body<-.10)
                if touched and recovered:
                    score=.35*state["quality"]+.30*clip(abs(r.close-lev)/(.7*a))+.20*clip(abs(body)/.7)+.15*vscore
                    if score>=.4:emit_signal(events,x,i,side,"BOS_RETEST",tf,score,lev)
                    state=None
                elif (r.close<lev-.6*a if side>0 else r.close>lev+.6*a):
                    state=None
        # Breakout replaces old stale pending only if new regime clearer.
        if r.close>r.prevhi24+.15*a and body>.30:
            state={"side":1,"level":float(r.prevhi24),"i":i,
                   "quality":clip((r.close-r.prevhi24)/(.85*a))}
        elif r.close<r.prevlo24-.15*a and body<-.30:
            state={"side":-1,"level":float(r.prevlo24),"i":i,
                   "quality":clip((r.prevlo24-r.close)/(.85*a))}
    return events

def assumed_spread(utc_timestamp,atr_m1,level=1.0):
    """NOT recorded bid-ask; session + volatility schedule for a stress test."""
    h=utc_timestamp.hour
    base=(.65 if 7<=h<17 else .95 if 1<=h<7 else 1.60)
    return level*(base+min(.8,max(0,float(atr_m1)-.8)*.12))

def trade_replay(m1,events,allowed_models,tf_allowed,spread_stress=1.0):
    ix=m1.index
    x=m1
    arr={z:x[z].to_numpy() for z in ("open","high","low","close")}
    # ATR for estimated intraday spread scaling uses only data up to prior bar.
    a=enriched(x).atr.shift(1).bfill().to_numpy()
    locate={ts:i for i,ts in enumerate(ix)}
    selected=[]
    for e in events:
        if e["model"] not in allowed_models or e["timeframe"] not in tf_allowed:continue
        j=locate.get(e["entry_time"])
        if j is None or j<1:continue
        selected.append((j,e))
    # Stronger quality first if multiple confirm at same minute.
    selected.sort(key=lambda pair:(pair[0],-pair[1]["score"],pair[1]["model"]))
    seen=set();equity=START_CASH;peak=START_CASH;maxdd=0.
    trades=[];busy=-1;prev_entry=None
    for j,e in selected:
        if j<=busy:continue
        if (j,e["model"],e["direction"]) in seen:continue
        seen.add((j,e["model"],e["direction"]))
        d=e["direction"];entry=float(arr["open"][j])
        # Every signal's candidate stop uses only the CLOSED signal bar.
        stop=e["stop"];risk=d*(entry-stop)
        if risk<=.08 or risk>4.0*e["atr"]:continue
        spread=assumed_spread(ix[j],a[j],spread_stress)
        if spread>risk*.65:continue
        qty_raw=equity*RISK/(risk+spread+2*SLIPPAGE_PER_SIDE_OZ)
        qty=math.floor(qty_raw/VOL_STEP_OZ)*VOL_STEP_OZ
        if qty<MIN_OZ:continue
        # Margin model with assumed leverage; not actual broker spec.
        margin=qty*entry/LEVERAGE
        if margin>equity*.75:continue
        target=entry+d*1.20*risk
        max_index=min(len(ix)-1,j+min(MAX_HOLD_M1,int(16*e["timeframe"])))
        reason="OPEN";exit_mid=None;finish=None
        for k in range(j,max_index+1):
            oo=float(arr["open"][k]);hh=float(arr["high"][k]);ll=float(arr["low"][k])
            if (oo<=stop if d>0 else oo>=stop):
                exit_mid=oo;finish=k;reason="GAP_SL";break
            if (ll<=stop if d>0 else hh>=stop):
                exit_mid=stop;finish=k;reason="SL";break
            if (hh>=target if d>0 else ll<=target):
                exit_mid=target;finish=k;reason="TP";break
            if k==max_index:
                exit_mid=float(arr["close"][k]);finish=k;reason="TIME";break
        if finish is None:continue
        # Round trip execution assumptions; spread estimated independently
        # at entry and exit using time/volatility, plus slippage and commissions.
        spread_exit=assumed_spread(ix[finish],a[finish],spread_stress)
        cost=(spread+spread_exit)/2 + 2*SLIPPAGE_PER_SIDE_OZ + COMMISSION_PER_OZ_ROUND
        gross=d*(exit_mid-entry)*qty
        pnl=(d*(exit_mid-entry)-cost)*qty
        equity+=pnl
        peak=max(equity,peak);maxdd=max(maxdd,(peak-equity)/peak)
        trades.append({"entry":str(ix[j]),"exit":str(ix[finish]),
                       "month":str(ix[finish])[:7],"model":e["model"],"tf":"M"+str(e["timeframe"]),
                       "side":"BUY" if d>0 else "SELL","reason":reason,
                       "quality":e["score"],"volume_lots":round(qty/CONTRACT_OZ,3),
                       "risk_usd":round((risk+spread+2*SLIPPAGE_PER_SIDE_OZ)*qty,2),
                       "cost_usd":round(cost*qty,3),"gross_usd":round(gross,3),
                       "pnl_usd":round(pnl,3),"pnl_r":round(pnl/max(1e-9,(risk+spread+2*SLIPPAGE_PER_SIDE_OZ)*qty),4),
                       "equity_usd":round(equity,2),"spread_estimate_usd_oz":round(spread,3)})
        busy=finish
        if equity<START_CASH*.3:break
    return trades,maxdd,equity

def metrics(trades):
    wins=[x for x in trades if x["pnl_usd"]>0];losers=[x for x in trades if x["pnl_usd"]<0]
    gains=sum(x["pnl_usd"] for x in wins);loss=-sum(x["pnl_usd"] for x in losers)
    n=len(trades);net=sum(x["pnl_usd"] for x in trades)
    equity=START_CASH;peak=equity;dd=0.
    for x in trades:
        equity+=x["pnl_usd"];peak=max(peak,equity);dd=max(dd,(peak-equity)/peak)
    month=defaultdict(list)
    for t in trades:month[t["month"]].append(t)
    monthly=[]
    for m in MONTHS:
        sub=month.get(m,[])
        count=len(sub);green=sum(t["pnl_usd"]>0 for t in sub)
        gp=sum(max(0,t["pnl_usd"]) for t in sub)
        gl=-sum(min(0,t["pnl_usd"]) for t in sub)
        monthly.append({"month":m,"n":count,"green":green,
                        "win_pct":round(100*green/count,2) if count else None,
                        "pf":round(gp/gl,3) if gl else None,
                        "pnl_usd":round(sum(t["pnl_usd"] for t in sub),2),
                        "pass":bool(count>=MIN_TRADES and count and green/count>=WIN_MIN
                                    and gl>0 and gp/gl>=PF_MIN and gp>gl)})
    return {"trades":n,"green":len(wins),"red":len(losers),
            "hit_pct":round(100*len(wins)/n,2) if n else None,
            "pf":round(gains/loss,3) if loss else None,
            "pnl_usd":round(net,2),"mdd_pct":round(100*dd,2),
            "expectancy_usd":round(net/n,3) if n else None,
            "monthly":monthly}

def mc(trades,rep=400):
    rng=np.random.default_rng(SEED)
    vals=np.array([t["pnl_r"] for t in trades],dtype=float)
    if not len(vals):return None
    outcomes=[]
    for _ in range(rep):
        v=rng.choice(vals,len(vals),replace=True)
        outcomes.append((float(np.sum(v)),float(max(0.,max(np.maximum.accumulate(np.r_[0.,np.cumsum(v)])-np.r_[0.,np.cumsum(v)])))))
    return {"bootstrap_repetitions":rep,"sum_r_p05":round(float(np.percentile([x[0] for x in outcomes],5)),2),
            "sum_r_p50":round(float(np.percentile([x[0] for x in outcomes],50)),2),
            "dd_r_p95":round(float(np.percentile([x[1] for x in outcomes],95)),2)}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    m1=fetch()
    missing={m:len(m1[m1.index.strftime("%Y-%m")==m]) for m in MONTHS}
    if any(n<18000 for n in missing.values()):
        raise ValueError("No complete months for historical research: "+str(missing))
    if not (m1.index.is_monotonic_increasing):raise ValueError("Unsorted")
    all_events=[];counts={}
    for minutes in (1,5,15,30):
        bars=enriched(aggregate(m1,minutes))
        events=signals_for(bars,minutes)
        counts["M"+str(minutes)]=len(events)
        all_events.extend(events)
        print("SIGNALS",minutes,len(events),flush=True)
    families=("SWEEP","BOS_RETEST","EMA_PULLBACK")
    scenarios=[]
    for model in families:
        for tf in (1,5,15,30):
            tag=model+"_M"+str(tf)
            trades,dd,eq=trade_replay(m1,all_events,{model},{tf},1.0)
            scenarios.append({"name":tag,"models":[model],"tfs":[tf],
                              "summary":metrics(trades),"num":len(trades),"trades":trades})
            print("BASE",tag,"N",len(trades),"PF",scenarios[-1]["summary"]["pf"],flush=True)
    # Several strategies in one EA, but one real XAUUSD position across all modules.
    for ids,tfs,tag in [
        (("SWEEP","EMA_PULLBACK"),(1,5),"SWEEP_EMA_M1M5"),
        (families,(1,5,15),"MULTI_3MODELS_M1M5M15"),
        (families,(1,5,15,30),"MULTI_3MODELS_ALL_TF"),
        (("SWEEP","BOS_RETEST"),(1,5),"SWEEP_BOS_M1M5")]:
        trades,dd,eq=trade_replay(m1,all_events,set(ids),set(tfs),1.)
        scenarios.append({"name":tag,"models":ids,"tfs":tfs,
                          "summary":metrics(trades),"num":len(trades),"trades":trades})
        print("BASE",tag,"N",len(trades),"PF",scenarios[-1]["summary"]["pf"],flush=True)
    # DO NOT tune on the test. Rank on Apr-May only. June validation,
    # July-Aug previously studied => corroboration, NOT virgin final holdout.
    train=lambda s:[x for x in s["trades"] if x["month"] in TRAIN]
    val=lambda s:[x for x in s["trades"] if x["month"] in VALID]
    test=lambda s:[x for x in s["trades"] if x["month"] in HOLDOUT]
    for s in scenarios:
        s["train"]=metrics(train(s));s["validation"]=metrics(val(s))
        s["test"]=metrics(test(s))
        s["montecarlo"]=mc(test(s))
        s["test_stress"]=None
    def selection(s):
        tr=s["train"];monthly=tr["monthly"]
        relevant=[q for q in monthly if q["month"] in TRAIN]
        good=all(q["pass"] for q in relevant)
        return (int(good),int((tr["pf"] or 0)>=PF_MIN),
                min((x["n"] for x in relevant),default=0),
                tr["pnl_usd"])
    scenarios.sort(key=selection,reverse=True)
    best=scenarios[0]
    # Re-run selected hypothesis at higher *modeled* variable spread cost,
    # WITHOUT re-selecting or using validation/test to optimize.
    stressed,_,_=trade_replay(m1,all_events,set(best["models"]),set(best["tfs"]),SPREAD_STRESS)
    best["test_stress"]=metrics([t for t in stressed if t["month"] in HOLDOUT])
    evidence={
        "project":"ALPHA65","classification":"RESEARCH_NOT_MT5_BACKTEST",
        "source":{"uri":URL,"sha256":SHA,"minutely_rows":len(m1),
                  "date_first":str(m1.index.min()),"date_last":str(m1.index.max())},
        "months":{"train":TRAIN,"validation":VALID,"historically_seen_holdout":HOLDOUT,
                  "minute_rows":missing},
        "broker_assumptions":{"starting_balance_usd":START_CASH,"risk_fraction":RISK,
             "contract_oz_per_lot":CONTRACT_OZ,"volume_min_lot":.01,
             "volume_step_lot":.01,"leverage_assumed":LEVERAGE,
             "round_trip_commission_usd_per_oz":COMMISSION_PER_OZ_ROUND,
             "slippage_usd_per_oz_each_side":SLIPPAGE_PER_SIDE_OZ,
             "spread_type":"SIMULATED variable spread by UTC session + ATR, NOT observed bid/ask"},
        "signals":counts,"scenarios_scanned":len(scenarios),
        "criteria":{"min_win_rate_month":65,"min_trades_per_full_month":159,
                    "min_profit_factor":PF_MIN,"max_dd_target_pct":15},
        "scenarios":[{k:v for k,v in s.items() if k!="trades"} for s in scenarios],
        "selected_by_training_only":best["name"],
        "approved":False,
        "important":["6-month M1 source cannot validate 12 months true OOS.",
           "July/Aug previously examined by other Nexus experiments, not a clean virgin holdout.",
           "Spread and slippage are proxy estimates; no historical bid-ask/tick execution.",
           "Model-specific price path is M1 OHLC; same-bar ambiguity SL before TP.",
           "Do not promote to a trading account without broker MT5 Strategy Tester."]
    }
    best_test=best["test"]
    pass_train=all(q["pass"] for q in best["train"]["monthly"] if q["month"] in TRAIN)
    pass_validation=all(q["pass"] for q in best["validation"]["monthly"] if q["month"] in VALID)
    pass_test=all(q["pass"] for q in best_test["monthly"] if q["month"] in HOLDOUT)
    evidence["approved"]=False # even if proxy passes, no 12mo virgin OOS and broker ticks
    evidence["screen_pass_train"]=pass_train
    evidence["screen_pass_validation"]=pass_validation
    evidence["screen_pass_test"]=pass_test
    (OUT/"RESULTS.json").write_text(json.dumps(evidence,indent=2,ensure_ascii=False,default=lambda x:float(x) if isinstance(x,np.generic) else str(x))+"\n")
    with (OUT/"TRADES.csv").open("w",newline="",encoding="utf-8") as f:
        import csv
        fields=list(best["trades"][0].keys()) if best["trades"] else []
        if fields:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(best["trades"])
    rows=["# ALPHA65 — backtest exploratório da auditoria","",
      "**Status: META NÃO ATINGIDA.** Replay Python em XAUUSD OHLC, NÃO MT5 ticks.",
      f"Dados: {len(m1)} barras M1, SHA256 verificado: {SHA}, {m1.index.min()} até {m1.index.max()}.",
      "Custos: spread VARIÁVEL SIMULADO por horário+ATR, slippage 0,10 USD/oz por lado, comissão hipotética 0,12 USD/oz por round trip.",
      "Assunções: contrato 100 oz/lote, volume mínimo 0,01 lote, step 0,01 lote, alavancagem 100x, banca US$10.000, risco planejado 0,75%/operação.",
      "**Não são condições reais da corretora; 12 meses OOS e ticks bid/ask não disponíveis nesta execução.**",
      "Treino abril–maio; validação junho; julho–agosto examinados anteriormente (não holdout virgem).","",
      "| Candidato | Timeframe | Total de trades | Acerto total | PF total | Resultado USD | MDD % | Menor mês (todos) | PF Julho/Ago |",
      "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for s in scenarios:
        z=s["summary"];monthly=z["monthly"]
        minmonthly=min(q["n"] for q in monthly)
        rows.append("| "+" | ".join([s["name"],"+".join("M"+str(i) for i in s["tfs"]),
             str(z["trades"]),str(z["hit_pct"]),str(z["pf"]),str(z["pnl_usd"]),
             str(z["mdd_pct"]),str(minmonthly),str(s["test"]["pf"])])+" |")
    rows+=["","## Melhor por critérios do treino (NÃO aprovado): "+best["name"],"",
           "| Mês | Janela | N | GREEN % | PF | Saldo USD | Passou metas |",
           "|---|---|---:|---:|---:|---:|---|"]
    for m in best["summary"]["monthly"]:
        stage="Treino" if m["month"] in TRAIN else "Validação" if m["month"] in VALID else "Examinado"
        rows.append("| "+" | ".join([m["month"],stage,str(m["n"]),str(m["win_pct"]),
                   str(m["pf"]),str(m["pnl_usd"]),str(m["pass"])])+" |")
    rows+=["","## Stress e Monte Carlo",
           "Stress 2x spread variável: "+json.dumps(best["test_stress"],ensure_ascii=False,default=str),
           "Bootstrap retornos do período final: "+json.dumps(best["montecarlo"],ensure_ascii=False,default=str),
           "Aviso: bootstrap IID não preserva regimes nem serial correlation, e não demonstra robustez.",
           "Arquivo TRADES.csv contém somente trades do candidato escolhido no treino.",
           "Nenhuma alteração em VWAP, ATLAS, robôs preservados, main ou execução real. Critério final exige MT5 tick data bid/ask e pelo menos 12 meses OOS, ainda não satisfeitos.",""]
    (OUT/"REPORT.md").write_text("\n".join(rows),encoding="utf-8")
    print("ALPHA65_DONE",json.dumps({"selected":best["name"],
         "all":best["summary"],"train":best["train"],"validation":best["validation"],
         "test":best_test,"count":len(scenarios)},ensure_ascii=False,default=str),flush=True)
if __name__=="__main__":main()
