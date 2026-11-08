"""NEXUS V4 frozen hourly primary signals, M5 conservative execution.

No 2026-07..10 reused holdout. Previously exposed 2026-01..06 is
retrospective only. NEVER promote to live or even forward paper automatically.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .data import load_history, month_range
from .engine import SCENARIOS, buy_hold
from .run import month_indices
from .strategies import build_features
from .v2_run import QUARTERS
from .v3_policy import aggregate_closed_h1
from .v4_system import POLICIES, replay_v4


def classify(results):
    """Losses are losses even in small samples; no retrospective promotion."""
    validation = [v for k, v in results["quarters"].items()
                  if k.startswith("retrospective_validation")]
    dev = [v for k, v in results["quarters"].items()
           if k.startswith("development")]
    for q in validation:
        if (q["base"]["trades_closed"] and
                any(q[sc]["net_usd"] <= 0 for sc in SCENARIOS)):
            return "REPROVADO", "Negative observed validation net after cost stress"
        if q["base"]["max_drawdown_pct_mark_to_market"] >= 10:
            return "REPROVADO", "Risk limit exceeded"
    dev_positive = sum(q["base"]["net_usd"] > 0 for q in dev)
    if all(q["base"]["trades_closed"] >= 20 for q in dev) and dev_positive < 3:
        return "REPROVADO", "Lacks persistence in three of four development quarters"
    if (sum(q["base"]["trades_closed"] for q in validation) < 80 or
            any(q["base"]["trades_closed"] < 25 for q in validation) or
            any(q["base"]["trades_closed"] < 20 for q in dev)):
        return "INCONCLUSIVO", "Too few independent trades for robust inference"
    if dev_positive < 3:
        return "REPROVADO", "Fails positive development quarter consistency"
    for q in validation:
        r = q["base"]
        if not (r["profit_factor"] is not None and r["profit_factor"] > 1.2):
            return "REPROVADO", "Profit factor too low"
        ci = r["ci95_expectancy_day_bootstrap_usd"]
        if ci is None or ci[0] <= 0:
            return "INCONCLUSIVO", "Cannot establish positive expectancy day-bootstrap CI"
    return "INCONCLUSIVO", "Previously examined validation; needs truly unseen data"


def run(*, output=Path("artifacts/nexus-m1m5-v4"),
        cache=Path(".cache/nexus_m1m5_v3")):
    months = list(month_range("2026-06", 18))
    if months[0] != "2025-01" or months[-1] != "2026-06":
        raise AssertionError("Frozen experimental horizon changed")
    output.mkdir(parents=True, exist_ok=True)
    results, sources, ledger, benchmarks = {}, {}, [], {}
    for symbol in ("BTCUSDT", "ETHUSDT"):
        bars, source = load_history(symbol, "5m", months, cache)
        hours = aggregate_closed_h1(bars)
        if len(hours) != len(bars) // 12:
            raise ValueError("Missing/incomplete or misaligned H1 candle")
        hf = build_features(hours)
        month_bounds = month_indices(bars, months)
        sources[symbol] = {
            "M5": source, "m5_candles": len(bars), "h1_candles": len(hours),
        }
        benchmarks[symbol] = {}
        for period, a, b in QUARTERS:
            start, stop = month_bounds[a], month_bounds[b]
            benchmarks[symbol][period] = {
                sc: buy_hold(bars, start, stop, scenario=sc)
                for sc in SCENARIOS
            }

        for policy in POLICIES:
            name = f"{symbol}:{policy.name}"
            row = {
                "symbol": symbol, "policy": asdict(policy),
                "quarters": {},
            }
            for period, a, b in QUARTERS:
                start, stop = month_bounds[a], month_bounds[b]
                q = {}
                for scenario in SCENARIOS:
                    metrics, trades = replay_v4(
                        bars, hours, hf, policy, scenario,
                        start=start, stop=stop,
                    )
                    q[scenario] = metrics
                    ledger.extend({
                        "candidate": name, "symbol": symbol,
                        "quarter": period, "scenario": scenario,
                        **trade,
                    } for trade in trades)
                row["quarters"][period] = q
            row["decision"], row["reason"] = classify(row)
            results[name] = row
        del bars, hours, hf

    csvfile = output / "trades_v4.csv"
    columns = [
        "candidate", "symbol", "quarter", "scenario", "signal_t",
        "entry_t", "exit_t", "entry_ref", "exit_ref", "entry", "exit",
        "qty", "initial_stop", "final_stop", "target",
        "gross_usd", "fees_usd", "execution_deviation_usd",
        "pnl_usd", "exit_reason", "signal_reason", "regime",
        "initial_stop_pct",
    ]
    with csvfile.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="raise")
        writer.writeheader()
        writer.writerows(ledger)

    ranks = []
    for name, c in results.items():
        dev = [q for key, q in c["quarters"].items() if key.startswith("development")]
        val = [q for key, q in c["quarters"].items() if
               key.startswith("retrospective_validation")]
        scenario_net = {
            sc: round(sum(q[sc]["net_usd"] for q in val), 4)
            for sc in SCENARIOS
        }
        n_val = sum(q["base"]["trades_closed"] for q in val)
        rows = [t for t in ledger if t["candidate"] == name and
                t["scenario"] == "base" and
                t["quarter"].startswith("retrospective_validation")]
        ranks.append({
            "candidate": name,
            "decision": c["decision"], "reason": c["reason"],
            "dev_base_net_usd": round(sum(q["base"]["net_usd"] for q in dev), 4),
            "dev_positive_quarters": sum(q["base"]["net_usd"] > 0 for q in dev),
            "validation_scenarios_usd": scenario_net,
            "validation_worst_usd": min(scenario_net.values()),
            "validation_trades": n_val,
            "validation_stop_count": sum(t["exit_reason"] in
                                         ("stop", "gap_stop") for t in rows),
            "validation_gross_usd": round(sum(t["gross_usd"] for t in rows), 4),
            "validation_fees_usd": round(sum(t["fees_usd"] for t in rows), 4),
            "validation_execution_deviation_usd": round(
                sum(t["execution_deviation_usd"] for t in rows), 4),
        })
    ranks.sort(key=lambda x: (-x["validation_worst_usd"], x["candidate"]))
    packet = {
        "project": "NEXUS V4, H1 signal / M5 execution",
        "status": "RESEARCH_ONLY",
        "initial_equity_per_fold": 10_000,
        "data_months": months,
        "input": sources, "benchmarks_buy_and_hold_100pct_exposure": benchmarks,
        "scenarios": SCENARIOS,
        "hypotheses_frozen_before_replay": [asdict(p) for p in POLICIES],
        "results": results, "ranking": ranks,
        "ledger_sha256": hashlib.sha256(csvfile.read_bytes()).hexdigest(),
        "retrospective_exposed_validation": True,
        "former_2026_07_to_10_holdout_excluded": True,
        "no_real_orders": True, "no_paper_activation": True,
        "no_parameter_optimization": True,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    (output / "results_v4.json").write_text(
        json.dumps(packet, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    md = [
        "# NEXUS V4 — sinal H1, execução M5, sem promessas",
        "",
        "Amostra histórica 2025-01..2026-06 já examinada na V1–V3. "
        "Julho–outubro 2026 NÃO reutilizados. Resultados positivos são "
        "apenas hipóteses retrospectivas; nenhuma aprovação automática.",
        "",
        "A entrada nasce do fechamento H1 e só pode entrar na primeira abertura "
        "M5 da hora seguinte. Stop se aplica **até no candle da entrada**. "
        "Máximo uma entrada por dia e cooldown de 12h; no máximo 40% "
        "nocional spot por conta isolada; 0,5% de risco planejado no stop "
        "incluindo fees+desvio; stop prioritário em intrabar ambíguo.",
        "",
        "Custos (fee/slippage) da V1, três cenários; saída com ledger auditável. "
        "Comparador cash 0% e buy-and-hold 100% de exposição (RISCO DIFERENTE).",
        "",
        "| Candidato | Decisão | Dev base USD | Val base USD | Val pior custo USD | Entradas validação | Stops |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for item in ranks:
        md.append(
            f"| {item['candidate']} | {item['decision']} | "
            f"{item['dev_base_net_usd']:.2f} | "
            f"{item['validation_scenarios_usd']['base']:.2f} | "
            f"{item['validation_worst_usd']:.2f} | "
            f"{item['validation_trades']} | "
            f"{item['validation_stop_count']} |")
    md.extend([
        "",
        "## Falhas e limites",
        "- Nem um único resultado anual/semestre positivo comprovado significa lucro futuro.",
        "- OHLC M5 não reproduz fila, spread tick-a-tick e impacto real de mercado.",
        "- As oito variantes compartilham mercados e preços: seus lucros NÃO são aditivos.",
        "- O custo de simulação é um modelo, não medição de fills na corretora.",
        "- Só novos dados posteriores e paper forward segregado podem fundamentar adoção.",
        "",
        "CSV SHA256: " + packet["ledger_sha256"],
    ])
    (output / "REPORT_V4.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({
        "candidates": len(results),
        "statuses": dict(Counter(v["decision"] for v in results.values())),
        "ranking": ranks,
    }, ensure_ascii=False))
    return packet


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("artifacts/nexus-m1m5-v4"))
    ap.add_argument("--cache", type=Path, default=Path(".cache/nexus_m1m5_v3"))
    options = ap.parse_args()
    run(output=options.out, cache=options.cache)
