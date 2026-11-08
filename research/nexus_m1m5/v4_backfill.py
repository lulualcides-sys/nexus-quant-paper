"""V4 INDEPENDENT BACKFILL 2024, first use for frozen 2026 V4 rules.

No parameter changes, no optimization, no signal selection or live activation.
2024 is retrospective market history NOT observed in V1-V4.
2023 excluded because Binance March-2023 contains a nonstandard early bar close.
They are a historical generalization test, NOT prospective/forward validation.
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
from .engine import SCENARIOS
from .run import month_indices
from .strategies import build_features
from .v3_policy import aggregate_closed_h1
from .v4_system import POLICIES, replay_v4

HORIZON_END = "2024-12"
HORIZON_MONTHS = 12


def backfill_windows(months):
    if len(months) != HORIZON_MONTHS or months[0] != "2024-01" or months[-1] != HORIZON_END:
        raise ValueError("Frozen backfill window changed")
    return [
        (f"unseen_backfill_2024_Q{q}", (q - 1) * 3, q * 3)
        for q in (1, 2, 3, 4)
    ]


def assess_backfill(quarters):
    """Never APTO, including if any past-year result is statistically positive."""
    q = list(quarters.values())
    ys = {sc: sum(x[sc]["net_usd"] for x in q) for sc in SCENARIOS}
    n = sum(x["base"]["trades_closed"] for x in q)
    if n and any(v <= 0 for v in ys.values()):
        return "REPROVADO", "2024 net nonpositive under at least one cost scenario"
    if n < 80:
        return "INCONCLUSIVO", "Fewer than 80 trades in 2024 historical backfill"
    return "INCONCLUSIVO", "Requires prospective live paper verification; history alone not enough"


def run(*, output=Path("artifacts/nexus-v4-backfill"),
        cache=Path(".cache/nexus_v4_backfill")):
    months = list(month_range(HORIZON_END, HORIZON_MONTHS))
    folds = backfill_windows(months)
    output.mkdir(parents=True, exist_ok=True)
    source, results, ledger = {}, {}, []
    for symbol in ("BTCUSDT", "ETHUSDT"):
        m5, manifest = load_history(symbol, "5m", months, cache)
        h1 = aggregate_closed_h1(m5)
        if len(h1) != len(m5) // 12:
            raise ValueError("Incomplete H1 aggregation or malformed monthly series")
        hf = build_features(h1)
        boundaries = month_indices(m5, months)
        source[symbol] = {"binance_m5": manifest,
                          "m5_candles": len(m5), "closed_h1_candles": len(h1)}
        for p in POLICIES:  # EXACT frozen V4 config, not replaced
            name = f"{symbol}:{p.name}"
            candidate = {
                "symbol": symbol, "policy": asdict(p), "quarters": {}
            }
            for label, a, b in folds:
                scenario_results = {}
                for sc in SCENARIOS:
                    report, trades = replay_v4(
                        m5, h1, hf, p, sc,
                        start=boundaries[a], stop=boundaries[b])
                    scenario_results[sc] = report
                    ledger.extend({
                        "candidate": name, "quarter": label,
                        "symbol": symbol, "scenario": sc, **t,
                    } for t in trades)
                candidate["quarters"][label] = scenario_results
            candidate["status"], candidate["reason"] = assess_backfill(candidate["quarters"])
            results[name] = candidate
        del m5, h1, hf

    columns = ["candidate", "quarter", "symbol", "scenario", "signal_t",
               "entry_t", "exit_t", "entry_ref", "exit_ref", "entry", "exit",
               "qty", "initial_stop", "final_stop", "target",
               "gross_usd", "fees_usd", "execution_deviation_usd",
               "pnl_usd", "exit_reason", "signal_reason", "regime",
               "initial_stop_pct"]
    tradefile = output / "trades_v4_backfill.csv"
    with tradefile.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="raise")
        writer.writeheader()
        writer.writerows(ledger)

    ranking = []
    for name, candidate in results.items():
        quarters = candidate["quarters"]
        yearly = {}
        for year in ("2024",):
            qs = [v for k, v in quarters.items() if f"_{year}_" in k]
            yearly[year] = {
                "net_by_scenario": {
                    sc: round(sum(q[sc]["net_usd"] for q in qs), 4)
                    for sc in SCENARIOS
                },
                "trades": sum(q["base"]["trades_closed"] for q in qs),
                "positive_quarters": sum(q["base"]["net_usd"] > 0 for q in qs),
            }
        ranking.append({
            "candidate": name, "yearly": yearly,
            "worst_1yr_net_usd": round(min(
                sum(q[sc]["net_usd"] for q in quarters.values())
                for sc in SCENARIOS), 4),
            "status": candidate["status"], "reason": candidate["reason"],
        })
    ranking.sort(key=lambda x: (-x["worst_1yr_net_usd"], x["candidate"]))
    document = {
        "title": "NEXUS V4 independent historical generalization 2024",
        "retrospective_only": True,
        "2024_previously_unexamined_by_nexus_v1_v4": True,
        "not_forward_live_evidence": True,
        "no_optimization": True, "no_promotion": True,
        "source": source, "months": months,
        "2023_exclusion": "2023-03 source has bar with early close at 2023-03-24; withheld pending data-quality review",
        "frozen_hypotheses": [asdict(p) for p in POLICIES],
        "scenarios": SCENARIOS, "results": results,
        "ranking": ranking,
        "ledger_sha256": hashlib.sha256(tradefile.read_bytes()).hexdigest(),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    (output / "backfill_results.json").write_text(
        json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8")
    lines = [
        "# NEXUS V4 independent backfill 2024",
        "",
        "Run exactly the V4 rules frozen before its 2025–Jun/2026 replay, "
        "on 2024 public Bitcoin/Ethereum Binance M5 historical archives never "
        "inspected in earlier Nexus Quant V1–V4 research. No parameter changed.",
        "Historical backfill is NOT actual prospective/forward performance.",
        "",
        "| Candidate | Status | 2024 net base USD | 2024 trades | Worst stress USD |",
        "|---|---|---:|---:|---:|",
    ]
    for x in ranking:
        b = x["yearly"]["2024"]
        lines.append(
            f"| {x['candidate']} | {x['status']} | "
            f"{b['net_by_scenario']['base']:.2f} | "
            f"{b['trades']} | {x['worst_1yr_net_usd']:.2f} |")
    lines.extend([
        "",
        "## Verification",
        "CSV sha256: " + document["ledger_sha256"],
        "All three original cost scenarios, independent quarterly ledgers, "
        "conservative intrabar fills and no real orders.",
        "2025 and Jan-Jun/2026 had already been inspected separately; "
        "positive 2024 will not erase a negative 2025 result.",
        "No V4 policy was adjusted after seeing the 2025–2026 V4 results.",
    ])
    (output / "BACKFILL_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "total": len(results),
        "statuses": dict(Counter(x["status"] for x in results.values())),
        "ranked": ranking,
    }, ensure_ascii=False))
    return document


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("artifacts/nexus-v4-backfill"))
    ap.add_argument("--cache", type=Path, default=Path(".cache/nexus_v4_backfill"))
    args = ap.parse_args()
    run(output=args.out, cache=args.cache)
