#!/usr/bin/env python3
"""Replay eight existing allowed-timeframe XAU candidates using source rules.

Historical OHLC replay, NOT MT5 execution and not 12 actual compiled EAs.
Source data 2025/full or 2026/partial Q2/Q3 pinned public provenance.
"""
from __future__ import annotations
import argparse
import csv
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/"pesquisa_python"))

from points10k_2025 import source as source_2025
from research_oos import download as source_2026
from alpha_xau_mtf_2025plus import (
    COST_GRID,horizon_bars,windows_by_quarter,replay_one,summarize)
from xau_exit_risk_batch6_2025plus import entry_inputs,risk_stats
from xau_entry_quality_batch7_2025plus import gate_signals
from xau_session_batch9_2025plus import source_events

PLANS=(
("XAU_EMA21_RUNNER_M15",15,"base","EMA21_BASE"),
("XAU_EMA21_RSI_MACD_M30",30,"base","EMA21_RSI_MACD"),
("XAU_EFFICIENCY_ER20_BREAK_M30",30,"base","EFFICIENCY_ER20_BREAK"),
("XAU_SHOCK_EXHAUSTION_M5",5,"base","SHOCK_EXHAUSTION"),
("XAU_SHOCK_EXHAUSTION_M15",15,"base","SHOCK_EXHAUSTION"),
("XAU_EMA21_RSI_MACD_M30_COST_TO_STOP_10PCT",30,"entry_cost_gate","EMA21_RSI_MACD"),
("XAU_VWAP_EMA_RECLAIM_M30",30,"session","VWAP_EMA_RECLAIM"),
("XAU_ASIA_TREND_BREAK_M30",30,"session","ASIA_TREND_BREAK"),
)
ALLOWED=(1,5,15,30)


def input_for(raw,tf,kind,model):
    if tf not in ALLOWED:raise ValueError("Somente M1/M5/M15/M30")
    if kind=="base":
        return entry_inputs(raw,tf,model)
    if kind=="entry_cost_gate":
        df,ev=entry_inputs(raw,tf,model)
        return df,gate_signals(df,ev,"COST_TO_STOP_LE_10PCT")
    if kind=="session":
        return source_events(raw,tf,model)
    raise ValueError("unknown stored candidate")


def test_plan(raw,period,cost,plan):
    id,tf,kind,model=plan
    df,events=input_for(raw,tf,kind,model)
    trades=[]
    qresults=[]
    for quarter,start,last in windows_by_quarter(df,horizon_bars(tf)):
        if start is None:
            continue
        items=replay_one(df,events,start,last,tf,"RUNNER_96H")
        trades.extend(items)
        s={**summarize(items,cost),**risk_stats(items,events,df,cost)}
        qresults.append(dict(quarter=quarter,N=s["N"],
                net_points=s["net_pts"],PF=s["PF"],
                net_R=s["net_R"],PF_R=s["PF_R"]))
    s={**summarize(trades,cost),**risk_stats(trades,events,df,cost)}
    return dict(id=id,period=period,TF="M"+str(tf),
        signal_family=model,N=s["N"],
        net_points=s["net_pts"],PF=s["PF"],
        drawdown_closed_points=s["mdd_pts"],
        net_R=s["net_R"],PF_R=s["PF_R"],
        drawdown_closed_R=s["MDD_R"],
        quarters=qresults,
        user_approval="RESEARCH_ONLY_NOT_LIVE",
        real_broker_ticks=False)


def main():
    parser=argparse.ArgumentParser(description="Replay research of eight XAUUSD candidates (not MT5 EAs)")
    parser.add_argument("--periodo",choices=["2025","2026"],default="2026")
    parser.add_argument("--custo",type=float,default=1.2,
                        help="custo hipotético por onça ida+volta: 0.8, 1.2 ou 1.6")
    args=parser.parse_args()
    if args.custo not in COST_GRID:
        parser.error("Escolha --custo 0.8, 1.2 ou 1.6")
    try:
        raw=source_2025()[0] if args.periodo=="2025" else source_2026()
    except Exception as e:
        raise SystemExit("Falha ao carregar dados históricos. Verifique internet e,"
           " para 2025, PREPARAR_DADOS_2025.bat: "+str(e))
    rows=[]
    for plan in PLANS:
        row=test_plan(raw,args.periodo,args.custo,plan)
        rows.append(row)
        print(f"{row['id']} | N={row['N']} | pontos={row['net_points']} |"
              f" PF={row['PF']} | R={row['net_R']}",flush=True)
    dest=ROOT/"resultados"
    dest.mkdir(parents=True,exist_ok=True)
    label="2026_parcial" if args.periodo=="2026" else "2025"
    obj=dict(symbol="XAUUSD",period=label,assumed_cost_usd_per_oz=args.custo,
        point_assumption_price_change=0.01,
        note="Replayed OHLC, no MT5 broker real ticks; historical results not true account returns",
        results=rows)
    jsonpath=dest/f"resultados_{label}_8_candidatos.json"
    jsonpath.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    csvpath=dest/f"resultados_{label}_8_candidatos.csv"
    fields=["id","TF","N","net_points","PF","drawdown_closed_points",
            "net_R","PF_R","drawdown_closed_R"]
    with csvpath.open("w",newline="",encoding="utf-8-sig") as f:
        writer=csv.DictWriter(f,fieldnames=fields)
        writer.writeheader()
        writer.writerows({k:row.get(k) for k in fields} for row in rows)
    print("ARQUIVOS:",jsonpath,csvpath,sep="\n")


if __name__=="__main__":
    main()
