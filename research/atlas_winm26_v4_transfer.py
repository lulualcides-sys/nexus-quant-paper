"""One-shot V4 transfer audit on a DIFFERENT real-contract WINM26 M5 export.

Raw source: wesleyzilva/tradetech, pinned Git blob 6ee0eebd10e24ac40c073efe73883c313e6c27b1.
The same fixed six signals are tested WITHOUT adjusting thresholds.

This is neither a Tracker replica nor independent exchange-verified data.
M5 uses R$30k virtual research capital so the 0.75% nominal risk can afford
a single contract through normal 5-minute volatility. Do not compare nominal
BRL P&L with the WINQ26 M1 results on R$5k.
"""
from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from research.atlas_v4_filters import CANDIDATES, candidate
from research.win_price_data import _number, _tick_check, read_win_csv, local_day, win_session
from research import atlas_win_backtest as win

SOURCE_FILE = "dados/candles/2026-1S_M26/WINM26_F_0_5min.csv"
SOURCE_URL = "https://raw.githubusercontent.com/wesleyzilva/tradetech/main/" + SOURCE_FILE
SOURCE_GIT_SHA = "6ee0eebd10e24ac40c073efe73883c313e6c27b1"
SYMBOL = "WINM26"
RESEARCH_BANK = 30000.0
MONTHS = (
    ("2026-03","2026-03-01","2026-04-01"),
    ("2026-04","2026-04-01","2026-05-01"),
    ("2026-05_partial","2026-05-01","2026-05-15"),
)
SCENARIOS = (0,1,2)

def fetch_source(path):
    req=urllib.request.Request(SOURCE_URL,headers={"User-Agent":"ATLAS-WINM26-independent-transfer/1.0"})
    with urllib.request.urlopen(req,timeout=45) as response:
        raw=response.read(5_000_001)
    if not raw or len(raw)>5_000_000:
        raise ValueError("WINM26 size outside public-file bounds")
    git_sha=hashlib.sha1(b"blob "+str(len(raw)).encode()+bytes([0])+raw).hexdigest()
    if git_sha!=SOURCE_GIT_SHA:
        raise ValueError("Unpinned WINM26 M5 source changed")
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(raw)
    return {"url":SOURCE_URL,"git_blob":git_sha,"sha256":hashlib.sha256(raw).hexdigest(),
            "original_size_bytes":len(raw),"source_verified_by_exchange":False}

def canonicalize(raw_path,out_path):
    """Profit 9-col monetary-volume and contract quantity: use quantity only."""
    records=[]
    with Path(raw_path).open(encoding="utf-8-sig",newline="") as stream:
        for n,p in enumerate(csv.reader(stream,delimiter=";"),1):
            if not p or not any(x.strip() for x in p):
                continue
            if p[0].strip().lower()=="ativo":
                continue
            if len(p)!=9 or p[0].strip().upper()!=SYMBOL:
                raise ValueError(f"WINM26 M5 row {n}: expected 9 Profit columns and WINM26")
            ts=datetime.strptime(p[1].strip()+" "+p[2].strip(),"%d/%m/%Y %H:%M:%S")
            o,h,l,c=[_number(x) for x in p[3:7]]
            for v in (o,h,l,c):
                _tick_check(v)
            volume_fi,qty=_number(p[7]),_number(p[8])
            if l>min(o,c) or h<max(o,c) or volume_fi<=0 or qty<=0 or int(qty)!=qty:
                raise ValueError(f"WINM26 row {n}: invalid prices/volume")
            records.append((ts,o,h,l,c,int(qty)))
    if len(records)<1000: raise ValueError("Not enough genuine contract candles")
    records.sort()
    if any(records[k][0]<=records[k-1][0] for k in range(1,len(records))):
        raise ValueError("WINM26 duplicate candle")
    out_path=Path(out_path)
    with out_path.open("w",encoding="utf-8",newline="") as out:
        w=csv.writer(out,delimiter=";")
        w.writerow(["Ativo","Data","Hora","Open","High","Low","Close","Volume"])
        for ts,o,h,l,c,qty in records:
            w.writerow([SYMBOL,ts.strftime("%d/%m/%Y"),ts.strftime("%H:%M:%S"),
                        int(o),int(h),int(l),int(c),qty])
    imported=read_win_csv(out_path,expected_symbol=SYMBOL)
    if imported["timeframe_seconds"]!=300 or len(imported["bars"])!=len(records):
        raise ValueError("WINM26 expected genuine native M5")
    return imported

def _cut(bars,start,end):
    eligible=[i for i,b in enumerate(bars) if start<=local_day(b["time"])<end]
    if not eligible or eligible[0]<160:
        return None
    return bars[eligible[0]-160:eligible[-1]+1]

def _quality(bars,start,end):
    by_day=defaultdict(int)
    for b in bars:
        day=local_day(b["time"])
        if start<=day<end and win_session(b["time"]):
            by_day[day]+=1
    n=list(by_day.values())
    return {"market_days":len(n),
            "days_with_65_or_more_m5":sum(x>=65 for x in n),
            "market_m5":sum(n),
            "median_m5_per_day":sorted(n)[len(n)//2] if n else None}

def compare(imported,source):
    if imported["symbol"]!=SYMBOL or imported["timeframe_seconds"]!=300:
        raise ValueError("Must use WINM26 5-minute genuine contract")
    bars=imported["bars"]
    out={"symbol":SYMBOL,"timeframe":"M5","source":source,
         "same_frozen_variants_as_winq26":list(CANDIDATES),
         "test_type":"cross-contract historical transfer, no threshold tuning",
         "partial_may":"Data file ends 2026-05-14, May is NOT a full calendar month",
         "capital_brl":RESEARCH_BANK,"risk_fraction":win.RISK,
         "contract_limit":win.MAX_CONTRACTS,
         "cost_fee_brl_roundtrip_per_contract":4,
         "slip_ticks_each_side":list(SCENARIOS),
         "not_comparable_nominal_pnl_with_winq26_m1_r5000":True,
         "prospective_validation":False,"approved_for_live":False,
         "months":{}}
    for month,start,end in MONTHS:
        sample=_cut(bars,start,end)
        coverage=_quality(bars,start,end)
        row={"coverage":coverage,"variants":{},"diagnostics":{},
             "status":"OK" if sample and coverage["days_with_65_or_more_m5"]>=8 else "INSUFFICIENT_DATA"}
        out["months"][month]=row
        if row["status"]!="OK":continue
        belongs=[start<=local_day(b["time"])<end for b in sample]
        for model in CANDIDATES:
            signals=[candidate(sample,i,model) if i>=100 and belongs[i] else 0
                     for i in range(len(sample))]
            with patch.object(win,"CAPITAL_BRL",RESEARCH_BANK):
                with patch.object(win,"candidate",side_effect=lambda b,i,v,recorded=signals:recorded[i]):
                    results={str(slip):win.simulate(sample,timeframe="M5",variant="original",
                                                    fee_brl=4.0,slip_ticks=slip)
                             for slip in SCENARIOS}
            row["variants"][model]=results
            row["diagnostics"][model]={
                "signals":sum(s!=0 for s in signals),
                "entered":results["1"].get("entries"),
                "closed":results["1"].get("closed"),
                "open_at_end":results["1"].get("open_at_end"),
            }
    return out

def summary(out):
    lines=[
        "# ATLAS V4 — transferibilidade para outro vencimento WINM26 M5",
        "",
        "Pesquisa de 05/11/2026: parâmetros V4 não foram ajustados após o resultado anterior no WINQ26.",
        "Dados históricos terceirizados Profit, não certificados pela B3. Sem ordens reais.",
        "Importante: M5 e banca virtual de R$30 mil (risco 0,75%) NÃO são comparáveis em BRL à análise WINQ26 M1/R$5 mil.",
        "Maio de WINM26 termina dia 14; mês INCOMPLETO.",
        "",
        "| Mês | Dias com >=65 M5 | Modelo | Sinais | Trades | Winrate % | P&L R$ | PF | 2 ticks P&L R$ |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for month,data in out["months"].items():
        q=data["coverage"]
        if data["status"]!="OK":
            lines.append(f"| {month} | {q['days_with_65_or_more_m5']} | INSUFICIENTE | — | — | — | — | — | — |")
            continue
        for model,scenarios in data["variants"].items():
            x=scenarios["1"]
            stress=scenarios["2"]
            values=[month,q["days_with_65_or_more_m5"],model,
                    data["diagnostics"][model]["signals"],x.get("closed"),
                    x.get("winrate_pct"),x.get("net_brl"),x.get("profit_factor"),
                    stress.get("net_brl")]
            lines.append("| "+" | ".join("N/D" if v is None else str(v) for v in values)+" |")
    lines+=["","## Interpretação",
         "- Teste de transferibilidade, não busca de parâmetros lucrativos; o próximo período genuinamente prospectivo continua necessário.",
         "- A baixa liquidez do contrato distante, quantidade insuficiente de negócios e custo por ordem podem inviabilizar um filtro.",
         "- Não contar meses sem trades como meses lucrativos.",
         "- Nenhuma estratégia V4 será ativada no bot paper/real por este estudo.",
         ""]
    return "\n".join(lines)

def main():
    with tempfile.TemporaryDirectory() as d:
        raw=Path(d)/"winm26_source.csv"
        normalized=Path(d)/"winm26_M5.csv"
        source=fetch_source(raw)
        imported=canonicalize(raw,normalized)
        result=compare(imported,source)
    report=summary(result)
    print("ATLAS_V4_CROSS_CONTRACT_START",flush=True)
    print(report,flush=True)
    print("ATLAS_V4_CROSS_CONTRACT_END",flush=True)
    path=Path("research/results")
    path.mkdir(parents=True,exist_ok=True)
    (path/"atlas_v4_winm26_cross_contract.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (path/"atlas_v4_winm26_cross_contract.md").write_text(report+"\n",encoding="utf-8")

if __name__=="__main__": main()
