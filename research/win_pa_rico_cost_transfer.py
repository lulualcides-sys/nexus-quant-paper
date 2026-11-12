"""WIN Price Action M1/M5: other-expiry and broker-cost sensitivity.

Research with original frozen setups. No MT5 orders, no parameter fitting.
Contracts PINNED by Git blob hash, not adjusted continuous symbols.
"""
from __future__ import annotations

import json
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory

from research.atlas_winq26_public import fetch as fetch_q, canonicalize as normalize_q
from research.win_pa_winj26_replication import read_source as read_j
from research.win_price_action import Settings, simulate
from research.win_price_data import read_win_csv,local_day

SCENARIOS={
    "original_r6_1tick":(4.0,1),
    "rico_no_rlp_r3_40_1tick":(1.4,1),
    "rico_no_rlp_r5_40_2tick":(1.4,2),
    "hypothetical_rlp_r2_50_1tick":(0.5,1),
}
PERIODS={"WINQ26_June2026":("2026-06-01","2026-07-01"),
         "WINQ26_July2026_partial":("2026-07-01","2026-08-01")}
MAX_DD_ACCEPTABLE=15
MIN_TRADES_PER_WINDOW=100

def clean(s):
    trades=s.pop("trades")
    s["net_rr_median"]=round(median(t["planned_net_rr"] for t in trades),3) if trades else None
    s["trades_below_1_to_1"]=sum(t["planned_net_rr"]<1 for t in trades)
    s["trades"]=trades
    return s


def eval_bars(bars,*,start=None,end=None):
    result={}
    for name,(fee,slip) in SCENARIOS.items():
        for gate in (0.0,1.0):
            cfg=Settings(starting_brl=2000.0,risk_fraction=0.01,
                         fee_brl_roundtrip=fee,slip_ticks_per_side=slip,
                         min_net_rr=gate)
            score=clean(simulate(bars,cfg,start_local=start,end_local=end))
            if any((start and local_day(t["entry_time"])<start)
                   or (end and local_day(t["entry_time"])>=end)
                   for t in score["trades"]):
                raise ValueError("Backtest crossed research window")
            score["passes_any_review"] = (
                score["closed"]>=MIN_TRADES_PER_WINDOW
                and score["net_brl"]>0
                and (score["profit_factor"] or 0)>=1.2
                and score["max_realized_drawdown_pct"]<=MAX_DD_ACCEPTABLE
                and score["unverifiable_position_gap_exits"]==0
                and not score["open_at_end"]
            )
            result[name+("__baseline" if gate==0 else "__net_rr1")]=score
    return result


def study(qbars,jbars,source):
    if len(qbars)<35000 or len(jbars)<5000:
        raise ValueError("Pinned dataset unexpectedly short")
    results={
        "status":"NOT_FOR_LIVE_ORDERS",
        "source":source,
        "cost_models_brl_roundtrip":{k:round(f+2*t,2) for k,(f,t) in SCENARIOS.items()},
        "contracts":{"WINQ26":len(qbars),"WINJ26":len(jbars)},
        "analysis_not_pristine_holdout":True,
        "bankroll_brl_each_run":2000,
        "one_WIN_simultaneously":True,
        "no_daily_loss_limit":True,
        "stop_win_stop_red":True,
        "risk_planned_brl":20,
        "assumed_b3_fee_brl_roundtrip":0.50,
        "broker_fee_quote_not_verified_in_account":True,
        "windows":{},
        "approved_for_live":False,
    }
    for name,(start,end) in PERIODS.items():
        results["windows"][name]=eval_bars(qbars,start=start,end=end)
    results["windows"]["WINJ26_2025_fragmented"]=eval_bars(jbars)
    return results


def markdown(report):
    lines=[
        "# WIN Price Action — custos Rico + novo vencimento (pesquisa)",
        "",
        "**Nenhuma operação real. Não aprovado para MT5.**",
        "",
        "Parâmetros congelados do Price Action: M1 + M5, microtrendline, rompimento/reteste e faixa. Apenas fees, slippage e filtro econômico 1:1 variam.",
        "R$2.000 por janela, 1 contrato, sem stop diário, stop técnico e meta 2R brutos.",
        "",
        "Cenários: R$6 anterior; R$3,40 (Rico 0,45 por ordem por lado, B3 até 0,50 total + slippage 1 tick/lado); R$5,40 (2 ticks/lado); R$2,50 com RLP hipotético sujeito a habilitação e condições.",
        "Promoção MetaTrader de R$0,26/contrato não foi presumida. Custos são aproximados, execução de robôs pela Rico não confirmada.",
        "",
        "### Resultados exploratórios",
        "",
        "| Contrato / janela | Custo | Filtro | Fechadas | Líquido R$ | PF | Mediana R/R líquido | Buracos enquanto aberto |",
        "|---|---|---|---:|---:|---:|---:|---:|"
    ]
    for window,scenarios in report["windows"].items():
        for key,s in scenarios.items():
            scenario,gate=key.split("__")
            pf=s["profit_factor"] if s["profit_factor"] is not None else "N/D"
            rr=s["net_rr_median"] if s["net_rr_median"] is not None else "N/D"
            lines.append(f"| {window} | {scenario} | {gate} | {s['closed']} | {s['net_brl']:+.2f} | "
                         f"{pf} | {rr} | {s['unverifiable_position_gap_exits']} |")
    lines+=["",
        "### Veredito",
        "",
        "- O outro vencimento WINJ26 tem apenas 5.129 M1 espalhados entre dias de 2025, insuficiente para resultados conclusivos.",
        "- WINQ26 já foi analisado nas pesquisas anteriores; lucro de julho, se houver, não equivale a ganho independente.",
        "- Para validação, requerer mais de 100 trades em múltiplos vencimentos não vistos e resultado positivo nos custos estressados e validação prospectiva.",
        "- Qualquer interrupção dos candles com posição aberta invalida aprovação; sem correspondência real entre OHLC e fila de execução.",
        "- Corrigir perdas com risco maior ou posterior escolha de janelas é proibido; manter PR em rascunho.",
        ""
    ]
    return "\n".join(lines)


def main():
    with TemporaryDirectory() as tmp:
        p=Path(tmp)
        source_q=fetch_q(p/"qraw.csv")
        normalize_q(p/"qraw.csv",p/"qnormal.csv")
        q=read_win_csv(p/"qnormal.csv",expected_symbol="WINQ26")
        j,source_j=read_j(p/"jnormal.csv")
        report=study(q["bars"],j["bars"],{"WINQ26":source_q,"WINJ26":source_j})
    out=Path("research/results");out.mkdir(parents=True,exist_ok=True)
    (out/"win_pa_rico_cost_transfer.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    md=markdown(report)
    (out/"win_pa_rico_cost_transfer.md").write_text(md+"\n",encoding="utf-8")
    print("PA_TRANSFER_START",flush=True);print(md,flush=True);print("PA_TRANSFER_END",flush=True)


if __name__=="__main__":
    main()
