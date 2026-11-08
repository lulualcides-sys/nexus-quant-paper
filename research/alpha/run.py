"""Run research: python -m research.alpha.run --out /tmp/alpha-result

Downloads only public SPOT archive candles; no credentials, trading, Telegram or main state.
"""
from __future__ import annotations
from collections import defaultdict
from importlib import import_module
from pathlib import Path
from random import Random
import argparse,csv,json,traceback

from research.alpha.data import SYMBOLS,MONTHS,load_symbol,aggregate_5m
from research.alpha.engine import backtest,check_candles,split_months,stats,SLIPPAGE_BPS,build,MIN_TRADES

BOTS=(
 "alpha01_volume_exhaustion","alpha02_breakout_retest","alpha03_vwap_deviation",
 "alpha04_ema_atr_pullback","alpha05_liquidity_rejection_proxy",
 "alpha06_volatility_momentum","alpha07_regime_mean_revert",
 "alpha08_opening_range_crypto","alpha09_consolidation_continuation",
 "alpha10_adaptive_regime")
SPLITS=("train","validation","final_test")
MONTH_FOR_SPLIT=dict(zip(SPLITS,MONTHS))

def daily_block_ci(ledger):
    byday=defaultdict(float)
    for x in ledger:
        byday[x["exit_ts_utc"][:10]]+=x["net_usdt"]
    if len(byday)<15 or len(ledger)<MIN_TRADES:
        return None
    values=list(byday.values()); n=len(values); rng=Random(20261108)
    estimates=sorted(sum(values[rng.randrange(n)] for _ in range(n)) for _ in range(500))
    return [round(estimates[12],4),round(estimates[487],4)]

def write_ledger(path,ledger):
    path.parent.mkdir(parents=True,exist_ok=True)
    keys=("signal_ts_utc","entry_ts_utc","exit_ts_utc","side","entry_raw","entry",
          "exit_raw","exit","qty","gross_usdt","costs_usdt","net_usdt","reason",
          "slippage_bps_per_side")
    with path.open("w",newline="",encoding="utf8") as dest:
        writer=csv.DictWriter(dest,fieldnames=keys)
        writer.writeheader()
        for row in ledger: writer.writerow(row)

def execute(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    catalog={}; manifests=[]; failures={}
    # An independent source failure cannot substitute BTC data for ETH or vice versa.
    for symbol in SYMBOLS:
        try:
            bars,manifest=load_symbol(symbol)
            catalog[symbol]={1:bars,5:aggregate_5m(bars)}
            manifests.extend(manifest)
        except Exception as exc:
            failures[symbol]=type(exc).__name__+": "+str(exc)
    (out/"source_manifest.json").write_text(json.dumps(dict(manifests=manifests,failures=failures),
                                            indent=2,ensure_ascii=False)+"\n")
    results=[]
    for bot in BOTS:
        mod=import_module("research.alpha.bots."+bot)
        for symbol in SYMBOLS:
            if symbol not in catalog:
                results.append(dict(robot=bot,symbol=symbol,status="NOT_VALIDATED",reason=failures[symbol]))
                continue
            bars=catalog[symbol][mod.TIMEFRAME]
            check_candles(bars,mod.TIMEFRAME)
            months=split_months(bars)
            if list(months)!=list(MONTHS):
                raise ValueError("unexpected data months: "+str(list(months)))
            feat=build(bars)
            audits={}
            for split in SPLITS:
                month=MONTH_FOR_SPLIT[split]
                a,b=months[month]
                if split=="train":
                    a=max(a,221)
                cases={}
                for scenario in SLIPPAGE_BPS:
                    run=backtest(bars,mod,mod.TIMEFRAME,a,b,scenario,features=feat)
                    ledger_file=f"ledgers/{symbol}_{bot}_{split}_{int(scenario)}bps.csv"
                    write_ledger(out/ledger_file,run["ledger"])
                    details=stats(run)
                    details.update(ledger_file=ledger_file,month=month,split=split,
                                   slippage_bps_per_side=scenario,
                                   signals_seen=run["signals_seen"],
                                   filled_orders=run["orders_filled"],
                                   block_bootstrap_net_95pct_usdt=daily_block_ci(run["ledger"]))
                    cases[str(int(scenario))]=details
                audits[split]=cases
            hold=audits["final_test"]["5"]
            stress=audits["final_test"]["10"]
            # One test month and no prospective paper: no technical approvals yet.
            status="REJECTED" if (hold["trades"]>=MIN_TRADES and
                   (hold["net_usdt"] is None or hold["net_usdt"]<=0 or
                    hold["profit_factor"] is None or hold["profit_factor"]<=1.2)) else "INCONCLUSIVE"
            if (status=="INCONCLUSIVE" and hold["trades"]>=MIN_TRADES and
                stress["net_usdt"] is not None and stress["net_usdt"]<=0):
                status="REJECTED"
            results.append(dict(robot=bot,symbol=symbol,timeframe=f"M{mod.TIMEFRAME}",
                                status=status,finance_currency="USDT",
                                reference_balance_usdt=5000,risk_fraction=.0075,
                                train=audits["train"],validation=audits["validation"],
                                final_test=audits["final_test"]))
    rank=sorted([r for r in results if "final_test" in r],
                key=lambda r:(r["final_test"]["5"]["net_usdt"] is None,
                              -(r["final_test"]["5"]["net_usdt"] or -10**20)))
    output=dict(schema=1,experiment="ALPHA-10-ISOLATED-NO-TRADING",
                experimental_design="2026-08 TRAIN / 2026-09 VALIDATION / 2026-10 FINAL",
                rules_frozen_before_final=True,final_not_prospective=True,
                data_provider="Binance public SPOT monthly M1; M5 from 5 real M1",
                quote_currency="USDT, NOT BRL; no unverified FX rate",
                trading_mode="long-only SPOT simulated; no real orders",
                costs=dict(taker_fee_bps_per_side=10,half_spread_bps_per_side=1,
                           slip_bps_per_side=list(SLIPPAGE_BPS)),
                notes=["No approval from single retrospective test month",
                       "Stops first if stop and target touched in same candle",
                       "No observed L2 book, slippage illustrative, no paper forward",
                       "Block bootstrap limited to days with trades; multiple comparisons not resolved",
                       "No R$ conversion; R$30k reference cannot be substituted for 5000 USDT",
                       "Trailing/equity mark-to-market excludes projected liquidation fees"],
                results=results,ranking_oos_5bps=[r["robot"]+" "+r["symbol"] for r in rank],
                unavailable_markets=failures)
    (out/"results.json").write_text(json.dumps(output,indent=2,ensure_ascii=False,allow_nan=False)+"\n")
    lines=["# ALPHA 10 — isolated laboratory","",
           "Data source: Binance SPOT monthly klines, August–October 2026.",
           "Currency: USDT; NO BRL conversion, NO WIN comparisons.",
           "No strategy is approved for real trading; test period is only one month.","",
           "| Candidate / pair | Closed trades OOS | Net OOS USDT 5bps | PF | Max DD% | OOS 10bps | Status |",
           "|---|---:|---:|---:|---:|---:|---|"]
    for r in rank:
        a=r["final_test"]["5"];s=r["final_test"]["10"]
        lines.append("| %s / %s | %s | %s | %s | %s | %s | %s |" %
            (r["robot"],r["symbol"],a["trades"],a["net_usdt"],a["profit_factor"],
             a["max_drawdown_pct"],s["net_usdt"],r["status"]))
    if failures:
        lines.extend(["","## Unavailable sources",""]+[f"- {k}: {v}" for k,v in failures.items()])
    lines.extend(["","All month-by-month results, 0/5/10 bps sensitivities, costs, uncertainty and CSV ledgers are in the Actions artifact.",
                  "Explicitly rejected WINFUT continuous synthetic series (PR #33)."])
    (out/"results.md").write_text("\n".join(lines)+"\n",encoding="utf8")
    return output

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",default="artifacts/alpha")
    a=parser.parse_args()
    report=execute(a.out)
    valid=sum("final_test" in x for x in report["results"])
    print("ALPHA strategies="+str(len(BOTS))+" tested_pairs="+str(valid)+
          " market_failures="+str(report["unavailable_markets"]))
    # Failed downloads are documented and do not yield fake zero P&L.
    if not valid:
        raise SystemExit(2)

if __name__=="__main__":
    main()
