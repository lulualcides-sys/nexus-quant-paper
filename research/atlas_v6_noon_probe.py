"""V6 diagnostic: discard midday signals only because losses clustered there.

CAUTION: The 12:00-15:00 guard was DERIVED by inspecting the same WINM26/Q26
historical trades in V5. Testing those same months is *training-set*
exploration, not proof of generalization. July partial has already been
inspected at an aggregate level, so it is NOT an untouched holdout.

No real orders, no change to original strategy or paper-forward operation.
"""
from __future__ import annotations

import json
import tempfile
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch

from research.atlas_v5_loss_ranking import (
    WINDOWS,_fetch_pinned,RAW_Q26_URL,RAW_Q26_BLOB,
    canonicalize_q26_m5,_month_cut,_coverage,RESEARCH_CAPITAL_BRL,
    m26_fetch,m26_canonicalize,
)
from research.atlas_v5_cost_aware import v5_candidate
from research.win_price_data import TZ,local_day
from research import atlas_win_backtest as simulator

PROBES=("v1_reference","v6_v1_skip_12_15",
        "v3_reference","v6_v3_skip_12_15")
MINUTE_START=12*60
MINUTE_END=15*60
FEE_BRL=4.0
COSTS=(1,2)

def probe_signal(bars,i,variant):
    if variant not in PROBES:
        raise ValueError("Unknown V6 exploratory hypothesis")
    if i<100 or i>=len(bars):
        return 0
    parent="v1_reference" if variant in ("v1_reference","v6_v1_skip_12_15") else "v3_reference"
    raw=v5_candidate(bars,i,parent)
    if not raw or not variant.startswith("v6_"):
        return raw
    local=datetime.fromtimestamp(bars[i]["time"],timezone.utc).astimezone(TZ)
    minute=local.hour*60+local.minute
    if MINUTE_START<=minute<MINUTE_END:
        return 0
    return raw

def compare_imported(sources,provenance):
    result={
        "question":"Would vetoing newly generated 12-15h signals improve known losses?",
        "source":provenance,
        "research_capital_per_period_brl":RESEARCH_CAPITAL_BRL,
        "fee_brl_per_contract_roundtrip":FEE_BRL,
        "slippage_ticks_each_side":list(COSTS),
        "investigated_models":list(PROBES),
        "pattern_discovered_by_reviewing_test_periods":True,
        "holdout_independent":False,
        "july_2026_incomplete_and_aggregate_already_seen":True,
        "cost_model_same_as_v5":True,
        "no_production_change":True,
        "approved_for_live_or_paper":False,
        "by_period":{},
    }
    for name,ticker,start,end,full in WINDOWS:
        base=sources[ticker]["bars"]
        month=_month_cut(base,start,end)
        quality=_coverage(base,start,end)
        period={"symbol":ticker,"full_month":full,
                "coverage":quality,"models":{}}
        result["by_period"][name]=period
        if month is None or quality["days_with_65_m5"]<8:
            period["status"]="INSUFFICIENT_DATA"
            continue
        period["status"]="BACKTESTED"
        eligible=[start<=local_day(row["time"])<end for row in month]
        for model in PROBES:
            signals=[probe_signal(month,i,model) if i>=100 and eligible[i] else 0
                     for i in range(len(month))]
            with patch.object(simulator,"CAPITAL_BRL",RESEARCH_CAPITAL_BRL):
                with patch.object(simulator,"candidate",
                                  side_effect=lambda b,i,v,s=signals:s[i]):
                    scenarios={
                        str(ticks):simulator.simulate(month,timeframe="M5",
                                                     variant="original",fee_brl=FEE_BRL,
                                                     slip_ticks=ticks)
                        for ticks in COSTS
                    }
            period["models"][model]={
                "signals":sum(s!=0 for s in signals),
                "simulations":scenarios,
            }
    return result

def report(data):
    lines=[
        "# ATLAS V6 — teste exploratório do veto de sinais entre 12h e 15h",
        "",
        "**AVISO: filtro extraído das PERDAS históricas já vistas; NÃO é validação fora da amostra.**",
        "O mesmo custo, 30 mil reais de banca por período, 0,75% de risco, 3 contratos máximos, entrada/stop/alvo e M5.",
        "Resultados avaliados com 2 ticks de slippage em cada lado + R$4/contrato ida e volta.",
        "V1/V3 base versus as mesmas versões impedidas de sinalizar das 12h às 15h; nenhuma outra variável alterada.",
        "",
        "## Período a período — 2 ticks de slippage por lado",
        "| Contrato/período | Mês completo | V1 trades | V1 líquido R$ | V1 sem 12–15h trades | V1 sem 12–15h líquido R$ | V3 trades | V3 líquido R$ | V3 sem 12–15h trades | V3 sem 12–15h líquido R$ |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name,p in data["by_period"].items():
        if p.get("status")!="BACKTESTED":
            lines.append(f"| {name} | {p['full_month']} | INDISPONÍVEL | — | — | — | — | — | — | — |")
            continue
        def get(model,key):
            return p["models"][model]["simulations"]["2"].get(key)
        lines.append("| "+" | ".join(map(str,[
            name,"Sim" if p["full_month"] else "Não (parcial)",
            get("v1_reference","closed"),get("v1_reference","net_brl"),
            get("v6_v1_skip_12_15","closed"),get("v6_v1_skip_12_15","net_brl"),
            get("v3_reference","closed"),get("v3_reference","net_brl"),
            get("v6_v3_skip_12_15","closed"),get("v6_v3_skip_12_15","net_brl")
        ]))+" |")
    lines+=["","## Soma descritiva — só meses completos",
            "| Modelo | Operações | Resultado líquido 2 ticks R$ | Ganho/queda versus pai R$ |",
            "|---|---:|---:|---:|"]
    parent={"v1_reference":None,"v6_v1_skip_12_15":"v1_reference",
            "v3_reference":None,"v6_v3_skip_12_15":"v3_reference"}
    agg={}
    for model in PROBES:
        sims=[p["models"][model]["simulations"]["2"] for p in data["by_period"].values()
              if p.get("status")=="BACKTESTED" and p["full_month"]]
        agg[model]={"trades":sum(x["closed"] for x in sims),
                    "net":round(sum(x["net_brl"] for x in sims),2),
                    "positive_months":sum(x["net_brl"]>0 for x in sims),
                    "nmonths":len(sims)}
    for model in PROBES:
        a=agg[model];prior=parent[model]
        diff=round(a["net"]-agg[prior]["net"],2) if prior else "referência"
        lines.append(f"| {model} | {a['trades']} | {a['net']} | {diff} |")
    lines+=["","## Limitações e decisão",
        "- Um filtro extraído da própria amostra pode aparentar melhora por sobreajuste. Esta comparação verifica a hipótese, mas **não prova edge real**.",
        "- Julho incompleto é publicado por transparência, não entra na soma e não é holdout intocado: seu P&L agregado foi visto antes de escolher o horário.",
        "- Suprimir 12–15h pode reduzir o número de operações e eliminar algumas vencedoras; interpretar junto com os trades e a sensibilidade ao custo.",
        "- O motor não modela profundidade do livro, fila de ordens, margens da corretora ou execução de sinais do Tracker.",
        "- Nenhuma variante será automaticamente promovida; novo contrato/período ainda não examinado e forward paper são obrigatórios.",
        ""]
    return "\n".join(lines)

def main():
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)
        mraw=p/"m26.csv";mnorm=p/"m26_m5.csv"
        qraw=p/"q26.csv";qnorm=p/"q26_m5.csv"
        sm=m26_fetch(mraw)
        m=m26_canonicalize(mraw,mnorm)
        sq=_fetch_pinned(RAW_Q26_URL,RAW_Q26_BLOB,qraw)
        q=canonicalize_q26_m5(qraw,qnorm)
        result=compare_imported({"WINM26":m,"WINQ26":q},
                                {"WINM26":sm,"WINQ26":sq})
    markdown=report(result)
    print("ATLAS_V6_TIME_VETO_START",flush=True)
    print(markdown,flush=True)
    print("ATLAS_V6_TIME_VETO_END",flush=True)
    folder=Path("research/results");folder.mkdir(parents=True,exist_ok=True)
    (folder/"atlas_v6_noon_exploratory.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (folder/"atlas_v6_noon_exploratory.md").write_text(markdown+"\n",encoding="utf-8")

if __name__=="__main__":
    main()
