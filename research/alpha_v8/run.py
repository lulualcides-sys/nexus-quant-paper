"""Predeclared V8 vs V5/V7 comparison on 3 historically uninspected assets.

No parameter grid search, no revisiting ALPHA02 rules, and no live orders.
Original BNB/XRP/ADA/DOGE results diagnosed V7; AVAX/LINK/LTC were reserved
for a new cross-market retrospective challenge. They are correlated crypto,
not future OOS. Three versions share one exact continuous engine and costs.
"""
import argparse,json
from pathlib import Path
from datetime import datetime
from collections import Counter
from research.alpha_v6.data import continuous,MONTHS
from research.alpha_v5.strategy import ConfirmedRegime
from research.alpha_v7.strategy import QualityRetest,BOT
from research.alpha_v8.strategy import StructureRetest
from research.alpha_v6.engine import replay
from research.alpha_v6.run import write_v6_ledger,_monthly_breakdown
from research.alpha.engine import START_USDT,stats
from research.alpha.run import daily_block_ci

MARKETS=("AVAXUSDT","LINKUSDT","LTCUSDT")
SLIPS=(0.,5.,10.)
ARMS=("v5_control","v7_full_filter","v8_structure_only")
MIN_INFERENCE_TRADES=50

def counts(baseline_ledger,v8):
    result=Counter()
    pnl={}
    base=v8.bars[0]["time"]
    for row in baseline_ledger:
        ts=int(datetime.fromisoformat(row["entry_ts_utc"]).timestamp())
        delta=ts-base
        if delta%300:raise AssertionError("entry timestamp not M5 aligned")
        i=delta//300-1
        if i<0 or i>=len(v8.bars):raise AssertionError("entry outside real source")
        reason=v8.filter(i)
        result[reason]+=1
        bucket=pnl.setdefault(reason,dict(trades=0,net_usdt=0.))
        bucket["trades"]+=1
        bucket["net_usdt"]+=float(row["net_usdt"])
    for val in pnl.values():val["net_usdt"]=round(val["net_usdt"],4)
    return dict(veto_counts=dict(result),baseline_ledger_by_veto=pnl,
                warning="Diagnostic grouping of baseline trades, not realized strategy results")

def run(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    results=[];manifest=[];failures={}
    for symbol in MARKETS:
        try:
            bars,meta=continuous(symbol)
            manifest+=meta
        except Exception as exc:
            failures[symbol]=type(exc).__name__+": "+str(exc)
            results.append(dict(market=symbol,status="NOT_VALIDATED",
                                reason=failures[symbol]))
            continue
        try:
            models={"v5_control":ConfirmedRegime(BOT,bars),
                    "v7_full_filter":QualityRetest(BOT,bars),
                    "v8_structure_only":StructureRetest(BOT,bars)}
            scenarios={}
            baseline=None
            for arm,model in models.items():
                scenario={}
                for slip in SLIPS:
                    run_result=replay(model,slippage_bps=slip,protect=False)
                    s=stats(run_result)
                    s.update(filled=run_result["orders_filled"],
                             signals=run_result["signals_seen"],
                             open_at_end=run_result["open_at_end"],
                             equity_with_open_mark_usdt=run_result["marked_total_equity_usdt"],
                             unrealized_net_usdt=run_result["marked_open_net_usdt"],
                             monthly_closed=_monthly_breakdown(run_result["ledger"]),
                             bootstrap_daily_block_95pct_usdt=daily_block_ci(run_result["ledger"]))
                    filename=f"ledgers/{symbol}_{arm}_{int(slip)}bps.csv"
                    write_v6_ledger(out/filename,run_result["ledger"])
                    s["ledger"]=filename
                    scenario[str(int(slip))]=s
                    if arm=="v5_control" and slip==5.:
                        baseline=run_result["ledger"]
                scenarios[arm]=scenario
            diag=counts(baseline,models["v8_structure_only"])
            results.append(dict(market=symbol,status="RESEARCH_ONLY",scenarios=scenarios,
                                diagnostics=diag,
                                statistically_sufficient={arm:scenarios[arm]["5"]["trades"]>=
                                                           MIN_INFERENCE_TRADES for arm in ARMS}))
        except Exception as exc:
            failures[symbol+":engine"]=type(exc).__name__+": "+str(exc)
            results.append(dict(market=symbol,status="NOT_VALIDATED",
                                reason=failures[symbol+":engine"]))
    result=dict(experiment="ALPHA-V8-STRUCTURE-ONLY-FROZEN-PRE-AVAX-LINK-LTC",
         executed_orders=0,approved_strategies=0,
         markets=results,source_manifests=manifest,source_failures=failures,
         full_months=MONTHS,quote_currency="USDT",
         sample_type="new-market retrospective, NOT forward",
         initial_equity_usdt_per_market=START_USDT,
         control="V5 same breakout signal, H1 H4 confirmation and long spot fills",
         variants={"V7":"strong breakout+volume+retest body+avoid chase",
                   "V8":"same strong breakout >0.20 ATR and strong retest close >=60% range only"},
         strategy=BOT,
         costs_bps_per_side={"taker":10,"half_spread":1,"slippage":list(SLIPS)},
         risk="0.75% modelled all-in stop risk, no-gap only",
         caveats=["Market correlations, previous model selection on inspected data",
           "All markets in this study are retrospective (no live forward out-of-sample)",
           "Real bid/ask orderbook and lot/step exchangeInfo unvalidated",
           "Never pretend filtering rejected baseline losing trades equals V8 net P&L",
           "No approval even if 1 asset profits; require forward paper and robust inference"])
    (out/"results.json").write_text(json.dumps(result,ensure_ascii=False,
                             indent=2,allow_nan=False)+"\n")
    (out/"source_manifest.json").write_text(json.dumps(dict(
         sources=manifest,failures=failures),ensure_ascii=False,indent=2)+"\n")
    lines=["# ALPHA V8 — independent cross-market study of M5 retest quality",
           "", "Original ALPHA02 + H1/H4 and continuous 22-month execution unchanged.",
           "No future data, no automated live trading, no profitability claim.",
           "", "| Market | Control | Trades | Net USDT 5bps | PF | Net USDT 10bps |",
           "|---|---|---:|---:|---:|---:|"]
    for market in results:
        if market["status"]!="RESEARCH_ONLY":
            lines.append(f"| {market['market']} | source invalid | N/V | N/V | N/V | N/V |")
            continue
        for arm in ARMS:
            p=market["scenarios"][arm]["5"]
            s=market["scenarios"][arm]["10"]
            def show(x):return "N/V" if x is None else str(x)
            lines.append("| %s | %s | %s | %s | %s | %s |"%
                         (market["market"],arm,p["trades"],show(p["net_usdt"]),
                          show(p["profit_factor"]),show(s["net_usdt"])))
    lines+=["","## Missing data / model errors"]
    lines.extend([f"- {k}: {v}" for k,v in failures.items()] or ["- None"])
    lines+=["","Full source SHA256s, per-exit-month ledgers and causal gate veto diagnostics",
             "in JSON. All three arms use identical exit engine and costs."]
    (out/"results.md").write_text("\n".join(lines)+"\n")
    print(f"V8 verified_source_files={len(manifest)}/{len(MARKETS)*len(MONTHS)}"
          f" valid_markets={sum(x['status']=='RESEARCH_ONLY' for x in results)}"
          f" errors={failures}")
    if len(manifest)!=len(MARKETS)*len(MONTHS) or failures:
        raise SystemExit("INCOMPLETE: no comparison can be validated")
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--out",default="artifacts/alpha-v8")
    a=p.parse_args()
    run(a.out)
