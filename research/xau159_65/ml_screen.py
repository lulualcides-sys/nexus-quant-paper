#!/usr/bin/env python3
"""Experimental XAUUSD 65% win & >=159 closed trades per full month.
No compiled EA; causal ML features and labels only from future outcomes during TRAIN.
Fit Apr-May 2026; threshold selection June; single untouched OOS July-August.
No future candle enters prediction; deterministic OHLC stop-first, fixed cost 0.60 USD/oz.
"""
from __future__ import annotations
import json,hashlib,io,urllib.request,math
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
OUT=Path(__file__).resolve().parent/"results_ml"
URL=("https://raw.githubusercontent.com/getdata-finance/xauusd-1m-ohlcv-metals-historical-data/"
"adcd99e7e0abee51e9a5eef123935e68a8d8aa30/XAUUSD_1m.csv")
SHA="a587597bbf88c2d868a00a4e0019cd705cee6ca4f20b0485d6b745f19fcc8225"
COST=0.60
HOLD=16
TP_ATR=1.10
SL_ATR=1.10
COOLDOWN=2
def load():
    req=urllib.request.Request(URL,headers={"User-Agent":"NexusQuant-ML-15965/1"})
    with urllib.request.urlopen(req,timeout=140) as response: b=response.read()
    if hashlib.sha256(b).hexdigest()!=SHA:raise ValueError("Data SHA not pinned")
    d=pd.read_csv(io.BytesIO(b),parse_dates=["datetime"])
    d["datetime"]=pd.to_datetime(d.datetime,utc=True)
    d=d.drop_duplicates("datetime").sort_values("datetime").set_index("datetime")
    for k in ("open","high","low","close","volume"):d[k]=pd.to_numeric(d[k])
    if not ((d.high>=d[["open","low","close"]].max(axis=1))&
            (d.low<=d[["open","high","close"]].min(axis=1))).all():raise ValueError("Invalid OHLC")
    return d
def features(d):
    c=d.close
    high=d.high;low=d.low
    pr=c.shift(1)
    tr=pd.concat((high-low,(high-pr).abs(),(low-pr).abs()),axis=1).max(axis=1)
    atr=tr.ewm(alpha=1/14,adjust=False).mean()
    ema8=c.ewm(span=8,adjust=False).mean()
    ema21=c.ewm(span=21,adjust=False).mean()
    ema55=c.ewm(span=55,adjust=False).mean()
    up=c.diff().clip(lower=0).ewm(alpha=1/5,adjust=False).mean()
    down=(-c.diff().clip(upper=0)).ewm(alpha=1/5,adjust=False).mean()
    rsi=100*up/(up+down).replace(0,np.nan)
    vol=d.volume/d.volume.shift(1).rolling(20).mean().replace(0,np.nan)
    rang=np.maximum((high-low).to_numpy(),1e-9)
    a=np.maximum(atr.to_numpy(),1e-8)
    index=d.index
    hour=index.hour.to_numpy()+index.minute.to_numpy()/60.0
    phases=(np.sin(2*np.pi*hour/24),np.cos(2*np.pi*hour/24))
    range18=(high.shift(1).rolling(18).max()-low.shift(1).rolling(18).min()).to_numpy()/a
    arr=[
        (c-d.open).to_numpy()/a,
        (c-pr).to_numpy()/a,
        (c-c.shift(3)).to_numpy()/a,
        (c-c.shift(8)).to_numpy()/a,
        (c-ema8).to_numpy()/a,
        (c-ema21).to_numpy()/a,
        (ema8-ema21).to_numpy()/a,
        (ema21-ema55).to_numpy()/a,
        (ema21-ema21.shift(5)).to_numpy()/a,
        (rsi.to_numpy()-50)/50,
        (np.minimum(c,d.open)-low).to_numpy()/rang,
        (high-np.maximum(c,d.open)).to_numpy()/rang,
        clip(atr/(atr.shift(1).rolling(20).mean().replace(0,np.nan))).to_numpy(),
        np.clip(np.nan_to_num(vol.to_numpy(),nan=0),0,4),
        np.clip(range18,0,8),
        phases[0],phases[1],
        index.dayofweek.to_numpy()/6.0
    ]
    X=np.stack(arr,axis=1)
    X=np.nan_to_num(X,nan=0,posinf=0,neginf=0)
    # direction-normalize the first 10 price-action components and two wicks; directions
    # are independent counterfactual training examples, never both executed simultaneously.
    long=X.copy()
    short=X.copy()
    short[:,:10]*=-1
    short[:,10],short[:,11]=X[:,11],X[:,10]
    long=np.column_stack((long,np.ones(len(X))))
    short=np.column_stack((short,np.full(len(X),-1)))
    return long,short,a
def clip(s):return s.clip(lower=.01,upper=4)
def simulate_labels(d,atr,direction):
    O=d.open.to_numpy();H=d.high.to_numpy();L=d.low.to_numpy();C=d.close.to_numpy()
    n=len(d);entry=np.roll(O,-1);stop=entry-direction*SL_ATR*atr;take=entry+direction*TP_ATR*atr
    done=np.zeros(n,dtype=bool);pnl=np.full(n,np.nan);end=np.full(n,-1,dtype=np.int32)
    for k in range(1,HOLD+2):
        limit=n-k;ix=np.arange(limit);valid=~done[:limit]
        if not valid.any():continue
        gap=(O[k:]<=stop[:limit] if direction>0 else O[k:]>=stop[:limit])
        sl=(L[k:]<=stop[:limit] if direction>0 else H[k:]>=stop[:limit])
        tp=(H[k:]>=take[:limit] if direction>0 else L[k:]<=take[:limit])
        anyhit=(gap|sl|tp)&valid
        # same candle stop before TP. Gap stop fills at opening.
        prices=np.where(gap,O[k:],np.where(sl,stop[:limit],take[:limit]))
        if k==HOLD+1:
            anyhit=valid
            prices=np.where(gap,O[k:],np.where(sl,stop[:limit],np.where(tp,take[:limit],C[k:])))
        if anyhit.any():
            ixhit=ix[anyhit]
            pnl[ixhit]=direction*(prices[anyhit]-entry[ixhit])-COST
            end[ixhit]=ixhit+k
            done[ixhit]=True
    # last HOLD+1 entries can't be assessed and should not be labeled.
    pnl[-HOLD-1:]=np.nan;end[-HOLD-1:]=-1
    return pnl,end
def evaluate(d,profitL,endL,profitS,endS,pLong,pShort,cutoff,month):
    months=np.asarray(d.index.strftime("%Y-%m"))
    selected=np.flatnonzero(months==month)
    left=int(selected[0]);last=int(selected[-1]);i=left;done=[]
    while i<=last-HOLD-2:
        p1=float(pLong[i]);p2=float(pShort[i])
        if max(p1,p2)<cutoff:i+=1;continue
        if p1>=p2:
            payoff=float(profitL[i]);j=int(endL[i]);dir=1
        else:
            payoff=float(profitS[i]);j=int(endS[i]);dir=-1
        if j<=i or j>last or not math.isfinite(payoff):i+=1;continue
        done.append((i,j,dir,payoff))
        i=j+COOLDOWN
    n=len(done);green=sum(x[3]>0 for x in done)
    gross=sum(max(0,x[3]) for x in done);loss=-sum(min(0,x[3]) for x in done)
    return {"month":month,"entries":n,"green":green,"red":n-green,
            "win_pct":round(green/n*100,2) if n else 0,
            "pf":round(gross/loss,3) if loss else None,
            "net_usd_per_oz":round(sum(x[3] for x in done),2),
            "qualifies":bool(n>=159 and green/n>=.65 and gross>loss) if n else False}
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    d=load()
    xL,xS,atr=features(d)
    pL,endsL=simulate_labels(d,atr,1);pS,endsS=simulate_labels(d,atr,-1)
    month=np.asarray(d.index.strftime("%Y-%m"))
    # Exclude HOLD last bars of each month to prevent leakage through month boundary.
    valid=(np.isfinite(pL)&np.isfinite(pS)&(atr>0))
    for day in ("2026-04","2026-05","2026-06","2026-07","2026-08"):
        ix=np.flatnonzero(month==day)
        valid[ix[-HOLD-2:]]=False
    train=valid&np.isin(month,["2026-04","2026-05"])
    X=np.concatenate((xL[train],xS[train]))
    y=np.concatenate(((pL[train]>0).astype(int),(pS[train]>0).astype(int)))
    model=HistGradientBoostingClassifier(learning_rate=.06,max_iter=110,max_depth=4,
        min_samples_leaf=150,l2_regularization=15,random_state=42)
    model.fit(X,y)
    probsL=model.predict_proba(xL)[:,1];probsS=model.predict_proba(xS)[:,1]
    cutoffs=np.round(np.arange(.50,.83,.025),3)
    trials=[]
    for cutoff in cutoffs:
        result=evaluate(d,pL,endsL,pS,endsS,probsL,probsS,float(cutoff),"2026-06")
        trials.append({"cutoff":float(cutoff),"june":result})
    # Threshold selected on June only, NOT July/Aug.
    trials.sort(key=lambda q:(int(q["june"]["qualifies"]),
                int(q["june"]["entries"]>=159 and (q["june"]["pf"] or 0)>1),
                int(q["june"]["entries"]>=159),
                q["june"]["net_usd_per_oz"],q["june"]["win_pct"]),reverse=True)
    chosen=trials[0]
    oos=[evaluate(d,pL,endsL,pS,endsS,probsL,probsS,chosen["cutoff"],month) for month in ("2026-07","2026-08")]
    approved=bool(chosen["june"]["qualifies"] and all(r["qualifies"] for r in oos))
    output={"approved":approved,"model":"HistGradientBoostingClassifier (nonlinear 19D vector)",
            "training":"2026-04 & 2026-05","validation":"2026-06","oos":["2026-07","2026-08"],
            "dataset_sha256":SHA,"rows":len(d),"cost_usd_per_oz":COST,
            "tp_atr":TP_ATR,"sl_atr":SL_ATR,"maxhold":HOLD,
            "selected_on_validation":chosen,"heldout_oos":oos,
            "thresholds_screened":len(trials),"all_june_trials":trials,
            "notes":["Each bar predicts BUY vs SELL from already-closed OHLC features.",
                     "Offline labels use future bars ONLY for supervised training; NEVER for feature inputs.",
                     "No valid validation threshold was selected from OOS.",
                     "OHLC proxy, no real-time ticks/bid-ask, broker commissions, or EA compile."]}
    (OUT/"RESULTADO_ML.json").write_text(json.dumps(output,indent=2,ensure_ascii=False)+"\n")
    msg=f"ML_VECTOR_159_65 {json.dumps({'approved':approved,'selected':chosen,'oos':oos,'num_training_rows':int(train.sum())},ensure_ascii=False)}"
    (OUT/"RELATORIO_ML.md").write_text("# Nexus Gold Vector ML — 65% / 159 entradas\n\n"+
        "**Resultado:** "+("APROVAÇÃO PROVISÓRIA; pendente MT5" if approved else "REPROVADO")+
        "\n\nApr–May treino, Jun limiar, Jul–Aug teste intocado.\n\n"+msg+"\n\n"+
        "TP 1,10 ATR, SL 1,10 ATR, custo fixo 0,60 USD/oz, stop primeiro, até 16 candles. "+
        "Sem tick real, spread variável ou ordens reais.\n")
    print(msg,flush=True)
if __name__=="__main__":main()
