"""Audit a specific execution flaw: stop on the WRONG side of retested LTA/LTD.

This does not add indicators, signals or filters. It checks whether the
previous stop sits beyond the invalidation line after a completed retest.
When not, compare the original PnL to an unoptimized mechanical correction
(stop behind the line by the SAME 0.1 ATR tolerance already used in v3).

This is a counterfactual research diagnosis. No user-specified Stop Red
distance or broker execution conditions are known. No trading approval.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path

from research.xau_price_action_m1m5 import (
    Settings,SourceQualityError,parse_quotes,candles_from_quotes,
    simulate_ticks,
)
from research.xau_pa_manual_rules_v3 import causal_signals
from research.xau_pa_fidelity_v4 import proxy_zones_repeated,gate_signals
from research.xau_pa_m5_context_m1_v6 import (
    DAYS,utc_ms,filter_m1_with_m5,confirm_m5_zone_touch,
    evaluate_day as prior_day,
)


def stop_geometry(signal):
    """Distance of stop from broken line, normalized by ATR and side.

    For a bullish LTD break, the technical stop belongs BELOW the broken
    line. For bearish LTA break, it belongs ABOVE the broken line.
    Such placement is a research interpretation, NOT the trader's actual
    unrecorded Stop Red instruction.
    """
    if signal["setup"]!="break_retest":
        return {"applicable":False}
    side=signal["side"]
    if side not in (-1,1):
        raise ValueError("Invalid trade side")
    if signal["atr"]<=0:
        raise ValueError("Invalid ATR")
    line=signal.get("line_retest_level")
    if line is None:
        raise ValueError("Broken-line retest signal missing its level")
    signed=(side*(line-signal["stop"]))/signal["atr"]
    return {
        "applicable":True,
        "line_stop_buffer_atr":round(signed,6),
        "stop_on_invalidated_side":signed<=0,
        "line_price":line,
        "old_stop":signal["stop"],
    }


def stop_line_repair(signals):
    """Copy signals: only repair wrong-side stops. NEVER alter entry signals.

    Re-uses the original 0.1 ATR technical stop buffer. Stop adjustments
    can make RR worse, reject an entry or increase losses. Report all cases.
    """
    new=[];adjusted=[]
    for s in signals:
        before=stop_geometry(s)
        if before.get("stop_on_invalidated_side",False):
            side=s["side"]
            line=before["line_price"]
            desired=line-side*.10*s["atr"]
            correct=min(s["stop"],desired) if side==1 else max(s["stop"],desired)
            if side*(correct-s["stop"])>=0:
                raise ValueError("Stop correction did not widen toward invalidation")
            copy={**s,"stop":correct,
                  "prior_stop":s["stop"],
                  "stop_correction_reason":"old_stop_inside_retested_line"}
            adjusted.append({
                "eligible_ms":s["eligible_ms"],"side":side,
                "line":line,"before":s["stop"],"after":correct,
                "change_usd_per_oz":round(abs(correct-s["stop"]),6),
            })
            new.append(copy)
        else:
            new.append(s)
    if len(new)!=len(signals):
        raise ValueError("Stop correction invented or removed a signal")
    for old,new_signal in zip(signals,new):
        for key in ("eligible_ms","signal_ms","side","setup","atr","breakout_ms",
                    "line_retest_level","line_kind"):
            if old.get(key)!=new_signal.get(key):
                raise ValueError("Technical stop repair altered price-action entries")
    return new,adjusted


def replay_signals(quotes,day):
    s=utc_ms(day,12);end=utc_ms(day,21)
    m1=candles_from_quotes(quotes,60)
    m5=candles_from_quotes(quotes,300)
    raw,_=causal_signals(m1,60,s,end,marking_mode="proxy",
                         proxy_zones_fn=proxy_zones_repeated)
    baseline,_=gate_signals(m1,raw,60)
    context,_,_=filter_m1_with_m5(baseline,m5)
    confirmed,_=confirm_m5_zone_touch(context,m1)
    return confirmed


def audit_day(path,day):
    if day not in DAYS:
        raise ValueError("Fixed previous-price panel only; cannot pick dates by outcome")
    quotes,src=parse_quotes(path,day)
    trade_begin=utc_ms(day,12);end=utc_ms(day,21)
    execution=[q for q in quotes if trade_begin<=q[0]<end]
    if not execution:
        raise SourceQualityError("No quote tape for 12-21 UTC")
    prior=prior_day(path,day)
    signals=replay_signals(quotes,day)
    after,changes=stop_line_repair(signals)
    costs=Settings()
    stressed=replace(costs,commission_roundtrip_usd_per_oz=.60,
                     slippage_usd_each_market_side=.20)
    versions={}
    for label,pool in (("unchanged_v6",signals),("line_stop_check",after)):
        versions[label]={
            "signals":len(pool),
            "costs":{
                name:simulate_ticks(execution,pool,60,config)
                for name,config in (("standard",costs),("double",stressed))
            },
        }
    for name in ("standard","double"):
        old=prior["results"]["v6_M5_context_M1_entry"]["costs"][name]
        trial=versions["unchanged_v6"]["costs"][name]
        if (old["signals"]!=trial["signals"] or
            old["filled"]!=trial["filled"] or
            abs(old["net_usd_per_oz"]-trial["net_usd_per_oz"])>1e-5 or
            [t["entry_ms"] for t in old["trades"]]!=
            [t["entry_ms"] for t in trial["trades"]]):
            raise ValueError("Reference replay does not match verified V6")
    by_entry={s["eligible_ms"]:stop_geometry(s) for s in signals}
    old_fills=versions["unchanged_v6"]["costs"]["double"]["trades"]
    entries=[]
    for t in old_fills:
        geom=by_entry.get(t["eligible_ms"])
        if geom is None:
            raise ValueError("Filled trade not associated with generated signal")
        entries.append({
            "entry_ms":t["entry_ms"],
            "signal_ms":t["signal_ms"],"setup":t["setup"],
            "side":t["side"],"entry":t["entry"],
            "stop":t["stop"],"target":t["target"],
            "exit_reason":t["reason"],
            "net_usd_per_oz":t["net_usd_per_oz"],
            **geom,
        })
    return {
        "day":day,"source":src,
        "original_v6_exactly_replayed":True,
        "same_M1_signals_and_execution_ticks":True,
        "only_stop_geometry_changed":True,
        "correct_stop_distances_user_confirmed":False,
        "is_not_mt5_broker":True,
        "live_trading_approved":False,
        "simulated_unit":"USD per 1 theoretical ounce",
        "candidate_geometry":{
            "break_retest_candidates":sum(stop_geometry(s)["applicable"] for s in signals),
            "stop_wrong_side_candidates":sum(stop_geometry(s).get("stop_on_invalidated_side",False)
                                             for s in signals),
            "original_filled":len(old_fills),
            "filled_stop_wrong_side":sum(
                row.get("stop_on_invalidated_side",False) for row in entries
            ),
            "actually_adjusted_candidate_stops":len(changes),
        },
        "changes":changes,
        "original_fills_with_geometry":entries,
        "models":versions,
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--ticks",required=True)
    parser.add_argument("--day",required=True)
    parser.add_argument("--out",required=True)
    parser.add_argument("--quarantine",required=True)
    args=parser.parse_args()
    try:
        result=audit_day(args.ticks,args.day)
    except SourceQualityError as exc:
        report={"day":args.day,"whole_day_quarantined":True,
                "reason":str(exc),"trades_included":0}
        file=Path(args.quarantine);file.parent.mkdir(parents=True,exist_ok=True)
        file.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
        print("QUARANTINED WHOLE DAY",args.day,str(exc))
        return
    target=Path(args.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    for name,part in result["models"].items():
        d=part["costs"]["double"]
        print("STOP_AUDIT",args.day,name,"signals",part["signals"],
              "filled",d["filled"],"wins",d["wins"],
              "losses",d["losses"],"net_USD_oz",d["net_usd_per_oz"])
    print("GEOMETRY",result["candidate_geometry"])


if __name__=="__main__":
    main()
