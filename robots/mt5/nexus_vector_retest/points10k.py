#!/usr/bin/env python3
"""10k-bar XAUUSD research: compare a reference VWAP proxy with five new
closed-candle strategies and three partial TPs. Never an MT5 tester claim.
"""
import json,math
from pathlib import Path
import numpy as np,pandas as pd
from research_oos import download,bars_for,prepared,raw_vwap_events
BASE=Path(__file__).resolve().parent
OUTPUT=BASE/"points10k_results"
POINT=.01   # assumption; verify XAUUSD SYMBOL_POINT in user's broker
GROSS_BENCH=21069
TRADES_BENCH=154
WINDOW=10000
WARM=240
COST=.80 # proxy round-trip price USD per oz incl spread/slippage/commission; not observed
def clamp(x):return max(0.,min(1.,float(x)))
def events(frame,kind):
    d=frame.reset_index();out=[]
    # On signal bar i close, only its own completed OHLC and earlier closed bars.
    # Historical pivot markers may NOT be stamped earlier than confirmation.
    for i in range(WARM,len(d)-1):
        b=d.iloc[i];a=float(b.atr)
        if a<=0 or not math.isfinite(a):continue
        prev=d.iloc[i-1]
        body=(b.close-b.open)/max(1e-8,b.high-b.low)
        side=0;level=None
        if kind=="SWEEP12":
            lows=d.low.iloc[i-12:i];highs=d.high.iloc[i-12:i]
            if b.low<lows.min()-.06*a and b.close>lows.min() and body>.12:
                side=1;level=lows.min()
            elif b.high>highs.max()+.06*a and b.close<highs.max() and body<-.12:
                side=-1;level=highs.max()
        elif kind=="EMA21_PULLBACK":
            if b.fema>b.sema and b.low<b.fema and b.close>b.fema and body>.17:side=1;level=b.fema
            elif b.fema<b.sema and b.high>b.fema and b.close<b.fema and body<-.17:side=-1;level=b.fema
        elif kind=="EMA21_CROSS":
            if prev.close<prev.fema-.08*a and b.close>b.fema+.08*a and body>.16:side=1;level=b.fema
            elif prev.close>prev.fema+.08*a and b.close<b.fema-.08*a and body<-.16:side=-1;level=b.fema
        elif kind=="MOMENTUM24":
            if b.close>b.rhi+.12*a and body>.38 and b.fema>b.sema:side=1;level=b.rhi
            elif b.close<b.rlo-.12*a and body<-.38 and b.fema<b.sema:side=-1;level=b.rlo
        elif kind=="BAND_REJECTION":
            sub=d.close.iloc[i-21:i]
            mid=float(sub.mean());dev=float(sub.std())
            if dev<=0:continue
            if b.low<mid-1.55*dev and b.close>mid-1.55*dev and body>.10:side=1;level=mid-1.55*dev
            elif b.high>mid+1.55*dev and b.close<mid+1.55*dev and body<-.10:side=-1;level=mid+1.55*dev
        elif kind=="VWAP_EMA_BLEND":
            # Separate combined strategy, not the original VWAP indicator.
            if b.fema>b.sema and prev.close<prev.vwap and b.close>b.vwap+.06*a and body>.14:side=1;level=b.vwap
            elif b.fema<b.sema and prev.close>prev.vwap and b.close<b.vwap-.06*a and body<-.14:side=-1;level=b.vwap
        else:raise ValueError(kind)
        if side==0:continue
        stop=(min(b.low,level)-.12*a if side>0 else max(b.high,level)+.12*a)
        # Reject stop that already lies on wrong side of next opening.
        entry=float(d.open.iloc[i+1]);risk=side*(entry-stop)
        if risk<.12*a or risk>3.0*a:continue
        quality=.40*clamp(abs(body)/.7)+.30*clamp(abs(b.close-level)/a)+.30*clamp(b.rvol/1.8 if math.isfinite(b.rvol) else 0)
        out.append((i,side,float(stop),float(quality)))
    return out

def simulate(d,signals,first,last,target_mult=(1,1.5,2),cool=1):
    b=d.reset_index()
    trades=[]
    lastclose=first-1
    for i,side,stop,score in signals:
        if i<first or i>=last-2:continue
        entrybar=i+1
        if entrybar<=lastclose+cool:continue
        entry=float(b.open.iloc[entrybar])
        risk=side*(entry-stop)
        if risk<=0:continue
        targets=[entry+side*risk*k for k in target_mult]
        remaining=1.;take_index=0;gross=0.;out=None;reason=None
        finish=min(last-1,entrybar+48)
        for j in range(entrybar,finish+1):
            q=b.iloc[j];op=float(q.open)
            stopped=(q.low<=stop if side>0 else q.high>=stop)
            if stopped:
                fill=min(op,stop) if side>0 else max(op,stop)
                gross+=remaining*side*(fill-entry)
                out=j;reason="SL";break
            for k in range(take_index,3):
                hit=q.high>=targets[k] if side>0 else q.low<=targets[k]
                if not hit:break
                fraction=(remaining if k==2 else 1/3)
                gross+=fraction*side*(targets[k]-entry)
                remaining-=fraction;take_index=k+1
            if take_index==3:out=j;reason="TP3";break
            if j==entrybar+48:
                gross+=remaining*side*(float(q.close)-entry)
                out=j;reason="TIME";break
        if out is None:continue  # no completed trade inside 10k-bar window
        # Cost of $0.8/oz round trip, independent of direction; 80 points if point=0.01.
        net=gross-COST
        trades.append({"signal":i,"entry":entrybar,"exit":out,"side":side,"gross_pts":gross/POINT,
                       "net_pts":net/POINT,"net_usd_oz":net,
                       "r_net":net/risk,"reason":reason,"quality":score})
        lastclose=out
    return trades

def stats(trades):
    if not trades:return {"N":0,"GREEN":0,"RED":0,"gross_pts":0.,"net_pts":0.,"PF":None,"win_pct":None,"mdd_pts":None}
    x=np.array([t['net_pts'] for t in trades]);gr=np.array([t['gross_pts'] for t in trades])
    wins=sum(x>0);gain=sum(np.maximum(x,0));loss=-sum(np.minimum(x,0))
    curve=np.cumsum(x);mdd=max(np.maximum.accumulate(np.r_[0.,curve])-np.r_[0.,curve])
    return {"N":len(x),"GREEN":int(wins),"RED":int(len(x)-wins),"gross_pts":round(float(sum(gr)),1),
            "net_pts":round(float(sum(x)),1),"PF":round(float(gain/loss),3) if loss else None,
            "win_pct":round(float(100*wins/len(x)),2),
            "avg_net_pts":round(float(x.mean()),1),"mdd_pts":round(float(mdd),1)}

def main():
    OUTPUT.mkdir(exist_ok=True,parents=True)
    raw=download()
    result={"source":"pinned xauusd 179662 M1 bars","sha256":"a587597bbf88c2d868a00a4e0019cd705cee6ca4f20b0485d6b745f19fcc8225",
            "point_assumption":POINT,"cost_model_roundtrip_usd_oz":COST,
            "benchmark":{"N":TRADES_BENCH,"gross_pts":GROSS_BENCH,"same_symbol_settings_unverified":True},
            "data_first":str(raw.index[0]),"data_last":str(raw.index[-1]),
            "model":"OHLC proxy; no broker MT5 real ticks, Bid/Ask, variable spreads or execution",
            "cases":[]}
    for tf in (1,5,15):
        df=prepared(raw if tf==1 else bars_for(raw,tf))
        count=(len(df)-WARM)//WINDOW
        if count<1:continue
        kindnames=["SWEEP12","EMA21_PULLBACK","EMA21_CROSS","MOMENTUM24","BAND_REJECTION","VWAP_EMA_BLEND"]
        for model in kindnames+["VWAP_PROXY"]:
            sig=raw_vwap_events(df) if model=="VWAP_PROXY" else events(df,model)
            for target in ((1,1.5,2),(.85,1.25,1.7),(1.25,1.75,2.5)):
                row={"strategy":model,"tf":"M"+str(tf),"tp_r":target,"windows":[]}
                for w in range(count):
                    st=WARM+w*WINDOW;en=st+WINDOW
                    deals=simulate(df,sig,st,en,target)
                    m=stats(deals)
                    row["windows"].append({"window":w,"from":str(df.index[st]),"to":str(df.index[en-1]),**m})
                tr=row["windows"][:max(1,count//2)]
                te=row["windows"][max(1,count//2):]
                def aggregate(q):
                    return {"windows":len(q),"N":sum(x["N"] for x in q),
                            "gross_pts":round(sum(x["gross_pts"] for x in q),1),
                            "net_pts":round(sum(x["net_pts"] for x in q),1),
                            "mean_N":round(sum(x["N"] for x in q)/len(q),1) if q else 0,
                            "min_N":min((x["N"] for x in q),default=0),
                            "positive_windows":sum(x["net_pts"]>0 for x in q)}
                row["training"]=aggregate(tr);row["test"]=aggregate(te)
                result["cases"].append(row)
            print("DONE_MODEL","M"+str(tf),model,"candidate count",count,flush=True)
    # Select using TRAIN only. Report test, never tune parameters on test.
    ranked=sorted(result["cases"],key=lambda q:(
        int(q["training"]["mean_N"]>=TRADES_BENCH),
        int(q["training"]["net_pts"]>0),q["training"]["net_pts"],
        q["training"]["mean_N"]),reverse=True)
    result["best_train"]=ranked[0];result["top5_train"]=[{"strategy":q["strategy"],"tf":q["tf"],"tp_r":q["tp_r"],
                                               "training":q["training"],"test":q["test"]} for q in ranked[:5]]
    result["per_timeframe_best"]={}
    for tf in ("M1","M5","M15"):
        best=next((r for r in ranked if r["tf"]==tf),None)
        if best:result["per_timeframe_best"][tf]={"strategy":best["strategy"],"tp_r":best["tp_r"],
                                                   "train":best["training"],"test":best["test"]}
    (OUTPUT/"RESULTADOS_10K.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    with (OUTPUT/"RELATORIO_10K.md").open("w") as f:
        f.write("# Pesquisa XAUUSD — 10 mil candles vs referência VWAP\\n\\n"
                "**Resultado reproduzível, mas NÃO é um backtest do MetaTrader.**\\n\\n"
                "Referência fornecida: 154 operações, 21.069 pontos brutos em 10.000 candles; "
                "não são comparáveis em um feed/período sem histórico exato do MT5.\\n\\n"
                "Ponto assumido 0,01 XAUUSD; custo hipotético fixo US$0,80/onça por operação = 80 pontos. "
                "TP1 1R / TP2 1,5R / TP3 2R (ou variação), parciais de 1/3, SL antes do TP em conflito.\\n\\n"
                "|Período|Modelo selecionado por treino|Entradas médias treino/10k|Pontos líquidos treino|Pontos líquidos nos blocos de teste|\\n"
                "|---|---|---:|---:|---:|\\n")
        for tf,item in result["per_timeframe_best"].items():
            f.write("|"+"|".join([tf,item["strategy"],str(item["train"]["mean_N"]),
                str(item["train"]["net_pts"]),str(item["test"]["net_pts"])])+"|\\n")
        f.write("\\n**Não escolher o melhor bloco retrospectivo como prova de vantagem.** "
                "M15 só possui uma janela completa e não tem bloco separado para teste com esta amostra. "
                "Aprovação exigirá ticks reais do broker e janelas adicionais.\\n")
    b=result["best_train"]
    print("SELECTED",json.dumps({"name":b["strategy"],"tf":b["tf"],"tp":b["tp_r"],
                  "train":b["training"],"test":b["test"]},ensure_ascii=False),flush=True)
    print("TOP5",json.dumps(result["top5_train"],ensure_ascii=False),flush=True)
    print("FULL_RESULTS",len(result["cases"]),flush=True)
if __name__=="__main__":main()
