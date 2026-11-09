"""Frozen cross-contract transfer, fee sensitivity and net-payoff audit.

This is research, never MT5 order routing. Costs are *scenarios*, not a broker
account statement. Price data are pinned third-party single-expiry Profit files.
WINJ26 is previously seen in other bots, so not a pristine global holdout.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from statistics import median

from research.atlas_winq26_public import fetch as fetch_q, canonicalize as canonicalize_q
from research.win_j26_pinned import fetch as fetch_j
from research.win_liquidity_sweep import Parameters, simulate
from research.win_price_data import local_day, read_win_csv

# Fee roundtrip = B3 up to R$0.50 + Rico nominal brokerage each side.
# 0.45/side day-trade without RLP on Rico costs page. MT5 broker page lists
# a 0.26-contract promotional PLAN; not assumed eligible for EA/live usage.
# RLP is NOT presumed authorized for automated routing; scenario only.
#
# One tick WIN=5 points=R$1 per side; 2 ticks both sides=R$4 slippage total.
SCENARIOS={
    "old_r6_1tick":(4.00,1),                  # R$6 modeled total
    "rico_no_rlp_1tick":(1.40,1),             # ~R$3.40 total
    "rico_no_rlp_2tick":(1.40,2),             # ~R$5.40 total stress
    "rico_rlp_hypothetical_1tick":(0.50,1),   # ~R$2.50 total, NOT guaranteed
}

# Freeze unchanged technical setup; one trade at a time, no daily lockout.
# Compare original and cost-only economic veto >= 1 net win per 1 net loss.
GATES={"baseline":0.0,"min_net_rr_1":1.0}
Q26_WINDOWS={
    "WINQ26_2026_june":("2026-06-01","2026-07-01"),
    "WINQ26_2026_july_partial":("2026-07-01","2026-08-01"),
}
MIN_VALID_TRADES=100


def score(raw):
    ledger=raw.pop("ledger")
    raw["exit_reasons"]={k:sum(x["why"]==k for x in ledger) for k in sorted({x["why"] for x in ledger})}
    raw["median_planned_net_rr"]=round(median(x["planned_net_rr"] for x in ledger),3) if ledger else None
    raw["under_1_net_rr"]=sum(x["planned_net_rr"] < 1.0 for x in ledger)
    raw["ledger"]=ledger
    return raw


def run_one(bars,*,label,start=None,end=None):
    result={"label":label,"days":len({local_day(b["time"]) for b in bars}),
            "m1_candles":len(bars),"variants":{}}
    for scenario,(fees,slippage) in SCENARIOS.items():
        for gate_name,net_rr in GATES.items():
            # Reset same 2k bankroll separately by run; no cross-window carry.
            cfg=Parameters(capital_brl=2000.0,per_trade_risk=0.01,
                           fee_roundtrip_brl=fees,
                           slippage_ticks_each_side=slippage,
                           min_net_rr=net_rr,
                           require_vwap_context=True)
            outcome=score(simulate(bars,cfg,start_date=start,end_date=end))
            if any((start and local_day(t["entry_time"]) < start) or
                   (end and local_day(t["entry_time"]) >= end)
                   for t in outcome["ledger"]):
                raise AssertionError("entry escaped period")
            outcome["research_sufficient"] = (
                outcome["trades"] >= MIN_VALID_TRADES
                and outcome["unverifiable_position_gap_exits"] == 0
                and not outcome["open_at_end"]
                and outcome["net_brl"] > 0
                and (outcome["profit_factor"] or 0) >= 1.2
            )
            result["variants"][f"{scenario}__{gate_name}"]=outcome
    return result


def build(qbars,jbars,provenance):
    if len(qbars)<35000 or len(jbars)<5000:
        raise ValueError("History unexpectedly shortened")
    result={
        "status":"OFFLINE_RESEARCH_NOT_LIVE",
        "assumptions":"R$2,000 per scenario/window; 1 WIN, 1% planned risk/trade, no daily stop",
        "sources":provenance,
        "contracts":["WINQ26","WINJ26"],
        "costs_brl_roundtrip":{k:round(f+2*t*1.0,2) for k,(f,t) in SCENARIOS.items()},
        "fees_not_confirmed_for_specific_MT5_account":True,
        "new_periods_truly_blind":False,
        "leakage_statement":"WINJ26 other-expiry has been inspected in previous Price Action work; no pristine new external series",
        "replay_limitations":[
            "M1 OHLC cannot resolve stop vs target ordering; pessimistic stop preference",
            "No real broker fills, spread/queue/slippage events or independent B3 feed attestation",
            "B3 R$0.50 quoted roundtrip is public educational maximum, not client statement",
            "Rico minicontract rate 0.45/side without RLP and MetaTrader promotional plan may differ in actual user account",
            "RLP activation and eligibility for EAs are not verified",
            "Only 5129 WINJ26 M1 bars across several months: not full continuous months",
            "No guaranteed profits; July 2026 is partial; data used previously for model exploration",
            "Simulated 1% can be exceeded on gaps and abnormal market moves",
        ],
        "windows":{},
    }
    # Use full Q26 for warmup, report only period entries.
    for window,(start,end) in Q26_WINDOWS.items():
        result["windows"][window]=run_one(qbars,label=window,start=start,end=end)
    result["windows"]["WINJ26_2025_partial_export"]=run_one(jbars,label="WINJ26_2025_partial_export")
    result["approved_for_real_money"]=False
    return result


def markdown(report):
    lines=[
        "# WIN Liquidity Sweep — custo realista vs execução e outro contrato",
        "",
        "**Pesquisa sem corretora; nenhuma versão aprovada para operar.**",
        "",
        "Base congelada: a mesma estratégia Liquidity Sweep, risco planejado 1% de R$2.000, 1 WIN, stops por operação, sem limite diário. Filtro adicional compara apenas R/R líquido mínimo 1:1.",
        "",
        "Fontes pinadas: WINQ26 35.574 M1 (2026); WINJ26 5.129 M1 (2025). Terceiros atribuem a exportação ao Profit; não há autenticação B3 independente.",
        "",
        "## Custos por operação completa, inclusive slippage simulado",
        "",
        "| Cenário | Total R$ | Descrição |",
        "|---|---:|---|",
        "| old_r6_1tick | 6,00 | Hipótese anterior R$4 fixos + 1 tick cada lado |",
        "| rico_no_rlp_1tick | 3,40 | R$0,45/cada lado pela Rico + R$0,50 B3 estimados + 1 tick/lado |",
        "| rico_no_rlp_2tick | 5,40 | Mesmo custo nominal, estressando 2 ticks/lado |",
        "| rico_rlp_hypothetical_1tick | 2,50 | RLP gratuito divulgado + B3 R$0,50 + 1 tick/lado: **não confirmar elegibilidade de robô** |",
        "",
        "A página do MT5 da Rico tem oferta específica de R$0,26/contrato condicionada a plano. Não a presumimos válida para todo perfil, nem contabilizamos descontos sem extrato.",
        "",
        "## Simulação por contrato e janela",
        "",
        "| Amostra | Cenário | Filtro econômico | Trades | Liquido R$ | PF | R/R líquido mediano | Buracos durante trade |",
        "|---|---|---|---:|---:|---:|---:|---:|"
    ]
    for key,window in report["windows"].items():
        for label,score in window["variants"].items():
            scenario,gate=label.split("__")
            pf=score["profit_factor"] if score["profit_factor"] is not None else "N/D"
            rr=score["median_planned_net_rr"] if score["median_planned_net_rr"] is not None else "N/D"
            lines.append(f"| {key} | {scenario} | {gate} | {score['trades']} | {score['net_brl']:+.2f} | {pf} | {rr} | {score['unverifiable_position_gap_exits']} |")
    lines+=["",
        "## Veredito de pesquisa",
        "",
        "- Critério pré-definido: pelo menos 100 operações em cada contrato/período suficiente, P&L positivo, PF>=1,2, zero execuções não verificáveis, custo estressado positivo, e validação prospectiva.",
        "- **Não promover com apenas contratos ou meses já vistos na pesquisa.** O segundo vencimento ainda cobre poucos pregões e foi inspecionado por outro robô.",
        "- A matemática dos custos é uma aproximação de pesquisa, não sua nota de corretagem; custos, RLP e execução de robôs no MetaTrader exigem verificação no ambiente da Rico.",
        "- Deixar PR draft; não integrar ao MT5 nem enviar ordens.",
        "",
        "## Evidência e reproduzibilidade",
        "",
        "- CI roda o parser de fonte com hash, os testes determinísticos da estratégia e o motor de comparação; JSON íntegro fica no artifact da execução por 30 dias.",
        "- Para novos contratos, exigimos preços brutos sem ajuste e sem mistura de vencimentos; futuro contínuo WINFUT não é uma fita executável de contrato único.",
        ""]
    return "\n".join(lines)


def main():
    with TemporaryDirectory() as temp:
        p=Path(temp)
        q_raw=p/"q26-raw.csv"
        q_converted=p/"WINQ26-M1.csv"
        prov_q=fetch_q(q_raw)
        canonicalize_q(q_raw,q_converted)
        q=read_win_csv(q_converted,expected_symbol="WINQ26")
        j,prov_j=fetch_j(p/"WINJ26-M1.csv")
        report=build(q["bars"],j["bars"],{"WINQ26":prov_q,"WINJ26":prov_j})
    out=Path("research/results")
    out.mkdir(parents=True,exist_ok=True)
    (out/"win_sweep_cross_contract_costs.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    txt=markdown(report)
    (out/"win_sweep_cross_contract_costs.md").write_text(txt+"\n",encoding="utf-8")
    print("CROSS_CONTRACT_START",flush=True)
    print(txt,flush=True)
    print("CROSS_CONTRACT_END",flush=True)


if __name__=="__main__":
    main()
