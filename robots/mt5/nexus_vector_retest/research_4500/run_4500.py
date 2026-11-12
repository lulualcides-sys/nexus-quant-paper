#!/usr/bin/env python3
"""4500 distinct completed XAUUSD OHLC candles on M1,M5,M15,M30,H1.

Vector Retest PROXY only; never represents compiled MT5 EA execution.
Pinned public M1 snapshot + separate pinned historical H1 snapshot.
All 4500 candles are the evaluation window; 220 earlier bars warm up signals.
"""
from __future__ import annotations
import hashlib
import io
import json
import math
import sys
import urllib.request
from pathlib import Path
import pandas as pd

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
sys.path.insert(0,str(BASE))
from research_oos import (prepared, bars_for, raw_vector_events, raw_vwap_events,
                          COST_PER_OUNCE, metrics)
M1_SHA="a587597bbf88c2d868a00a4e0019cd705cee6ca4f20b0485d6b745f19fcc8225"
M1_URL=("https://raw.githubusercontent.com/getdata-finance/"
        "xauusd-1m-ohlcv-metals-historical-data/"
        "adcd99e7e0abee51e9a5eef123935e68a8d8aa30/XAUUSD_1m.csv")
# Separate source only because six months of M1 cannot yield 4500 H1 candles.
H1_URL=("https://huggingface.co/datasets/vichetkao/xauusd_dataset_2026/"
        "resolve/8ee2bd6/data/bars_reference/xauusd_H1.parquet")
BARS=4500
WARM=220
HOLD=48
TFS={"M1":1,"M5":5,"M15":15,"M30":30,"H1":60}
OUT=HERE/"results"

def fetch(url,expected_hash=None):
    request=urllib.request.Request(url,headers={"User-Agent":"NexusQuant-4500-Bar-Research/1.0"})
    with urllib.request.urlopen(request,timeout=180) as res:
        data=res.read()
    sha=hashlib.sha256(data).hexdigest()
    if expected_hash and sha!=expected_hash:
        raise ValueError(f"Unrecognized dataset: {sha} != {expected_hash}")
    if len(data)<15000:raise ValueError("Remote data unexpectedly small")
    return data,sha

def normalized(raw):
    """Normalize hourly broker-source bar fields without inventing OHLCV."""
    d=raw.copy()
    d.columns=[str(c).strip().lower() for c in d.columns]
    print("H1_COLS",list(d.columns),flush=True)
    if "datetime" in d.columns:
        series=d.pop("datetime")
    elif "time" in d.columns:
        series=d.pop("time")
    elif "timestamp" in d.columns:
        series=d.pop("timestamp")
    elif isinstance(d.index,pd.DatetimeIndex):
        series=pd.Series(d.index,index=d.index)
    else:
        raise ValueError("H1 source lacks an identifiable timestamp")
    if pd.api.types.is_numeric_dtype(series):
        vals=pd.to_numeric(series,errors="raise")
        unit="ms" if vals.abs().median()>1e11 else "s"
        when=pd.to_datetime(vals,unit=unit,utc=True,errors="raise")
    else:
        when=pd.to_datetime(series,utc=True,errors="raise")
    for label in ("open","high","low","close"):
        if label not in d.columns:raise ValueError("H1 source missing "+label)
        d[label]=pd.to_numeric(d[label],errors="raise")
    field=next((v for v in ("tick_volume","tickvol","volume","vol") if v in d.columns),None)
    if not field: raise ValueError("H1 source missing actual volume; cannot backtest RVOL")
    d["volume"]=pd.to_numeric(d[field],errors="coerce")
    if d["volume"].isna().any() or (d["volume"]<0).any() or (d["volume"]>0).sum()<4700:
        raise ValueError(f"H1 volume is incomplete: {field}")
    d=d[["open","high","low","close","volume"]]
    d.index=pd.DatetimeIndex(when,name="datetime")
    d=d.dropna().sort_index()
    if d.index.duplicated().any(): raise ValueError("Duplicate H1 timestamps")
    if not ((d.high>=d[["open","low","close"]].max(axis=1))&
            (d.low<=d[["open","high","close"]].min(axis=1))).all():
        raise ValueError("Bad H1 OHLC")
    print("H1_VOLUME_FIELD",field,"BARS",len(d),"DATE",d.index.min(),d.index.max(),flush=True)
    return d

def replay_bounded(frame,events,first_i):
    """Conservative 3x1/3 target fills, with unresolved end-of-data excluded.

    Slippage+spread approximated once per round trip at 0.60 USD per oz.
    No leverage, compounding, floating PnL, funding or broker commissions.
    """
    bar=frame.reset_index()
    last_exit=-1
    prev_dir=0
    last_entry=-1000000
    closed=[]
    unfinished=0
    for i,d,stop,score in events:
        if i+1>=len(bar):unfinished+=1;continue
        if i+1<=last_exit or i+1-last_entry<8 or d==prev_dir:continue
        entry=float(bar.iloc[i+1].open)
        risk=d*(entry-stop)
        if not math.isfinite(risk) or risk<=0:continue
        targets=[entry+d*risk*r for r in (1,1.5,2)]
        remaining=1.0
        next_tp=0
        earned=0.0
        out=None
        why="UNRESOLVED"
        last=min(len(bar)-1,i+1+HOLD)
        for j in range(i+1,last+1):
            b=bar.iloc[j]
            gap=(b.open<=stop if d>0 else b.open>=stop)
            stop_hit=(b.low<=stop if d>0 else b.high>=stop)
            if stop_hit: # assume stop BEFORE any TP in ambiguous OHLC candle
                exitprice=float(b.open) if gap else stop
                earned+=remaining*d*(exitprice-entry)
                out=j;why="SL";break
            for k in range(next_tp,3):
                hit=(b.high>=targets[k] if d>0 else b.low<=targets[k])
                if not hit:break
                share=remaining if k==2 else 1/3
                earned+=share*d*(targets[k]-entry)
                remaining-=share
                next_tp=k+1
            if next_tp==3:
                out=j;why="TP3";break
            if j==i+1+HOLD:
                earned+=remaining*d*(b.close-entry)
                out=j;why="TIME";break
        last_entry=i+1
        prev_dir=d
        if out is None:
            unfinished+=1
            last_exit=len(bar) # unresolved trade remains active
            continue
        last_exit=out
        net_per_ounce=earned-COST_PER_OUNCE
        closed.append({"signal_bar":int(i),"entry_bar":int(i+1),"exit_bar":int(out),
                       "dir":int(d),"score":round(float(score),4),"why":why,
                       "net_r":net_per_ounce/risk,
                       "net_usd_per_oz":net_per_ounce,"stop_risk_usd_per_oz":risk})
    return [x for x in closed if x["signal_bar"]>=first_i],unfinished

def make_metrics(deals):
    m=metrics(deals)
    if not deals:
        return {**m,"green":0,"red":0,"neutral":0,
                "net_usd_per_oz":0,"gross_plus_cost_assumed":None}
    green=sum(x["net_r"]>0 for x in deals)
    red=sum(x["net_r"]<0 for x in deals)
    flat=len(deals)-green-red
    money=sum(x["net_usd_per_oz"] for x in deals)
    return {**m,"green":green,"red":red,"neutral":flat,
            "net_usd_per_oz":round(money,2),
            "cost_usd_per_oz_each_trade":COST_PER_OUNCE}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    b1,digest=fetch(M1_URL,M1_SHA)
    d=pd.read_csv(io.BytesIO(b1),parse_dates=["datetime"])
    d["datetime"]=pd.to_datetime(d["datetime"],utc=True)
    for name in ("open","high","low","close","volume"):
        d[name]=pd.to_numeric(d[name],errors="raise")
    d=d.drop_duplicates("datetime").sort_values("datetime").set_index("datetime")
    if len(d)<100000:raise ValueError("M1 source too small")
    bh,hash_h1=fetch(H1_URL)
    h=normalized(pd.read_parquet(io.BytesIO(bh)))
    raw={"m1":{"url":M1_URL,"sha256":digest,"rows":len(d),
               "last":str(d.index.max())},
         "h1":{"url":H1_URL,"sha256":hash_h1,"rows":len(h),
               "last":str(h.index.max())}}
    result={"model":"Vector Retest proxy (NOT compiled EA)", "requested_bars":BARS,
            "warmup_bars":WARM,"cost_assumed_usd_per_oz":COST_PER_OUNCE,
            "max_hold_bars":HOLD,
            "notes":["Each timeframe uses exactly 4500 bars for the signal evaluation window.",
                     "Different bar durations = different calendar windows.",
                     "H1 series is a DIFFERENT provider from M1-M30; comparison is not same broker.",
                     "Results exclude unresolved positions and use conservative SL-first OHLC assumption.",
                     "No MT5 execution, historical ticks, exact spreads, slippage, or commissions."],
            "sources":raw,"cases":[]}
    for tf,minutes in TFS.items():
        bars=h if tf=="H1" else bars_for(d,minutes)
        if len(bars)<BARS+WARM:
            raise ValueError(f"Insufficient {tf} bars: {len(bars)} < {BARS+WARM}")
        prepared_frame=prepared(bars.tail(BARS+WARM))
        first=len(prepared_frame)-BARS
        used=prepared_frame.iloc[first:]
        assert len(used)==4500, (tf,len(used))
        print("EVAL",tf,"COUNT",len(used),"START",used.index.min(),"END",used.index.max(),flush=True)
        entry={"timeframe":tf,"bars":len(used),"start":str(used.index.min()),
               "end":str(used.index.max()),"source":("H1_HF" if tf=="H1" else "M1_GITHUB"),
               "models":[]}
        for label,fn in (("VECTOR_RETEST",raw_vector_events),("VWAP_PROXY",raw_vwap_events)):
            events=fn(prepared_frame)
            trades,unresolved=replay_bounded(prepared_frame,events,first)
            last_split=first+int(BARS*.7)
            metric=make_metrics(trades)
            metric_oos=make_metrics([x for x in trades if x["signal_bar"]>=last_split])
            entry["models"].append({"name":label,"signals_window":sum(x[0]>=first for x in events),
                                    "unresolved_end_excluded":unresolved,
                                    "full_4500":metric,
                                    "last_1350":metric_oos})
            print("RESULT",tf,label,"ALL",metric,"LAST_1350",metric_oos,flush=True)
        result["cases"].append(entry)
    (OUT/"results_4500.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines=["# Backtest histórico exploratório — XAUUSD / 4.500 candles por período","",
           "**Modelo:** Nexus Vector Retest (proxy Python do EA, NÃO EA compilado).",
           "**Fontes:** M1–M30 GitHub XAUUSD M1 SHA256 fixo; H1 HuggingFace parquet de outra origem, SHA256 gravado no JSON.",
           "**Método:** 4.500 candles avaliados em cada TF, com 220 candles ANTERIORES de aquecimento. Entrada na abertura seguinte. TP1/TP2/TP3 com 1/3 cada; stop-primeiro; máximo 48 barras; custos hipotéticos US$0,60/oz por ida e volta.",
           "**Importante:** não equivale a backtest MetaTrader 5, nem inclui dados bid/ask de ticks, comissão, swap ou execução real.","",
           "| Período | Data inicial | Data final | Modelo | 4.500 candles | Operações encerradas | GREEN | RED | Acerto | Profit Factor | Resultado R | DD R | Últimos 1.350 R |",
           "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for case in result["cases"]:
        for model in case["models"]:
            m=model["full_4500"]; o=model["last_1350"]
            lines.append("| "+ " | ".join([case["timeframe"],case["start"][:10],case["end"][:10],
                model["name"],str(case["bars"]),str(m["N"]),str(m["green"]),str(m["red"]),
                str(m["Win_pct"])+"%",str(m["PF"]),str(m["R_net"]),str(m["MDD_R"]),
                str(o["R_net"])])+" |")
    lines+=["","**R** = múltiplo do risco inicial por operação, não USD nem percentual da banca.",
            "**GREEN/RED** contam trades encerrados com P&L líquido proxy positivo/negativo após o custo fixo.",
            "Não converter resultados diretamente em dinheiro/lote sem especificação da corretora; período H1 tem provedor diferente."]
    (OUT/"REPORT_4500.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print("DONE 5 TF x 4500 bars",flush=True)
if __name__=="__main__":
    main()
