"""Frozen V4 transfer check on SOL 2026 January-June, never previously inspected here.

This is a chronological BACKWARD stress test of already selected July-Oct
candidates, NOT forward paper validation and cannot support automatic approval.
"""
from pathlib import Path
import argparse,json
from research.alpha.run import BOTS,write_ledger,daily_block_ci
from research.alpha.engine import START_USDT,stats
from research.alpha_v4.data import month,TRANSFER_MONTHS
from research.alpha_v4.strategy import MultiTimeframe
from research.alpha_v4.engine import backtest

SYMBOL="SOLUSDT"
SLIPS=(0.,5.,10.)

def run(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    sources=[];failures={};records=[]
    for month_text in TRANSFER_MONTHS:
        try:
            raw,meta=month(SYMBOL,month_text)
            sources.append(meta)
        except Exception as exc:
            failures[month_text]=type(exc).__name__+": "+str(exc)
            for bot in BOTS:
                records.append(dict(robot=bot,period=month_text,status="NOT_VALIDATED",
                                    reason=failures[month_text]))
            continue
        for bot in BOTS:
            try:
                model=MultiTimeframe(bot,raw)
                scenarios={}
                for slip in SLIPS:
                    r=backtest(model,slip)
                    s=stats(r)
                    s.update(open_at_month_end=r["open_end"],
                             marked_open_net_usdt=r["marked_open_net_usdt"],
                             signals=r["signals_seen"],filled_orders=r["orders_filled"],
                             bootstrap_95pct_usdt=daily_block_ci(r["ledger"]))
                    path=f"ledgers/SOLUSDT_{month_text}_{bot}_{int(slip)}bps.csv"
                    write_ledger(out/path,r["ledger"])
                    s["ledger"]=path
                    scenarios[str(int(slip))]=s
                records.append(dict(robot=bot,period=month_text,status="RESEARCH_ONLY",
                                    scenarios=scenarios))
            except Exception as exc:
                failures[f"{month_text}:{bot}"]=type(exc).__name__+": "+str(exc)
                records.append(dict(robot=bot,period=month_text,status="NOT_VALIDATED",
                                    reason=str(exc)))
    ranking=[]
    for bot in BOTS:
        cases=[r for r in records if r["robot"]==bot and "scenarios" in r]
        if len(cases)!=len(TRANSFER_MONTHS):
            ranking.append(dict(robot=bot,months_valid=len(cases),status="NOT_VALIDATED",
                                net_usdt=None))
            continue
        period_metrics=[c["scenarios"]["5"] for c in cases]
        trades=sum(s["trades"] for s in period_metrics)
        net=round(sum(s["net_usdt"] or 0. for s in period_metrics),4) if trades else None
        winners=sum(s["net_usdt"] is not None and s["net_usdt"]>0
                    for s in period_metrics)
        sensitivity={str(int(s)):round(sum(c["scenarios"][str(int(s))]["net_usdt"] or 0.
                       for c in cases),4) for s in SLIPS}
        ranking.append(dict(robot=bot,trades=trades,net_usdt=net,
                            months_valid=len(cases),positive_months=winners,
                            sensitivity_net_usdt=sensitivity,
                            status=("REJECTED_BACKWARD" if trades>=100 and net is not None and net<=0
                                    else "INCONCLUSIVE_NO_FORWARD_EVIDENCE")))
    ranking.sort(key=lambda x:(x.get("net_usdt") is None,-(x.get("net_usdt") or 0)))
    result=dict(study="ALPHA-V4-FROZEN-TRANSFER-BACKWARD-SOL-JAN-JUN-2026",
                research_only=True,approved=0,previously_selected_from="SOL July-Oct 2026",
                independent_future_test=False,market="Binance SOLUSDT SPOT",
                quote_currency="USDT, NOT BRL",starting_balance_per_robot=START_USDT,
                costs_bps_per_side=dict(taker_fee=10,half_spread=1,slippage=list(SLIPS)),
                source_manifest=sources,source_failures=failures,records=records,
                ranking=ranking,limits=["SOL transfer predates the selection months",
                "Full source checksum is necessary but not evidence of fillability",
                "No price/lot exchangeInfo archived to prove real executable sizing",
                "Intrabar stop-first and hourly lookahead boundaries still OHLC approximations",
                "10 family comparisons and market correlation: no statistical proof",
                "Historical selection of best SOL candidates cannot be reused as untouched holdout"])
    (out/"results.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,
                                            allow_nan=False)+"\n")
    (out/"source_manifest.json").write_text(json.dumps(dict(sources=sources,
                   failures=failures),ensure_ascii=False,indent=2)+"\n")
    lines=["# ALPHA V4 — backward transfer, not approved",
           "", "Unchanged V4 signals and costs on SOLUSDT Jan-Jun 2026,",
           "all files must pass Binance official SHA256. Backward retrospective: NOT forward.",
           "", "| Bot | Closed | Positive months | Net USDT 5bps | Net USDT 10bps | Status |",
           "|---|---:|---:|---:|---:|---|"]
    for r in ranking:
        sensitive=r.get("sensitivity_net_usdt",{})
        net=r.get("net_usdt")
        lines.append("| %s | %s | %s | %s | %s | %s |"%
             (r["robot"],r.get("trades","N/V"),r.get("positive_months","N/V"),
              net if net is not None else "N/V",sensitive.get("10","N/V"),r["status"]))
    lines.extend(["","## Source failures"])
    lines.extend([f"- {k}: {v}" for k,v in failures.items()] or ["- None"])
    lines.extend(["","JSON has month-by-month PF, drawdown, costs, win rate, sensitivity and ledger paths.",
                  "No trading, no win rate for zero operations, no BRL conversion."])
    (out/"results.md").write_text("\n".join(lines)+"\n")
    print(f"TRANSFER_V4 validated records={sum('scenarios' in x for x in records)}"
          f"/{len(TRANSFER_MONTHS)*len(BOTS)}; errors={len(failures)}")
    return result

if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--out",default="artifacts/alpha-v4-transfer")
    opts=a.parse_args()
    result=run(opts.out)
    if any(r["period_utc"] not in TRANSFER_MONTHS for r in result["source_manifest"]):
        raise SystemExit("unexpected month")
    if len(result["source_manifest"])!=len(TRANSFER_MONTHS):
        raise SystemExit("transfer source incomplete: NO financial validation")
