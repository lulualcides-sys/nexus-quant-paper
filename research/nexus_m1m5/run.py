"""Reproducible 6-robot Binance SPOT laboratory. NEVER launches live/paper bots.

Example (after monthly archives are published):
python -m research.nexus_m1m5.run --end 2026-10 --months 22 --out /tmp/nexus-m1m5
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .data import INTERVAL_MS, aggregate_closed_m15, load_history, month_range
from .engine import buy_hold, replay
from .strategies import SPECS, build_features

SYMBOLS = ("BTCUSDT", "ETHUSDT")
SCENARIOS = ("base", "double_cost", "adverse")


def month_indices(bars, months):
    first = {}
    for i, b in enumerate(bars):
        mo = datetime.fromtimestamp(b.t / 1000, timezone.utc).strftime("%Y-%m")
        if mo not in first:
            first[mo] = i
    if any(m not in first for m in months):
        raise ValueError("Some requested months have no historical candles")
    return [first[m] for m in months] + [len(bars)]


def split_folds(months):
    """Freeze windows before inspecting ANY observed P&L.

    No parameter optimization is performed here. 'final' is inspected once,
    only after all predeclared windows, and must never be reused for selection.
    """
    count = len(months)
    if count < 12:
        return {"smoke_unvalidated": (0, count)}, None
    final_n = max(2, round(count * .20))
    pre = count - final_n
    if pre < 10:
        raise ValueError("Insufficient pretest months for three expanding windows")
    folds = {"development": (0, pre - 6),
             "validation": (pre - 6, pre)}
    for j in range(3):
        a = pre - 6 + 2 * j
        folds[f"walkforward_{j + 1}"] = (a, a + 2)
    folds["final_intocado_primeiro_uso"] = (pre, count)
    return folds, (pre, count)


def judgement(main, double, adverse, wf, sensitivity=None):
    if main is None:
        return "INCONCLUSIVO", "No independent final holdout"
    n = main["trades_closed"]
    if n == 0:
        return "INCONCLUSIVO", "No closed trades in final holdout"
    if main["net_usd"] <= 0 or double["net_usd"] <= 0 or adverse["net_usd"] <= 0:
        return "REPROVADO", "Negative net P&L in final or cost-stress scenario"
    if n < 80 or (main["effective_n_lag1_approx"] or 0) < 60:
        return "INCONCLUSIVO", "Too few effectively independent trades"
    ci = main["ci95_expectancy_day_bootstrap_usd"]
    if ci is None or ci[0] <= 0:
        return "INCONCLUSIVO", "Cannot establish positive expectancy with day bootstrap"
    if (main["profit_factor"] or 0) <= 1.20:
        return "REPROVADO", "Profit factor <= 1.20"
    if main["max_drawdown_pct_mark_to_market"] >= 10 or main["circuit_breaker_tripped"]:
        return "REPROVADO", "Circuit breaker or excessive marked-to-market drawdown"
    if sum(x["net_usd"] > 0 for x in wf) < 2:
        return "REPROVADO", "Fewer than 2/3 positive walk-forward windows"
    if (main["concentration_top3_of_positive_pnl"] or 1) > .50:
        return "INCONCLUSIVO", "Profit excessively concentrated in three trades"
    if sensitivity is None or any(
        v.get("net_usd", 0) <= 0 or v.get("trades_closed", 0) < 10
        for v in sensitivity.values()
    ):
        return "INCONCLUSIVO", "Signal threshold stability on validation window not established"
    return "APTO PARA PAPER FORWARD", "Initial research gates passed; never live approval"


def _ledger(outfile, rows):
    columns = ["symbol", "timeframe", "variant", "fold", "scenario",
               "robot", "signal_t", "entry_t", "exit_t", "entry", "exit", "qty",
               "pnl_usd", "fees_usd", "execution_deviation_usd", "stop", "target",
               "exit_reason", "signal_reason", "regime"]
    with outfile.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def execute(end="2026-10", months=22, out=Path("research/results/nexus_m1m5"),
            cache=Path(".cache/nexus_m1m5"), symbols=SYMBOLS):
    out.mkdir(parents=True, exist_ok=True)
    month_list = list(month_range(end, months))
    folds, final_window = split_folds(month_list)
    results, ledgers, manifests = {}, [], {}
    for sym in symbols:
        if sym not in SYMBOLS:
            raise ValueError("Only approved spot pairs")
        m1, m1sources = load_history(sym, "1m", month_list, cache)
        m5, m5sources = load_history(sym, "5m", month_list, cache)
        h15 = aggregate_closed_m15(m5)
        m1f, m5f, h15f = build_features(m1), build_features(m5), build_features(h15)
        h15closes = [b.t + 900_000 for b in h15]
        manifests[sym] = {"1m": m1sources, "5m": m5sources,
                          "derived_closed_15m_count": len(h15)}
        for name, spec in SPECS.items():
            tf = spec["tf"]
            bars, features = (m1, m1f) if tf == "1m" else (m5, m5f)
            indices = month_indices(bars, month_list)
            variants = ("immediate", "retest") if name == "breakout" else ("default",)
            for variant in variants:
                key = f"{sym}:{name}:{variant}"
                r = {"symbol": sym, "timeframe": tf, "strategy": name, "variant": variant,
                     "predeclared_config": spec, "folds": {}}
                for label, (a, z) in folds.items():
                    start, stop = max(210, indices[a]), indices[z]
                    if stop <= start:
                        raise ValueError("Not enough closed bars for a validation fold")
                    stats = {}
                    for scenario in SCENARIOS:
                        report, trades = replay(
                            bars, features, name, scenario, start=start, stop=stop,
                            higher=h15 if tf == "5m" else None,
                            higher_features=h15f if tf == "5m" else None,
                            higher_closes=h15closes if tf == "5m" else None,
                            breakout_mode=variant if name == "breakout" else "immediate",
                        )
                        if scenario == "base":
                            report["buy_hold"] = buy_hold(bars, start, stop, scenario)
                            baseline, _ = replay(
                                bars, features, name, scenario, start=start, stop=stop,
                                simple=True,
                            )
                            report["simple_ema20_50"] = {
                                "net_usd": baseline["net_usd"],
                                "trades_closed": baseline["trades_closed"],
                            }
                        stats[scenario] = report
                        if label in ("validation", "final_intocado_primeiro_uso", "smoke_unvalidated"):
                            ledgers.extend({
                                "symbol": sym, "timeframe": tf, "variant": variant,
                                "fold": label, "scenario": scenario, **trade,
                            } for trade in trades)
                    r["folds"][label] = stats

                # Diagnose threshold fragility ONLY on prior validation bars;
                # avoid experimenting on the already-inspected final holdout.
                r["signal_sensitivity_validation"] = {}
                if final_window is not None:
                    vstart, vend = folds["validation"]
                    for variant_label, multiplier in (("looser_0.90", 0.9), ("tighter_1.10", 1.1)):
                        perturb, _ = replay(
                            bars, features, name, "base",
                            start=max(210, indices[vstart]), stop=indices[vend],
                            higher=h15 if tf == "5m" else None,
                            higher_features=h15f if tf == "5m" else None,
                            higher_closes=h15closes if tf == "5m" else None,
                            breakout_mode=variant if name == "breakout" else "immediate",
                            sensitivity=multiplier,
                        )
                        r["signal_sensitivity_validation"][variant_label] = {
                            "net_usd": perturb["net_usd"],
                            "trades_closed": perturb["trades_closed"],
                            "profit_factor": perturb["profit_factor"],
                            "max_dd_pct": perturb["max_drawdown_pct_mark_to_market"],
                        }
                if final_window is None:
                    r["decision"], r["decision_reason"] = "INCONCLUSIVO", "Smoke data; no final holdout"
                else:
                    final = r["folds"]["final_intocado_primeiro_uso"]
                    wf = [r["folds"][f"walkforward_{i}"]["base"] for i in range(1, 4)]
                    r["decision"], r["decision_reason"] = judgement(
                        final["base"], final["double_cost"], final["adverse"], wf,
                        r["signal_sensitivity_validation"])
                results[key] = r
        # Discard raw symbol arrays before loading next market.
        del m1, m5, m1f, m5f, h15, h15f
    ledger_path = out / "trades.csv"
    _ledger(ledger_path, ledgers)
    artifact = {
        "project": "NEXUS M1/M5 six independent hypotheses (spot, long-only)",
        "research_only": True, "no_forward_execution": True, "no_live_orders": True,
        "holdout_integrity_note": (
            "The original 2026-07..10 holdout was first evaluated in Actions "
            "run 42488027943; subsequent commits/tests recheck that exposed period. "
            "Do NOT claim a new untouched holdout or promote a positive recheck."
        ),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source": "Binance public monthly spot klines with verified SHA256 checksums",
        "units": "UTC milliseconds, normalized from post-2025 spot microseconds",
        "symbols": list(symbols), "months": month_list,
        "timeframes": ["1m", "5m"], "no_interpolation": True,
        "rules": {
            "no_shorting": True, "starting_equity_usd_per_bot_per_fold": 10000,
            "entry": "next REAL available candle open + modeled execution deviation",
            "fee_per_side_regular_spot": .001,
            "base_slippage_per_side": .0002, "adverse_execution_deviation_per_side": .0011,
            "double_cost_fee_per_side": .002, "double_cost_slippage_per_side": .0004,
            "daily_loss_lock": .02, "drawdown_circuit_breaker": .10,
            "M1_planned_stop_risk": .0025, "M5_planned_stop_risk": .005,
            "spread_extra_fee": 0,
            "intrabar_ambiguity": "stop before target, same-candle exits allowed",
            "M15": "strict closed M15 from aligned 3x M5",
            "holdout_consumed_once": bool(final_window),
            "first_holdout_read_action_run": 42488027943,
            "all_subsequent_replays": "RECHECK of exposed final holdout; never label virgin OOS",
            "final_is_untouched_only_BEFORE_first_run": True,
            "no_parameters_fitted_to_heldout": True,
        },
        "folds_month_indices": {k: list(v) for k, v in folds.items()},
        "checksum_sources": manifests,
        "results": results,
        "ledger": ledger_path.name,
    }
    rendered = json.dumps(artifact, indent=2, ensure_ascii=False, allow_nan=False)
    (out / "results.json").write_text(rendered, encoding="utf-8")
    ledger_sha = hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    ranked = []
    for key, r in results.items():
        f = r["folds"].get("final_intocado_primeiro_uso", {}).get("base")
        stressed = r["folds"].get("final_intocado_primeiro_uso", {}).get("double_cost")
        adverse = r["folds"].get("final_intocado_primeiro_uso", {}).get("adverse")
        ranked.append({
            "candidate": key, "decision": r["decision"], "why": r["decision_reason"],
            "final_net_usd": f["net_usd"] if f else None,
            "final_profit_factor": f["profit_factor"] if f else None,
            "final_trades": f["trades_closed"] if f else None,
            "double_cost_net_usd": stressed["net_usd"] if stressed else None,
            "adverse_net_usd": adverse["net_usd"] if adverse else None,
        })
    ranked.sort(key=lambda x: (
        x["decision"] != "APTO PARA PAPER FORWARD",
        -(min(x["final_net_usd"], x["double_cost_net_usd"], x["adverse_net_usd"])
          if x["final_net_usd"] is not None else float("-inf"))))
    table = [
        "# NEXUS M1/M5 — relatório auditável, não é lucro real",
        "",
        f"- Fonte: Binance spot {', '.join(symbols)}; meses: {month_list[0]} até {month_list[-1]} UTC.",
        "- Critérios definidos antes dos resultados; sem parâmetros otimizados pelo P&L.",
        "- Taxas de 0,10% por lado, custo dobrado 0,20% de taxa e 0,04% de slippage, e cenário adverso com execução pior.",
        "- Todos candidatos desativados; nenhuma estratégia promovida automaticamente.",
        f"- CSV de operações SHA256: {ledger_sha}",
        "- Observação: a primeira execução completa consome o holdout final; não reutilizá-lo para ajuste.",
        "",
        "| Candidato | Decisão | Trades final | Líquido final US$ | PF final | Custo dobrado US$ | Adverso US$ |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for x in ranked:
        fmt = lambda v: "N/D" if v is None else f"{v:.3f}" if isinstance(v, float) else str(v)
        table.append("| " + " | ".join([
            x["candidate"], x["decision"], fmt(x["final_trades"]),
            fmt(x["final_net_usd"]), fmt(x["final_profit_factor"]),
            fmt(x["double_cost_net_usd"]), fmt(x["adverse_net_usd"])]) + " |")
    table += ["", "## Motivos", ""]
    for x in ranked:
        table.append(f"- **{x['candidate']}**: {x['why']}.")
    (out / "REPORT.md").write_text("\n".join(table) + "\n", encoding="utf-8")
    return artifact


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--end", default="2026-10")
    p.add_argument("--months", type=int, default=22)
    p.add_argument("--out", type=Path, default=Path("research/results/nexus_m1m5"))
    p.add_argument("--cache", type=Path, default=Path(".cache/nexus_m1m5"))
    args = p.parse_args()
    results = execute(args.end, args.months, args.out, args.cache)
    print(json.dumps({
        "months": len(results["months"]),
        "candidates_including_breakout_comparison": len(results["results"]),
        "decisions": {k: v["decision"] for k, v in results["results"].items()},
        "output": str(args.out),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
