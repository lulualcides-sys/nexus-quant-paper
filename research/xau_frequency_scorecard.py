"""Precommitted chronologically separated XAUUSD candidate scorecard.

Research-only: no auto-tuning and no broker execution. First choose candidate
using only training sessions; afterwards score validation and future holdout.
Pass mark requires many trades and future validation; past fit alone cannot
authorize the indicator or an EA.
"""
from __future__ import annotations
from collections import defaultdict
import argparse
import json
from math import isfinite
from pathlib import Path
import random
import statistics

TRAIN = (
 "20260921","20260922","20260923","20260924","20260925",
 "20260928","20260929","20260930","20261001","20261002",
 "20261005","20261006","20261007","20261008","20261009",
)
VALIDATION = (
 "20261012","20261013","20261014","20261015","20261016",
 "20261019","20261020","20261021","20261022","20261023",
)
FUTURE_HOLDOUT = ("20261109_18","20261110_00")
ALL = TRAIN + VALIDATION + FUTURE_HOLDOUT
PRESELECT_TRAIN_TRADES = 20
MIN_VALIDATION_TRADES = 30
MIN_UNSEEN_FUTURE_TRADES = 100


def load(path: str | Path) -> dict:
    x=json.loads(Path(path).read_text(encoding="utf-8"))
    if (x.get("trading_approved") is not False or
        x.get("original_greenhouse_tracker_match") is not False or
        x.get("real_broker_backtest") is not False or
        len(x.get("source_sha256", "")) != 64 or
        x.get("quote_rows",0)<1000):
        raise ValueError("Unverified quote provenance/approval state")
    return x


def sum_stats(day_reports: list[dict], candidate: str, scenario: str) -> dict:
    values=[]; all_trades=[]
    signals=filled=expired=0; active_days=0; profitable_days=0
    gross_win=gross_loss=0.
    for report in day_reports:
        v=report["variants"][candidate]
        s=v["scenarios"][scenario]
        signals+=v["signals"];filled+=s["filled"];expired+=s["expired"]
        ledger=s["ledger"]
        if len(ledger)!=s["filled"]:
            raise ValueError("Ledger/fill mismatch")
        day_net=sum(float(t["net_usd_per_oz"]) for t in ledger)
        if abs(day_net-s["net_usd_per_oz"]) > 0.001:
            raise ValueError("P&L mismatch")
        if not isfinite(day_net):
            raise ValueError("Nonfinite P&L")
        values.append(day_net)
        active_days+=bool(ledger)
        profitable_days+=bool(ledger) and day_net>0
        all_trades.extend(ledger)
        gross_win+=sum(max(float(t["net_usd_per_oz"]),0) for t in ledger)
        gross_loss-=sum(min(float(t["net_usd_per_oz"]),0) for t in ledger)
    net=gross_win-gross_loss
    # Fixed-seed bootstrap across DAYS (not individual highly correlated ticks).
    # CI is descriptive only; session selection, invalid feeds and brokerage
    # constraints can still bias an apparent positive result.
    if values:
        rng=random.Random(20261110)
        sampled=sorted(sum(rng.choices(values,k=len(values))) for _ in range(3000))
        lo,hi=sampled[75],sampled[2924]
    else:
        lo=hi=0.
    peak=equity=drawdown=0.
    for t in all_trades:
        equity+=float(t["net_usd_per_oz"])
        peak=max(peak,equity)
        drawdown=max(drawdown,peak-equity)
    return {
        "source_days":len(day_reports),
        "signal_count":signals,"filled_count":filled,"expired":expired,
        "fill_rate":round(filled/signals,4) if signals else None,
        "wins":sum(float(t["net_usd_per_oz"])>0 for t in all_trades),
        "losses":sum(float(t["net_usd_per_oz"])<0 for t in all_trades),
        "net_usd_per_oz":round(net,6),
        "profit_factor":round(gross_win/gross_loss,6) if gross_loss>0 else None,
        "expectancy_usd_per_oz":round(net/filled,6) if filled else None,
        "active_days":active_days,
        "positive_active_days":profitable_days,
        "max_closed_drawdown_usd_per_oz":round(drawdown,6),
        "day_bootstrap_net_p025":round(lo,6),
        "day_bootstrap_net_p975":round(hi,6),
    }


def _load_windows(directory, ids, min_days):
    rows=[]; missing=[]; bad=[]
    root=Path(directory)
    for day in ids:
        filename=root/f"xau_{day}.json"
        if filename.exists():
            obj=load(filename)
            if obj["day"] != day[:8]:
                raise ValueError("Mismatched day ID")
            rows.append(obj)
        else:
            note=root/f"quarantine_{day}.json"
            if note.exists():
                q=json.loads(note.read_text())
                if q.get("day_id") != day:
                    raise ValueError("Mismatched quarantine")
                bad.append(q)
            else:
                missing.append(day)
    if missing:
        raise ValueError(f"Missing sessions without data-quality evidence: {missing}")
    if len(rows)<min_days:
        raise ValueError(f"Not enough clean sessions ({len(rows)}/{len(ids)})")
    return rows,bad


def rank_training(directory: str|Path) -> dict:
    training,quarantine=_load_windows(directory,TRAIN,12)
    keys=sorted(training[0]["variants"].keys())
    for r in training:
        if set(r["variants"])!=set(keys):
            raise ValueError("Missing candidate variant in a day")
    board=[]
    for key in keys:
        ref=sum_stats(training,key,"friction")
        stress=sum_stats(training,key,"double_friction")
        qualifies=(
            ref["filled_count"]>=PRESELECT_TRAIN_TRADES
            and ref["active_days"]>=6
            and stress["net_usd_per_oz"]>0
            and stress["profit_factor"] is not None
            and stress["profit_factor"]>=1.20
        )
        board.append({"name":key, "training":ref,"double_friction":stress,
                      "preselected":bool(qualifies)})
    eligible=sorted(
        [x for x in board if x["preselected"]],
        key=lambda x:(-x["double_friction"]["profit_factor"],
                      -x["double_friction"]["net_usd_per_oz"],x["name"])
    )
    # Selection made and materialized BEFORE reading validation or holdout.
    selection=eligible[0]["name"] if eligible else None
    return {"dataset":"TRAIN only: no validation or holdout accessed",
            "clean_training_days":len(training),"quarantined":quarantine,
            "preselected_candidate":selection,"board":board,
            "trading_approved":False}


def final_assessment(directory: str|Path, selection: dict) -> dict:
    if selection.get("dataset")!="TRAIN only: no validation or holdout accessed":
        raise ValueError("Training selection state invalid")
    name=selection["preselected_candidate"]
    validation,bad_valid=_load_windows(directory,VALIDATION,8)
    final, bad_holdout = _load_windows(directory,FUTURE_HOLDOUT,2)
    board=[]
    for key in sorted(validation[0]["variants"]):
        stats=sum_stats(validation,key,"friction")
        stress=sum_stats(validation,key,"double_friction")
        board.append({"name":key,"validation":stats,"double_friction":stress})
    selected_valid=next((b for b in board if b["name"]==name),None)
    selected_fut={
        "friction":sum_stats(final,name,"friction"),
        "double_friction":sum_stats(final,name,"double_friction"),
    } if name else None
    reasons=[]
    if name is None:
        reasons.append("No strategy met training selection gate at double trading costs")
    else:
        val=selected_valid["validation"]
        stress=selected_valid["double_friction"]
        f=selected_fut["double_friction"]
        if stress["filled_count"]<MIN_VALIDATION_TRADES:
            reasons.append("Insufficient validation fills")
        if (stress["profit_factor"] is None or stress["profit_factor"]<1.20
            or stress["net_usd_per_oz"]<=0 or stress["day_bootstrap_net_p025"]<=0):
            reasons.append("Validation performance not statistically robust after double costs")
        if f["filled_count"]<MIN_UNSEEN_FUTURE_TRADES:
            reasons.append("Too few genuinely unseen future fills for approval")
        if f["net_usd_per_oz"]<=0:
            reasons.append("Future out-of-sample performance not positive under double costs")
    reasons.extend([
        "No verified broker-specific costs, swap, latency and rejects",
        "No demonstrated same-feed match to original Greenhouse Tracker",
        "Not validated within connected MetaTrader5 with user broker feed",
    ])
    return {
        "train_selected_before_future_data":name,
        "validation_quarantines":bad_valid,"future_quarantines":bad_holdout,
        "validation_days":len(validation),"future_days":len(final),
        "all_variant_validation_board":board,
        "future_preselected_only":selected_fut,
        "approval_blocked":True,
        "approval_reasons":reasons,
        "note":"All variants reported. Positive historical fit is not a trading approval.",
    }


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--dir",required=True)
    p.add_argument("--mode",required=True,choices=("preselect","final"))
    p.add_argument("--selected-json")
    p.add_argument("--out",required=True)
    args=p.parse_args()
    if args.mode=="preselect":
        result=rank_training(args.dir)
    else:
        if not args.selected_json:
            raise ValueError("Selection file required, produced earlier from training")
        selected=json.loads(Path(args.selected_json).read_text(encoding="utf-8"))
        result=final_assessment(args.dir,selected)
    dest=Path(args.out)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if args.mode=="preselect":
        print("PRESELECT TRAIN:",result["preselected_candidate"])
        for row in result["board"]:
            print("TRAIN",row["name"],"signals",row["training"]["signal_count"],
                "fills",row["training"]["filled_count"],
                "net",row["double_friction"]["net_usd_per_oz"])
    else:
        print("FINAL SELECTED",result["train_selected_before_future_data"],
              "APPROVED",not result["approval_blocked"])
        for row in result["all_variant_validation_board"]:
            print("VALID",row["name"],"signals",row["validation"]["signal_count"],
                "fills",row["validation"]["filled_count"],
                "net",row["double_friction"]["net_usd_per_oz"])
        print("UNSEEN",result["future_preselected_only"])
