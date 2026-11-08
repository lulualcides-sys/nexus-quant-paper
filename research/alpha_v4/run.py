"""ALPHA V4: comparative, reproducible H1-filtered M1/M5 replay.

No secrets, state or broker access. No in-sample parameter optimization.
BTC/ETH months were previously inspected in V1-V3/PR35; SOLUSDT is a new
cross-market retrospective check, not prospective evidence.
"""
from __future__ import annotations
from collections import defaultdict
from pathlib import Path
import argparse, json
from research.alpha.run import BOTS, write_ledger, daily_block_ci
from research.alpha.engine import stats,START_USDT
from research.alpha_v4.data import SYMBOLS, MONTHS, month
from research.alpha_v4.strategy import MultiTimeframe
from research.alpha_v4.engine import backtest

SLIPPAGE=(0.,5.,10.)
MAIN_SCENARIO="5"

def run(out):
    root=Path(out);root.mkdir(parents=True,exist_ok=True)
    records=[];manifests=[];errors={}
    for symbol in SYMBOLS:
        for period in MONTHS:
            try:
                bars,meta=month(symbol,period)
                manifests.append(meta)
            except Exception as exc:
                errors[symbol+":"+period]=type(exc).__name__+": "+str(exc)
                for name in BOTS:
                    records.append(dict(robot=name,market=symbol,month=period,
                                        status="NOT_VALIDATED",
                                        reason=errors[symbol+":"+period]))
                continue
            for name in BOTS:
                try:
                    model=MultiTimeframe(name,bars)
                    scenarios={}
                    for slip in SLIPPAGE:
                        report=backtest(model,slip)
                        outcome=stats(report)
                        outcome.update(orders=report["orders_filled"],
                                       signals=report["signals_seen"],
                                       open_at_month_end=report["open_end"],
                                       marked_open_net_usdt=report["marked_open_net_usdt"],
                                       bootstrap_95pct_usdt=daily_block_ci(report["ledger"]))
                        fname=f"ledgers/{symbol}_{period}_{name}_{int(slip)}bps.csv"
                        write_ledger(root/fname,report["ledger"])
                        outcome["ledger"]=fname
                        scenarios[str(int(slip))]=outcome
                    records.append(dict(robot=name,market=symbol,month=period,
                                        timeframe=f"M{model.minutes}",
                                        h1_confirmation="closed hourly only",
                                        testing="prior_exposed" if symbol!="SOLUSDT" else "new_cross_market_retrospective",
                                        scenarios=scenarios,status="RESEARCH_ONLY"))
                except Exception as exc:
                    errors[f"{symbol}:{period}:{name}"]=type(exc).__name__+": "+str(exc)
                    records.append(dict(robot=name,market=symbol,month=period,
                                        status="NOT_VALIDATED",reason=str(exc)))
    ranking=[]
    for name in BOTS:
        for symbol in SYMBOLS:
            cases=[row for row in records if row["robot"]==name
                   and row["market"]==symbol and "scenarios" in row]
            by_month={x["month"]:x["scenarios"][MAIN_SCENARIO] for x in cases}
            if len(by_month)!=len(MONTHS):
                ranking.append(dict(robot=name,market=symbol,status="NOT_VALIDATED",
                                    months_valid=len(by_month),net_usdt=None))
                continue
            net=sum(x["net_usdt"] or 0. for x in by_month.values())
            trades=sum(x["trades"] for x in by_month.values())
            monthly=[{**dict(month=m),**by_month[m]} for m in MONTHS]
            positive=sum(x["net_usdt"] is not None and x["net_usdt"]>0
                         for x in by_month.values())
            stress={str(int(s)):round(sum(c["scenarios"][str(int(s))]["net_usdt"] or 0.
                         for c in cases),4) for s in SLIPPAGE}
            # Technical approval strictly forbidden without genuine forward OOS.
            ranking.append(dict(robot=name,market=symbol,
                                months_valid=len(by_month),positive_months=positive,
                                closed_trades=trades,net_usdt=round(net,4),
                                stress_net_usdt=stress,monthly=monthly,
                                status=("REJECTED" if trades>=100 and net<=0 else
                                        "INCONCLUSIVE_REQUIRES_FORWARD")))
    ranking.sort(key=lambda r:(r["net_usdt"] is None,-(r["net_usdt"] or 0)))
    summary=dict(protocol="ALPHA-V4-H1-M1-M5-FROZEN-2026-11-08",
       research_only=True,real_orders=0,approved=0,
       no_claim_of_profit=True,results_only_on_valid_verified_candles=True,
       base_repo="lulualcides-sys/nexus-quant-paper",
       quote_currency="USDT; no BRL conversion",reference_capital_usdt_per_pair=START_USDT,
       cost_bps_per_side=dict(taker_fee=10,half_spread=1,slippage=list(SLIPPAGE)),
       train_holdout_note=("BTC/ETH July-Oct previously exposed to analysis; "
          "SOL July-Oct new cross-market retrospective check, NOT prospective paper."),
       sources=manifests,source_failures=errors,records=records,ranking=ranking,
       limits=["price precision is not archived symbol tick/lot-size proof",
               "no broker order-book, bid/ask quotes, queue positions or real fills",
               "stops can gap below planned risk; OHLC intrabar stop-first convention",
               "open end-of-month positions excluded from realized P&L",
               "per-model per-market results assume independent 5000 USDT books",
               "20+ competing hypotheses and prior inspected outcomes prevent statistical approval"])
    (root/"results.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False,
                                           allow_nan=False)+"\n",encoding="utf8")
    (root/"source_manifest.json").write_text(json.dumps(
          dict(sources=manifests,failures=errors),indent=2,ensure_ascii=False)+"\n")
    lines=["# ALPHA V4 — H1 closed-bar trend confirmation + M1/M5 entry",
           "","**NOT LIVE.** Spot long-only. Fees 10bps, half-spread 1bp,",
           "slippage 0/5/10bps **per side**, not the WIN minimum tick.",
           "All model families previously exposed on BTC/ETH; SOL is new market only.",
           "No version approved, regardless of positive retrospective results.",
           "", "| Rank | Model | Market | Months valid | Trades | Positive months | Net 5bps (USDT) | Net 10bps (USDT) | Status |",
           "|---:|---|---|---:|---:|---:|---:|---:|---|"]
    for i,r in enumerate(ranking,1):
        stress=r.get("stress_net_usdt") or {}
        def val(v):return "N/V" if v is None else str(v)
        lines.append("| %d | %s | %s | %s | %s | %s | %s | %s | %s |"%
            (i,r["robot"],r["market"],r.get("months_valid","N/V"),
             r.get("closed_trades","N/V"),r.get("positive_months","N/V"),
             val(r["net_usdt"]),val(stress.get("10")),r["status"]))
    lines.extend(["","## Source or strategy failures"])
    lines.extend(["- "+k+": "+v for k,v in errors.items()] or ["- None"])
    lines.extend(["","Per-month and per-side cost results, win rate, profit factor,",
                  "drawdowns, block confidence bounds, SHA256 and all closed-trade ledgers",
                  "are in results.json and the attached CSV files."])
    (root/"results.md").write_text("\n".join(lines)+"\n",encoding="utf8")
    print(f"V4 completed dataset/robot combinations={sum('scenarios' in x for x in records)} "
          f"source_failures={len(errors)} approvals=0")
    return summary

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",default="artifacts/alpha-v4")
    args=parser.parse_args()
    result=run(args.out)
    if not any(x["market"]=="SOLUSDT" and "scenarios" in x
               for x in result["records"]):
        raise SystemExit("new cross-market dataset unavailable; no accepted OOS result")
