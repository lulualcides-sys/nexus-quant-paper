"""ALPHA V6 continuous vs causal profit-protection: fixed ALPHA02 across assets.

No training on BNB/XRP outcomes. SOL V5 records were already inspected.
Each market is one 22-month book, not 22 monthly restarts. Order/signal rules
and 0.75% risk fixed. Both versions use the SAME continuous replay engine.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
import argparse,json,csv
from research.alpha_v6.data import continuous,MARKETS,MONTHS
from research.alpha_v5.strategy import ConfirmedRegime
from research.alpha_v6.engine import replay,PROTECT_ACTIVATE_ATR,TRAIL_FROM_CLOSE_ATR
from research.alpha.engine import stats,START_USDT
from research.alpha.run import daily_block_ci

BOT="alpha02_breakout_retest"
SLIPPAGE=(0.,5.,10.)
SEEN_MARKET="SOLUSDT"
NEW_MARKETS=("BNBUSDT","XRPUSDT")
LEDGER_FIELDS=("signal_ts_utc","entry_ts_utc","exit_ts_utc","side","entry_raw",
               "entry","exit_raw","exit","qty","gross_usdt","costs_usdt",
               "net_usdt","reason","slippage_bps_per_side",
               "stop_protect_activated")

def write_v6_ledger(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",newline="",encoding="utf8") as file:
        writer=csv.DictWriter(file,fieldnames=LEDGER_FIELDS,extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)
assert set(NEW_MARKETS)|{SEEN_MARKET}==set(MARKETS)

def _monthly_breakdown(ledger):
    months=defaultdict(list)
    for row in ledger:
        m=row["exit_ts_utc"][:7]
        months[m].append(row)
    result={}
    for m in MONTHS:
        trades=months.get(m,[])
        result[m]=dict(closed=len(trades),
           realized_net_usdt=(round(sum(x["net_usdt"] for x in trades),4)
             if trades else None),
           costs_usdt=(round(sum(x["costs_usdt"] for x in trades),4)
             if trades else None))
    if sum(x["closed"] for x in result.values())!=len(ledger):
        raise AssertionError("exit outside audited periods")
    return result

def run(out):
    dest=Path(out);dest.mkdir(parents=True,exist_ok=True)
    markets=[];manifests=[];errors={}
    for symbol in MARKETS:
        try:
            data,source=continuous(symbol)
            manifests.extend(source)
        except Exception as exc:
            errors[symbol]=type(exc).__name__+": "+str(exc)
            markets.append(dict(symbol=symbol,status="NOT_VALIDATED",reason=errors[symbol]))
            continue
        try:
            model=ConfirmedRegime(BOT,data)
            cases={}
            for variant,protect in (("v5_continuous",False),("v6_protected",True)):
                runs={}
                for slip in SLIPPAGE:
                    r=replay(model,slippage_bps=slip,protect=protect)
                    s=stats(r)
                    s.update(status="RESEARCH_ONLY",capital_start_usdt=START_USDT,
                             equity_realized_usdt=round(r["equity"],4),
                             marked_total_equity_usdt=r["marked_total_equity_usdt"],
                             open_at_end=r["open_at_end"],
                             marked_open_net_usdt=r["marked_open_net_usdt"],
                             signal_count=r["signals_seen"],
                             filled_count=r["orders_filled"],
                             protect_activation_count=r["protection_activations"],
                             bootstrap_daily_block_ci_95_usdt=daily_block_ci(r["ledger"]),
                             month_by_exit=_monthly_breakdown(r["ledger"]))
                    fname=f"ledgers/{symbol}_{variant}_{int(slip)}bps.csv"
                    write_v6_ledger(dest/fname,r["ledger"])
                    s["ledger"]=fname
                    runs[str(int(slip))]=s
                cases[variant]=runs
            markets.append(dict(symbol=symbol,status="RETROSPECTIVE_RESEARCH_NOT_APPROVED",
                evidence=("previously_examined_SOL" if symbol==SEEN_MARKET
                          else "new_cross_asset_retrospective_not_forward"),
                periods=list(MONTHS),variants=cases))
        except Exception as exc:
            errors[symbol+":model"]=type(exc).__name__+": "+str(exc)
            markets.append(dict(symbol=symbol,status="NOT_VALIDATED",
                                reason=errors[symbol+":model"]))
    report=dict(experiment="ALPHA-V6-CONTINUOUS-NEXT-CLOSED-BAR-TRAILING",
      created_utc="2026-11-08",research_only=True,approved_for_paper=0,
      real_broker_orders=0,signal_family=BOT,markets=markets,
      source_manifests=manifests,source_errors=errors,
      currency="USDT",notional_books_per_symbol=1,initial_book_usdt=START_USDT,
      months_per_market=len(MONTHS),
      arms=dict(v5_continuous="V5 original signals+exits, monthly reset removed",
                v6_protected="exact same model, protective stop after 2 H1 ATR close"),
      fixed_rules=dict(protection_activate_favorable_close_atr=PROTECT_ACTIVATE_ATR,
          trail_from_close_atr=TRAIL_FROM_CLOSE_ATR,activation="following bar only",
          atr_for_protection="entry H1 ATR frozen",
          fee_bps_per_side=10,half_spread_bps_per_side=1,
          slippage_bps_per_side=list(SLIPPAGE),target_h1_atr=4,
          original_stop_h1_atr=1.5,stop_risk_fraction=.0075,
          max_hold_hours=72,cooldown_hours=24,monthly_reset=False),
      statistical_limits=["These are retrospective samples, not future paper",
          "ALPHA02 selected after looking at historical SOL results",
          "BNB/XRP are correlated and are not independent future time periods",
          "Maker fills, live spreads, actual slippage and exchange lot sizes unverified",
          "OHLC stop/target collision always chooses adverse stop",
          "No P&L manufactured for zero trades",
          "No auto-promotion even if positive; require prospective independent evidence"],
      result_status="NO_STRATEGY_APPROVED")
    (dest/"results.json").write_text(json.dumps(report,ensure_ascii=False,
                              indent=2,allow_nan=False)+"\n",encoding="utf8")
    (dest/"source_manifest.json").write_text(json.dumps(
          dict(sources=manifests,errors=errors),ensure_ascii=False,indent=2)+"\n")
    md=["# ALPHA V6 — continuous ledger / protected stop vs unchanged V5",
        "","Each asset has ONE continuous 2025-01 to 2026-10 5000-USDT virtual book.",
        "No monthly reset, no unrealized positions silently counted as wins.",
        "SOL previously seen, BNB/XRP are newly checked correlated markets.",
        "Costs: 10bps taker + 1bp half-spread + slippage 0,5,10bps per side.",
        "", "| Asset | Version | Trades | Net 5bps | PF 5bps | DD 5bps | Net 10bps | Open end | Status |",
        "|---|---|---:|---:|---:|---:|---:|---|---|"]
    for r in markets:
        if "variants" not in r:
            md.append(f"| {r['symbol']} | N/V | N/V | N/V | N/V | N/V | N/V | N/V | NOT VALIDATED |")
            continue
        for version in ("v5_continuous","v6_protected"):
            a=r["variants"][version]["5"]
            b=r["variants"][version]["10"]
            def num(v):return "N/V" if v is None else str(v)
            md.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s |"%
                (r["symbol"],version,a["trades"],num(a["net_usdt"]),
                 num(a["profit_factor"]),num(a["max_drawdown_pct"]),
                 num(b["net_usdt"]),a["open_at_end"],r["status"]))
    md+=["","## Missing data or model errors"]
    md.extend([f"- {k}: {v}" for k,v in errors.items()] or ["- None"])
    md+=["","Monthly breakdown by real close timestamp in results.json.",
         "Even positive historical P&L requires robust future paper and true execution costs."]
    (dest/"results.md").write_text("\n".join(md)+"\n")
    print("V6 markets validated="+str(sum("variants" in r for r in markets))+
          "/3; ZIPs="+str(len(manifests))+"/66; errors="+str(errors))
    # For the official result, incomplete inputs are a FAILED validation.
    if len(manifests)!=len(MARKETS)*len(MONTHS) or len(errors):
        raise SystemExit(2)
    return report

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",default="artifacts/alpha-v6")
    args=parser.parse_args()
    run(args.out)
