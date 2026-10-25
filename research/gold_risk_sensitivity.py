"""Sensitivity analysis — increase planned *risk*, never manufacture accuracy.

Freeze top five gold methods ranked solely by the older development period.
Keep same entries, costs, stops and next-bar execution.
Compare risk 0.5%, 0.75%, 1.0%, plus double-fee stress in 2025-26.
Only backward-looking simulations, never real FBS orders.
"""
import json
from pathlib import Path
from research import screen_v2
from research.screen_v2 import (aggregate_hourly_to_h4,STRATEGIES,MARKETS,
                                 evaluate,TRAIN_START,CUTOFF,TEST_END,training_gate)
from research.backtest_year import get_history

RISKS=(0.005,0.0075,0.01)
BOT_COUNT=5

def main():
    bars=aggregate_hourly_to_h4(get_history(MARKETS["XAUUSD"]))
    inds=screen_v2.make_indicators(bars)
    screen_v2.RISK=0.005
    dev=[]
    for strat in STRATEGIES:
        d=evaluate(bars,inds,strat,"XAUUSD",TRAIN_START,CUTOFF)
        if training_gate(d):
            dev.append((strat,d))
    dev.sort(key=lambda x:(x[1]["return_pct"],-x[1]["max_dd_pct"]),reverse=True)
    picks=dev[:BOT_COUNT]
    result={"disclaimer":"EX POST risk sensitivity, NOT FBS execution or expected future ROI",
            "selection":"5 top training-positive gold candidates picked exclusively from older period",
            "periods":["2024-10-24..2025-10-23 TRAIN","2025-10-24..2026-10-24 RETROSPECTIVE REVIEW (previously inspected)"],
            "market":"XAUUSD","ticker_reference":"GC=F futures, not FBS CFD",
            "risk_levels":RISKS,"strategies":[]}
    for strat,devrow in picks:
        s={"strategy":strat,"train_0p5":devrow,"alternatives":[]}
        for risk in RISKS:
            screen_v2.RISK=risk
            regular=evaluate(bars,inds,strat,"XAUUSD",CUTOFF,TEST_END)
            stress=evaluate(bars,inds,strat,"XAUUSD",CUTOFF,TEST_END,2)
            s["alternatives"].append({"risk":risk,"review":regular,"double_fees":stress,
                "negative_months":sum(x<0 for x in regular["monthly"].values())})
            print(strat,risk,"pnl",regular["pnl_usd"],"dd",regular["max_dd_pct"],flush=True)
        result["strategies"].append(s)
    header=[
    "# Ouro H4 — teste de sensibilidade ao risco (sem prometer ganhos)",
    "",
    "**Todos os números são backtests retrospectivos em dados de referência, não ordens da FBS.**",
    "A seleção foi feita apenas por desempenho no desenvolvimento de 2024–2025. O ano seguinte já foi examinado em pesquisas anteriores, portanto não pode comprovar independência.",
    "Foram preservadas as regras originais, entradas na abertura posterior ao sinal, custos estimados e cenários com taxas em dobro.",
    "",
    "| Robô | Risco/entrada | Retorno 12m | Drawdown | P&L US$ | Custos dobrados (P&L) | Meses negativos |",
    "|---|---:|---:|---:|---:|---:|---:|"]
    for s in result["strategies"]:
        for v in s["alternatives"]:
            z=v["review"];x=v["double_fees"]
            header.append(f'| {s["strategy"]} | {100*v["risk"]:.2f}% | {z["return_pct"]:+.2f}% | {z["max_dd_pct"]:.2f}% | {z["pnl_usd"]:+.2f} | {x["pnl_usd"]:+.2f} | {v["negative_months"]} |')
    header+=["","**Importante:** aumentar risco proporcionalmente não cria vantagem; apenas amplifica ganhos e perdas. Estratégias do mesmo ativo podem perder juntas.",
            "Não adotar risco alto em conta real sem meses de observação prospectiva e comprovação de custos específicos da corretora."]
    path=Path("research/results");path.mkdir(exist_ok=True,parents=True)
    (path/"gold_risk_sensitivity.md").write_text("\n".join(header)+"\n")
    (path/"gold_risk_sensitivity.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
if __name__=="__main__":main()
