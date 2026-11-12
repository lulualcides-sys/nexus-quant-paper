#!/usr/bin/env python3
"""XAUUSD M1 high-frequency objective screening. Historical OHLC PROXY only.
Train Apr-Jun 2026, freeze selection, test unseen Jul-Aug 2026.
Require EACH full month: 159 completed entries, 65% net wins, PF>1.
Never run orders or claim that the MQL5 EA was tested.
"""
import io,json,hashlib,urllib.request
from pathlib import Path
import numpy as np,pandas as pd
OUT=Path(__file__).resolve().parent/"results"
URL=("https://raw.githubusercontent.com/getdata-finance/xauusd-1m-ohlcv-metals-historical-data/"
"adcd99e7e0abee51e9a5eef123935e68a8d8aa30/XAUUSD_1m.csv")
SHA="a587597bbf88c2d868a00a4e0019cd705cee6ca4f20b0485d6b745f19fcc8225"
COST=0.60
TRAIN=["2026-04","2026-05","2026-06"]
OOS=["2026-07","2026-08"]
def read():
    rq=urllib.request.Request(URL,headers={"User-Agent":"Nexus15965-Research/1"})
    with urllib.request.urlopen(rq,timeout=140) as response: data=response.read()
    if hashlib.sha256(data).hexdigest()!=SHA: raise ValueError("SHA mismatch")
    df=pd.read_csv(io.BytesIO(data),parse_dates=["datetime"])
    df["datetime"]=pd.to_datetime(df.datetime,utc=True)
    df=df.drop_duplicates("datetime").sort_values("datetime").set_index("datetime")
    for k in ("open","high","low","close","volume"):df[k]=pd.to_numeric(df[k])
    if not ((df.high>=df[["low","close","open"]].max(axis=1))&
            (df.low<=df[["high","close","open"]].min(axis=1))).all():raise ValueError("Bad candles")
    return df
def prepared(df):
    d=df.copy();c=d.close
    tr=pd.concat((d.high-d.low,(d.high-c.shift(1)).abs(),(d.low-c.shift(1)).abs()),axis=1).max(axis=1)
    d["atr"]=tr.ewm(alpha=1/14,adjust=False).mean()
    d["e21"]=c.ewm(span=21,adjust=False).mean()
    d["e55"]=c.ewm(span=55,adjust=False).mean()
    up=c.diff().clip(lower=0).ewm(alpha=.5,adjust=False).mean()
    down=(-c.diff().clip(upper=0)).ewm(alpha=.5,adjust=False).mean()
    d["rsi2"]=100*up/(up+down).replace(0,np.nan)
    d["rsi2prev"]=d.rsi2.shift(1)
    d["z"]=(c-d.e21)/d.atr.replace(0,np.nan)
    d["slope"]=(d.e21-d.e55)/d.atr.replace(0,np.nan)
    d["rv"]=d.volume/d.volume.shift(1).rolling(20).mean().replace(0,np.nan)
    d["prevclose"]=c.shift(1);d["prevema"]=d.e21.shift(1)
    d["prev8hi"]=d.high.shift(1).rolling(8).max()
    d["prev8lo"]=d.low.shift(1).rolling(8).min()
    return d
def clip(v):return np.clip(v,0,1)
def signals(d,style,thresh,minscore):
    o=d.open.to_numpy();c=d.close.to_numpy();h=d.high.to_numpy();l=d.low.to_numpy()
    atr=np.maximum(d.atr.to_numpy(),1e-12)
    ema=d.e21.to_numpy();slope=d.slope.to_numpy()
    z=d.z.to_numpy();rsi=d.rsi2prev.to_numpy()
    rv=np.nan_to_num(d.rv.to_numpy(),nan=0)
    body=(c-o)/np.maximum(h-l,1e-9)
    uw=(h-np.maximum(o,c))/np.maximum(h-l,1e-9)
    lw=(np.minimum(o,c)-l)/np.maximum(h-l,1e-9)
    pc=d.prevclose.to_numpy();pe=d.prevema.to_numpy()
    if style=="FADE":
        buy=(z<-thresh)&(body>.07)&(lw>.1)&(rsi<45)
        sell=(z>thresh)&(body<-.07)&(uw>.1)&(rsi>55)
        dr=np.where(buy,1,np.where(sell,-1,0))
        score=.25*clip((np.abs(z)-thresh)/1.1)+.25*clip(np.abs(body)/.5)+.2*clip(np.where(dr>0,lw,uw)/.35)+.15*clip(1.3-np.abs(slope))+.15*clip(rv/1.4)
    elif style=="TREND":
        buy=(slope>thresh)&(l<ema-.12*atr)&(body>.08)&(rsi<55)
        sell=(slope<-thresh)&(h>ema+.12*atr)&(body<-.08)&(rsi>45)
        dr=np.where(buy,1,np.where(sell,-1,0))
        score=.25*clip(np.abs(slope)/1.3)+.25*clip(np.abs(body)/.55)+.2*clip(np.where(dr>0,(ema-l)/atr,(h-ema)/atr)/.5)+.15*clip(np.abs(c-pc)/atr/.75)+.15*clip(rv/1.4)
    elif style=="RECLAIM":
        buy=(c>ema)&(pc<pe-thresh*atr)&(body>.12)
        sell=(c<ema)&(pc>pe+thresh*atr)&(body<-.12)
        dr=np.where(buy,1,np.where(sell,-1,0))
        score=.25*clip(np.abs(body)/.6)+.25*clip(np.abs(c-ema)/atr/.6)+.2*clip(np.abs(pc-pe)/atr)+.15*clip(np.abs(c-pc)/atr/.8)+.15*clip(rv/1.5)
    elif style=="BREAK":
        hi=d.prev8hi.to_numpy();lo=d.prev8lo.to_numpy()
        buy=(c>hi+thresh*atr)&(body>.35)&(slope>0)
        sell=(c<lo-thresh*atr)&(body<-.35)&(slope<0)
        dr=np.where(buy,1,np.where(sell,-1,0))
        score=.25*clip(np.where(dr>0,(c-hi)/atr,(lo-c)/atr)/.65)+.25*clip(np.abs(slope)/1.3)+.2*clip(np.abs(body)/.75)+.15*clip(np.abs(c-pc)/atr/.8)+.15*clip(rv/1.5)
    else:raise ValueError(style)
    dr=np.where((score>=minscore)&np.isfinite(score),dr,0).astype(np.int8)
    dr[:100]=0;dr[-30:]=0
    return dr
def run(d,dr,tp,sl,hold,cool,months,month_masks):
    o=d.open.to_numpy();hi=d.high.to_numpy();lo=d.low.to_numpy();close=d.close.to_numpy()
    atr=d.atr.to_numpy();out=[]
    for month in months:
        indexes=month_masks[month];first=int(indexes[0]);last=int(indexes[-1])
        i=first
        while i<=last-hold-2:
            side=int(dr[i])
            if not side or not np.isfinite(atr[i]) or atr[i]<=0:
                i+=1;continue
            entry=float(o[i+1]);risk=sl*float(atr[i]);reward=tp*float(atr[i])
            if risk<COST or reward<COST*.5:
                i+=1;continue
            stop=entry-side*risk;take=entry+side*reward
            finish=None;price=None
            for j in range(i+1,min(i+hold+2,last+1)):
                # opening gap and stop hit before profit if both touched
                if (o[j]<=stop if side>0 else o[j]>=stop):
                    finish=j;price=float(o[j]);break
                if (lo[j]<=stop if side>0 else hi[j]>=stop):
                    finish=j;price=stop;break
                if (hi[j]>=take if side>0 else lo[j]<=take):
                    finish=j;price=take;break
                if j==i+hold+1:
                    finish=j;price=float(close[j]);break
            if finish is None:i+=1;continue
            net=side*(price-entry)-COST
            out.append({"month":month,"entry":i+1,"exit":finish,"net":net,"r":net/risk,"win":net>0})
            i=finish+max(1,cool)
    return out
def stats(trades,months):
    out=[];w=0;net=0.;gp=0.;gl=0.;rnet=0.
    for month in months:
        ts=[t for t in trades if t["month"]==month]
        n=len(ts);wins=sum(t["win"] for t in ts)
        gains=sum(max(0,t["net"]) for t in ts);losses=-sum(min(0,t["net"]) for t in ts)
        pnl=sum(t["net"] for t in ts)
        out.append({"month":month,"entries":n,"green":wins,"red":n-wins,
                    "win_pct":round(wins/n*100,2) if n else 0,
                    "pf":round(gains/losses,3) if losses else None,
                    "usd_per_oz":round(pnl,2),
                    "passes":bool(n>=159 and n>0 and wins/n>=.65 and gains>losses)})
        w+=wins;net+=pnl;gp+=gains;gl+=losses;rnet+=sum(t["r"] for t in ts)
    return {"entries":len(trades),"green":w,"hit_pct":round(w/len(trades)*100,2) if trades else 0,
            "pf":round(gp/gl,3) if gl else None,"net_usd_per_oz":round(net,2),
            "net_r":round(rnet,2),"monthly":out,"passes_all":all(x["passes"] for x in out)}
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    df=prepared(read())
    masks={m:np.flatnonzero(df.index.strftime("%Y-%m")==m) for m in TRAIN+OOS}
    if any(len(v)<20000 for v in masks.values()):
        raise ValueError("Not enough data for full train/OOS months: "+str({k:len(v) for k,v in masks.items()}))
    grid=[]
    hours=df.index.hour.to_numpy()
    for fam in ("FADE","TREND","RECLAIM","BREAK"):
        values={"FADE":(.25,.60,1.0),"TREND":(.04,.16,.32),
                "RECLAIM":(.07,.20,.38),"BREAK":(.02,.10,.23)}[fam]
        for t in values:
            for scoremin in (.43,.62):
                rawdire=signals(df,fam,t,scoremin)
                for session in ("all","liquid_7_20_utc"):
                    dire=rawdire.copy()
                    if session!="all":dire[(hours<7)|(hours>=20)]=0
                    for tp,sl in ((.85,1.0),(1.10,1.10),(1.35,1.25)):
                        cfg={"family":fam,"threshold":t,"score_min":scoremin,
                             "session":session,"tp_atr":tp,"sl_atr":sl,
                             "maxhold":16,"cooldown":3}
                        tr=run(df,dire,tp,sl,16,3,TRAIN,masks)
                        grid.append({"cfg":cfg,"train":stats(tr,TRAIN)})
    # Selection based exclusively on training months, NOT the unseen July/August.
    def quality(x):
        tr=x["train"];m=tr["monthly"]
        return (int(tr["passes_all"]),
                int((tr["pf"] or 0)>1 and all(i["entries"]>=159 for i in m)),
                int(all(i["entries"]>=159 for i in m)),
                tr["net_r"],min(i["entries"] for i in m))
    grid.sort(key=quality,reverse=True)
    top=grid[:5]
    for row in top:
        c=row["cfg"];dire=signals(df,c["family"],c["threshold"],c["score_min"])
        if c["session"]!="all":dire[(hours<7)|(hours>=20)]=0
        row["oos"]=stats(run(df,dire,c["tp_atr"],c["sl_atr"],c["maxhold"],c["cooldown"],OOS,masks),OOS)
    best=top[0]
    approved=bool(best["train"]["passes_all"] and best["oos"]["passes_all"])
    summary={"objective":"XAUUSD 65% net wins AND >=159 filled trades per month",
             "months_train":TRAIN,"months_out_of_sample":OOS,
             "dataset_url":URL,"sha256":SHA,"raw_rows":len(df),
             "month_rows":{k:len(v) for k,v in masks.items()},
             "round_trip_cost_usd_oz":COST,"grid_size":len(grid),
             "qualifying_in_sample":sum(x["train"]["passes_all"] for x in grid),
             "best_train_selected":best,
             "approved":approved,"top5":top,
             "important":"OHLC approximation, NOT compiled MQL5, no real bid ask or commissions"}
    (OUT/"resultados.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
    lines=["# XAUUSD — Meta 65% GREEN e 159 entradas mensais", "",
           "**STATUS:** "+("PASSOU screening exploratório, pendente MetaTrader5" if approved else "NÃO VALIDADO. Critérios não atingidos."),
           "Amostra: 179.662 candles XAUUSD M1, fonte SHA256 fixa. Treino 2026-04 a 06; teste sem otimização 2026-07 a 08.",
           "Uma entrada por vez; sinal ao fechar candle e entrada na abertura seguinte; stop primeiro quando vela atinge SL e TP; custo ida e volta hipotético de US$ 0,60/oz.",
           "Contam-se negócios encerrados com resultado líquido positivo; mínimo de 159 por mês COMPLETO, não média mensal. PF>1 obrigatório.",
           "Não é teste do EA compilado no MetaTrader 5.","",
           "| Janela | Mês | Entradas | GREEN | Acerto | PF | Resultado US$/oz | Aprovou |",
           "|---|---|---:|---:|---:|---:|---:|---|"]
    for period,key in (("Treino","train"),("Fora da amostra","oos")):
        for m in best[key]["monthly"]:
            lines.append("| "+period+" | "+m["month"]+" | "+str(m["entries"])+" | "+str(m["green"])+" | "+str(m["win_pct"])+"% | "+str(m["pf"])+" | "+str(m["usd_per_oz"])+" | "+("SIM" if m["passes"] else "NÃO")+" |")
    lines+=["","Hipótese selecionada sem olhar o teste: \`"+json.dumps(best["cfg"])+"\`",
           "Quantidade de variantes pré-definidas: "+str(len(grid))+". Variantes aprovadas em treino: "+str(summary["qualifying_in_sample"])+".",
           "Se falhou, não aprovar nem publicar EA como lucrativo; nova hipótese e novo período virgem necessários.",""]
    (OUT/"RELATORIO.md").write_text("\n".join(lines))
    print("SCREEN_RESULTS",json.dumps({"approved":approved,"qualified_training":summary["qualifying_in_sample"],
                                     "best":best},default=str),flush=True)
if __name__=="__main__":main()
