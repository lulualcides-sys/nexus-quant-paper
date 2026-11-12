#!/usr/bin/env python3
"""XAUUSD ONLY: original vs inverted EMA21 Pullback entries and larger TPs.
Historical 10,000 M15-bar windows; closed-bar signals -> next-open entries.
Inverted stops are rebuilt on the OPPOSITE side of the signal candle.
OHLC, NOT MT5 Bid/Ask or broker fills; modeled 0.80 USD/oz total cost.
"""
import json,math
from pathlib import Path
from points10k import events,WINDOW,WARM,POINT
from points10k_2025 import source
from research_oos import prepared,bars_for,download

HERE=Path(__file__).resolve().parent
OUT=HERE/"inverse_runner_results"
COST=.80
HOLD=128
CASES=(("NORMAL_BASIC",1,"basic"),("INVERSE_BASIC",-1,"basic"),
       ("NORMAL_WIDE",1,"wide"),("INVERSE_WIDE",-1,"wide"),
       ("NORMAL_RUNNER",1,"runner"),("INVERSE_RUNNER",-1,"runner"))
TARGETS={"basic":(1.,1.5,2.),"wide":(1.5,3.,5.),"runner":(1.,2.,5.)}

def replay(df,signals,start,end,polarity=1,style="basic",cost=COST):
    bars=df.reset_index()
    trades=[]
    busy=start-1
    for i,signed,_,quality in signals:
        if i<start or i>=end-2:continue
        j=i+1
        if j<=busy:continue
        b=bars.iloc[i]
        direction=int(signed*polarity)
        entry=float(bars.open.iloc[j])
        atr=float(b.atr)
        if not math.isfinite(atr) or atr<=0:continue
        # The inverted position MUST have the stop on its own losing side.
        stop=float(b.low)-.12*atr if direction>0 else float(b.high)+.12*atr
        risk=direction*(entry-stop)
        if risk<.12*atr or risk>3.5*atr:continue
        tp=[entry+direction*risk*r for r in TARGETS[style]]
        trail=stop
        remaining=1.
        nexttp=0
        gross=0.
        out=None
        endbar=min(end-1,j+HOLD)
        for k in range(j,endbar+1):
            bar=bars.iloc[k]
            opening=float(bar.open)
            stop_hit=(float(bar.low)<=trail if direction>0 else float(bar.high)>=trail)
            if stop_hit:
                fill=min(opening,trail) if direction>0 else max(opening,trail)
                gross+=remaining*direction*(fill-entry)
                out=k;reason="STOP";break
            for t in range(nexttp,3):
                hit=float(bar.high)>=tp[t] if direction>0 else float(bar.low)<=tp[t]
                if not hit:break
                fraction=remaining if t==2 else 1/3
                gross+=fraction*direction*(tp[t]-entry)
                remaining-=fraction
                nexttp=t+1
            if nexttp==3:
                out=k;reason="TP3";break
            if k==j+HOLD:
                gross+=remaining*direction*(float(bar.close)-entry)
                out=k;reason="TIME";break
            if style=="runner" and nexttp>0:
                # Update ONLY AFTER the bar CLOSE. Trailing acts next candle.
                newstop=(entry if nexttp==1 else max(entry,float(bar.close)-1.5*atr)) if direction>0 else (
                          entry if nexttp==1 else min(entry,float(bar.close)+1.5*atr))
                trail=max(trail,newstop) if direction>0 else min(trail,newstop)
        if out is None:continue
        net=gross-cost
        trades.append({"entry":j,"exit":out,"gross_pts":gross/POINT,
                       "net_pts":net/POINT,"tp_reached":nexttp,
                       "reason":reason,"direction":direction})
        busy=out
    return trades

def metrics(trades):
    if not trades:return {"n":0,"win_pct":None,"pf":None,"gross_pts":0,"net_pts":0}
    n=len(trades)
    gp=sum(max(0,x["net_pts"]) for x in trades)
    gl=-sum(min(0,x["net_pts"]) for x in trades)
    p=[x["net_pts"] for x in trades]
    equity=peak=dd=0.
    for val in p:
        equity+=val;peak=max(peak,equity);dd=max(dd,peak-equity)
    return {"n":n,"green":sum(x>0 for x in p),
            "win_pct":round(100*sum(x>0 for x in p)/n,2),
            "pf":round(gp/gl,3) if gl else None,
            "gross_pts":round(sum(x["gross_pts"] for x in trades),1),
            "net_pts":round(sum(p),1),
            "maxdd_pts":round(dd,1),"mean_net_pts":round(sum(p)/n,1)}

def measure(data,label):
    frame=prepared(bars_for(data,15))
    sig=events(frame,"EMA21_PULLBACK")
    count=(len(frame)-WARM)//WINDOW
    if count<1:raise ValueError("Missing full 10k M15 candles for "+label)
    windows=[]
    for w in range(count):
        st=WARM+w*WINDOW;ed=st+WINDOW
        cases=[]
        for name,direction,style in CASES:
            a=metrics(replay(frame,sig,st,ed,direction,style,COST))
            stress=metrics(replay(frame,sig,st,ed,direction,style,COST*2))
            cases.append({"case":name,**a,"cost_x2_net_pts":stress["net_pts"]})
            print("RESULT",label,w,name,"N",a["n"],"PF",a["pf"],"NET",a["net_pts"],flush=True)
        windows.append({"window":w,"start":str(frame.index[st]),"end":str(frame.index[ed-1]),
                        "bars":WINDOW,"cases":cases})
    return {"source":label,"total_m15":len(frame),"windows":windows}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    # 2026 source SHA pinned inside download().
    yr26=measure(download(),"2026_pinned")
    # Second provider public CSV, immutable Git commit; OOS is not virgin.
    yr25=measure(source()[0],"2025_external")
    result={"symbol":"XAUUSD ONLY","benchmark_user":{"gross_pts":21069,"n":154,
               "exact_mt5_comparable":False},
            "point_assumption":POINT,"model_cost_usd_oz":COST,"max_hold_M15_bars":HOLD,
            "rules":"3 exits 1/3 each; runner TP1=1R, TP2=2R, TP3=5R, stop BE after TP1, trailing 1.5ATR after TP2; only closed candle stop updates",
            "risk":"Stops fully rebuilt for reversed direction, not a negated past PnL",
            "limits":["OHLC replay not MT5 tick tester", "Spread and slippage modeled",
             "2025 previously researched, not blind holdout","No live orders or deployed EA"],
            "windows":[yr25,yr26]}
    (OUT/"RESULTADOS.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    rows=["# Ouro XAUUSD — inverter a mão e deixar lucro correr","",
          "Apenas XAUUSD, M15, blocos fixos de 10.000 candles.",
          "A entrada usa candle fechado e abertura seguinte. Reversão troca direção, stop, TPs e as condições de risco.",
          "Runner: TP1=1R, TP2=2R, TP3=5R, com 1/3 em cada; break-even após TP1 e trailing 1,5ATR após TP2 somente no fechamento.",
          "Wide: TP1=1,5R / TP2=3R / TP3=5R; basic: 1R / 1,5R / 2R.",
          "Custos hipotéticos US$ 0,80/onça round trip; USD 0,01 por ponto assumido.",
          "Não é teste MT5 de ticks bid/ask ou execução da corretora.","",
          "| Fonte | Janela | Estratégia | N | Green% | PF | Pontos brutos | Pontos líquidos | Líquidos custo x2 |",
          "|---|---:|---|---:|---:|---:|---:|---:|---:|"]
    for entry in result["windows"]:
        for window in entry["windows"]:
            for c in window["cases"]:
                rows.append("| "+" | ".join([entry["source"],str(window["window"]),c["case"],
                   str(c["n"]),str(c["win_pct"]),str(c["pf"]),str(c["gross_pts"]),
                   str(c["net_pts"]),str(c["cost_x2_net_pts"])])+" |")
    (OUT/"RELATORIO.md").write_text("\n".join(rows)+"\n")
    print("DONE_XAU_ONLY",json.dumps({"2025":yr25["windows"],"2026":yr26["windows"]},ensure_ascii=False),flush=True)
if __name__=="__main__":
    main()
