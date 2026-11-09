"""Independent historical WINQ26 sweep-reversal research, with a pinned real M1 CSV.

Only one new robot. Compare VWAP context enabled against one predefined ablation,
and costs 0/1/2 slippage ticks/side. The periods are NOT pristine holdouts:
other models already used portions of this third-party dataset.
"""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from research.atlas_winq26_public import SOURCE_BLOB, SOURCE_URL, SYMBOL, canonicalize, fetch
from research.win_liquidity_sweep import Parameters, simulate
from research.win_price_data import TZ, local_day, read_win_csv

PERIODS = {
    "2026_fev_mar": ("2026-02-13", "2026-04-01"),
    "2026_abr_mai": ("2026-04-01", "2026-06-01"),
    "2026_jun": ("2026-06-01", "2026-07-01"),
    "2026_jul": ("2026-07-01", "2026-08-01"),
}

def period_bars(bars, start, end):
    indices = [i for i, b in enumerate(bars) if start <= local_day(b["time"]) < end]
    if not indices:
        raise ValueError("Missing period " + start)
    return bars[max(0, indices[0]-70):indices[-1]+1]


def _snapshot(outcome):
    ledger=outcome.pop("ledger")
    loss_streak = 0
    worst_streak = 0
    for trade in ledger:
        loss_streak = loss_streak + 1 if trade["net_brl"] < 0 else 0
        worst_streak = max(worst_streak, loss_streak)
    outcome["worst_consecutive_reds"] = worst_streak
    outcome["stop_red_count"] = sum(t["why"].startswith("STOP_RED") for t in ledger)
    outcome["stop_win_count"] = sum(t["why"].startswith("STOP_WIN") for t in ledger)
    outcome["ledger"] = ledger
    return outcome


def study(bars, provenance, quality):
    if len(bars) < 30000:
        raise ValueError("The pinned WINQ26 M1 dataset is incomplete")
    result = {
        "strategy":"WIN Liquidity Sweep M1/M5 (independent robot)",
        "status":"EXPLORATORY_BACKTEST_NOT_VALIDATED",
        "data_source": provenance,
        "quality": quality,
        "instrument":"WINQ26 single-expiry unadjusted traded price grid",
        "candles_m1": len(bars),
        "capital_brl_per_independent_period": 2000,
        "max_positions_at_once":1,
        "daily_loss_limit":False,
        "cost_scenarios_slippage_ticks_each_side":[0,1,2],
        "declared_models":{
            "sweep_vwap":"sweep, volume, M5 veto, session OHLCV-VWAP proxy context",
            "sweep_no_vwap":"identical signal but without VWAP proxy filter (feature ablation)"
        },
        "periods":{},
        "warning":[
            "Source is historical third-party Profit export, independently unverified by B3",
            "M1 OHLC does not establish sequence or order-book fill priority",
            "Transaction cost is a sensitivity assumption rather than a broker quote",
            "No daily loss lockout could lead to ruin after consecutive losses",
            "The chosen data were previously inspected in other studies; not pristine OOS",
            "Stop losses may gap/slip further than the planned 1% risk",
            "No real orders, no automated broker connection, no promise of profits",
        ],
    }
    for period,(start,end) in PERIODS.items():
        part=period_bars(bars,start,end)
        entry={"start":start,"end_exclusive":end,"market_bars":sum(start<=local_day(b["time"])<end for b in part),
               "models":{}}
        for name,vwap in (("sweep_vwap",True),("sweep_no_vwap",False)):
            costs={}
            for ticks in (0,1,2):
                cfg=Parameters(require_vwap_context=vwap,slippage_ticks_each_side=ticks)
                stats=_snapshot(simulate(part,cfg,start_date=start,end_date=end))
                if any(not(start<=local_day(t["entry_time"])<end) for t in stats["ledger"]):
                    raise AssertionError("An entry occurred outside a data period")
                costs[str(ticks)]=stats
            entry["models"][name]=costs
        result["periods"][period]=entry

    def approved(name):
        for period in PERIODS:
            baseline=result["periods"][period]["models"][name]["1"]
            stress=result["periods"][period]["models"][name]["2"]
            if (baseline["trades"] < 30 or stress["trades"] < 30
                    or baseline["net_brl"] <= 0 or stress["net_brl"] <= 0
                    or (baseline["profit_factor"] or 0) < 1.2
                    or (stress["profit_factor"] or 0) < 1.2):
                return False
        return True

    result["retrospective_review_pass"]={name:approved(name) for name in ("sweep_vwap","sweep_no_vwap")}
    result["approved_for_real_orders"]=False
    return result


def report_md(report):
    lines=[
        "# Novo robô independente: WIN Liquidity Sweep M1/M5",
        "",
        "**Resultado histórico exploratório, não comprovante de rentabilidade.**",
        f"- Origem: {SOURCE_URL}",
        f"- Git blob SHA1 fixo: {SOURCE_BLOB}",
        f"- Candles M1 reais declarados pelo exportador terceiro: {report['candles_m1']}",
        "- Capital R$2.000 por janela, 1 WIN por vez, stops por trade, sem limite diário.",
        "- Filtros: falso rompimento com retorno para dentro da faixa, candle de rejeição, volume, momentum M5 e VWAP estimada.",
        "- Teste de controle: mesmo robô com filtro de VWAP desligado; parâmetros não ajustados após ver os resultados.",
        "- Custos: R$4 de ida/volta estimados mais 0, 1 ou 2 ticks de slippage por lado.",
        "",
        "## Resultado principal — 1 tick de slippage por lado",
        "",
        "| Janela | Versão | Candles | Trades | Acerto | Líquido R$ | PF | DD realizado | Maior série de RED |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|"
    ]
    for pname,item in report["periods"].items():
        for model in ("sweep_vwap","sweep_no_vwap"):
            x=item["models"][model]["1"]
            fmt=lambda x:"N/D" if x is None else str(x)
            lines.append(f"| {pname} | {model} | {item['market_bars']} | "
                         f"{x['trades']} | {fmt(x['winrate_pct'])}% | {x['net_brl']:+.2f} | "
                         f"{fmt(x['profit_factor'])} | {x['max_realized_drawdown_pct']}% | {x['worst_consecutive_reds']} |")
    lines+=["","## Sensibilidade a custo (resultado líquido em R$)","",
            "| Janela | Versão | 0 tick/lado | 1 tick/lado | 2 ticks/lado |",
            "|---|---|---:|---:|---:|"]
    for pname,item in report["periods"].items():
        for model in ("sweep_vwap","sweep_no_vwap"):
            x=item["models"][model]
            lines.append(f"| {pname} | {model} | {x['0']['net_brl']:+.2f} | {x['1']['net_brl']:+.2f} | {x['2']['net_brl']:+.2f} |")
    lines+=["","## Conclusão de avaliação",""]
    for name,value in report["retrospective_review_pass"].items():
        lines.append(f"- {name}: {'passou triagem histórica, ainda sem validação externa' if value else 'NÃO passou triagem histórica'}.")
    lines+=["",
        "Para avaliar lucro sustentável, exigir períodos inéditos de contrato e logs de paper-forward.",
        "Os dados foram reutilizados anteriormente para outros robôs; não considerar os meses como teste cego.",
        "O indicador VWAP é aproximação por candle, não VWAP de negócios ao nível de tick.",
        "O ledger JSON é reproduzível no artifact do GitHub Actions; não contém operações reais.",
        ""]
    return "\n".join(lines)


def main():
    with TemporaryDirectory() as temp:
        raw=Path(temp)/"WINQ26_raw.csv"
        normalized=Path(temp)/"WINQ26_M1.csv"
        provenance=fetch(raw)
        quality=canonicalize(raw,normalized)
        data=read_win_csv(normalized,expected_symbol=SYMBOL)
        result=study(data["bars"],provenance,quality)
    out=Path("research/results")
    out.mkdir(parents=True, exist_ok=True)
    (out/"win_liquidity_sweep_winq26.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    txt=report_md(result)
    (out/"win_liquidity_sweep_winq26.md").write_text(txt+"\n",encoding="utf-8")
    print("WIN_LIQUIDITY_RESULT_START",flush=True)
    print(txt,flush=True)
    print("WIN_LIQUIDITY_RESULT_END",flush=True)


if __name__=="__main__":
    main()
