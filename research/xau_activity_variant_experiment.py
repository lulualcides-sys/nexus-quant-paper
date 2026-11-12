"""Predeclared XAUUSD quote activity research variants; never fit on evaluation days."""
from __future__ import annotations
from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from research.xau_quote_tracker_reference import QuotePolicy, scan_closed
from research.xau_dukascopy_replay import aggregate_real_quotes
from research.xau_quote_execution_backtest import (
    ExecutionAssumptions, simulate_quote_execution, _ticks
)

# Freeze variants BEFORE evaluating the chronological later days.
# These are hypotheses, not the original Greenhouse algorithm.
VARIANTS = {
    "baseline": {},
    "activity_110": {"activity_factor":1.10},
    "moderate_reclaim": {"activity_factor":1.10,"min_wick_fraction":0.24,
                         "close_location":0.59},
    "broad_reclaim": {"activity_factor":1.00,"min_wick_fraction":0.20,
                      "close_location":0.55,"sweep_atr":0.03},
}
TRAIN_DATES = ("20261019","20261020","20261021","20261022")
EVAL_DATES = ("20261103","20261104")
ALL_DATES = TRAIN_DATES+EVAL_DATES


def run_one(path: str | Path, tf: str, variant: str, *, fee: float=.30, slip: float=.10):
    if variant not in VARIANTS or tf not in ("M1","M5"):
        raise ValueError("Unknown predeclared variant/timeframe")
    seconds=60 if tf=="M1" else 300
    bars, provenance=aggregate_real_quotes(path,seconds,point=.001)
    policy=replace(QuotePolicy(timeframe_seconds=seconds,point=.001,tick_size=.001),
                   **VARIANTS[variant])
    signals=scan_closed(bars,len(bars)-2,policy)
    planned=[]
    for s in signals:
        stamp=int(datetime.fromisoformat(s["time_utc"]).timestamp()*1000)
        planned.append({
            "signal_ms":stamp,"eligible_ms":stamp+seconds*1000,
            "side":1 if s["side"]=="BUY" else -1,
            "entry":s["levels"]["50"],
            "target":s["levels"]["200"],
            "stop":s["levels"]["-100"],
        })
    outcome=simulate_quote_execution(_ticks(Path(path)),planned,
        ExecutionAssumptions(timeframe_seconds=seconds,
            commission_roundtrip_usd_per_oz=fee,slippage_usd_per_side=slip))
    return {"timeframe":tf,"variant":variant,"parameters":policy.__dict__,
            "source":provenance,"execution":outcome,
            "actual_broker_result":False,"original_greenhouse_equivalence":False}


def summarize(folder: str | Path):
    folder=Path(folder)
    records={}
    for tf in ("M1","M5"):
        for name in VARIANTS:
            parts={}
            for group,days in (("train",TRAIN_DATES),("evaluation",EVAL_DATES)):
                rows=[]
                for day in days:
                    file=folder/f"{day}_{tf}_{name}.json"
                    data=json.loads(file.read_text(encoding="utf-8"))
                    if data["variant"]!=name or data["timeframe"]!=tf:
                        raise ValueError("Mixed variant evidence")
                    if not data["source"]["first_candle_utc"].startswith(
                        f"{day[:4]}-{day[4:6]}-{day[6:]}"):
                        raise ValueError("Mixed source date")
                    rows.append(data)
                ledgers=[t for r in rows for t in r["execution"]["ledger"]]
                n=sum(r["execution"]["filled"] for r in rows)
                if n!=len(ledgers): raise ValueError("Missing ledger")
                net=round(sum(t["net_usd_per_oz"] for t in ledgers),6)
                parts[group]={
                    "signals":sum(r["execution"]["planned_signals"] for r in rows),
                    "filled":n,"wins":sum(t["net_usd_per_oz"]>0 for t in ledgers),
                    "losses":sum(t["net_usd_per_oz"]<0 for t in ledgers),
                    "net_usd_per_oz":net,
                    "expectancy_usd_per_oz":round(net/n,6) if n else None,
                }
            records[f"{tf}_{name}"]=parts
    # Selection based solely on TRAIN, but even a positive evaluation does not
    # approve live trading. Min 10 train fills avoids selecting a single winner.
    selected={}
    for tf in ("M1","M5"):
        candidates=[(name,records[f"{tf}_{name}"]["train"])
                    for name in VARIANTS]
        eligible=[(name,s) for name,s in candidates if s["filled"]>=10]
        selected[tf]=max(eligible,key=lambda x:x[1]["net_usd_per_oz"])[0] if eligible else None
    return {"train_dates":TRAIN_DATES,"evaluation_dates":EVAL_DATES,
            "selection_rule":"maximum TRAIN net among variants with >=10 train fills; otherwise NONE",
            "selected_before_evaluation":selected,
            "results":records,"approved_for_live":False,
            "note":"Small exploratory historical panel; not a genuine future holdout after inspection. "
                   "No broker costs or Tracker equivalence verified."}


def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--ticks")
    ap.add_argument("--day")
    ap.add_argument("--out",required=True)
    ap.add_argument("--summary-dir")
    args=ap.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    if args.summary_dir:
        r=summarize(args.summary_dir)
        (out/"comparison.json").write_text(json.dumps(r,indent=2)+"\n")
        for k,v in r["results"].items():
            print(k,"TRAIN",v["train"],"EVALUATION",v["evaluation"])
        print("TRAIN-ONLY SELECTED",r["selected_before_evaluation"],"LIVE APPROVAL",r["approved_for_live"])
    else:
        if args.day not in ALL_DATES or not args.ticks:
            raise ValueError("Only predeclared dates and raw quote files allowed")
        for tf in ("M1","M5"):
            for name in VARIANTS:
                r=run_one(args.ticks,tf,name)
                (out/f"{args.day}_{tf}_{name}.json").write_text(json.dumps(r,indent=2)+"\n")
                e=r["execution"]
                print(args.day,tf,name,"signals",e["planned_signals"],
                      "fills",e["filled"],"net",e["net_usd_per_oz"])


if __name__=="__main__":
    main()
