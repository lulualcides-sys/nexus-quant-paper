"""Paired V4/V5 SOL SPOT historical experiment with a sealed retrospective 2025 check.

V5 code frozen in Git before the 2025 data was fetched. Same fills, costs,
initial balance and original bots as V4. No strategy selection on 2025 outcomes.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from research.alpha_v4.data import month,V5_BLIND_SOL_MONTHS,MONTHS,TRANSFER_MONTHS
from research.alpha_v4.strategy import MultiTimeframe
from research.alpha_v5.strategy import ConfirmedRegime
from research.alpha_v4.engine import backtest
from research.alpha.engine import stats, START_USDT
from research.alpha.run import BOTS, write_ledger,daily_block_ci

MARKET="SOLUSDT"
PRIOR_MONTHS=tuple(TRANSFER_MONTHS)+tuple(MONTHS)
SLIP=(0.,5.,10.)
CANDIDATE_STATUS="RESEARCH_ONLY_UNAPPROVED"

def _monthly_summary(cases):
    active=[x for x in cases if x and x["trades"]>0 and x["net_usdt"] is not None]
    trades=sum(x["trades"] for x in cases if x is not None)
    if not active:
        return dict(net_usdt=None,trades=trades,positive_months=0,negative_months=0,
                    winning_fraction=None,total_costs_usdt=None,
                    profit_factor=None)
    gains=0.;losses=0.
    return dict(net_usdt=round(sum(x["net_usdt"] for x in active),4),
          trades=trades,
          positive_months=sum(x["net_usdt"]>0 for x in active),
          negative_months=sum(x["net_usdt"]<0 for x in active),
          winning_fraction=round(sum(x["net_usdt"]>0 for x in active)/len(active),3),
          total_costs_usdt=round(sum(x["total_costs_usdt"] for x in active),4),
          # monthly PF cannot be added; leave null instead of fake combined PF
          profit_factor=None)

def run(out):
    out=Path(out)
    out.mkdir(parents=True,exist_ok=True)
    records=[];sources=[];errors={}
    for period in (*PRIOR_MONTHS,*V5_BLIND_SOL_MONTHS):
        try:
            bars,manifest=month(MARKET,period)
            sources.append(manifest)
        except Exception as exc:
            errors[period]=type(exc).__name__+": "+str(exc)
            for name in BOTS:
                records.append(dict(month=period,robot=name,status="NOT_VALIDATED",
                                    reason=errors[period]))
            continue
        for name in BOTS:
            try:
                models={"original_v4":MultiTimeframe(name,bars),
                        "h4_guard_v5":ConfirmedRegime(name,bars)}
                outcomes={}
                for tag,model in models.items():
                    scenarios={}
                    for slip in SLIP:
                        result=backtest(model,slip)
                        metrics=stats(result)
                        # all-in trade P&L includes taker fees, half-spread, slippage
                        metrics.update(fills=result["orders_filled"],
                          signals=result["signals_seen"],
                          open_at_end=result["open_end"],
                          marked_open_net_usdt=result["marked_open_net_usdt"],
                          daily_block_ci_95_usdt=daily_block_ci(result["ledger"]))
                        if abs(sum(x["net_usdt"] for x in result["ledger"])-
                               (result["equity"]-START_USDT))>0.05:
                            raise AssertionError("ledger and equity differ")
                        csv=f"ledgers/{MARKET}_{period}_{name}_{tag}_{int(slip)}bps.csv"
                        write_ledger(out/csv,result["ledger"])
                        metrics["ledger"]=csv
                        scenarios[str(int(slip))]=metrics
                    outcomes[tag]=scenarios
                records.append(dict(month=period,robot=name,
                         evidence="previously_exposed_development" if period in PRIOR_MONTHS else
                                  "new_uninspected_backward_2025_SOL_not_forward",
                         status=CANDIDATE_STATUS,variants=outcomes))
            except Exception as exc:
                errors[period+":"+name]=type(exc).__name__+": "+str(exc)
                records.append(dict(month=period,robot=name,status="NOT_VALIDATED",
                                    reason=errors[period+":"+name]))
    comparisons=[]
    for bot in BOTS:
        row=dict(robot=bot,diagnostic_2026={},backward_2025={},
                 status="NOT_APPROVED")
        for periods,key in ((PRIOR_MONTHS,"diagnostic_2026"),
                            (V5_BLIND_SOL_MONTHS,"backward_2025")):
            cases=[x for x in records if x["robot"]==bot and x["month"] in periods
                   and x.get("variants")]
            if len(cases)!=len(periods):
                row[key]=dict(status="NOT_VALIDATED",months_verified=len(cases),
                              months_expected=len(periods))
                continue
            for version in ("original_v4","h4_guard_v5"):
                bycost={}
                for slip in SLIP:
                    metrics=_monthly_summary([
                        x["variants"][version][str(int(slip))] for x in cases])
                    bycost[str(int(slip))]=metrics
                row[key][version]=bycost
        comparisons.append(row)
    report=dict(title="V5 causally confirmed H4 entry; unchanged V4 stop/target/cost",
          report_version="2026-11-08-frozen-before-2025-source-review",
          venue="Binance SPOT",symbol=MARKET,quote_currency="USDT",
          sample_type="retrospective_not_forward",
          periods=dict(development=list(PRIOR_MONTHS),
                       uninspected_backward=list(V5_BLIND_SOL_MONTHS)),
          capital_usdt_per_bot=START_USDT,
          fee_bps_per_side=10,assumed_halfspread_bps_per_side=1,
          slippage_bps_per_side=list(SLIP),
          source_manifests=sources,source_failures=errors,
          observations=records,comparisons=comparisons,approved=0,
          caveats=["Backwards 2025 data are not forward OOS",
                   "New regime filter based on inspected losses from V4 2026",
                   "Same-market, multiple ALPHA correlated candidates",
                   "No orderbook execution, no exchangeInfo lot-size history",
                   "A positive historical backtest is insufficient for promotion",
                   "Unclosed month-end positions are unbooked but marked separately",
                   "Zero trades means statistically inconclusive, never zero return"])
    (out/"results.json").write_text(json.dumps(report,ensure_ascii=False,
                                  indent=2,allow_nan=False)+"\n",encoding="utf8")
    (out/"source_manifest.json").write_text(json.dumps(
        dict(sources=sources,source_failures=errors),indent=2,
        ensure_ascii=False)+"\n",encoding="utf8")
    lines=["# ALPHA V5 — rigorously paired H4 entry gate","",
           "**Neither positive backtest nor green CI certifies profitability.**",
           "SO LUSDT SPOT (SOLUSDT), 5000 USDT per robot; same 10 entries,",
           "same V4 exits and modeled fees, no trade forwarding.",
           "", "| Bot | Period | V4 trades | V4 net 5bps | V5 trades | V5 net 5bps | V5 net 10bps |",
           "|---|---|---:|---:|---:|---:|---:|"]
    def num(x):return "N/V" if x is None else str(x)
    for row in comparisons:
        for label,key in (("Jan-Oct 2026 already seen","diagnostic_2026"),
                          ("Jan-Dec 2025 new BACKWARD","backward_2025")):
            a=row[key].get("original_v4",{}).get("5",{})
            b=row[key].get("h4_guard_v5",{}).get("5",{})
            c=row[key].get("h4_guard_v5",{}).get("10",{})
            lines.append("| %s | %s | %s | %s | %s | %s | %s |"%
                (row["robot"],label,num(a.get("trades")),num(a.get("net_usdt")),
                 num(b.get("trades")),num(b.get("net_usdt")),
                 num(c.get("net_usdt"))))
    lines.extend(["","## Data or model failures"])
    lines.extend([f"- {k}: {v}" for k,v in errors.items()] or ["- None"])
    lines.extend(["","V5 modifies entries ONLY. July–Oct 2026 previously seen;",
      "Jan–Jun 2026 previously seen; 2025 samples new, but earlier than",
      "signal design, therefore NOT forward validation.",
      "Full per-month risk, P&L, trade outcomes and hashes in results.json."])
    (out/"results.md").write_text("\n".join(lines)+"\n",encoding="utf8")
    print(f"V5 COMPLETE combos={sum('variants' in x for x in records)}"
          f"/{len(BOTS)*(len(PRIOR_MONTHS)+len(V5_BLIND_SOL_MONTHS))}"
          f" verified_months={len(sources)} errors={len(errors)}")
    if len(sources)!=len(PRIOR_MONTHS)+len(V5_BLIND_SOL_MONTHS):
        raise RuntimeError("incomplete historical dataset: no final validation")
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--out",default="artifacts/alpha-v5")
    options=p.parse_args()
    run(options.out)
