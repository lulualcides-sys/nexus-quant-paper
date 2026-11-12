"""Gold PA test: warm up indicators from 09:00 UTC, trade 12:00-17:00.

COLD CONTROL: only see 12:00-17:00 quotes, matching historical short-window
experiments. WARM: see 09:00-12:00 strictly as past indicator initialization,
never place trades before 12:00. The same post-noon quotes execute both cases.

One additional QUALITY arm can quantify the separately frozen signal-candle
veto. It is NOT a profitable or broker-approved setting by default.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime,timezone
from pathlib import Path

from research.xau_price_action_m1m5 import (
    Settings,SourceQualityError,parse_quotes,candles_from_quotes,
    scan_signals,simulate_ticks,
)
from research.xau_pa_quality_experiment import quality_veto


MARCH=(
 "20260309","20260310","20260311","20260312","20260313",
 "20260316","20260317","20260318","20260319","20260320",
)
OCTOBER=(
 "20261012","20261013","20261014","20261015","20261016",
 "20261019","20261020","20261021","20261022","20261023",
)
DAYS=MARCH+OCTOBER
ARMS=("cold_control","warm_control","warm_quality")
COSTS=("standard","double")


def at_ms(day: str,hr: int) -> int:
    year=int(day[:4]);month=int(day[4:6]);d=int(day[6:])
    return int(datetime(year,month,d,hr,tzinfo=timezone.utc).timestamp()*1000)


def one_day(filepath: str|Path,day: str):
    if day not in DAYS: raise ValueError("Date must be preregistered")
    all_quotes,source=parse_quotes(filepath,day)
    start=at_ms(day,9);trade_start=at_ms(day,12);end=at_ms(day,17)
    if (all_quotes[0][0]<start or all_quotes[-1][0]>end+59999 or
        all_quotes[0][0]>start+60000 or all_quotes[-1][0]<end-120000):
        raise SourceQualityError("Incomplete 09-17 UTC source coverage")
    cold=[row for row in all_quotes if trade_start<=row[0]<end]
    # Important: even warm scenarios trade only on exactly the same 12-17 tape.
    if len(cold)<1500 or cold[0][0]>trade_start+60000:
        raise SourceQualityError("Missing comparable 12-17 UTC quote window")
    cfg=Settings()
    from dataclasses import replace
    stressed=replace(cfg,commission_roundtrip_usd_per_oz=.60,
                     slippage_usd_each_market_side=.20)
    results={}
    for tf,label in ((60,"M1"),(300,"M5")):
        b_cold=candles_from_quotes(cold,tf)
        b_warm=candles_from_quotes(all_quotes,tf)
        # Eight hours contain 480 M1 bars, but only 96 M5 bars.
        # Apply a timeframe-aware coverage gate; 100 M5 would reject
        # every correctly captured full session.
        min_warm=(300 if tf==60 else 90)
        if len(b_cold)<50 or len(b_warm)<min_warm:
            raise SourceQualityError("Too few complete candles for indicator warmup")
        cold_signals=scan_signals(b_cold,tf,cfg)
        full_signals=scan_signals(b_warm,tf,cfg)
        # Signals formed at or after 12 UTC; no trading in the warmup.
        warm_signals=[s for s in full_signals
                      if trade_start<=s["eligible_ms"]<end]
        filtered=quality_veto(b_warm,warm_signals,tf)
        plans={
            "cold_control":cold_signals,
            "warm_control":warm_signals,
            "warm_quality":filtered,
        }
        results[label]={}
        for arm,signals in plans.items():
            # identical quote feed for entries/exits, regardless of warmup.
            scenarios={}
            for cost,settings in (("standard",cfg),("double",stressed)):
                backtest=simulate_ticks(cold,signals,tf,settings)
                if backtest["filled"]>backtest["signals"]:
                    raise ValueError("Position count exceeds confirmed signals")
                scenarios[cost]=backtest
            results[label][arm]={
                "signals":len(signals),
                "costs":scenarios
            }
        if results[label]["warm_quality"]["signals"]>results[label]["warm_control"]["signals"]:
            raise ValueError("Quality gate fabricated extra entries")
    return {
        "day":day,"source":source,
        "warmup_start_utc":"09:00",
        "execution_start_utc":"12:00",
        "execution_end_utc":"17:00",
        "same_execution_tape_for_all_arms":True,
        "price_action_parameters_unchanged":True,
        "extra_quality_gate_predeclared":True,
        "broker_verified":False,
        "approved_for_live":False,
        "units":"simulated USD per theoretical ounce",
        "results":results,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--ticks",required=True)
    p.add_argument("--day",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--quarantine",required=True)
    a=p.parse_args()
    try:
        record=one_day(a.ticks,a.day)
    except SourceQualityError as ex:
        item={"day":a.day,"fully_excluded":True,"reason":str(ex),
              "counted_operations":0}
        destination=Path(a.quarantine);destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(json.dumps(item,indent=2)+"\n",encoding="utf-8")
        print("WARMUP QUARANTINE",a.day,ex)
        return
    path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(record,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    for tf,row in record["results"].items():
        for arm,stats in row.items():
            d=stats["costs"]["double"]
            print("WARMUP",a.day,tf,arm,"signals",stats["signals"],
                  "fills",d["filled"],"netUSDperOz",d["net_usd_per_oz"],
                  "PF",d["profit_factor"])


if __name__=="__main__":
    main()
