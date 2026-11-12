"""V5 30-month official Binance fee-stressed test, no promotion.

2024 and 2025 are development histories examined in V4; 2026-Jan/Jun is
previously inspected retrospective evaluation, NOT a fresh OOS test.
V5 reports all candidates, not only the best, and keeps V4 baseline.
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
from .v5_policy import H4_POLICIES, aggregate_closed_h4

MONTHS = list(month_range("2026-06", 30))
FOLDS = tuple(
    (f"dev_{year}_Q{q}", (year - 2024) * 12 + (q - 1) * 3,
     (year - 2024) * 12 + q * 3)
    for year in (2024, 2025) for q in (1, 2, 3, 4)
) + tuple((f"seen_validation_2026_Q{q}", 24 + (q - 1)*3, 24 + q*3)
          for q in (1, 2))


def variants():
    # Do not re-tune wins and losses until result green; fixed exits outperform
    # trailing in examined 2024-25 V4 records. Include both V4 original fixed
    # controls and *both* predetermined H4 quality hypotheses.
    fixed = [p for p in POLICIES if p.exit_mode == "fixed"]
    return [(p, None) for p in fixed] + [
        (p, gate) for p in fixed for gate in H4_POLICIES
    ]


def financial_status(years):
    """Explicitly reject net losses; too-small N / inspected data never APTO."""
    for year in ("2024", "2025", "2026"):
        if years[year]["trades"] and any(
            net <= 0 for net in years[year]["scenario_net_usd"].values()
        ):
            return "REPROVADO", f"{year}: nonpositive result under cost model"
    if (years["2024"]["trades"] < 50 or
        years["2025"]["trades"] < 50 or
        years["2026"]["trades"] < 25):
        return "INCONCLUSIVO", "Too few independent trades and reused 2026 data"
    return "INCONCLUSIVO", "Retrospective only; no untouched prospective forward evidence"


def run(*, output=Path("artifacts/nexus-v5"),
        cache=Path(".cache/nexus_v5")):
    if MONTHS[0] != "2024-01" or MONTHS[-1] != "2026-06":
        raise ValueError("Frozen historical time window violated")
    output.mkdir(parents=True, exist_ok=True)
    sources, results, ledger = {}, {}, []
    for symbol in ("BTCUSDT", "ETHUSDT"):
        m5, manifests = load_history(symbol, "5m", MONTHS, cache)
        h1 = aggregate_closed_h1(m5)
        h4 = aggregate_closed_h4(h1)
        if len(h1) != len(m5) // 12 or len(h4) != len(h1) // 4:
            raise ValueError("Incomplete H1/H4 aggregation; no synthetic fills")
        f1, f4 = build_features(h1), build_features(h4)
        h4_closes = [h.t + 14_400_000 for h in h4]
        month_indices_m5 = month_indices(m5, MONTHS)
        sources[symbol] = {
            "binance_public_5m_sha256_monthly": manifests,
            "m5_candles": len(m5),
            "closed_h1_candles": len(h1),
            "closed_h4_candles": len(h4),
        }
        for entry, gate in variants():
            label = gate.name if gate else "v4_unfiltered_control"
            name = f"{symbol}:{entry.name}:{label}"
            quarters = {}
            for fold, a, b in FOLDS:
                cases = {}
                for scenario in SCENARIOS:
                    report, trades = replay_v4(
                        m5, h1, f1, entry, scenario,
                        start=month_indices_m5[a], stop=month_indices_m5[b],
                        h4=h4 if gate else None,
                        h4_features=f4 if gate else None,
                        h4_closes=h4_closes if gate else None,
                        entry_gate=gate,
                    )
                    cases[scenario] = report
                    ledger.extend({
                        "candidate": name, "symbol": symbol,
                        "fold": fold, "scenario": scenario, **trade,
                    } for trade in trades)
                quarters[fold] = cases
            results[name] = {
                "symbol": symbol, "setup": asdict(entry),
                "h4_gate": asdict(gate) if gate else None,
                "quarters": quarters,
            }
        del m5, h1, h4, f1, f4

    rows = []
    for name, r in results.items():
        years = {}
        for year in ("2024", "2025", "2026"):
            qs = [q for label, q in r["quarters"].items()
                  if f"_{year}_" in label]
            trs = [t for t in ledger if t["candidate"] == name and
                   t["scenario"] == "base" and f"_{year}_" in t["fold"]]
            winners = [t["pnl_usd"] for t in trs if t["pnl_usd"] > 0]
            losers = [t["pnl_usd"] for t in trs if t["pnl_usd"] <= 0]
            mean_gain = sum(winners)/len(winners) if winners else None
            mean_loss = sum(losers)/len(losers) if losers else None
            break_even = (
                abs(mean_loss) / (mean_gain + abs(mean_loss))
                if mean_gain is not None and mean_loss is not None
                and (mean_gain + abs(mean_loss)) else None
            )
            years[year] = {
                "trades": len(trs),
                "winrate": len(winners) / len(trs) if trs else None,
                "break_even_winrate_from_observed_payoff": break_even,
                "average_winner_usd": mean_gain,
                "average_loser_usd": mean_loss,
                "scenario_net_usd": {
                    sc: round(sum(q[sc]["net_usd"] for q in qs), 4)
                    for sc in SCENARIOS
                },
                "veto_reasons_base": dict(Counter({
                    reason: sum(q["base"]["h4_veto_counts"].get(reason, 0)
                                for q in qs)
                    for reason in {
                        k for q in qs for k in q["base"]["h4_veto_counts"]
                    }
                })),
                "exit_reason_counts": dict(Counter(t["exit_reason"] for t in trs)),
            }
        r["years"] = years
        r["decision"], r["reason"] = financial_status(years)
        minval = min(years["2026"]["scenario_net_usd"].values())
        rows.append({
            "candidate": name, "decision": r["decision"], "reason": r["reason"],
            "2024_base": years["2024"]["scenario_net_usd"]["base"],
            "2025_base": years["2025"]["scenario_net_usd"]["base"],
            "2026_base": years["2026"]["scenario_net_usd"]["base"],
            "2026_worst": minval,
            "n2024": years["2024"]["trades"],
            "n2025": years["2025"]["trades"],
            "n2026": years["2026"]["trades"],
            "2026_winrate": years["2026"]["winrate"],
            "2026_break_even": years["2026"]["break_even_winrate_from_observed_payoff"],
        })
    rows.sort(key=lambda x: (-x["2026_worst"], x["candidate"]))

    columns = [
        "candidate", "symbol", "fold", "scenario", "signal_t",
        "entry_t", "exit_t", "entry_ref", "exit_ref", "entry", "exit",
        "qty", "initial_stop", "final_stop", "target", "gross_usd",
        "fees_usd", "execution_deviation_usd", "pnl_usd", "exit_reason",
        "signal_reason", "regime", "initial_stop_pct",
    ]
    ledger_file = output / "all_v5_entries.csv"
    with ledger_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="raise")
        writer.writeheader()
        writer.writerows(ledger)
    doc = {
        "status": "RESEARCH_ONLY_NO_LIVE_TRADING",
        "not_true_out_of_sample": True,
        "2024_2025_development_previously_inspected": True,
        "2026_validation_already_exposed_v1_v4": True,
        "2026_07_10_excluded_from_selection": True,
        "hypotheses_frozen": {
            "entries": [asdict(p) for p in POLICIES if p.exit_mode=="fixed"],
            "h4_gates": [asdict(p) for p in H4_POLICIES],
        },
        "months": MONTHS, "folds": FOLDS, "scenarios": SCENARIOS,
        "sources": sources, "results": results,
        "ranking_for_review_only": rows,
        "ledger_sha256": hashlib.sha256(ledger_file.read_bytes()).hexdigest(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (output / "results_v5.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    md = [
        "# NEXUS V5 — entry quality correction with H4 filter",
        "",
        "Read BEFORE interpreting any gain: 2024–2026-06 data were already",
        "reviewed in earlier experiments; **none is untouched OOS**.",
        "Do not claim any positive candidate is validated or deploy it.",
        "",
        "| Candidate | Decision | 2024 net USD | 2025 net USD | 2026-H1 net USD | 2026 worst cost USD | Trades 2024/25/26 |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        md.append(
            f"| {row['candidate']} | {row['decision']} | "
            f"{row['2024_base']:.2f} | {row['2025_base']:.2f} | "
            f"{row['2026_base']:.2f} | {row['2026_worst']:.2f} | "
            f"{row['n2024']}/{row['n2025']}/{row['n2026']} |"
        )
    md.extend([
        "", "## Honest limits",
        "- V4 controls included on the same exact historical folds, not cherry-picked.",
        "- All BTC/ETH spot Binance official ZIPs verified by monthly SHA256.",
        "- Fixed exits: trailing empirically reduced prior V4 winner payoff.",
        "- H4 gate is causal, with H1 signal and next M5 open, conservative fill.",
        "- Costs remain full regular Binance spot and doubled/adverse cases.",
        "- Each candidate has an independent virtual $10,000 account per quarter.",
        "- Never add P&L across 12 simultaneous independent candidate books.",
        "- Low trade count or mixed-year negative net disqualifies promotion.",
        "- A possible historical winner needs truly new forward paper data.",
        "",
        "Complete ledger SHA256: " + doc["ledger_sha256"],
    ])
    (output / "REPORT_V5.md").write_text("\n".join(md)+"\n", encoding="utf-8")
    print(json.dumps({
        "candidates": len(rows),
        "statuses": dict(Counter(x["decision"] for x in rows)),
        "ranking": rows,
    }, ensure_ascii=False))
    return doc


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("artifacts/nexus-v5"))
    parser.add_argument("--cache", type=Path, default=Path(".cache/nexus_v5"))
    args = parser.parse_args()
    run(output=args.out, cache=args.cache)
