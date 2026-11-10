"""Price Action gold v5: causal rolling support/resistance vs fixed-open v4.

ONE predeclared change: in `proxy` research mode, use confirmed swing pairs
observed before EACH signal candle to refresh lateral range boundaries.
Leave all LTA/LTD break/retest rules, thresholds, stops, RR, position lock,
market spread, fees, time window, and account-risk assumptions UNCHANGED.

A user-drawn mark is never overwritten. Both models are proxies until a
timestamped manual drawing is supplied; any profit is historical USD/oz only.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path

from research.xau_pa_fidelity_v4 import (
    proxy_zones_repeated,confirm_v4,gate_signals,
)
from research.xau_pa_manual_rules_v3 import (
    causal_signals,parse_mark_file,
)
from research.xau_pa_shared_execution import simulate_shared_quotes
from research.xau_price_action_m1m5 import (
    Settings,SourceQualityError,parse_quotes,candles_from_quotes,simulate_ticks,
)
from research.xau_pa_frequency_v2 import utc_ms


# Locked before viewing any results from these 10 dates.
FEBRUARY=("20260209","20260210","20260211","20260212","20260213")
JULY=("20260720","20260721","20260722","20260723","20260724")
DAYS=FEBRUARY+JULY
ARMS=("v4_fixed","v5_rolling")
COSTS=("standard","double")


def rolling_confirmed_zones(closed_before_signal, candle_start_ms: int, tf: int):
    """Only previous CLOSED bars. No update using the signal candle itself.

    Uses 90 M1 bars or 42 M5 bars as a fixed recent lookback and two
    confirmed swing touches for EACH side, exactly the existing v4 geometry.
    The range must not originate from just one price spike.
    """
    if tf not in (60,300):
        raise ValueError("Only M1 or M5")
    lookback=(90 if tf==60 else 42)
    historic=closed_before_signal[-lookback:]
    if len(historic)<40:
        return None
    if historic[-1]["time"]*1000+tf*1000>candle_start_ms:
        raise ValueError("Future bar supplied to rolling zone provider")
    zone=proxy_zones_repeated(historic,candle_start_ms)
    if zone is not None and zone.source!="proxy":
        raise ValueError("Automatic mark fraudulently tagged user")
    return zone


def signals_for(candles,tf,start,end,*,mode="proxy",lines=(),zones=None):
    if mode not in ("proxy","manual"):
        raise ValueError("Unrecognized mark provenance")
    opts={
        "marking_mode":mode,"manual_lines":lines,"manual_zones":zones,
    }
    fixed,fd=causal_signals(
        candles,tf,start,end,**opts,
        proxy_zones_fn=proxy_zones_repeated if mode=="proxy" else None,
    )
    rolling,rd=causal_signals(
        candles,tf,start,end,**opts,
        proxy_zones_fn=proxy_zones_repeated if mode=="proxy" else None,
        proxy_dynamic_zone_fn=rolling_confirmed_zones if mode=="proxy" else None,
    )
    fixed_accepted,fv=gate_signals(candles,fixed,tf)
    rolling_accepted,rv=gate_signals(candles,rolling,tf)
    # Manual mode intentionally never modifies the provided drawings.
    if mode=="manual" and rolling_accepted!=fixed_accepted:
        raise ValueError("User-supplied marks were altered")
    return {
        "v4_fixed":(fixed_accepted,{**fd,"quality_veto_counts":fv}),
        "v5_rolling":(rolling_accepted,{**rd,"quality_veto_counts":rv}),
    }


def experiment_day(path,day,*,mode="proxy",marks_file=None):
    if day not in DAYS:
        raise ValueError("Day is outside preregistered XAUUSD research panel")
    if mode=="manual" and marks_file is None:
        raise ValueError("Manual drawings are required; do not fake user marks")
    quotes,src=parse_quotes(path,day)
    open_feed=utc_ms(day,9);start=utc_ms(day,12);end=utc_ms(day,21)
    if (quotes[0][0]<open_feed or quotes[0][0]>open_feed+60000 or
        quotes[-1][0]<end-120000 or quotes[-1][0]>end+59999):
        raise SourceQualityError("Whole session missing quote coverage")
    trade_quotes=[q for q in quotes if start<=q[0]<end]
    if len(trade_quotes)<1500 or trade_quotes[0][0]>start+60000:
        raise SourceQualityError("Trading quote tape too short")
    base=Settings()
    stress=replace(base,commission_roundtrip_usd_per_oz=.60,
                   slippage_usd_each_market_side=.20)
    groups={name:[] for name in ARMS}
    scores={}
    for seconds,tf in ((60,"M1"),(300,"M5")):
        bars=candles_from_quotes(quotes,seconds)
        if len(bars)<(360 if seconds==60 else 110):
            raise SourceQualityError("Incomplete timeframe source history")
        lines,zones=(parse_mark_file(marks_file,day,seconds,start,bars)
                     if mode=="manual" else ((),None))
        variants=signals_for(bars,seconds,start,end,
                             mode=mode,lines=lines,zones=zones)
        scores[tf]={}
        for name,(signals,reasons) in variants.items():
            groups[name].extend(signals)
            row={
                "signals":len(signals),
                "setups":dict(sorted(Counter(x["setup"] for x in signals).items())),
                "reasons":reasons,"costs":{},
            }
            for cost,cfg in (("standard",base),("double",stress)):
                result=simulate_ticks(trade_quotes,signals,seconds,cfg)
                if result["signals"]!=len(signals):
                    raise ValueError("Unverifiable signal ledger")
                row["costs"][cost]=result
            scores[tf][name]=row
    scores["SHARED"]={}
    for name,signals in groups.items():
        result={"signals":len(signals),
                "setups":dict(sorted(Counter(x["setup"] for x in signals).items())),
                "reasons":{"one_global_position":True},
                "costs":{}}
        for cost,cfg in (("standard",base),("double",stress)):
            e=simulate_shared_quotes(trade_quotes,signals,cfg)
            if e["filled"]>result["signals"]:
                raise ValueError("Shared engine invented a fill")
            result["costs"][cost]=e
        scores["SHARED"][name]=result
    return {
        "day":day,"source":src,"source_mark_mode":mode,
        "manual_drawings_reproduced":False,
        "same_quotes_and_exec_for_both_arms":True,
        "one_shared_XAUUSD_position":True,
        "not_a_mt5_broker_feed":True,
        "approved_for_real_trades":False,
        "warming_period_utc":"09:00-12:00",
        "trading_period_utc":"12:00-21:00",
        "experiment":"One causal rolling S/R update vs fixed-open zone. LTA/LTD unchanged.",
        "results":scores,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--ticks",required=True)
    p.add_argument("--day",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--quarantine",required=True)
    p.add_argument("--mode",choices=("proxy","manual"),default="proxy")
    p.add_argument("--manual-marks")
    args=p.parse_args()
    try:
        out=experiment_day(args.ticks,args.day,mode=args.mode,
                           marks_file=args.manual_marks)
    except SourceQualityError as error:
        data={"day":args.day,"whole_source_quarantined":True,
              "reason":str(error),"included_fills":0}
        target=Path(args.quarantine);target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
        print("WHOLE XAU SESSION QUARANTINED",args.day,error)
        return
    path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    for tf,row in out["results"].items():
        for policy,v in row.items():
            s=v["costs"]["double"]
            print("V5",args.day,tf,policy,
                  "signals",v["signals"],"fills",s["filled"],
                  "wins",s["wins"],"losses",s["losses"],
                  "net_usd_per_oz",s["net_usd_per_oz"])


if __name__=="__main__":
    main()
