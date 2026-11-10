"""XAUUSD price-action candidates with three distinct entry setups.

M1 microtrend breakout + retest; M5 liquidity sweep; M15 range rejection.
Research ONLY. Historical Dukascopy BID/ASK, not MT5 dealer executions.
Fixed hypotheses (not hyperparameter optimization) before reading results.
Public reference data may differ from broker or executable spot prices.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from research.xau_dukascopy_replay import aggregate_real_quotes
from research.xau_quote_execution_backtest import (
    ExecutionAssumptions, _ticks, simulate_quote_execution,
)

TIMEFRAMES = {"M1": 60, "M5": 300, "M15": 900}
DAYS = ("20261028","20261029","20261030","20261103","20261104","20261105")
START_UTC = 12
END_UTC = 17


def atr14_prior(bars, i):
    # Every calculation excludes the signal candle at i.
    tr = []
    for j in range(i-14, i):
        x = bars[j]
        old = bars[j-1]["close"]
        tr.append(max(x["high"]-x["low"],abs(x["high"]-old),abs(x["low"]-old)))
    return sum(tr)/14


def decide(bars, i, timeframe):
    """Completed candle i -> limit order eligible from next candle onward.

    No bar after i is used to calculate signals, stops, targets, or entries.
    """
    tf = TIMEFRAMES[timeframe]
    if i < 16 or i >= len(bars):
        return None
    # Never join distant sessions, weekends or missing candles into a setup.
    if any(bars[j]["time"]-bars[j-1]["time"] != tf for j in range(i-15, i+1)):
        return None
    atr = atr14_prior(bars,i)
    if not math.isfinite(atr) or atr <= 0:
        return None
    candle = bars[i]
    spread = candle["spread_points"] * .001
    if spread <= 0 or spread > .30*atr:
        return None
    side = 0
    stop = None
    target = None
    entry = candle["close"]  # FIXED limit, not a fictitious market fill.
    rule = None
    if timeframe == "M1":
        broken = bars[i-1]
        prior = bars[i-11:i-1]
        upper = max(x["high"] for x in prior)
        lower = min(x["low"] for x in prior)
        if (broken["close"] > upper and
                candle["low"] <= upper+.20*atr and
                candle["close"] > upper and candle["close"] > candle["open"]):
            side = 1
            stop = min(candle["low"],upper)-.15*atr
        elif (broken["close"] < lower and
                candle["high"] >= lower-.20*atr and
                candle["close"] < lower and candle["close"] < candle["open"]):
            side = -1
            stop = max(candle["high"],lower)+.15*atr
        rule = "M1_BREAK_RETEST"
    elif timeframe == "M5":
        prior = bars[i-12:i]
        upper = max(x["high"] for x in prior)
        lower = min(x["low"] for x in prior)
        width = candle["high"]-candle["low"]
        if width <= 0:
            return None
        if (candle["low"] < lower-.05*atr and candle["close"] > lower
                and candle["close"] > candle["open"]
                and (min(candle["open"],candle["close"])-candle["low"])/width >= .35):
            side = 1
            stop = candle["low"]-.15*atr
        elif (candle["high"] > upper+.05*atr and candle["close"] < upper
                and candle["close"] < candle["open"]
                and (candle["high"]-max(candle["open"],candle["close"]))/width >= .35):
            side = -1
            stop = candle["high"]+.15*atr
        rule = "M5_SWEEP_REJECTION"
    else:
        prior = bars[i-10:i]
        upper = max(x["high"] for x in prior)
        lower = min(x["low"] for x in prior)
        mid = (upper+lower)/2
        if (upper-lower <= 0 or upper-lower > 7*atr
                or abs(bars[i-1]["close"]-bars[i-7]["close"]) > 2*atr):
            return None
        if (candle["low"] <= lower+.25*atr
                and candle["close"] > candle["open"]
                and lower+.20*atr <= candle["close"] < mid):
            side = 1
            stop = min(candle["low"],lower)-.15*atr
            target = mid
        elif (candle["high"] >= upper-.25*atr
                and candle["close"] < candle["open"]
                and mid < candle["close"] <= upper-.20*atr):
            side = -1
            stop = max(candle["high"],upper)+.15*atr
            target = mid
        rule = "M15_RANGE_REACTION"
    if not side or stop is None or stop <= 0:
        return None
    risk = side*(entry-stop)
    if risk <= 0:
        return None
    if target is None:
        target = entry+side*(1.5 if timeframe == "M1" else 1.8)*risk
    elif side*(target-entry) < .8*risk:
        return None
    # Require reasonable stop width relative to completed-bar ATR,
    # and account for expected bid/ask + twice-stressed fees.
    if risk < .60*atr or risk < 2*(spread+.60+2*.20):
        return None
    if side*(target-entry) <= 0:
        return None
    return {
        "signal_ms": candle["time"]*1000,
        "eligible_ms": (candle["time"]+tf)*1000,
        "side":side,"entry":round(entry,5),
        "stop":round(stop,5),"target":round(target,5),
        "rule":rule,
    }


def planned(bars, timeframe):
    # Exclude the last possibly-forming candle in public CSV.
    return [setup for i in range(16,len(bars)-1)
            if (setup:=decide(bars,i,timeframe)) is not None]


def session(source, day):
    if day not in DAYS:
        raise ValueError("Unregistered day; no retrospective substitutions")
    out = {"day":day,"paper_only":True,"broker_execution_verified":False,
           "market":"XAUUSD public Dukascopy bid/ask reference",
           "units":"USD per theoretical ONE troy ounce",
           "quarantined":False,"timeframes":{}}
    for tf,seconds in TIMEFRAMES.items():
        bars, provenance = aggregate_real_quotes(source,seconds,point=.001)
        expected = 5*3600//seconds
        if len(bars) < .9*expected:
            raise ValueError(f"Incomplete entire source session for {tf}")
        # Strictly one 12:00-17:00 UTC session, without neighboring timestamps.
        first = datetime.fromtimestamp(bars[0]["time"],timezone.utc)
        last = datetime.fromtimestamp(bars[-1]["time"],timezone.utc)
        wanted = datetime.strptime(day,"%Y%m%d").replace(tzinfo=timezone.utc)
        if (first.date() != wanted.date() or last.date() != wanted.date()
                or first.hour != START_UTC or last.hour < END_UTC-1):
            raise ValueError(f"Unverified 12-17 UTC source: {day} {tf}")
        signals = planned(bars,tf)
        # Identical signal schedule in all commission scenarios.
        baseline = simulate_quote_execution(
            _ticks(Path(source)), signals,
            ExecutionAssumptions(timeframe_seconds=seconds,
                                 ttl_bars=2,max_hold_bars={"M1":12,"M5":8,"M15":6}[tf],
                                 commission_roundtrip_usd_per_oz=.30,
                                 slippage_usd_per_side=.10))
        stress = simulate_quote_execution(
            _ticks(Path(source)), signals,
            ExecutionAssumptions(timeframe_seconds=seconds,
                                 ttl_bars=2,max_hold_bars={"M1":12,"M5":8,"M15":6}[tf],
                                 commission_roundtrip_usd_per_oz=.60,
                                 slippage_usd_per_side=.20))
        out["timeframes"][tf] = {
            "candles":len(bars),"source_sha256":provenance["source_sha256"],
            "source_rows":provenance["source_rows"],
            "signals":len(signals),"baseline":baseline,"double_friction":stress,
        }
    return out


def aggregate(folder, output):
    reports = []
    for d in DAYS:
        path = Path(folder)/f"xau_{d}.json"
        if not path.is_file():
            raise ValueError(f"Missing predeclared day {d}")
        reports.append(json.loads(path.read_text()))
    clean = [r for r in reports if not r.get("quarantined")]
    if len(clean) < 3:
        raise ValueError("Too few uncontaminated whole sessions")
    rows=[]
    for tf in TIMEFRAMES:
        for cost in ("baseline","double_friction"):
            for part,subset in (
                ("earlier",[r for r in clean if r["day"]<="20261030"]),
                ("later",[r for r in clean if r["day"]>="20261103"]),
                ("all",clean)):
                if not subset:
                    raise ValueError("Missing a complete chronological period")
                executions=[r["timeframes"][tf][cost] for r in subset]
                pnl=[t["net_usd_per_oz"] for e in executions for t in e["ledger"]]
                gains=sum(x for x in pnl if x>0)
                losses=-sum(x for x in pnl if x<0)
                rows.append({
                    "tf":tf,"costs":cost,"segment":part,"sessions":len(subset),
                    "signals":sum(r["timeframes"][tf]["signals"] for r in subset),
                    "entries":sum(e["filled"] for e in executions),
                    "wins":sum(x>0 for x in pnl),"losses":sum(x<0 for x in pnl),
                    "net_usd_per_oz":round(sum(pnl),5),
                    "profit_factor":round(gains/losses,4) if losses>0 else None,
                })
    result = {
        "study":"XAUUSD M1 breakout+retest / M5 sweep / M15 range",
        "paper_only":True,"approved_for_trading":False,
        "data_previously_seen_in_other_research":True,
        "independent_out_of_sample":False,
        "not_account_profit":True,
        "all_predeclared_days":list(DAYS),
        "quarantined_entire_days":[r["day"] for r in reports if r.get("quarantined")],
        "n_valid_days":len(clean),"results":rows,
    }
    Path(output).write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(result,ensure_ascii=False))
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--ticks",type=Path)
    ap.add_argument("--day")
    ap.add_argument("--out",required=True,type=Path)
    ap.add_argument("--reports",type=Path)
    args=ap.parse_args()
    if args.reports:
        aggregate(args.reports,args.out)
        return
    if not args.ticks or args.day not in DAYS:
        ap.error("Supply --ticks and predeclared --day")
    try:
        report=session(args.ticks,args.day)
    except (ValueError,OSError) as exc:
        # A bad tick quarantines the WHOLE day. Never cherry-pick rows.
        report={"day":args.day,"paper_only":True,"quarantined":True,
                "reason":type(exc).__name__+": "+str(exc)[:180]}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"day":args.day,"quarantined":report["quarantined"],
                      "reasons":report.get("reason"),
                      "results":({tf:report["timeframes"][tf]["double_friction"]["net_usd_per_oz"]
                                  for tf in TIMEFRAMES} if not report["quarantined"] else {})},
                     ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
