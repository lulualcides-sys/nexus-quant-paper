#!/usr/bin/env python3
"""Transfer test of FIXED EMA21_PULLBACK M15 strategy against VWAP_PROXY on
independent 2025 daily public XAUUSD M1 OHLCV archive; no new optimization.
"""
import os, json,hashlib
from pathlib import Path
import pandas as pd
from points10k import events, simulate, stats, WINDOW, WARM, POINT, COST
from research_oos import prepared,bars_for,raw_vwap_events
ROOT=Path(os.environ.get("EXTERNAL_GOLD_ROOT","thirdparty/gold"))
OUT=Path(__file__).resolve().parent/"points10k_2025_results"
PIN="b2cfdc571ffac9eff9f2132ea6946da559d29af2"
def source():
    p=sorted(ROOT.glob("XAUUSD/1m/2025/*/*.csv"))
    if len(p)<260:raise RuntimeError(f"Not enough 2025 daily source files: {len(p)}")
    ledger=[];dfs=[]
    for file in p:
        data=file.read_bytes()
        digest=hashlib.sha256(data).hexdigest()
        ledger.append([file.relative_to(ROOT).as_posix(),digest])
        x=pd.read_csv(file,usecols=["timestamp","datetime_utc","open","high","low","close","volume"])
        x["datetime"]=pd.to_datetime(x["datetime_utc"],utc=True,errors="raise")
        unixms=(x["datetime"].astype("int64")//1000000)
        if not (unixms==pd.to_numeric(x["timestamp"])).all():raise ValueError(f"Time mismatch {file}")
        dfs.append(x[["datetime","open","high","low","close","volume"]])
    d=pd.concat(dfs,ignore_index=True)
    if d.datetime.duplicated().any():raise ValueError("Duplicate minute")
    for k in ["open","high","low","close","volume"]:d[k]=pd.to_numeric(d[k],errors="raise")
    d=d.sort_values("datetime").set_index("datetime")
    valid=(d.high>=d[["open","close","low"]].max(axis=1))&(d.low<=d[["open","close","high"]].min(axis=1))&(d.volume>=0)
    if not valid.all():raise ValueError("Invalid OHLCV")
    return d,ledger
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    raw,manifest=source()
    (OUT/"DATA_SHA256.json").write_text(json.dumps({"pinned_git_commit":PIN,
         "daily_files":len(manifest),"sha256_files":manifest},indent=2)+"\n")
    bars=prepared(bars_for(raw,15))
    count=(len(bars)-WARM)//WINDOW
    if count<2:raise ValueError(f"Less than two complete 10k-bar M15 windows: {len(bars)}")
    result={"dataset_git_commit":PIN,"source_daily_files":len(manifest),"m1_bars":len(raw),
            "m15_bars":len(bars),"m15_full_10k_windows":count,
            "period_start":str(bars.index.min()),"period_end":str(bars.index.max()),
            "same_rules_as_2026":True,"point":POINT,"cost_assumption_usd_oz":COST,
            "notes":"Independent source, bid/ask and broker ticks unavailable; no retraining.",
            "results":[]}
    for name,signals in [
        ("EMA21_PULLBACK",events(bars,"EMA21_PULLBACK")),
        ("VWAP_PROXY",raw_vwap_events(bars))
    ]:
        rows=[]
        for window in range(count):
            start=WARM+window*WINDOW;end=start+WINDOW
            trades=simulate(bars,signals,start,end,(1,1.5,2))
            metrics=stats(trades)
            rows.append({"window":window,"first":str(bars.index[start]),
                         "last":str(bars.index[end-1]),**metrics})
            print("CHECK",name,"BLOCK",window,"STATS",metrics,flush=True)
        result["results"].append({"strategy":name,"windows":rows,
            "total_N":sum(z["N"] for z in rows),
            "net_points":round(sum(z["net_pts"] for z in rows),1),
            "positive_windows":sum(z["net_pts"]>0 for z in rows)})
    (OUT/"VALIDACAO_2025.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    head=["# Validação 2025 — EMA21 Pullback M15 sem mudar parâmetros",
          "","Fonte: repositório secundário XAUUSD M1 OHLCV com commit Git fixo; não é execução MT5 real.",
          f"{len(raw)} M1, {len(bars)} M15, {count} janelas completas de 10.000 candles M15.",
          f"Ponto assumido={POINT}, custo hipotético ida/volta={COST} USD/oz, três TPs e prioridade ao SL.",
          "","| Modelo | Janela | N | GREEN | Acerto | PF | Pontos brutos | Pontos líquidos |",
          "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for row in result["results"]:
        for x in row["windows"]:
            head.append("| "+ " | ".join([row["strategy"],str(x["window"]),str(x["N"]),
             str(x["GREEN"]),str(x["win_pct"]),str(x["PF"]),
             str(x["gross_pts"]),str(x["net_pts"])])+" |")
    head+=["","A ausência de bid/ask e slippage reais impede homologação para conta real.",
           "O VWAP_PROXY é uma referência aproximada, não a instalação exata do usuário.",""]
    (OUT/"RELATORIO_2025.md").write_text("\n".join(head))
    print("FINISHED_2025",json.dumps({"windows":count,"models":[{"strategy":r["strategy"],
                 "total_N":r["total_N"],"net_points":r["net_points"],"positive_windows":r["positive_windows"]}
                 for r in result["results"]]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
