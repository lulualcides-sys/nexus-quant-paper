"""V2 fee-aware research. Deliberately EXCLUDES the exposed 2026-07..10 holdout.

The training 2025 and validation 2026-01..06 were already examined at
aggregate level in V1, so THIS IS NOT clean untouched out-of-sample evidence.
V2 is NOT allowed to promote or activate any bot.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .data import aggregate_closed_m15, load_history, month_range
from .engine import SCENARIOS, replay
from .run import month_indices
from .strategies import SPECS, build_features
from .v2_policy import policies

PAIRS = ("BTCUSDT", "ETHUSDT")
QUARTERS = [
    ("development_Q1_2025", 0, 3),
    ("development_Q2_2025", 3, 6),
    ("development_Q3_2025", 6, 9),
    ("development_Q4_2025", 9, 12),
    ("retrospective_validation_Q1_2026", 12, 15),
    ("retrospective_validation_Q2_2026", 15, 18),
]


def judge(result):
    # False-positive prevention: no "APTO" in any branch.
    validation = [v for k, v in result["quarters"].items()
                  if k.startswith("retrospective_validation")]
    development = [v for k, v in result["quarters"].items()
                   if k.startswith("development")]
    # A small sample must never conceal an actual observed net loss:
    # reject loss-makers first; leave empty or nonnegative sparse books inconclusive.
    for period in validation:
        if (period["base"]["trades_closed"] > 0 and
            any(period[sc]["net_usd"] <= 0 for sc in SCENARIOS)):
            return "REPROVADO", "Net loss/zero after costs in a validation quarter"
        if period["base"]["max_drawdown_pct_mark_to_market"] >= 10:
            return "REPROVADO", "Excessive marked-to-market drawdown"
    for period in validation + development:
        if period["base"]["trades_closed"] < 20:
            return "INCONCLUSIVO", "Fewer than 20 trades in at least one quarter"
    if sum(p["base"]["net_usd"] > 0 for p in development) < 3:
        return "REPROVADO", "Fewer than 3 positive development quarters"
    return ("INCONCLUSIVO",
            "Positive retrospective screen only; holdout previously exposed, require new unseen data")


def run_v2(*, end="2026-06", months=18,
           output=Path("artifacts/nexus-m1m5-v2"),
           cache=Path(".cache/nexus_m1m5_v2")):
    if end != "2026-06" or months != 18:
        raise ValueError("V2 excludes previously exposed final 2026-07..10; frozen data window")
    output.mkdir(parents=True, exist_ok=True)
    month_list = list(month_range(end, months))
    records, results, sources = [], {}, {}
    for symbol in PAIRS:
        m1, src1 = load_history(symbol, "1m", month_list, cache)
        m5, src5 = load_history(symbol, "5m", month_list, cache)
        h15 = aggregate_closed_m15(m5)
        f1, f5, fh15 = build_features(m1), build_features(m5), build_features(h15)
        closes = [x.t + 900_000 for x in h15]
        sources[symbol] = {"1m": src1, "5m": src5, "derived_m15_candles": len(h15)}
        for robot, spec in SPECS.items():
            bars, features = (m1, f1) if spec["tf"] == "1m" else (m5, f5)
            boundaries = month_indices(bars, month_list)
            variants = ("immediate", "retest") if robot == "breakout" else ("default",)
            for variant in variants:
                for policy in policies(spec["tf"]):
                    candidate = f"{symbol}:{robot}:{variant}:{policy.name}"
                    config = asdict(policy)
                    result = {
                        "symbol": symbol, "robot": robot, "variant": variant,
                        "timeframe": spec["tf"], "policy": config, "quarters": {}
                    }
                    for label, mstart, mend in QUARTERS:
                        start, stop = max(210, boundaries[mstart]), boundaries[mend]
                        scenarios = {}
                        for sc in SCENARIOS:
                            report, trades = replay(
                                bars, features, robot, sc, start=start, stop=stop,
                                higher=h15 if spec["tf"] == "5m" else None,
                                higher_features=fh15 if spec["tf"] == "5m" else None,
                                higher_closes=closes if spec["tf"] == "5m" else None,
                                breakout_mode=variant if robot == "breakout" else "immediate",
                                research_policy=config,
                            )
                            scenarios[sc] = report
                            if sc == "base" or label.startswith("retrospective_validation"):
                                records.extend({
                                    "symbol": symbol, "robot": robot,
                                    "variant": variant, "policy": policy.name,
                                    "quarter": label, "scenario": sc,
                                    **t
                                } for t in trades)
                        result["quarters"][label] = scenarios
                    result["decision"], result["reason"] = judge(result)
                    results[candidate] = result
        del m1, m5, h15, f1, f5, fh15
    tradefile = output / "trades_v2.csv"
    headers = [
        "symbol", "robot", "variant", "policy", "quarter", "scenario",
        "signal_t", "entry_t", "exit_t", "entry", "exit", "qty",
        "pnl_usd", "fees_usd", "execution_deviation_usd", "stop",
        "target", "exit_reason", "signal_reason", "regime",
    ]
    with tradefile.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    artifact = {
        "name": "NEXUS M1/M5 V2 fee-aware cost and regime research",
        "not_live": True, "not_forward_paper": True, "no_auto_promotion": True,
        "previously_seen_validation": True,
        "untouched_final_reserved": False,
        "excluded_reused_final": "2026-07..10 — previous V1 exposed this interval",
        "months": month_list,
        "source": "Binance official spot monthly klines + SHA256",
        "checksum_manifest": sources,
        "scenarios": SCENARIOS,
        "policies_frozen": [asdict(p) for p in policies("1m")] +
                           [asdict(p) for p in policies("5m")],
        "quarter_windows": [{"name": n, "start_month": month_list[a],
                             "end_month": month_list[b - 1]} for n, a, b in QUARTERS],
        "results": results,
        "trade_ledger": tradefile.name,
        "trade_ledger_sha256": hashlib.sha256(tradefile.read_bytes()).hexdigest(),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    (output / "results_v2.json").write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    rankings = []
    for key, r in results.items():
        dev = [v for k, v in r["quarters"].items() if k.startswith("development")]
        val = [v for k, v in r["quarters"].items() if k.startswith("retrospective_validation")]
        worst = min(sum(q[sc]["net_usd"] for q in val) for sc in SCENARIOS)
        rankings.append({
            "candidate": key, "decision": r["decision"],
            "dev_quarters_positive": sum(p["base"]["net_usd"] > 0 for p in dev),
            "development_net": round(sum(p["base"]["net_usd"] for p in dev), 2),
            "validation_base_net": round(sum(q["base"]["net_usd"] for q in val), 2),
            "validation_worst_cost_net": round(worst, 2),
            "validation_trades": sum(q["base"]["trades_closed"] for q in val),
            "reason": r["reason"],
        })
    rankings.sort(key=lambda x: -x["validation_worst_cost_net"])
    columns = [
        "# NEXUS M1/M5 V2 — cost-aware (retrospectivo, não lucro real)",
        "",
        "**Não é fora da amostra intocado.** A PR V1 já expôs os resultados agregados"
        " de 2025–2026. Julho–outubro/2026 foram excluídos integralmente.",
        "Os parâmetros V2 não podem ser alterados após observar este resultado e"
        " chamar de teste independente. Nenhum modelo foi ativado.",
        "",
        f"Entradas registradas em trades_v2.csv; SHA256 {artifact['trade_ledger_sha256']}",
        "",
        "| Candidato | Decisão | Desenvolvimento US$ | Validação base US$ | Validação pior custo US$ | Trades validação |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for x in rankings:
        columns.append(
            f"| {x['candidate']} | {x['decision']} | "
            f"{x['development_net']:.2f} | {x['validation_base_net']:.2f} | "
            f"{x['validation_worst_cost_net']:.2f} | {x['validation_trades']} |"
        )
    columns.extend([
        "", "## Diagnóstico por candidato", "",
        *[f"- {x['candidate']}: {x['reason']}; {x['dev_quarters_positive']}/4 "
          "trimestres positivos de desenvolvimento" for x in rankings],
        "",
        "## Limitações",
        "- Sem execução real ou medição bid/ask; fills de stops/alvos aproximados por OHLC.",
        "- Somente compras spot, taxa regular 0,10% por lado e custos base/duplo/adverso.",
        "- Resultado líquido positivo aqui seria uma hipótese retrospectiva, não lucro futuro.",
        "- Nenhum candidato pode ser APTO sem novo período prospectivo realmente não visto.",
    ])
    (output / "REPORT_V2.md").write_text("\n".join(columns) + "\n", encoding="utf-8")
    print(json.dumps({
        "period": f"{month_list[0]}..{month_list[-1]}",
        "candidates": len(results),
        "status_counts": {k: sum(v["decision"] == k for v in results.values())
                          for k in ("REPROVADO", "INCONCLUSIVO")},
        "top_5_research": rankings[:5],
    }, ensure_ascii=False))
    return artifact


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="artifacts/nexus-m1m5-v2", type=Path)
    parser.add_argument("--cache", default=".cache/nexus_m1m5_v2", type=Path)
    args = parser.parse_args()
    run_v2(output=args.out, cache=args.cache)
