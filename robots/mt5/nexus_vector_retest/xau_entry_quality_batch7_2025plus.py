#!/usr/bin/env python3
"""XAUUSD risk/quality-gated entrances, frozen exits and entry signals, 2025+.

ONLY native MT5 timeframes M1 M5 M15 M30 permitted; the existing prioritized
candidates studied on M5/M15/M30. Uses original Runner96h without modification.
Research OHLC proxy; no broker execution; historical periods previously seen.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from research_oos import download
from points10k_2025 import source as load2025
from alpha_xau_mtf_2025plus import (
    CUTOFF,COST_GRID,horizon_bars,windows_by_quarter,replay_one,summarize)
from xau_exit_risk_batch6_2025plus import (
    ALLOWED_TF,CANDIDATES,entry_inputs,risk_stats)

GATES=("UNFILTERED","RISK_ATR_0P7_TO_2P2",
       "COST_TO_STOP_LE_10PCT","QUALITY_GE_0P35",
       "RISK_AND_QUALITY")
OUT=Path(__file__).resolve().parent/"xau_entry_quality_batch7_2025plus_results"
# Fixed before test: USD 1.20/oz assumed round-trip when making cost gate.
ASSUMED_COST_FOR_SIGNAL=1.2
BASELINE_REFERENCE_COST_0P8={
    "EMA21_RUNNER_M15":{"2025":14839.4,"2026":6527.2},
    "EMA21_RSI_MACD_M30":{"2025":12240.5,"2026":19682.8},
    "ER20_BREAK_M30":{"2025":39638.5,"2026":29870.4},
    "SHOCK_EXHAUSTION_M5":{"2025":17994.8,"2026":8295.2},
    "SHOCK_EXHAUSTION_M15":{"2025":27240.8,"2026":14913.5},
}


def gate_signals(df,entries,gate):
    """No future-bar price info. Risk is checked on known next opening price.

    Return signals in same chronological order as original. Existing stop,
    side, candle and strength are copied unchanged, never tuned.
    """
    if gate not in GATES:
        raise ValueError("unsupported entry gate")
    op=df.open.to_numpy(dtype=float)
    atr=df.atr.to_numpy(dtype=float)
    result=[]
    for event in entries:
        i,side,stop,quality=event
        if i+1>=len(df):
            continue
        risk=float(side*(op[i+1]-stop))
        a=float(atr[i])
        if not np.isfinite([risk,a,quality]).all() or risk<=0 or a<=0:
            continue
        in_band=.7*a<=risk<=2.2*a
        modest_cost=(ASSUMED_COST_FOR_SIGNAL/risk)<=.10
        good_quality=float(quality)>=.35
        include=(gate=="UNFILTERED"
            or gate=="RISK_ATR_0P7_TO_2P2" and in_band
            or gate=="COST_TO_STOP_LE_10PCT" and modest_cost
            or gate=="QUALITY_GE_0P35" and good_quality
            or gate=="RISK_AND_QUALITY" and in_band and good_quality)
        if include:
            result.append(event)
    return result


def evaluate(raw,year,name,tf,model):
    if tf not in ALLOWED_TF or raw.empty or raw.index.min()<CUTOFF:
        raise ValueError("outside approved TF / data scope")
    df,orig=entry_inputs(raw,tf,model)
    sigs={gate:gate_signals(df,orig,gate) for gate in GATES}
    if sigs["UNFILTERED"]!=orig:
        raise AssertionError("baseline signals mutated")
    hold=horizon_bars(tf)
    trades_by_gate={mode:[] for mode in GATES}
    quarters=[]
    for q,first,last in windows_by_quarter(df,hold):
        if first is None:
            quarters.append({"quarter":q,"status":"INSUFFICIENT_BARS"})
            continue
        metrics={}
        for gate in GATES:
            t=replay_one(df,sigs[gate],first,last,tf,"RUNNER_96H")
            trades_by_gate[gate].extend(t)
            metrics[gate]={str(cost):{**summarize(t,cost),
                        **risk_stats(t,sigs[gate],df,cost)}
                        for cost in COST_GRID}
        quarters.append(dict(quarter=q,
            first=str(df.index[first]),last=str(df.index[last-1]),
            gates=metrics))
        print("GATE_QUARTER",json.dumps(dict(
             year=year,candidate=name,quarter=q,
             gates={key:metrics[key]["1.2"] for key in GATES})),flush=True)
    totals={gate:{str(cost):{**summarize(trades_by_gate[gate],cost),
                  **risk_stats(trades_by_gate[gate],sigs[gate],df,cost)}
                  for cost in COST_GRID} for gate in GATES}
    if round(totals["UNFILTERED"]["0.8"]["net_pts"],1)!=BASELINE_REFERENCE_COST_0P8[name][year]:
        raise AssertionError("historical baseline trade parity broken: "+name+year)
    answer=dict(year=year,candidate=name,tf=f"M{tf}",model=model,
         source_bars=len(df),signals_before=len(orig),
         signal_counts={m:len(sigs[m]) for m in GATES},
         quarters=quarters,summary=totals)
    print("GATE_YEAR",json.dumps(dict(year=year,candidate=name,
         tf=f"M{tf}",signal_counts=answer["signal_counts"],
         summary=totals)),flush=True)
    return answer


def screen(cases):
    comparisons=[]
    for name,tf,model in CANDIDATES:
        a=next(x for x in cases if x["year"]=="2025" and x["candidate"]==name)
        b=next(x for x in cases if x["year"]=="2026" and x["candidate"]==name)
        for gate in GATES:
            x=a["summary"][gate]["1.2"]
            y=b["summary"][gate]["1.2"]
            sx=a["summary"][gate]["1.6"]
            sy=b["summary"][gate]["1.6"]
            base25=a["summary"]["UNFILTERED"]["1.2"]
            base26=b["summary"]["UNFILTERED"]["1.2"]
            q25=sum(z["gates"][gate]["1.2"]["net_R"]>0
                for z in a["quarters"] if "gates" in z)
            q26=sum(z["gates"][gate]["1.2"]["net_R"]>0
                for z in b["quarters"] if "gates" in z)
            improved=(x["net_R"]>base25["net_R"] and
                      y["net_R"]>base26["net_R"])
            enough=(x["N"]>=100 and y["N"]>=50
                and x["N"]>=.75*base25["N"]
                and y["N"]>=.75*base26["N"])
            robust=(x["net_R"]>0 and y["net_R"]>0
                and sx["net_R"]>0 and sy["net_R"]>0
                and x["PF_R"] is not None and y["PF_R"] is not None
                and x["PF_R"]>1.1 and y["PF_R"]>1.1
                and q25>=3 and q26>=1)
            dd_ok=(x["MDD_R"] is not None and y["MDD_R"] is not None
                and base25["MDD_R"] is not None and base26["MDD_R"] is not None
                and x["MDD_R"]<=1.1*base25["MDD_R"]
                and y["MDD_R"]<=1.1*base26["MDD_R"])
            passed=bool(gate!="UNFILTERED" and improved and enough
                        and robust and dd_ok)
            comparisons.append(dict(candidate=name,timeframe=f"M{tf}",
                gate=gate,N_2025=x["N"],N_2026_partial=y["N"],
                net_R_2025=x["net_R"],net_R_2026_partial=y["net_R"],
                baseline_net_R_2025=base25["net_R"],
                baseline_net_R_2026_partial=base26["net_R"],
                PF_R_2025=x["PF_R"],PF_R_2026_partial=y["PF_R"],
                MDD_R_2025=x["MDD_R"],MDD_R_2026_partial=y["MDD_R"],
                stress_net_R_2025=sx["net_R"],
                stress_net_R_2026_partial=sy["net_R"],
                positive_quarters_2025=q25,
                positive_quarters_2026_partial=q26,
                improved_in_both=bool(improved),
                enough_trades=bool(enough),robust_cost_and_profit=bool(robust),
                acceptable_dd=bool(dd_ok),
                preliminary_screen=passed))
    return comparisons


def main():
    a,_=load2025()
    b=download()
    if a.index.min()<CUTOFF or b.index.min()<CUTOFF:
        raise ValueError("pre-2025 data prohibited")
    cases=[]
    for name,tf,model in CANDIDATES:
        for year,raw in (("2025",a),("2026",b)):
            cases.append(evaluate(raw,year,name,tf,model))
    ranked=screen(cases)
    selected=[r for r in ranked if r["preliminary_screen"]]
    payload=dict(symbol="XAUUSD",from_utc="2025-01-01",
        allowed_timeframes=["M1","M5","M15","M30"],
        studied_candidates=CANDIDATES,gates=GATES,
        historical_year_2026_is_partial=True,
        signal_filter_cost_usd_per_oz=ASSUMED_COST_FOR_SIGNAL,
        assumed_roundtrip_costs_usd_per_oz=COST_GRID,
        original_exit="RUNNER_96H",method="original signals and stops, filter only entry; next open fill, stop first, same 96h runner and quarter embargo",
        warnings=["Research retrospective years repeatedly inspected, no new OOS.",
          "2026 only Q2 and Q3 from a different historical feed.",
          "Filter thresholds are a pre-registered hypothesis, not a guarantee.",
          "Smaller N can inflate PF; screen requires >=75% of original trade count.",
          "No real broker ticks, variable spread, commission, slippage, swap, lot rounding or intratrade drawdown.",
          "All nine saved candidates and exits remain unchanged."],
        annual_cases=cases,comparison=ranked,preliminary_shortlist=selected,
        approved_for_live=False)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"GATE7_ALL.json").write_text(json.dumps(payload,indent=2)+"\n")
    lines=["# XAUUSD batch7 — risk/quality entry gates, 2025+",
       "","Only M1/M5/M15/M30 (tested M5/M15/M30), original Runner96h unchanged.",
       "OHLC research proxy, not real MT5 ticks, repeat-explored historical data.",
       "","| Candidate | Gate | N25 | R25 | PF_R25 | N26 | R26 | PF_R26 | Improved both | Passed screen |",
       "|---|---|---:|---:|---:|---:|---:|---:|---|---|"]
    for r in ranked:
        lines.append("| "+" | ".join(str(r[k]) for k in (
            "candidate","gate","N_2025","net_R_2025","PF_R_2025",
            "N_2026_partial","net_R_2026_partial","PF_R_2026_partial",
            "improved_in_both","preliminary_screen"))+" |")
    lines+=["","## Research-only shortlist",str(selected),
      "","Approval for real account: NEVER, need untouched forward broker data."]
    (OUT/"GATE7_REPORT.md").write_text("\n".join(lines)+"\n")
    print("GATE_COMPLETE",json.dumps(dict(evaluations=len(cases),
        comparisons=len(ranked),shortlisted=selected)),flush=True)


if __name__=="__main__":
    main()
