"""Paired continuous ALPHA02 quality study on four SPOT markets for 22 months.

This file fixes V7 thresholds before first ADA/DOGE replay. No tune/search.
The BNB/XRP retrospective analysis motivates the quality hypothesis but
must NOT be represented as a new independent holdout. ADA/DOGE are other
historical correlated markets, not prospective time OOS.
"""
import argparse,csv,json
from pathlib import Path
from collections import Counter
from datetime import datetime
from research.alpha_v6.data import continuous,MONTHS
from research.alpha_v5.strategy import ConfirmedRegime
from research.alpha_v7.strategy import QualityRetest,BOT
from research.alpha_v6.engine import replay
from research.alpha.engine import START_USDT,stats
from research.alpha.run import daily_block_ci
from research.alpha_v6.run import write_v6_ledger,_monthly_breakdown

MARKETS=("BNBUSDT","XRPUSDT","ADAUSDT","DOGEUSDT")
NEW_CHECK_MARKETS=("ADAUSDT","DOGEUSDT")
SLIPPAGE=(0.,5.,10.)
ARMS=("v5_continuous","v7_entry_quality")
MIN_AUDIT_TRADES_PER_MARKET=35

def _gate_diagnostics(original_ledger,quality):
    reason_counts=Counter()
    pnl_by_reason={}
    for trade in original_ledger:
        when=int(datetime.fromisoformat(trade["entry_ts_utc"]).timestamp())
        start=quality.bars[0]["time"]
        offset=when-start
        if offset%300:raise ValueError("M5 trade not aligned with source")
        idx=offset//300-1
        if idx<0 or idx>=len(quality.bars):
            raise ValueError("entry out of source")
        reason=quality.filter(idx)
        reason_counts[reason]+=1
        bucket=pnl_by_reason.setdefault(reason,dict(count=0,net_usdt=0.0))
        bucket["count"]+=1
        bucket["net_usdt"]+=float(trade["net_usdt"])
    for result in pnl_by_reason.values():
        result["net_usdt"]=round(result["net_usdt"],4)
    return dict(reasons=dict(reason_counts),baseline_counterfactual_by_reason=pnl_by_reason,
                caveat="V5 baseline veto diagnostics only; NOT V7 realized counterfactual")

def run(out):
    output=Path(out);output.mkdir(parents=True,exist_ok=True)
    results=[];provenance=[];failures={}
    for market in MARKETS:
        try:
            raw,manifests=continuous(market)
            provenance.extend(manifests)
        except Exception as exc:
            failures[market]=type(exc).__name__+": "+str(exc)
            results.append(dict(symbol=market,status="NOT_VALIDATED",reason=failures[market]))
            continue
        try:
            baseline=ConfirmedRegime(BOT,raw)
            candidate=QualityRetest(BOT,raw)
            variants={}
            saved_runs={}
            for label,model in (("v5_continuous",baseline),("v7_entry_quality",candidate)):
                scenarios={}
                for slip in SLIPPAGE:
                    r=replay(model,slippage_bps=slip,protect=False)
                    metrics=stats(r)
                    metrics.update(orders=r["orders_filled"],signals=r["signals_seen"],
                      marked_equity_usdt=r["marked_total_equity_usdt"],
                      marked_open_net_usdt=r["marked_open_net_usdt"],
                      open_at_end=r["open_at_end"],
                      monthly_closed=_monthly_breakdown(r["ledger"]),
                      bootstrap_daily_block_ci_95_usdt=daily_block_ci(r["ledger"]))
                    csvfile=f"ledgers/{market}_{label}_{int(slip)}bps.csv"
                    write_v6_ledger(output/csvfile,r["ledger"])
                    metrics["ledger"]=csvfile
                    scenarios[str(int(slip))]=metrics
                    saved_runs[(label,int(slip))]=r
                variants[label]=scenarios
            diag=_gate_diagnostics(saved_runs[("v5_continuous",5)]["ledger"],candidate)
            prior=variants["v5_continuous"]["5"]
            curr=variants["v7_entry_quality"]["5"]
            results.append(dict(symbol=market,status="RESEARCH_ONLY",
              evidence_type=("new_correlated_market_retrospective" if
                  market in NEW_CHECK_MARKETS else "priorly_inspected_development_market"),
              expected_causal_veto=diag,variants=variants,
              primary_pnl_change_usdt=(round(curr["net_usdt"]-prior["net_usdt"],4)
                  if curr["net_usdt"] is not None and prior["net_usdt"] is not None else None),
              primary_trades_sufficient=(curr["trades"]>=MIN_AUDIT_TRADES_PER_MARKET),
              independent_forward_approval=False))
        except Exception as exc:
            failures[market+":model"]=type(exc).__name__+": "+str(exc)
            results.append(dict(symbol=market,status="NOT_VALIDATED",
                                reason=failures[market+":model"]))
    report=dict(protocol="ALPHA-V7-CAUSAL-BREAKOUT-QUALITY-FROZEN-PRE-ADA-DOGE",
      trading_orders=0,approved=0,source="Binance SPOT monthly 1m signed SHA256",
      sample_type="retrospective assets, NOT forward",
      exposure="independent 5000 USDT virtual book per market, 22 months continuous",
      bot=BOT,currency="USDT",initial_book_usdt=START_USDT,
      execution=dict(fee_bps_per_side=10,half_spread_bps_per_side=1,
                     slippage_bps_per_side=list(SLIPPAGE),
                     initial_stop_h1_atr=1.5,target_h1_atr=4,
                     max_hold_hours=72,cooldown_hours=24,
                     max_initial_stop_loss_fraction_theoretical=.0075),
      sources=provenance,source_failures=failures,markets=results,
      limitations=["Earlier BNB/XRP results motivated filter: not an untouched holdout",
       "ADA/DOGE are new symbols but same prior dates and correlated with crypto",
       "No exact historical Binance exchangeInfo filters, actual spreads or fills",
       "Stops may gap below planned 0.75% risk",
       "Empty results NOT treated as profit or zero return",
       "Selected ALPHA02 after other 9 tested: multiple comparisons",
       "Do not promote until genuine forward paper and independent testing"])
    (output/"results.json").write_text(json.dumps(report,ensure_ascii=False,
                                    indent=2,allow_nan=False)+"\n",encoding="utf8")
    (output/"source_manifest.json").write_text(json.dumps(dict(
        sources=provenance,failures=failures),indent=2,ensure_ascii=False)+"\n")
    lines=["# ALPHA V7 — BREAKOUT QUALITY, CONTROLLED ENTRY FILTER",
           "", "Comparisons pair **same exit engine, costs, bankroll, continuous candles**.",
           "V5 original H4 entry vs V7 additional closed-M5 breakout quality.",
           "NO live trades, NO guarantee, NO forward validation.",
           "", "| Market | Arm | Trades | Net 5bps | PF 5bps | DD 5bps | Net 10bps |",
           "|---|---|---:|---:|---:|---:|---:|"]
    for market in results:
        if market["status"]!="RESEARCH_ONLY":
            lines.append("| %s | N/V | N/V | N/V | N/V | N/V | N/V |"%market["symbol"])
            continue
        for arm in ARMS:
            p=market["variants"][arm]["5"]
            s=market["variants"][arm]["10"]
            def val(x):return "NOT VALIDATED" if x is None else str(x)
            lines.append("| %s | %s | %s | %s | %s | %s | %s |"%
                (market["symbol"],arm,p["trades"],val(p["net_usdt"]),
                 val(p["profit_factor"]),val(p["max_drawdown_pct"]),
                 val(s["net_usdt"])))
    lines+=["","## Missing data/models"]
    lines.extend([f"- {k}: {v}" for k,v in failures.items()] or ["- None"])
    lines+=["","Per-exit-month details, trade veto diagnostics and official hashes",
            "in results.json and source_manifest.json. All trades in CSV."]
    (output/"results.md").write_text("\n".join(lines)+"\n")
    print(f"V7 source={len(provenance)}/{len(MARKETS)*len(MONTHS)}"
          f" verified_markets={sum(x['status']=='RESEARCH_ONLY' for x in results)}"
          f"/{len(MARKETS)} failures={failures}")
    if len(provenance)!=len(MARKETS)*len(MONTHS) or failures:
        raise SystemExit("study incomplete; cannot approve")
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--out",default="artifacts/alpha-v7")
    options=p.parse_args()
    run(options.out)
