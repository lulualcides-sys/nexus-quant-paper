"""ALPHA V2 immutable paired experiment. Original baseline and filtered variant.

Run: python -m research.alpha_v2.run --out artifacts/alpha-v2

Closed bars only; no trading, state mutations, Telegram or broker connections.
"""
from __future__ import annotations
import argparse,csv,json
from datetime import datetime,timezone
from collections import Counter
from pathlib import Path
from importlib import import_module
from research.alpha.data import SYMBOLS,load_symbol,download_month,aggregate_5m
from research.alpha.engine import (
    History,build,backtest,check_candles,stats,START_USDT)
from research.alpha.run import BOTS,daily_block_ci,write_ledger
from research.alpha_v2.daily import load_week
from research.alpha_v2.filters import Filtered,ROUNDTRIP_BPS,COST_MULTIPLIER

# Frozen on 08 November 2026 before accessing July or November P&L.
PERIODS=(("2026-07","backward_unseen"),("2026-08","train_seen"),
         ("2026-09","validation_seen"),("2026-10","previously_seen"),
         ("2026-11","november_01_07_unseen"))
SLIPPAGE=(0.,5.,10.)
MAIN_SLIP=5.
MIN_CANDIDATE_TRADES=100

def assemble(symbol):
    """Original August-October data, additional July backward stress and Nov daily."""
    rows,manifest=load_symbol(symbol)
    missing={}
    try:
        july,meta=download_month(symbol,"2026-07")
        rows=july+rows
        manifest.insert(0,meta)
    except Exception as exc:
        missing["2026-07"]=type(exc).__name__+": "+str(exc)
    try:
        november,meta=load_week(symbol)
        rows+=november
        manifest.extend(meta)
    except Exception as exc:
        missing["2026-11"]=type(exc).__name__+": "+str(exc)
    # For missing periods, do NOT interpolate or join non-adjacent months as continuous.
    segments={}
    for key in ("2026-07","2026-08","2026-09","2026-10","2026-11"):
        segment=[row for row in rows if
                 datetime.fromtimestamp(row["time"],timezone.utc).strftime("%Y-%m")==key]
        if segment:
            segments[key]=segment
    # Validate each segment alone. All inserted data is previously verified.
    for month,part in segments.items():
        for left,right in zip(part,part[1:]):
            if right["time"]-left["time"]!=60:
                raise ValueError("missing real M1 candles in "+month)
    return segments,manifest,missing

def evaluate_segment(bot,bars,minutes,slip,baseline=False):
    """Segments deliberately do not use unseen earlier/other test-period returns."""
    if len(bars)<260:
        raise ValueError("not enough closed candles for warmup")
    a=241
    f=build(bars)
    result=backtest(bars,bot,minutes,a,len(bars),slip,features=f)
    details=stats(result)
    if result["ledger"]:
        total=sum(float(x["net_usdt"]) for x in result["ledger"])
        if abs(total-(result["equity"]-START_USDT))>0.03:
            raise AssertionError("ledger/equity mismatch")
    details.update(signals=result["signals_seen"],filled=result["orders_filled"],
                   bootstrap_daily_block_ci_95_usdt=daily_block_ci(result["ledger"]))
    return result,details

def filter_counts(bars,bot,features):
    counts=Counter()
    for i in range(241,len(bars)-1):
        counts[bot.diagnose(History(bars,i+1),features,i)]+=1
    return dict(counts)

def run(out):
    out=Path(out)
    out.mkdir(parents=True,exist_ok=True)
    results=[]; all_manifests=[]; unavailable={}
    for symbol in SYMBOLS:
        try:
            months,manifest,missing=assemble(symbol)
            all_manifests+=manifest
            for m,problem in missing.items():
                unavailable[symbol+":"+m]=problem
        except Exception as exc:
            unavailable[symbol]=type(exc).__name__+": "+str(exc)
            continue
        for name in BOTS:
            filtered=Filtered(name)
            original=import_module("research.alpha.bots."+name)
            minutes=original.TIMEFRAME
            record=dict(robot=name,symbol=symbol,timeframe="M"+str(minutes),
                        rule_revision="frozen_v2_2026-11-08",periods={})
            for month,split in PERIODS:
                if month not in months:
                    record["periods"][split]=dict(status="NOT_VALIDATED",month=month,
                                                    reason=unavailable.get(symbol+":"+month,"source unavailable"))
                    continue
                try:
                    bars=months[month] if minutes==1 else aggregate_5m(months[month])
                    check_candles(bars,minutes)
                    features=build(bars)
                    diagnostic=filter_counts(bars,filtered,features)
                    stats_by_slip={}
                    for slip in (SLIPPAGE if split in
                            ("backward_unseen","november_01_07_unseen","previously_seen")
                            else (MAIN_SLIP,)):
                        run_filtered=backtest(bars,filtered,minutes,241,len(bars),slip,
                                              features=features)
                        metrics=stats(run_filtered)
                        if run_filtered["ledger"]:
                            if abs(sum(t["net_usdt"] for t in run_filtered["ledger"])-
                                   (run_filtered["equity"]-START_USDT))>0.03:
                                raise AssertionError("filtered ledger reconciliation failed")
                        metrics.update(month=month,split=split,
                                       slip_bps_per_side=slip,
                                       signals=run_filtered["signals_seen"],
                                       bootstrap_daily_block_ci_95_usdt=
                                           daily_block_ci(run_filtered["ledger"]))
                        fname=f"ledgers/{name}_{symbol}_{split}_{int(slip)}bps_filtered.csv"
                        write_ledger(out/fname,run_filtered["ledger"])
                        metrics["ledger"]=fname
                        stats_by_slip[str(int(slip))]=metrics
                    original_run=backtest(bars,original,minutes,241,len(bars),MAIN_SLIP,features=features)
                    original_stats=stats(original_run)
                    original_path=f"ledgers/{name}_{symbol}_{split}_5bps_original.csv"
                    write_ledger(out/original_path,original_run["ledger"])
                    original_stats["ledger"]=original_path
                    record["periods"][split]=dict(month=month,filter_gate_counts=diagnostic,
                         original_5bps=original_stats,filtered=stats_by_slip)
                except Exception as exc:
                    record["periods"][split]=dict(status="NOT_VALIDATED",month=month,
                                                  reason=type(exc).__name__+": "+str(exc))
            hold=record["periods"].get("november_01_07_unseen",{})
            back=record["periods"].get("backward_unseen",{})
            live=hold.get("filtered",{}).get("5",{})
            prior=back.get("filtered",{}).get("5",{})
            # Success in an isolated week + a backward window is still NOT proof of
            # prospective profitability. Never auto-approve, even when net>0.
            if ("net_usdt" in live and live["net_usdt"] is not None and
                live["trades"]>=MIN_CANDIDATE_TRADES and
                live["net_usdt"]<=0):
                status="REJECTED_OOS"
            elif ("net_usdt" in prior and prior["net_usdt"] is not None and
                  prior["trades"]>=MIN_CANDIDATE_TRADES and
                  prior["net_usdt"]<=0):
                status="REJECTED_BACKWARD"
            else:
                status="INCONCLUSIVE_NOT_APPROVED"
            record["status"]=status
            results.append(record)
    output=dict(protocol="ALPHA-V2-2026-11-08-FROZEN-FILTERS",
                counts=dict(robots=10,markets=2,combinations_expected=20,
                            combinations_written=len(results)),
                source="Binance public SPOT, daily/monthly SHA256 checked",
                currency="USDT; never BRL",capital_per_pair_usdt=5000,
                risk_fraction=.0075,real_orders=0,
                status="NO_STRATEGY_APPROVED",
                period_definitions={
                   "train_seen":"August 2026. Prior outcomes inspected.",
                   "validation_seen":"September 2026. Prior outcomes inspected.",
                   "previously_seen":"October 2026. Not independent.",
                   "backward_unseen":"July 2026. NEW but before development; not forward validation.",
                   "november_01_07_unseen":"Nov 1-7 2026. Previously uninspected retrospective holdout; NOT paper forward."},
                execution=dict(commission_bps_per_side=10,half_spread_bps_per_side=1,
                               slippage_bps_per_side=list(SLIPPAGE),
                               primary_cost_roundtrip_bps=ROUNDTRIP_BPS,
                               require_target_gross_over_cost=COST_MULTIPLIER,
                               pricing="next candle open, worst-case simultaneous stop-first"),
                independent_approval=False,parameter_selection_after_holdout=False,
                caveats=["No broker fills or quote-level spreads",
                         "Mean monthly samples not an independent future backtest",
                         "No adjusted multiple comparisons across 20 pairs",
                         "July is backward, November contains seven days only",
                         "No positive expectation assumed; no claims of trading profit"],
                source_manifests=all_manifests,unavailable=unavailable,results=results)
    (out/"results.json").write_text(json.dumps(output,indent=2,ensure_ascii=False,allow_nan=False)+"\n")
    (out/"source_manifest.json").write_text(json.dumps(dict(manifests=all_manifests,
                        unavailable=unavailable),indent=2,ensure_ascii=False)+"\n")
    lines=["# ALPHA V2 — filtered versus original, no deployment","",
           "Original signals remain unchanged. Frozen costs/regime/liquidity filters.",
           "Backtests: long-only SPOT, 5,000 USDT separate per pair, 0.75% modeled stop risk.",
           "5bps primary slippage per side + 10bps fee + 1bp half-spread per side.",
           "Nov 1–7 was not inspected in previous study but is retrospective, not prospective.","",
           "| Model | Pair | Jul filtered net | Jul trades | Nov 5bps net | Nov trades | Original Nov net | Nov 0bps | Nov 10bps | Classification |",
           "|---|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    ordered=[]
    for r in results:
        july=r["periods"].get("backward_unseen",{})
        nov=r["periods"].get("november_01_07_unseen",{})
        jp=july.get("filtered",{}).get("5",{})
        np=nov.get("filtered",{}).get("5",{})
        n0=nov.get("filtered",{}).get("0",{})
        n10=nov.get("filtered",{}).get("10",{})
        original=nov.get("original_5bps",{})
        ordered.append((np.get("net_usdt"),r,jp,np,n0,n10,original))
    ordered.sort(key=lambda x:(x[0] is None,-(x[0] or 0)))
    for _,r,jp,np,n0,n10,original in ordered:
        def val(v):return "NOT VALIDATED" if v is None else str(v)
        lines.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |"%
            (r["robot"],r["symbol"],val(jp.get("net_usdt")),jp.get("trades","N/V"),
             val(np.get("net_usdt")),np.get("trades","N/V"),
             val(original.get("net_usdt")),val(n0.get("net_usdt")),
             val(n10.get("net_usdt")),r["status"]))
    lines+=["","## Source failures", ""]
    lines.extend(["- "+key+": "+value for key,value in unavailable.items()] or ["- None"])
    lines+=["","Complete paired monthly metrics, block intervals, gate counts, fees, DD and ledger paths are in results.json.",
             "An empty ledger never implies 0 measured profitability; metrics are null and inconclusive.",
             "No variant can be promoted without more genuine unseen periods and paper fills."]
    (out/"results.md").write_text("\n".join(lines)+"\n")
    return output

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--out",default="artifacts/alpha-v2")
    args=p.parse_args()
    result=run(args.out)
    print("ALPHA-V2 summary pairs=%s unavailable=%s approvals=0"%
          (len(result["results"]),result["unavailable"]))
    if not result["results"]:
        raise SystemExit(2)
