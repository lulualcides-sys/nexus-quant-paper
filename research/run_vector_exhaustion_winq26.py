"""Pinned, exploratory WINQ26 2026 replay of independent vector-exhaustion hypothesis.

Historical source was previously studied by Nexus Quant, so this is NOT an
untouched out-of-sample validation. It neither measures Greenhouse's proprietary
signals nor uses any broker order/fill data.
"""
from __future__ import annotations

import json
import tempfile
from dataclasses import replace
from pathlib import Path

from research.atlas_winq26_public import fetch,canonicalize
from research.vector_exhaustion_reference import Rules,replay,_day
from research.win_price_data import read_win_csv

WINDOWS={
    "Apr_May_2026":("2026-04-01","2026-06-01"),
    "June_2026":("2026-06-01","2026-07-01"),
    "July_2026_partial":("2026-07-01","2026-08-01")
}
COSTS={
    "legacy_6_brl":Rules(fee_roundtrip_brl=4,slippage_ticks_each_side=1),
    "rico_no_rlp_3_4_brl_UNVERIFIED":Rules(fee_roundtrip_brl=1.40,slippage_ticks_each_side=1),
    "slippage_stress_5_4_brl_UNVERIFIED":Rules(fee_roundtrip_brl=1.40,slippage_ticks_each_side=2),
}
MIN_REVIEW_TRADES=100

def study(bars):
    out={"source_note":"Third-party WINQ26 Profit export, not authenticated B3",
         "analysis":"EXPLORATORY_NOT_PROPRIETARY_TRACKER_NOT_OOS",
         "strategy_name":"NQ_Vector_Exhaustion_Research",
         "public_fibo_geometry":True,
         "proprietary_signal_detector_recovered":False,
         "bankroll_brl":2000,
         "contracts_per_trade":1,
         "max_planned_risk_fraction":0.01,
         "assumed_costs_brl_per_roundtrip":[6,3.4,5.4],
         "approval_for_real_orders":False,
         "windows":{}}
    for name,(start,end) in WINDOWS.items():
        sample=[b for b in bars if start<=_day(b["time"])<end]
        out["windows"][name]={}
        for cost_name,rules in COSTS.items():
            result=replay(sample,rules)
            ledger=result.pop("ledger")
            result["trades"]=ledger
            result["passes_retrospective_screen"]=(
                result["closed_paper_trades"]>=MIN_REVIEW_TRADES
                and result["net_closed_brl"]>0
                and (result["profit_factor"] or 0)>=1.2
                and result["unverifiable_gap_or_session_exits"]==0
                and result["ambiguous_within_M1"]==0
                and not result["unclosed_at_end"]
            )
            out["windows"][name][cost_name]=result
    return out

def markdown(report):
    s=["# Independent MT5 vector indicator — historical WINQ26 study","",
       "**This is not Tracker or its proprietary signal logic; no EA or real money use.**","",
       "Model: after close, 20-bar wick/sweep and volume hypothesis. "
       "Draw 0/50/100/200/-100 based on candle amplitude. Entry is a pending 50% limit, "
       "not an immediate fill. Gross target and stop from 50% are exactly 1:1.","",
       "Data: third-party WINQ26 previously inspected by Nexus Quant. This is NOT blind OOS. "
       "1 WIN, R$2,000, 1% max planned stop-risk, pessimistic M1 execution. "
       "No market depth/ticks or real broker confirmations.","",
       "| Month | Cost scenario | Signals | Risk-vetoed | Closed | Net BRL | Win rate % | PF | M1 ambiguous | Unverifiable gaps |",
       "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for m,tests in report["windows"].items():
        for label,a in tests.items():
            s.append(f"| {m} | {label} | {a['signals']} | {a['rejected_for_1pct_budget']} | "
                     f"{a['closed_paper_trades']} | {a['net_closed_brl']:+.2f} | "
                     f"{a['winning_rate_pct'] if a['winning_rate_pct'] is not None else 'N/D'} | "
                     f"{a['profit_factor'] if a['profit_factor'] is not None else 'N/D'} | "
                     f"{a['ambiguous_within_M1']} | {a['unverifiable_gap_or_session_exits']} |")
    s+=["","## Invalid claims and quality gates","",
        "- The original Greenhouse Tracker signal algorithm is not public; this strategy is an **independent hypothesis**.",
        "- When entry is the candle's midpoint, target 200% and stop -100% are equal distances from entry. Costs make the net payoff <1:1.",
        "- With R$2,000 and a 1% max planned risk, 1 WIN may not be affordable when the signal candle is large. Signals vetoed for that reason must NOT be counted as trades.",
        "- M1 OHLC cannot determine whether limit/target/stop occurred in which sequence. Ambiguous candles are reported and cannot validate profits.",
        "- Data holes within a trade cannot validate actual fills; paper P&L does not prove market execution.",
        "- The comparison uses historical costs **assumed**, not the user's Rico statement; no training on this evaluation period.",
        "- Positive numbers (if any) do not prove live profitable edge; follow fresh contract data, tick replay, OOS and forward paper monitoring.",
        ""]
    return "\n".join(s)

def main():
    with tempfile.TemporaryDirectory() as temp:
        p=Path(temp)
        src=fetch(p/"qraw.csv")
        canonicalize(p/"qraw.csv",p/"q26_normalized.csv")
        data=read_win_csv(p/"q26_normalized.csv",expected_symbol="WINQ26")
        if data["timeframe_seconds"]!=60 or len(data["bars"])<30000:
            raise RuntimeError("source unavailable or no authentic single-expiry M1")
        out=study(data["bars"])
        out["source"]=src
    folder=Path("research/results")
    folder.mkdir(parents=True,exist_ok=True)
    (folder/"nq_vector_independent_winq26.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    report=markdown(out)
    (folder/"nq_vector_independent_winq26.md").write_text(report+"\n",encoding="utf-8")
    print("VECTOR_RESEARCH_START")
    print(report)
    print("VECTOR_RESEARCH_END")

if __name__=="__main__":
    main()
