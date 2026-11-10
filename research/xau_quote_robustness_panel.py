"""Summarize a fixed XAUUSD tick-replay panel without selecting winning settings.

All dates and cost assumptions are selected in advance in the workflow.
This is NOT a walk-forward optimization, a brokerage return, or a claim
of statistically sufficient out-of-sample trades.
"""
from __future__ import annotations
import json
from pathlib import Path


TRAIN_END = "20261030"


def combined(panels: list[dict]) -> dict:
    if not panels:
        raise ValueError("Need per-session audited reports")
    closed = []
    planned = filled = expired = 0
    for report in panels:
        e = report["execution"]
        if report.get("broker_lot_or_commission_verified") is not False:
            raise ValueError("Broker source mistakenly marked verified")
        if report.get("independently_validated_with_original_greenhouse") is not False:
            raise ValueError("False original Tracker equivalence")
        if not report.get("spread_accounted_through_actual_bid_ask"):
            raise ValueError("Missing actual spread accounting")
        closed.extend(e["ledger"])
        planned += e["planned_signals"]
        filled += e["filled"]
        expired += e["unfilled_expired"]
    if filled != len(closed):
        raise ValueError("Ledger/fill mismatch")
    gross_profit = sum(t["net_usd_per_oz"] for t in closed if t["net_usd_per_oz"] > 0)
    gross_loss = -sum(t["net_usd_per_oz"] for t in closed if t["net_usd_per_oz"] < 0)
    net = sum(t["net_usd_per_oz"] for t in closed)
    equity = peak = max_dd = 0.
    for t in closed:
        equity += t["net_usd_per_oz"]
        peak = max(peak, equity)
        max_dd = max(max_dd, peak-equity)
    return {
        "signals": planned, "filled":filled,"expired":expired,
        "wins":sum(t["net_usd_per_oz"]>0 for t in closed),
        "losses":sum(t["net_usd_per_oz"]<0 for t in closed),
        "net_usd_per_oz":round(net,6),
        "expectancy_usd_per_oz":round(net/filled,6) if filled else None,
        "profit_factor":round(gross_profit/gross_loss,6) if gross_loss>0 else None,
        "max_closed_drawdown_usd_per_oz":round(max_dd,6),
        "sufficient_sample_for_promoting_to_broker":False,
    }


def aggregate(directory: str|Path, dates: list[str]) -> dict:
    if len(dates) != len(set(dates)) or not dates or dates != sorted(dates):
        raise ValueError("Dates must be sorted and unique")
    folder=Path(directory)
    result = {"source":"fixed Dukascopy bid/ask replay",
              "date_window":dates,
              "train_end_inclusive":TRAIN_END,
              "note":"Research only. Same unoptimized parameters, no broker execution",
              "variants":{},"approved_for_trading":False}
    for tf in ("M1","M5"):
        result["variants"][tf]={}
        for scenario in ("base","friction"):
            data=[]
            train=[]; evaluation=[]
            for day in dates:
                f=folder/f"xau_{day}_{tf}_{scenario}.json"
                r=json.loads(f.read_text(encoding="utf-8"))
                if r["source"]["first_candle_utc"][:10].replace("-","") != day:
                    raise ValueError("Report date/source mismatch")
                if r["source"]["source_rows"] < 1000:
                    raise ValueError("No adequate historical quote coverage")
                data.append(r)
                (train if day<=TRAIN_END else evaluation).append(r)
            result["variants"][tf][scenario]={
                "overall":combined(data),
                "prior_block_through_oct30":combined(train) if train else None,
                "later_block_november":combined(evaluation) if evaluation else None,
            }
    return result


if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--reports",required=True)
    ap.add_argument("--dates",required=True,help="Comma-separated YYYYMMDD")
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    dates=args.dates.split(",")
    result=aggregate(args.reports,dates)
    Path(args.output).write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    for tf,v in result["variants"].items():
        for name,stats in v.items():
            print(tf,name,stats["overall"])
            print(" later block:",stats["later_block_november"])
