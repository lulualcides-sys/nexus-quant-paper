"""XAUUSD Price Action v6: M5 context, M1 decision and ONE XAU position.

Predeclared change: preserve v4's M1 microtrendline BREAK -> WAIT -> RETEST
logic without EMA. For RANGE TOUCHS ONLY, require a confirmed sideways M5
context AND an M5 support/resistance zone built from earlier, confirmed
double-touch swings; otherwise veto. M5 never independently opens orders.

Control: identical v4 M1 signals and engine, with the same 09-21 tape.
Treatment: filter the control's range trades using *completed M5 candles*.
No new/unobserved signals, parameter optimization, custom MT5 execution,
or attribution of automated marks to user drawings.

This is one falsifiable hypothesis, NOT a claim of strategy fidelity or profit.
"""
from __future__ import annotations
import argparse
from bisect import bisect_right
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path

from research.xau_price_action_m1m5 import (
    Settings,SourceQualityError,atr,candles_from_quotes,parse_quotes,
    simulate_ticks,
)
from research.xau_pa_manual_rules_v3 import causal_signals,sideways
from research.xau_pa_fidelity_v4 import proxy_zones_repeated,gate_signals
from research.xau_pa_frequency_v2 import utc_ms

# Never select dates based on a good historical trade.
JUNE=("20260622","20260623","20260624","20260625","20260626")
JULY=("20260727","20260728","20260729","20260730","20260731")
DAYS=JUNE+JULY
POLICIES=("v4_M1_reference","v6_M5_context_M1_entry")
COSTS=("standard","double")


def m5_context_at(m5bars,signal_end_ms):
    """M5 bars whose *end* is <= M1 signal candle close are admissible.

    Avoid current/incomplete M5 context even though whole-day OHLC is
    available to the historical runner. No future highs/lows ever enter.
    """
    ends=[(b["time"]+300)*1000 for b in m5bars]
    cutoff=bisect_right(ends,signal_end_ms)
    history=m5bars[:cutoff]
    if len(history)<42:
        return {"status":"warmup","last_m5_end_ms":None,"zone":None}
    last_m5_end_ms=(history[-1]["time"]+300)*1000
    if last_m5_end_ms>signal_end_ms:
        raise ValueError("M5 context leaked an unfinished candle")
    r=atr(history,len(history)-1,14)
    if r is None or r<=0:
        return {"status":"no_atr","last_m5_end_ms":last_m5_end_ms,"zone":None}
    regime="range" if sideways(history,len(history),r) else "not_range"
    # Function requires 2 confirmed taps on BOTH sides; only preceding M5.
    zone=(proxy_zones_repeated(history[-72:],last_m5_end_ms)
          if regime=="range" else None)
    return {
        "status":regime,"last_m5_end_ms":last_m5_end_ms,
        "zone":zone,"atr_M5":r,
    }


def filter_m1_with_m5(m1signals,m5bars):
    """Only exclude poor M1 RANGE touch signals; no new trades fabricated.

    Break/retest remains separate and unchanged. All range entries require
    pre-existing M5 support/resistance, a completed M5 ranging regime, and
    an M1 rejection candle whose pre-existing low/high tested that M5 zone.
    """
    selected=[];rejected=Counter()
    reasons=[]
    last_end=-1
    for s in sorted(m1signals,key=lambda z:z["eligible_ms"]):
        t=s["eligible_ms"]
        if t<last_end:
            raise ValueError("M1 signal order must be chronological")
        last_end=t
        context=m5_context_at(m5bars,t)
        if s["setup"]=="break_retest":
            selected.append({**s,"M5_context_at_signal":context["status"],
                             "context_m5_end_ms":context["last_m5_end_ms"]})
            rejected["break_retest_preserved"]+=1
            continue
        if s["setup"]!="range_rejection":
            raise ValueError("Unexpected non-manual Price Action setup")
        if context["status"]!="range":
            rejected["M5_not_lateral"]+=1
            reasons.append({"signal_ms":s["signal_ms"],"why":"M5_not_lateral"})
            continue
        zone=context["zone"]
        if zone is None:
            rejected["M5_no_double_touch_mark"]+=1
            reasons.append({"signal_ms":s["signal_ms"],"why":"M5_no_double_touch_mark"})
            continue
        side=s["side"]
        if side not in (-1,1):
            raise ValueError("Invalid Price Action side")
        # The signal's M1 OHLC is NOT directly embedded in current v4
        # signal; use retest stop as a conservative contact proxy only
        # where price geometry is known. Prefer pass in actual M1 candle.
        # This function intentionally does not decide touch from a stop.
        selected.append({**s,"M5_context_at_signal":"range",
                         "context_m5_end_ms":context["last_m5_end_ms"],
                         "m5_zone_source":zone.source,
                         "m5_support_low":zone.support_low,
                         "m5_support_high":zone.support_high,
                         "m5_resistance_low":zone.resistance_low,
                         "m5_resistance_high":zone.resistance_high})
        rejected["M5_confirmed_lateral_with_mark"]+=1
    return selected,dict(sorted(rejected.items())),reasons


def confirm_m5_zone_touch(signals,m1bars):
    """Actual completed M1 candle must intersect earlier M5 zone.
    v4 M1 range signal already checked its own candle rejection quality.
    No stop-price inference or lookahead.
    """
    index={b["time"]*1000:b for b in m1bars}
    approved=[];veto=Counter()
    for s in signals:
        if s["setup"]!="range_rejection":
            approved.append(s);continue
        candle=index.get(s["signal_ms"])
        if candle is None or s["eligible_ms"]!=(candle["time"]+60)*1000:
            raise ValueError("M1 signal candle not available and closed")
        # Require candle to cross/enter price zone set by completed M5
        if s["side"]==1:
            touch=(candle["low"]<=s["m5_support_high"] and
                   candle["high"]>=s["m5_support_low"])
        else:
            touch=(candle["high"]>=s["m5_resistance_low"] and
                   candle["low"]<=s["m5_resistance_high"])
        if not touch:
            veto["M1_rejection_not_at_M5_mark"]+=1
        else:
            veto["M1_rejection_confirmed_at_M5_mark"]+=1
            approved.append(s)
    return approved,dict(sorted(veto.items()))


def audit_excursions(trades,quotes):
    """Quote-level favorable/adverse movement only BEFORE actual exit.

    Never infer a price after stopping out, never substitute mid-price for
    executable BID (long exit) / ASK (short exit). This is diagnostic only:
    it does not adjust entries, stops or PnL of the existing experiment.
    """
    from bisect import bisect_left,bisect_right
    stamps=[q[0] for q in quotes]
    annotated=[]
    for trade in trades:
        side=trade["side"]
        risk=side*(trade["entry"]-trade["stop"])
        if risk<=0:raise ValueError("Expected positive entry-to-stop distance")
        start=bisect_left(stamps,trade["entry_ms"])
        stop=bisect_right(stamps,trade["exit_ms"])
        if start>=stop:
            raise ValueError("No quotes inside confirmed trade duration")
        excursions=[
            side*((bid if side==1 else ask)-trade["entry"])
            for _,bid,ask in quotes[start:stop]
        ]
        mfe=max(excursions)/risk
        mae=min(excursions)/risk
        annotated.append({**trade,
            "MFE_R_before_actual_exit":round(mfe,5),
            "MAE_R_before_actual_exit":round(mae,5),
            "stopped_after_0_5R":trade["reason"]=="STOP" and mfe>=.5,
            "stopped_after_1R":trade["reason"]=="STOP" and mfe>=1.,
        })
    return annotated


def evaluate_day(path,day):
    if day not in DAYS:raise ValueError("Only preregistered June/July 2026 dates")
    quotes,src=parse_quotes(path,day)
    start=utc_ms(day,9);market_open=utc_ms(day,12);end=utc_ms(day,21)
    if (quotes[0][0]<start or quotes[0][0]>start+60000 or
        quotes[-1][0]<end-120000 or quotes[-1][0]>end+59999):
        raise SourceQualityError("Whole day lacks 09-21 UTC quotes")
    execution=[q for q in quotes if market_open<=q[0]<end]
    if len(execution)<1500 or execution[0][0]>market_open+60000:
        raise SourceQualityError("Missing actual 12-21 market quote tape")
    m1bars=candles_from_quotes(quotes,60)
    m5bars=candles_from_quotes(quotes,300)
    if len(m1bars)<360 or len(m5bars)<110:
        raise SourceQualityError("Insufficient M1/M5 warmup and execution coverage")
    settings=Settings()
    stress=replace(settings,commission_roundtrip_usd_per_oz=.60,
                   slippage_usd_each_market_side=.20)
    raw,events=causal_signals(
        m1bars,60,market_open,end,marking_mode="proxy",
        proxy_zones_fn=proxy_zones_repeated,
    )
    baseline,gate=gate_signals(m1bars,raw,60)
    filtered,reasons,details=filter_m1_with_m5(baseline,m5bars)
    confirmed,touch_veto=confirm_m5_zone_touch(filtered,m1bars)
    if len(confirmed)>len(baseline):
        raise ValueError("Treatment unexpectedly invented trades")
    results={}
    for policy,signals in ((POLICIES[0],baseline),(POLICIES[1],confirmed)):
        outcome={
            "signals":len(signals),
            "setup_signals":dict(sorted(Counter(t["setup"] for t in signals).items())),
            "costs":{},
        }
        for cost,assumptions in (("standard",settings),("double",stress)):
            # BOTH variants simulate the same single timeframe, one XAU position.
            tested=simulate_ticks(execution,signals,60,assumptions)
            if tested["filled"]>len(signals):
                raise ValueError("Filled count exceeded signals")
            if any(t["entry_ms"]<market_open or t["entry_ms"]>=end for t in tested["trades"]):
                raise ValueError("Out-of-session fill")
            tested["trades"]=audit_excursions(tested["trades"],execution)
            outcome["costs"][cost]=tested
        results[policy]=outcome
    return {
        "day":day,"source":src,
        "quote_source":"Dukascopy historical spot XAUUSD BID/ASK",
        "manual_user_marks_present":False,
        "strategy_fidelity_verified":False,
        "M5_context_M1_entries_only":True,
        "no_independent_M5_orders":True,
        "single_XAU_position":True,
        "source_is_not_MT5_broker":True,
        "auto_trading_approved":False,
        "warmup_utc":"09:00-12:00",
        "trading_utc":"12:00-21:00",
        "signal_detector_v4_rejections":gate,
        "M5_context_rejections":reasons,
        "M1_M5_zone_touch_rejections":touch_veto,
        "signals_rejected_M5":details,
        "v3_source_events":events,
        "results":results,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--ticks",required=True)
    p.add_argument("--day",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--quarantine",required=True)
    a=p.parse_args()
    try:
        r=evaluate_day(a.ticks,a.day)
    except SourceQualityError as exc:
        q={"day":a.day,"whole_source_quarantined":True,
           "reason":str(exc),"trades_included":0}
        target=Path(a.quarantine);target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(q,ensure_ascii=False,indent=2)+"\n")
        print("QUARANTINED",a.day,exc)
        return
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
    for mode,record in r["results"].items():
        z=record["costs"]["double"]
        print("CONTEXT_V6",a.day,mode,
              "signals",record["signals"],"fills",z["filled"],
              "wins",z["wins"],"losses",z["losses"],
              "net_USD_per_oz",z["net_usd_per_oz"])
    print("M5_REASONS",r["M5_context_rejections"],r["M1_M5_zone_touch_rejections"])


if __name__=="__main__":
    main()
