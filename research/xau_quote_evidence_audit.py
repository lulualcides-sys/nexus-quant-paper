"""Independent exit/quality audit over saved XAUUSD quote execution ledgers.

Reads prior evidence artifacts without re-downloading raw quote feeds. This
code analyzes *why* the reference rules failed; it never tunes thresholds.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
import json
from math import isfinite
from pathlib import Path


def analyze_evidence(folder: str | Path, dates: list[str]) -> dict:
    if not dates or dates != sorted(set(dates)):
        raise ValueError("Dates must be unique and chronologically sorted")
    folder=Path(folder)
    out={
        "source":"PREVIOUS published Dukascopy quotes-derived ledgers only",
        "dates":dates, "broker_account_validated":False,
        "verified_greenhouse_equivalence":False,
        "strategies":{},
        "eligible_for_broker_orders":False,
    }
    source_hashes_by_day = {}
    for tf in ("M1","M5"):
        by_scenario={}
        for scenario in ("base","friction"):
            events=[]; signals=filled=expired=0
            for day in dates:
                path=folder/f"xau_{day}_{tf}_{scenario}.json"
                if not path.is_file():
                    raise ValueError(f"Missing evidence {path.name}")
                record=json.loads(path.read_text(encoding="utf-8"))
                src=record["source"]
                exe=record["execution"]
                if (not src["first_candle_utc"].startswith(
                    f"{day[:4]}-{day[4:6]}-{day[6:]}") or
                    len(src["source_sha256"]) != 64 or
                    src["source_rows"] < 1000 or
                    record["independently_validated_with_original_greenhouse"] is not False or
                    record["broker_lot_or_commission_verified"] is not False or
                    record["spread_accounted_through_actual_bid_ask"] is not True):
                    raise ValueError(f"Invalid provenance for {path.name}")
                if day in source_hashes_by_day and source_hashes_by_day[day]!=src["source_sha256"]:
                    raise ValueError("Source changed between timeframes/scenarios")
                source_hashes_by_day[day]=src["source_sha256"]
                if not (0<=exe["filled"]==exe["closed"]<=exe["planned_signals"]):
                    raise ValueError("Invalid fill/plan accounting")
                if len(exe["ledger"]) != exe["filled"]:
                    raise ValueError("Missing closed-trade entries")
                signals+=exe["planned_signals"];filled+=exe["filled"]
                expired+=exe["unfilled_expired"]
                for trade in exe["ledger"]:
                    opening=datetime.fromisoformat(trade["entry_time_utc"])
                    closing=datetime.fromisoformat(trade["exit_time_utc"])
                    if (opening.tzinfo is None or closing.tzinfo is None or
                        opening>closing or opening.date().isoformat()!=
                        f"{day[:4]}-{day[4:6]}-{day[6:]}" or
                        trade["side"] not in ("BUY","SELL") or
                        trade["reason"] not in
                        ("STOP","STOP_SAME_TICK","TARGET","TIME","SESSION_END")):
                        raise ValueError(f"Incorrect ledger time/exit reason {path.name}")
                    pnl=float(trade["net_usd_per_oz"])
                    if not isfinite(pnl):
                        raise ValueError("Invalid nonfinite P&L")
                    events.append({
                        "day":day,"side":trade["side"],"exit_reason":trade["reason"],
                        "pnl_usd_per_oz":pnl,
                        "holding_minutes":round((closing-opening).total_seconds()/60,3),
                    })
            counts=Counter(t["exit_reason"] for t in events)
            pnl_by_reason=defaultdict(float)
            for trade in events:
                pnl_by_reason[trade["exit_reason"]]+=trade["pnl_usd_per_oz"]
            gross_profit=sum(max(0,t["pnl_usd_per_oz"]) for t in events)
            gross_loss=-sum(min(0,t["pnl_usd_per_oz"]) for t in events)
            net=gross_profit-gross_loss
            by_scenario[scenario]={
                "signals":signals,"filled":filled,"expired":expired,
                "fill_rate":round(filled/signals,4) if signals else None,
                "net_usd_per_oz":round(net,6),
                "expectancy_usd_per_oz":round(net/filled,6) if filled else None,
                "profit_factor":round(gross_profit/gross_loss,4) if gross_loss else None,
                "wins":sum(t["pnl_usd_per_oz"]>0 for t in events),
                "losses":sum(t["pnl_usd_per_oz"]<0 for t in events),
                "exit_reason_counts":dict(sorted(counts.items())),
                "exit_reason_pnl_usd_per_oz":{
                    k:round(v,6) for k,v in sorted(pnl_by_reason.items())
                },
                "mean_holding_minutes":round(
                    sum(t["holding_minutes"] for t in events)/filled,3
                ) if filled else None,
                "days_with_filled_orders":len(set(t["day"] for t in events)),
            }
        if by_scenario["base"]["signals"] != by_scenario["friction"]["signals"]:
            raise ValueError("Cost scenarios disagree on signal count")
        if by_scenario["base"]["filled"] != by_scenario["friction"]["filled"]:
            raise ValueError("Cost scenarios disagree on limit fills")
        if by_scenario["friction"]["net_usd_per_oz"] > by_scenario["base"]["net_usd_per_oz"]+1e-6:
            raise ValueError("Costs perversely increased estimated net return")
        out["strategies"][tf]=by_scenario
    out["approval_fail_reasons"]=[
        "No actual MT5 broker data/execution, swap, latency or margin verified",
        "No same-feed comprehensive original Greenhouse Tracker signal comparison",
    ]
    for tf in ("M1","M5"):
        research=out["strategies"][tf]["friction"]
        if research["filled"] < 100:
            out["approval_fail_reasons"].append(
                f"{tf}: {research['filled']} fills, fewer than predeclared 100-trade research gate")
        if research["net_usd_per_oz"] <= 0:
            out["approval_fail_reasons"].append(
                f"{tf}: negative/zero net simulated return after cost stress")
    return out


def human_report(result: dict) -> str:
    lines=[
        "# XAUUSD fixed-parameter historical quote ledger audit",
        "",
        "Source: already published GitHub Actions ledger artifact; **no new raw quote downloads**.",
        "No live trading. No original Greenhouse equivalence. Dollars per hypothetical ounce.",
        "",
        "| TF | Planned signals | Filled | Fill rate | Wins/Losses | Net with costs (US$/oz) | PF | Trading approval |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for tf in ("M1","M5"):
        e=result["strategies"][tf]["friction"]
        percent=f"{100*e['fill_rate']:.1f}%" if e["fill_rate"] is not None else "N/A"
        pf=f"{e['profit_factor']:.3f}" if e["profit_factor"] is not None else "N/A"
        lines.append(
            f"| {tf} | {e['signals']} | {e['filled']} | {percent} | "
            f"{e['wins']}/{e['losses']} | {e['net_usd_per_oz']:+.3f} | {pf} | BLOCKED |"
        )
    lines.append("")
    for tf in ("M1","M5"):
        e=result["strategies"][tf]["friction"]
        lines.extend([
            f"## {tf}: breakdown by actual simulated exit reason",
            "",
            "| Exit reason | Count | Sum net US$/oz |",
            "|---|---:|---:|",
        ])
        for reason,n in e["exit_reason_counts"].items():
            pnl=e["exit_reason_pnl_usd_per_oz"][reason]
            lines.append(f"| {reason} | {n} | {pnl:+.3f} |")
        if not e["filled"]: lines.append("| No fills | 0 | N/A |")
        lines.append("")
    lines.append("## Hard stops before approval")
    lines.extend(f"- {v}" for v in result["approval_fail_reasons"])
    lines.append("")
    lines.append("A different parameter set tested on these same dates would be in-sample, not new evidence.")
    return "\n".join(lines)+"\n"


if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--reports",required=True)
    p.add_argument("--dates",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    report=analyze_evidence(args.reports,args.dates.split(","))
    output=Path(args.out);output.mkdir(parents=True,exist_ok=True)
    (output/"xau_ledger_audit.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    (output/"xau_ledger_audit.md").write_text(human_report(report),encoding="utf-8")
    print(human_report(report))
