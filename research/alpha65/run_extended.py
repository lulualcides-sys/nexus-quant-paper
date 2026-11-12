#!/usr/bin/env python3
"""ALPHA65 historical transfer test: 6 months 2024 train, 6 months 2024 validation,
12 full 2025 months, fixed unchanged 3 candidate families from run.py.
Secondary archive Git SHA pinned, but NOT broker ticks and provenance unverified.
"""
from __future__ import annotations
import os
import hashlib
from pathlib import Path
import json
import pandas as pd
import run as core

ROOT=Path(os.environ.get("ALPHA65_EXTERNAL_GOLD_ROOT","thirdparty/gold"))
PIN="b2cfdc571ffac9eff9f2132ea6946da559d29af2"
PIN_URL="https://github.com/parshant65-lang/Gold-XAUUSD-1m-2020-2025-Historical-Data/tree/"+PIN
core.TRAIN=[f"2024-{m:02d}" for m in range(1,7)]
core.VALID=[f"2024-{m:02d}" for m in range(7,13)]
core.HOLDOUT=[f"2025-{m:02d}" for m in range(1,13)]
core.MONTHS=core.TRAIN+core.VALID+core.HOLDOUT
core.OUT=Path(__file__).resolve().parent/"results_extended_2025"
core.URL=PIN_URL
core.SHA="PENDING_COMPOSITE_SHA256"

def load_archive():
    files=sorted(ROOT.glob("XAUUSD/1m/2024/*/*.csv"))+sorted(ROOT.glob("XAUUSD/1m/2025/*/*.csv"))
    if len(files)<440:
        raise RuntimeError(f"Expected >440 daily XAUUSD files for 2024-25, found {len(files)}")
    h=hashlib.sha256()
    data=[]
    for p in files:
        raw=p.read_bytes()
        h.update(p.relative_to(ROOT).as_posix().encode()+b"\0"+hashlib.sha256(raw).digest())
        d=pd.read_csv(p,usecols=["timestamp","datetime_utc","open","high","low","close","volume"])
        d["datetime"]=pd.to_datetime(d["datetime_utc"],utc=True,errors="raise")
        d["timestamp"]=pd.to_numeric(d["timestamp"],errors="raise")
        ts_ms=d["datetime"].astype("int64")//1_000_000
        if not (d["timestamp"]==ts_ms).all():
            raise ValueError("Timestamp mismatch for "+str(p))
        if not (d["datetime"].dt.strftime("%Y-%m-%d")==p.stem[-10:]).all():
            raise ValueError("Daily file dated wrong: "+str(p))
        data.append(d[["datetime","open","high","low","close","volume"]])
    x=pd.concat(data,ignore_index=True)
    for col in ("open","high","low","close","volume"):
        x[col]=pd.to_numeric(x[col],errors="raise")
    if x["datetime"].duplicated().any():raise ValueError("Repeated minute in external source")
    x=x.sort_values("datetime").set_index("datetime")
    valid=((x.high>=x[["open","low","close"]].max(axis=1))&
           (x.low<=x[["open","high","close"]].min(axis=1))&
           (x.volume>=0))
    if not valid.all():raise ValueError("Invalid OHLCV in external source")
    if not ((x.index.year==2024)|(x.index.year==2025)).all():
        raise ValueError("Leakage out of calendar scope")
    hsum=h.hexdigest()
    core.SHA=hsum
    print("ALPHA65_EXTERNAL_DATA",json.dumps({"git_sha":PIN,"composite_sha256":hsum,
       "daily_files":len(files),"minute_rows":len(x),"first":str(x.index.min()),
       "last":str(x.index.max())}),flush=True)
    return x

def main():
    core.fetch=load_archive
    core.main()
    p=core.OUT/"RESULTS.json"
    result=json.loads(p.read_text())
    result["source"]["uri"]=PIN_URL
    result["source"]["git_sha"]=PIN
    result["source"]["type"]="THIRD_PARTY_PUBLIC_DAILY_CSV_OHLCV_BID_ASK_UNAVAILABLE"
    result["source"]["verified"]="Pinned Git commit, timestamp/OHLC and per-file hash checks; provider and feed NOT independently audited"
    result["months"]["train"]=core.TRAIN
    result["months"]["validation"]=core.VALID
    result["months"]["historically_seen_holdout"]=core.HOLDOUT
    result["months"]["holdout_is_virgin"]=False
    result["important"]=[
        "Only 2024/2025 OHLCV bars from a third-party GitHub archive. No broker bid/ask, quote timestamps or variable observed spread.",
        "2025 sample is 12 full calendar months by coverage, but not regulatory-quality tick backtest.",
        "No MQL5 MetaEditor compilation or MT5 Strategy Tester. Spread commission/slippage are explicit hypotheses.",
        "No martingale/grid; no live trading; rejected candidates stay isolated."
    ]
    result["approved"]=False
    p.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    rp=core.OUT/"REPORT.md"
    txt=rp.read_text()
    txt=txt.replace("Treino abril–maio; validação junho; julho–agosto examinados anteriormente (não holdout virgem).",
      "Treino jan–jun/2024; validação jul–dez/2024; teste adicional jan–dez/2025 (12 meses). Provedor alternativo OHLCV, sem ticks bid/ask; não homologado para corretora.")
    txt=txt.replace("179.662 barras M1","barras M1 do repositório alternativo")
    txt=txt.replace("**Não são condições reais da corretora; 12 meses OOS e ticks bid/ask não disponíveis nesta execução.**",
      "**Doze meses do arquivo público foram avaliados, mas não são ticks bid/ask nem condições reais da corretora.**")
    txt=txt.replace("Nenhuma alteração em VWAP, ATLAS, robôs preservados, main ou execução real. Critério final exige MT5 tick data bid/ask e pelo menos 12 meses OOS, ainda não satisfeitos.",
      "Nenhuma alteração em VWAP, ATLAS, robôs preservados, main ou execução real. A janela tem 12 meses, mas falta MT5 bid/ask ticks auditáveis com especificação e custos do broker.")
    rp.write_text(txt)
    print("ALPHA65_EXTENDED_FINISHED",json.dumps({"months":len(core.HOLDOUT),"best":result["selected_by_training_only"],
      "test":result["scenarios"][0]["test"],"source_sha":result["source"]["sha256"]},default=str),flush=True)
if __name__=="__main__":main()
