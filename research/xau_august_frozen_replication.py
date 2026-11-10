"""Frozen XAUUSD August 2026 replication; descriptive, never optimize parameters.

Uses precisely the six pre-existing frequency variants and both M1/M5
with real Dukascopy bid/ask price updates. August is earlier in calendar
time than the September/October design panel, so it is a *historical
replication*, NEVER a prospective forward / untouched future holdout.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.xau_frequency_lab import VARIANTS
from research.xau_frequency_scorecard import sum_stats

DATES = tuple(
    f"202608{day:02d}" for day in
    (3,4,5,6,7,10,11,12,13,14,17,18,19,20,21,24,25,26,27,28)
)
KEYS = tuple(f"{v.name}_{tf}" for tf in ("M1","M5") for v in VARIANTS)
SCENARIOS = ("no_costs", "friction", "double_friction")


def summarize(folder: str | Path) -> dict:
    folder=Path(folder)
    clean=[]; quarantine=[]
    for date in DATES:
        data=folder/f"xau_{date}.json"
        bad=folder/f"quarantine_{date}.json"
        if data.is_file() == bad.is_file():
            raise ValueError(f"Expected exactly one result or quarantine for {date}")
        if bad.is_file():
            q=json.loads(bad.read_text(encoding="utf-8"))
            if (q.get("day_id")!=date or q.get("all_trades_excluded_before_scoring") is not True
                or not q.get("data_quality_error")):
                raise ValueError("Incomplete quarantine provenance")
            quarantine.append(q)
            continue
        v=json.loads(data.read_text(encoding="utf-8"))
        if (v["day"] != date or len(v["source_sha256"])!=64
            or v["quote_rows"]<1000 or v["original_greenhouse_tracker_match"] is not False
            or v["real_broker_backtest"] is not False or v["trading_approved"] is not False
            or set(v["variants"])!=set(KEYS) or v["m1_bars"]<50 or v["m5_bars"]<50):
            raise ValueError(f"Invalid dataset/provenance for {date}")
        for name,row in v["variants"].items():
            if set(row["scenarios"]) != set(SCENARIOS):
                raise ValueError("Missing cost sensitivity case")
            for cost in SCENARIOS:
                sim=row["scenarios"][cost]
                if (sim["filled"]>row["signals"] or
                    sim["filled"]!=len(sim["ledger"])):
                    raise ValueError("Inconsistent fills")
        clean.append(v)

    first=[x for x in clean if x["day"] <= "20260814"]
    later=[x for x in clean if x["day"] >= "20260817"]
    if len(clean)<16 or len(first)<8 or len(later)<8:
        raise ValueError("Insufficient clean coverage for fixed August comparison")

    out={
        "title":"XAUUSD frozen six-variant August 2026 HISTORICAL replication",
        "predeclared_days":list(DATES),
        "clean_days":[v["day"] for v in clean],
        "quarantine":quarantine,
        "split_first_block":"20260803-20260814",
        "split_second_block":"20260817-20260828",
        "not_a_future_holdout":True,
        "any_strategy_approved_for_trading":False,
        "origin":"Dukascopy historical XAUUSD bid/ask updates; not a user's MT5 broker",
        "financial_units":"Hypothetical USD per one troy ounce, not account PnL",
        "variants":{}
    }
    for name in KEYS:
        item={}
        for cost in SCENARIOS:
            item[cost]={
                "all":sum_stats(clean,name,cost),
                "first_half":sum_stats(first,name,cost),
                "second_half":sum_stats(later,name,cost),
            }
        # With unchanged fills, more cost cannot generate more net profit.
        a,b,c=(item[k]["all"] for k in SCENARIOS)
        if a["filled_count"]!=b["filled_count"] or b["filled_count"]!=c["filled_count"]:
            raise ValueError("Cost scenario changed fills")
        if not (a["net_usd_per_oz"]+1e-6 >= b["net_usd_per_oz"]
                >= c["net_usd_per_oz"]-1e-6):
            raise ValueError("Cost scenario paradox")
        out["variants"][name]=item
    out["approval_reasons"]=[
        "This is an earlier historical calendar period, not prospective OOS",
        "No demo MT5 with broker-specific XAU feed, costs, lot-size or slippage verification",
        "No exhaustive original Greenhouse Tracker same-feed comparison",
        "No authorization to merge or place orders",
    ]
    return out


def markdown_report(report: dict) -> str:
    lines=[
        "# XAUUSD M1 and M5 — fixed six-variant historical replay, August 2026",
        "",
        f"Clean days: **{len(report['clean_days'])}** out of 20 planned. "
        f"Full-session quarantines: **{len(report['quarantine'])}**.",
        "All variants and both timeframes are reported. No best-model cherry-picking.",
        "The period predates development. **It is NOT a future holdout, and not a real MT5 account backtest.**",
        "",
        "| Variant | TF | Signals | Filled | Wins/Losses | Net US$/oz | PF | Days active | Split 1 net | Split 2 net |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in KEYS:
        a=report["variants"][name]["double_friction"]
        total=a["all"]; first=a["first_half"]; second=a["second_half"]
        pf=f"{total['profit_factor']:.3f}" if total["profit_factor"] is not None else "—"
        tf=name.rsplit("_",1)[-1]
        variant=name[:-(len(tf)+1)]
        lines.append(
            f"| {variant} | {tf} | {total['signal_count']} | {total['filled_count']} | "
            f"{total['wins']}/{total['losses']} | {total['net_usd_per_oz']:+.3f} | "
            f"{pf} | {total['active_days']} | {first['net_usd_per_oz']:+.3f} | "
            f"{second['net_usd_per_oz']:+.3f} |"
        )
    lines.extend([
        "",
        "All US$/oz figures are **hypothetical** under double friction "
        "(round-trip fee $0.60/oz, adverse stop/market slippage $0.20/oz; "
        "bid/ask historical spread accounted). No swap, margin or live rejects.",
        "",
        "## Safety and interpretation",
        "- No model is eligible for broker orders from this experiment alone.",
        "- One signal is not necessarily one filled order; entries are limits at closed-bar Fibonacci levels.",
        "- The analysis cannot establish the original proprietary Tracker signal algorithm.",
        "- Forward-prospective and authorized MT5 feed validation remain mandatory.",
        "",
        "Quarantined source dates (if any):",
    ])
    lines.extend(f"- {q['day_id']}: {q['data_quality_error']}"
                 for q in report["quarantine"])
    if not report["quarantine"]:
        lines.append("- None")
    return "\n".join(lines)+"\n"


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--reports",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    report=summarize(args.reports)
    target=Path(args.out);target.mkdir(parents=True,exist_ok=True)
    (target/"august_2026_comparison.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    md=markdown_report(report)
    (target/"august_2026_comparison.md").write_text(md,encoding="utf-8")
    print(md)


if __name__=="__main__":
    main()
