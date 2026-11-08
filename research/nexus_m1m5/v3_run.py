"""V3: freeze hypotheses before any backtest. Historical research only.

Jan 2025-Jun 2026 includes previously inspected prices. Never mark this
sample out-of-sample or activate any trading from this report.
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
from .engine import SCENARIOS, replay
from .run import month_indices
from .strategies import SPECS, build_features
from .v2_run import QUARTERS, judge
from .v3_policy import aggregate_closed_h1, policies

PAIRS = ("BTCUSDT", "ETHUSDT")
SETUPS = (("sweep", "immediate"), ("trend", "immediate"),
          ("breakout", "retest"))


def run(*, output=Path("artifacts/nexus-m1m5-v3"),
        cache=Path(".cache/nexus_m1m5_v3")):
    output.mkdir(parents=True, exist_ok=True)
    months = list(month_range("2026-06", 18))
    results, ledger, sources = {}, [], {}
    for symbol in PAIRS:
        m1, s1 = load_history(symbol, "1m", months, cache)
        m5, s5 = load_history(symbol, "5m", months, cache)
        h1 = aggregate_closed_h1(m5)
        if len(h1) < 240 or h1[0].t != m5[0].t:
            raise ValueError("Hourly series incomplete or misaligned")
        f1, f5, fh1 = build_features(m1), build_features(m5), build_features(h1)
        h1_closes = [b.t + 3_600_000 for b in h1]
        sources[symbol] = {"1m": s1, "5m": s5, "h1_count": len(h1)}
        for robot, variant in SETUPS:
            tf = SPECS[robot]["tf"]
            bars, features = (m1, f1) if tf == "1m" else (m5, f5)
            boundaries = month_indices(bars, months)
            for policy in policies(tf):
                name = f"{symbol}:{robot}:{variant}:{policy.name}"
                candidate = {
                    "symbol": symbol, "robot": robot, "variant": variant,
                    "timeframe": tf, "policy": asdict(policy), "quarters": {},
                }
                for label, a, b in QUARTERS:
                    start, stop = max(210, boundaries[a]), boundaries[b]
                    scenarios = {}
                    for sc in SCENARIOS:
                        summary, trades = replay(
                            bars, features, robot, sc, start=start, stop=stop,
                            breakout_mode=variant,
                            research_policy=asdict(policy), macro=h1,
                            macro_features=fh1, macro_closes=h1_closes)
                        scenarios[sc] = summary
                        ledger.extend({
                            "candidate": name, "symbol": symbol, "robot": robot,
                            "quarter": label, "scenario": sc, **t
                        } for t in trades)
                    candidate["quarters"][label] = scenarios
                candidate["decision"], candidate["reason"] = judge(candidate)
                results[name] = candidate
        del m1, m5, h1, f1, f5, fh1

    headers = ["candidate", "symbol", "robot", "quarter", "scenario",
               "signal_t", "entry_t", "exit_t", "entry", "exit", "qty",
               "pnl_usd", "fees_usd", "execution_deviation_usd", "stop",
               "target", "exit_reason", "signal_reason", "regime"]
    csvfile = output / "trades_v3.csv"
    with csvfile.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(ledger)

    ranking = []
    for name, c in results.items():
        dev = [x for k, x in c["quarters"].items() if k.startswith("development")]
        val = [x for k, x in c["quarters"].items()
               if k.startswith("retrospective_validation")]
        ranking.append({
            "candidate": name,
            "decision": c["decision"],
            "development_base_usd": round(sum(x["base"]["net_usd"] for x in dev), 2),
            "development_positive_quarters": sum(x["base"]["net_usd"] > 0 for x in dev),
            "validation_base_usd": round(sum(x["base"]["net_usd"] for x in val), 2),
            "validation_worst_cost_usd": round(min(
                sum(x[sc]["net_usd"] for x in val) for sc in SCENARIOS), 2),
            "validation_trades": sum(x["base"]["trades_closed"] for x in val),
            "validation_stops": sum(
                t["exit_reason"] in ("stop", "gap_stop") for t in ledger
                if t["candidate"] == name and t["scenario"] == "base" and
                t["quarter"].startswith("retrospective_validation")),
            "reason": c["reason"],
        })
    ranking.sort(key=lambda x: -x["validation_worst_cost_usd"])
    manifest = {
        "name": "NEXUS V3 closed-H1 macro risk vs unchanged V1 trigger",
        "window": "2025-01..2026-06", "source": sources,
        "scenarios": SCENARIOS, "setups": SETUPS,
        "policies_1m": [asdict(p) for p in policies("1m")],
        "policies_5m": [asdict(p) for p in policies("5m")],
        "results": results, "ranking": ranking,
        "ledger_sha256": hashlib.sha256(csvfile.read_bytes()).hexdigest(),
        "previously_seen_validation": True,
        "exposed_2026_07_to_10_excluded": True,
        "not_live": True, "no_paper_forward": True,
        "auto_promotion": False,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    (output / "results_v3.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8")
    md = [
        "# NEXUS M1/M5 V3 — execution and entry audit",
        "",
        "Not out-of-sample: 2025 and 2026-01..06 inspected before. "
        "2026-07..10 V1 holdout intentionally excluded.",
        "",
        "Original causal sweep M1, trend M5 and breakout/retest M5 preserved.",
        "V3 frozen variants: full CLOSED H1 EMA20>=EMA50>EMA200, positive EMA50 "
        "12h slope, restricted extension and hourly ATR floor. Stops at least "
        "0.6%/0.9% or 0.8x/1.2x H1 ATR; targets 2R/2.3R; hold 24h/48h.",
        "Original risk budget, fees, slippage and conservative stop priority preserved.",
        "",
        "| Candidate | Decision | Dev base USD | Val base USD | Worst cost USD | Trades | Stops |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for x in ranking:
        md.append(
            f"| {x['candidate']} | {x['decision']} | "
            f"{x['development_base_usd']:.2f} | {x['validation_base_usd']:.2f} | "
            f"{x['validation_worst_cost_usd']:.2f} | "
            f"{x['validation_trades']} | {x['validation_stops']} |")
    md.extend([
        "",
        "Ledger CSV sha256: " + manifest["ledger_sha256"],
        "Every scenario and quarter, closed candle, next candle open, fees and "
        "estimated execution costs recorded. No broker orders or automations.",
        "No candidate can be promoted merely by selecting its best historical result.",
    ])
    (output / "REPORT_V3.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({
        "candidates": len(results),
        "status_counts": dict(Counter(v["decision"] for v in results.values())),
        "top_5": ranking[:5],
    }, ensure_ascii=False))
    return manifest


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=Path("artifacts/nexus-m1m5-v3"))
    p.add_argument("--cache", type=Path, default=Path(".cache/nexus_m1m5_v3"))
    args = p.parse_args()
    run(output=args.out, cache=args.cache)
