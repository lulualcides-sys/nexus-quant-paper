"""Genuine WINQ26 M1 source-backed research for the WIN Price Action bot.

Only the fixed third-party Profit export pinned in atlas_winq26_public is used.
Independent of Atlas signals. No synthetic bars, fabricated fills or broker orders.
June 2026 = exploratory development; July = retrospective later period, NOT
an untouched holdout for strategies that were already adjusted on this source.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

from research.atlas_winq26_public import (
    SOURCE_BLOB, SOURCE_URL, SYMBOL, canonicalize, fetch
)
from research.win_price_data import TZ, local_day, read_win_csv, win_session
from research.win_price_action import Settings, simulate

PERIODS = {
    "junho_2026": ("2026-06-01", "2026-07-01"),
    "julho_2026": ("2026-07-01", "2026-08-01"),
}
SLIPPAGE_TICKS = (0, 1, 2)


def _coverage(bars, start, end):
    days = {}
    for bar in bars:
        d = local_day(bar["time"])
        if start <= d < end and win_session(bar["time"]):
            days[d] = days.get(d, 0) + 1
    return {
        "pregoes": len(days),
        "candles_m1": sum(days.values()),
        "minutos_median_por_pregao": median(days.values()) if days else None,
        "dias_com_300_barras": sum(v >= 300 for v in days.values()),
    }


def _longest_losses(trades):
    streak, worst = 0, 0
    for trade in trades:
        streak = streak + 1 if trade["net_brl"] < 0 else 0
        worst = max(worst, streak)
    return worst


def _score(raw):
    trades = raw.pop("trades")
    setup_types = sorted({t["setup"] for t in trades})
    subsets = {}
    for s in setup_types:
        x = [t for t in trades if t["setup"] == s]
        gain = sum(t["net_brl"] for t in x if t["net_brl"] > 0)
        loss = -sum(t["net_brl"] for t in x if t["net_brl"] < 0)
        subsets[s] = {
            "operacoes": len(x),
            "resultado_liquido_brl": round(sum(t["net_brl"] for t in x), 2),
            "winrate_pct": round(100 * sum(t["net_brl"] > 0 for t in x) / len(x), 2),
            "profit_factor": round(gain / loss, 3) if loss else None,
        }
    raw["resultado_por_setup"] = subsets
    raw["max_reds_consecutivos"] = _longest_losses(trades)
    raw["median_planned_net_rr"] = round(median(t["planned_net_rr"] for t in trades),3) if trades else None
    raw["trades_below_1_to_1_net_rr"] = sum(t["planned_net_rr"] < 1 for t in trades)
    raw["quantidade_stop_red"] = Counter(t["reason"] for t in trades)["STOP"]
    raw["quantidade_stop_win"] = Counter(t["reason"] for t in trades)["TARGET"]
    raw["quantidade_stop_na_entrada"] = Counter(t["reason"] for t in trades)["STOP_ENTRY_BAR"]
    raw["quantidade_target_na_entrada"] = Counter(t["reason"] for t in trades)["TARGET_ENTRY_BAR"]
    raw["trades"] = trades
    return raw


def run(imported, provenance, quality):
    if imported["symbol"] != SYMBOL or imported["timeframe_seconds"] != 60:
        raise ValueError("Only original WINQ26 M1 data eligible")
    bars = imported["bars"]
    report = {
        "study": "WIN Price Action M1/M5 — June July 2026 pinned real WINQ26",
        "status": "BACKTEST_RETROSPECTIVO_NAO_VALIDADO",
        "paper_only": True,
        "source": provenance,
        "source_data": {
            "symbol": SYMBOL,
            "source_vendor_claim": "Profit export in public third-party GitHub repository",
            "exchange_independently_verified": False,
            "source_blob_sha1": SOURCE_BLOB,
            "raw_candles": len(bars),
            "first_local": datetime.fromtimestamp(bars[0]["time"],timezone.utc).astimezone(TZ).isoformat(),
            "last_local": datetime.fromtimestamp(bars[-1]["time"],timezone.utc).astimezone(TZ).isoformat(),
            "volume_column_used": "Quantidade (contratos), not financial Volume",
            "quality": quality,
        },
        "parameters": {
            "starting_brl": 2000,
            "max_concurrent_contracts": 1,
            "risk_fraction_per_trade": 0.01,
            "daily_loss_gate": False,
            "fee_brl_roundtrip": 4,
            "slippage_ticks_each_side": list(SLIPPAGE_TICKS),
            "stop_win": "2R if room, 1.5R minimum in range",
            "stop_red": "retest extreme + one tick",
            "fibonacci_filter": False,
            "signal_timing": "completed M1/M5, entry next M1 open",
        },
        "periods": {},
        "warnings": [
            "Source is third-party genuine-claimed Profit CSV, not independently B3 authenticated",
            "Candles M1 do not prove intrabar execution sequence or queue priority",
            "Costs and slip are assumptions; intraday slippage can be worse than 2 ticks",
            "No daily stop allows repeated losses beyond original capital",
            "Same contract WINQ26, only June/July 2026; no other future expiry validation",
            "Strategy settings were designed after initial historical ATLAS research; neither month is a pristine holdout",
            "No forward paper trading, no live orders, no guarantee of profit",
        ]
    }
    for period,(start,end) in PERIODS.items():
        coverage = _coverage(bars, start, end)
        if coverage["candles_m1"] < 1000:
            raise ValueError(f"Insufficient real WINQ26 M1 candles for {period}: {coverage}")
        result = {"coverage": coverage, "cost_scenarios": {}, "economic_guard_cost_scenarios": {}}
        for slips in SLIPPAGE_TICKS:
            settings = Settings(slip_ticks_per_side=slips)
            base = simulate(bars, settings, start_local=start, end_local=end)
            # State at the end of the entire source is not meaningful for June-only.
            outcome = _score(base)
            if any(not (start <= local_day(t["entry_time"]) < end) for t in outcome["trades"]):
                raise AssertionError("Entry escaped its period")
            result["cost_scenarios"][f"slippage_{slips}_ticks_each_way"] = outcome
            guarded = _score(simulate(bars, Settings(slip_ticks_per_side=slips, min_net_rr=1.0),
                                      start_local=start, end_local=end))
            if any(not (start <= local_day(t["entry_time"]) < end) for t in guarded["trades"]):
                raise AssertionError("Guarded entry escaped its period")
            result["economic_guard_cost_scenarios"][f"slippage_{slips}_ticks_each_way"] = guarded
        report["periods"][period] = result
    report["total_operations_at_base_cost"] = sum(
        report["periods"][p]["cost_scenarios"]["slippage_1_ticks_each_way"]["closed"]
        for p in PERIODS)
    report["research_conclusion"] = "PASSA_REVIEW" if (
        all(
            all(
                report["periods"][p]["cost_scenarios"][f"slippage_{k}_ticks_each_way"]["unverifiable_position_gap_exits"] == 0
                and not report["periods"][p]["cost_scenarios"][f"slippage_{k}_ticks_each_way"]["open_at_end"]
                and report["periods"][p]["cost_scenarios"][f"slippage_{k}_ticks_each_way"]["net_brl"] > 0
                and report["periods"][p]["cost_scenarios"][f"slippage_{k}_ticks_each_way"]["closed"] >= 30
                and (report["periods"][p]["cost_scenarios"][f"slippage_{k}_ticks_each_way"]["profit_factor"] or 0) >= 1.2
                for k in (1,2)
            ) for p in PERIODS
        )) else "NAO_PASSA_REVIEW"
    report["economic_guard_research_review"] = (
        "NAO_PASSA_REVIEW" if any(
            (report["periods"][p]["economic_guard_cost_scenarios"][f"slippage_{k}_ticks_each_way"]["closed"] < 30
             or report["periods"][p]["economic_guard_cost_scenarios"][f"slippage_{k}_ticks_each_way"]["net_brl"] <= 0
             or report["periods"][p]["economic_guard_cost_scenarios"][f"slippage_{k}_ticks_each_way"]["unverifiable_position_gap_exits"] > 0
             or report["periods"][p]["economic_guard_cost_scenarios"][f"slippage_{k}_ticks_each_way"]["open_at_end"]
             or (report["periods"][p]["economic_guard_cost_scenarios"][f"slippage_{k}_ticks_each_way"]["profit_factor"] or 0) < 1.2)
            for p in PERIODS for k in (1,2)
        ) else "PASSA_TRIAGEM_RETROSPECTIVA_NAO_APROVA_REAL"
    )
    report["approved_real_money"] = False
    return report


def markdown(report):
    lines = [
        "# WIN Price Action M1/M5 — backtest com WINQ26 real, junho/julho 2026",
        "",
        "**Backtest retrospectivo, não é execução de corretora.** Dados de terceiros não auditados pela B3.",
        "",
        f"- Fonte: {SOURCE_URL}",
        f"- SHA1 fixo do Git blob: {SOURCE_BLOB}",
        f"- Candles M1 importados: {report['source_data']['raw_candles']}",
        f"- Período: {report['source_data']['first_local']} até {report['source_data']['last_local']}",
        "- Banca R$ 2.000; um WIN; stop Red/Win; sem limite de perdas diárias.",
        "- Risco por entrada planejado máximo 1% incluindo taxas e slippage; stops podem executar pior.",
        "- R$ 4 custos por roundtrip + 0, 1 ou 2 ticks de slippage por lado.",
        "",
        "## Resultados separados e sensibilidade a slippage",
        "",
        "| Mês | Pregões | Candles M1 | Slippage/lado | Operações | Acerto | Líquido (R$) | PF | DD realizado | Max reds |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for month,item in report["periods"].items():
        c=item["coverage"]
        for slips in SLIPPAGE_TICKS:
            sc=item["cost_scenarios"][f"slippage_{slips}_ticks_each_way"]
            def fmt(v):
                return "N/D" if v is None else str(v)
            lines.append(
                f"| {month} | {c['pregoes']} | {c['candles_m1']} | {slips} | "
                f"{sc['closed']} | {fmt(sc['win_rate_pct'])}% | "
                f"{sc['net_brl']:+.2f} | {fmt(sc['profit_factor'])} | "
                f"{sc['max_realized_drawdown_pct']}% | {sc['max_reds_consecutivos']} |"
            )
    lines += ["","## Filtro econômico pré-definido: R/R líquido mínimo 1:1","",
              "| Mês | Slippage/lado | Trades após filtro | Líquido (R$) | Sinais vetados por custo |",
              "|---|---:|---:|---:|---:|"]
    for month,item in report["periods"].items():
        for slips in SLIPPAGE_TICKS:
            x=item["economic_guard_cost_scenarios"][f"slippage_{slips}_ticks_each_way"]
            lines.append(f"| {month} | {slips} | {x['closed']} | {x['net_brl']:+.2f} | "
                         f"{x['rejected']['uneconomic_rr']} |")
    lines += ["","Não selecionar o filtro só porque evita operações perdedoras no histórico já conhecido.",
              "Review do filtro: "+report["economic_guard_research_review"],""]
    lines += ["","## Integridade: lacunas durante operações e exposição não encerrada","",
              "| Mês | Slippage/lado | Saídas não verificáveis por dados faltantes | Posição aberta ao fim? |",
              "|---|---:|---:|---|"]
    for month,item in report["periods"].items():
        for slips in SLIPPAGE_TICKS:
            x=item["cost_scenarios"][f"slippage_{slips}_ticks_each_way"]
            lines.append(f"| {month} | {slips} | {x['unverifiable_position_gap_exits']} | "
                         f"{'sim' if x['open_at_end'] else 'não'} |")
    lines += ["","Uma liquidação presumida após candles M1 ausentes não comprova preenchimento"
              " de ordens. Tais operações invalidam aprovação automática.", ""]
    lines += ["","## Relação risco/retorno líquida planejada (1 tick por lado)","",
              "| Mês | Mediana R/R líquido | Operações com R/R líquido inferior a 1 |",
              "|---|---:|---:|"]
    for month,item in report["periods"].items():
        sc=item["cost_scenarios"]["slippage_1_ticks_each_way"]
        lines.append(f"| {month} | {sc['median_planned_net_rr'] if sc['median_planned_net_rr'] is not None else 'N/D'} | "
                     f"{sc['trades_below_1_to_1_net_rr']}/{sc['closed']} |")
    lines += ["","Alvo bruto 2R não é payoff líquido 2R quando há taxas/slippage.",""]
    lines += ["","## Estratificação dos setups (1 tick por lado)"]
    for month,item in report["periods"].items():
        sc=item["cost_scenarios"]["slippage_1_ticks_each_way"]
        lines.append(f"### {month}")
        lines.append(f"- Sinais rejeitados: {sc['rejected']}; operações: {sc['closed']}.")
        for name,s in sc["resultado_por_setup"].items():
            lines.append(f"- {name}: {s['operacoes']} operações, resultado {s['resultado_liquido_brl']:+.2f} BRL, acerto {s['winrate_pct']}%, PF {s['profit_factor']}.")
        if not sc["resultado_por_setup"]:
            lines.append("- Nenhuma operação em nenhum setup nas condições atuais.")
    lines += ["",f"**Gate retrospectivo: {report['research_conclusion']}** (não promove para dinheiro real).",
              "","## Alertas",
              *["- " + w for w in report["warnings"]],
              "","Nenhuma cotação sintética, performance inventada ou operação real foi usada.",
              "Arquivo JSON com ledger de cada operação no artifact do GitHub Actions.",
              ""]
    return "\n".join(lines)


def main():
    with tempfile.TemporaryDirectory() as work:
        raw=Path(work)/"WINQ26_raw.csv"
        normalized=Path(work)/"WINQ26_M1.csv"
        provenance=fetch(raw)
        quality=canonicalize(raw, normalized)
        imported=read_win_csv(normalized,expected_symbol=SYMBOL)
        report=run(imported,provenance,quality)
    out=Path("research/results")
    out.mkdir(parents=True,exist_ok=True)
    (out/"win_price_action_winq26_backtest.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    summary=markdown(report)
    (out/"win_price_action_winq26_backtest.md").write_text(
        summary,encoding="utf-8")
    print("WIN_PA_BACKTEST_START",flush=True)
    print(summary,flush=True)
    print("WIN_PA_BACKTEST_END",flush=True)


if __name__ == "__main__":
    main()
