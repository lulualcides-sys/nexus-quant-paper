#!/usr/bin/env python3
"""Independent exploratory XAUUSD OHLC replay; NOT an MT5 backtest.

Compares the NEW Vector Retest and a closed-candle VWAP proxy with the
SAME next-bar fills, 3 partial TP levels, SL-first collisions and price costs.
No parameter fitting on OOS. No trading orders. Unit R is risk-adjusted,
not a cash return. Uses only verified pinned historical source.
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from math import isfinite
import hashlib, json, urllib.request
import pandas as pd

COMMIT="adcd99e7e0abee51e9a5eef123935e68a8d8aa30"
URL="https://raw.githubusercontent.com/getdata-finance/xauusd-1m-ohlcv-metals-historical-data/"+COMMIT+"/XAUUSD_1m.csv"
SHA256="a587597bbf88c2d868a00a4e0019cd705cee6ca4f20b0485d6b745f19fcc8225"
COST_PER_OUNCE=0.60
PERIODS={"M5":5,"M15":15,"M30":30}
OUTPUT=Path(__file__).resolve().parent/"research_results"

def download():
    request=urllib.request.Request(URL,headers={"User-Agent":"Nexus-Vector-Retest-Research/1.0"})
    with urllib.request.urlopen(request,timeout=130) as response:
        data=response.read()
    digest=hashlib.sha256(data).hexdigest()
    if digest!=SHA256:raise ValueError(f"Verified source SHA256 mismatch: {digest}")
    temp=OUTPUT/"temporary.csv";temp.parent.mkdir(parents=True,exist_ok=True);temp.write_bytes(data)
    df=pd.read_csv(temp,parse_dates=["datetime"]);temp.unlink()
    df["datetime"]=pd.to_datetime(df["datetime"],utc=True)
    for c in ("open","high","low","close","volume"):
        df[c]=pd.to_numeric(df[c],errors="raise")
    df=df.drop_duplicates("datetime").sort_values("datetime").set_index("datetime")
    if not ((df.high>=df[["open","close","low"]].max(axis=1)) &
            (df.low<=df[["open","close","high"]].min(axis=1))).all():
        raise ValueError("Corrupted OHLC")
    return df

def bars_for(df,m):
    n=df.close.resample(str(m)+"min").count()
    agg=df.resample(str(m)+"min").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"})
    return agg[n>=m].dropna().copy()

def prepared(df):
    d=df.copy()
    tr=pd.concat([d.high-d.low,(d.high-d.close.shift(1)).abs(),(d.low-d.close.shift(1)).abs()],axis=1).max(axis=1)
    d["atr"]=tr.ewm(alpha=1/14,adjust=False).mean()
    d["fema"]=d.close.ewm(span=21,adjust=False).mean()
    d["sema"]=d.close.ewm(span=55,adjust=False).mean()
    d["rvol"]=d.volume/d.volume.shift(1).rolling(20,min_periods=20).mean().replace(0,float("nan"))
    d["rhi"]=d.high.shift(1).rolling(24,min_periods=24).max()
    d["rlo"]=d.low.shift(1).rolling(24,min_periods=24).min()
    # VWAP anchored to UTC day of the dataset (not broker-server midnight).
    days=d.index.floor("D")
    price=(d.high+d.low+d.close)/3
    weighted=price*d.volume
    d["vwap"]=weighted.groupby(days).cumsum()/d.volume.groupby(days).cumsum().replace(0,float("nan"))
    return d

def clip(x):return max(0.,min(1.,x))

def raw_vector_events(df):
    x=df.reset_index()
    events=[];dir0=0;level=0;age=0;breakbar=-1;quality=0
    # Chronological, only completed bar i; risk stop from retest bar i.
    for i in range(65,len(x)-1):
        r=x.iloc[i]; a=r.atr
        if not isfinite(a) or a<=0 or not isfinite(r.rhi):continue
        higher=r.close>r.rhi+.08*a
        lower=r.close<r.rlo-.08*a
        breakout=1 if higher else -1 if lower else 0
        if dir0:
            age+=1
            if age>8:dir0=0
            elif i>breakbar:
                d=dir0
                touch=r.low<=level+.18*a if d>0 else r.high>=level-.18*a
                reclaim=r.close>=level+.04*a if d>0 else r.close<=level-.04*a
                if touch and reclaim and d*(r.close-r.open)>0:
                    re=clip((d*(r.close-level)/a)/.55)
                    ema=clip((d*(r.fema-r.sema)/a+.07)/.55)
                    momentum=clip((d*(r.close-x.iloc[i-5].close)/a)/1.40)
                    rv=clip(r.rvol/1.80) if isfinite(r.rvol) else 0
                    vector=.25*quality+.25*re+.20*ema+.15*momentum+.15*rv
                    if vector>=.51:
                        stop=min(r.low,level)-.14*a if d>0 else max(r.high,level)+.14*a
                        entry=x.iloc[i+1].open
                        risk=d*(entry-stop)
                        if .30*a<=risk<=2.60*a:
                            events.append((i,d,stop,vector))
                            dir0=0
                            continue
        if breakout:
            dir0=breakout
            level=r.rhi if breakout>0 else r.rlo
            age=0;breakbar=i
            quality=clip((breakout*(r.close-level)/a)/.70)
    return events

def raw_vwap_events(df):
    x=df.reset_index();events=[]
    day=None;side0=0;pending=0;streak=0
    for i in range(60,len(x)-1):
        r=x.iloc[i];a=r.atr
        if not isfinite(a) or a<=0 or not isfinite(r.vwap):continue
        newday=r.datetime.floor("D")
        if newday!=day:day=newday;side0=pending=streak=0
        side=1 if r.close>r.vwap+.12*a else -1 if r.close<r.vwap-.12*a else 0
        if side==0:pending=streak=0;continue
        if side0==0:side0=side;continue
        if side!=side0:side0=pending=side;streak=1
        elif pending==side:streak+=1
        if pending!=side or streak<2:continue
        pending=streak=0
        body=side*(r.close-r.open)
        if body<=0:continue
        quality=body/max(r.high-r.low,1e-8)
        disp=side*(r.close-r.vwap)
        rvol=r.rvol if isfinite(r.rvol) else 0
        score=.40*clip(quality/.70)+.35*clip(disp/(.60*a))+.25*clip(rvol/1.80)
        if score<.42:continue
        stop=r.low-.08*a if side>0 else r.high+.08*a
        if side*(x.iloc[i+1].open-stop)>0:
            events.append((i,side,stop,score))
    return events

def fills(frame, events, split):
    # identical assumptions for both strategies, skip overlapping positions,
    # 8 bar cooldown + same direction guard, 3 equal target tranches.
    b=frame.reset_index()
    closed=-1;lastdir=0;lastentry=-1000000;trades=[]
    for i,side,stop,score in events:
        if i+1<=closed or i+1-lastentry<8 or side==lastdir:continue
        entry=float(b.iloc[i+1].open);risk=side*(entry-stop)
        if risk<=0.0 or not isfinite(risk):continue
        target=[entry+side*x*risk for x in (1.,1.5,2.)]
        remaining=1.;earned=0.;nexttp=0;out=i+1;why="OPEN"
        last=min(len(b)-1,i+1+48)
        for j in range(i+1,last+1):
            bar=b.iloc[j]
            gap_stop=(bar.open<=stop if side>0 else bar.open>=stop)
            stop_hit=(bar.low<=stop if side>0 else bar.high>=stop)
            if stop_hit:
                exitprice=float(bar.open) if gap_stop else stop
                earned+=remaining*side*(exitprice-entry)
                why="SL";out=j;break
            for k in range(nexttp,3):
                hit=bar.high>=target[k] if side>0 else bar.low<=target[k]
                if not hit:break
                volume=remaining if k==2 else 1/3
                earned+=volume*side*(target[k]-entry)
                remaining-=volume;nexttp=k+1
            if nexttp>=3:why="TP3";out=j;break
            if j==last:
                earned+=remaining*side*(bar.close-entry)
                why="TIME";out=j;break
        netr=(earned-COST_PER_OUNCE)/risk
        trades.append({"signal_bar":i,"side":side,"entry_bar":i+1,"exit_bar":out,
                       "net_r":netr,"reason":why,"oos":i>=split})
        closed=out;lastentry=i+1;lastdir=side
    return trades

def metrics(deals):
    if not deals:return {"N":0,"PF":None,"R_net":None,"Win_pct":None,"R_avg":None,"MDD_R":None}
    vals=[d["net_r"] for d in deals]
    positives=sum(max(0,x) for x in vals)
    losses=sum(-min(0,x) for x in vals)
    equity=peak=mdd=0.
    for v in vals:
        equity+=v
        if equity>peak:peak=equity
        if peak-equity>mdd:mdd=peak-equity
    return {"N":len(vals),"PF":round(positives/losses,3) if losses else None,
            "R_net":round(sum(vals),2),"Win_pct":round(100*sum(x>0 for x in vals)/len(vals),2),
            "R_avg":round(sum(vals)/len(vals),4),"MDD_R":round(mdd,2)}

def main():
    df=download();results={"source":URL,"sha256":SHA256,"m1_rows":len(df),
                           "first":str(df.index.min()),"last":str(df.index.max()),
                           "method":"Synthetic M5/M15/M30 OHLC. Entry next open. SL first. TP partials 1R,1.5R,2R; 48-bar max; fixed 0.60 USD/oz cost. No commission, no real broker fills.",
                           "cases":[]}
    for tf,m in PERIODS.items():
        data=prepared(bars_for(df,m));split=int(len(data)*.70)
        for name,signal in (("VECTOR_RETEST",raw_vector_events),("VWAP_PROXY",raw_vwap_events)):
            events=signal(data)
            trades=fills(data,events,split)
            row={"name":name,"timeframe":tf,"signals":len(events),"training":metrics([x for x in trades if not x["oos"]]),
                 "test":metrics([x for x in trades if x["oos"]]),"closed_trades":len(trades)}
            results["cases"].append(row)
            print(name,tf,"test",row["test"],flush=True)
    OUTPUT.mkdir(parents=True,exist_ok=True)
    (OUTPUT/"results.json").write_text(json.dumps(results,ensure_ascii=False,indent=2)+"\n")
    head="# Nexus Vector Retest: teste historico exploratorio, comparacao identica de custos\n\n"
    head+="**NAO e backtest MQL5 compilado. Sem ticks/spread por broker, sem slippage real ou comissoes.**\n\n"
    head+=f"Fonte XAUUSD M1 SHA256 `{SHA256}`, {len(df)} candles, {df.index.min()} a {df.index.max()}.\n\n"
    head+="Treino/teste: primeiros 70%/ultimos 30% cronologicos em cada periodo. Custo: US$ 0,60/oz por ida-e-volta, stop primeiro se TP/SL na mesma barra.\n\n"
    head+="| Modelo | TF | N teste | PF | R liquido | R medio | DD (R) | Acerto |\n|---|---|---:|---:|---:|---:|---:|---:|\n"
    for c in results["cases"]:
        x=c["test"]
        head+=f'| {c["name"]} | {c["timeframe"]} | {x["N"]} | {x["PF"]} | {x["R_net"]} | {x["R_avg"]} | {x["MDD_R"]} | {x["Win_pct"]}% |\n'
    head+="\nA comparacao e proxy: o modelo VWAP nao e o indicador real do usuario. Nao prometer superioridade se PF<=1 ou R teste<=0.\n"
    (OUTPUT/"REPORT.md").write_text(head)
    print(head)
if __name__=="__main__":main()
