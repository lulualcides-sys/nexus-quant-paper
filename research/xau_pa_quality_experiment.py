"""Frozen quality-of-entry hypothesis for XAUUSD Price Action M1/M5.

CONTROL: unchanged signal detector and tick-by-tick execution in
research.xau_price_action_m1m5.

QUALITY_V1: filter the SAME completed-bar price-action signals by candlestick
rejection shape and extreme volatility BEFORE placing the next-quote market
order. This is a veto, not a new/original commercial Tracker signal.
No tuning or variant selection based on the sample being evaluated.
All outcomes are USD per hypothetical single troy ounce, not real-account PnL.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path

from research.xau_price_action_m1m5 import (
    Settings,SourceQualityError,parse_quotes,candles_from_quotes,
    scan_signals,simulate_ticks
)

# Ex ante fixed. These values were not fitted on July or September test dates.
FIRST = ("20260706","20260707","20260708","20260709","20260710",
         "20260713","20260714","20260715","20260716","20260717")
SECOND = ("20260907","20260908","20260909","20260910","20260911",
          "20260914","20260915","20260916","20260917","20260918")
DAYS = FIRST + SECOND

MODES=("control","quality_v1")
COSTS=("standard","double")


def pass_quality(bar: dict, signal: dict, tf: int) -> bool:
    """OHLC and quote count of the signal bar only; no future state."""
    if signal["timeframe_seconds"] != tf or bar["time"]*1000 != signal["signal_ms"]:
        raise ValueError("Signal/candle mismatch; cannot inspect a future bar")
    if signal["side"] not in (1,-1):
        raise ValueError("Invalid signal side")
    if signal["setup"] not in ("break_retest","range_rejection"):
        raise ValueError("Unknown setup")
    height=float(bar["high"])-float(bar["low"])
    reference=float(signal["atr"])
    if height<=0 or reference<=0:
        return False
    if not .40<=height/reference<=2.50:
        return False
    if bar.get("quote_updates",0) < (15 if tf==60 else 25):
        return False
    op=float(bar["open"]);cl=float(bar["close"])
    body=abs(cl-op)/height
    close_loc=(cl-float(bar["low"]))/height
    side=int(signal["side"])
    if signal["setup"]=="break_retest":
        # Strong follow-through after a retest at the prior microtrendline.
        return body >= .45 and (close_loc >= .70 if side==1 else close_loc<=.30)
    # Rejection must actually show a wick on the side of the touched edge.
    wick=(min(op,cl)-float(bar["low"]) if side==1 else
          float(bar["high"])-max(op,cl))/height
    return (wick>=.35 and body>=.16 and
            (close_loc>=.68 if side==1 else close_loc<=.32))


def quality_veto(bars: list[dict], signals: list[dict], tf: int):
    by_timestamp={bar["time"]*1000:bar for bar in bars}
    accepted=[]
    for signal in signals:
        candle=by_timestamp.get(signal["signal_ms"])
        if candle is None:
            raise ValueError("Signal not in historical source")
        if pass_quality(candle,signal,tf):
            accepted.append(signal)
    return accepted


def run_day(path: str | Path, day: str) -> dict:
    if day not in DAYS:
        raise ValueError("Only fixed dates, never dynamically selected winners")
    quotes,source=parse_quotes(path,day)
    base=Settings()
    double=replace(base,
       commission_roundtrip_usd_per_oz=2*base.commission_roundtrip_usd_per_oz,
       slippage_usd_each_market_side=2*base.slippage_usd_each_market_side)
    experiments={}
    for tf,label in ((60,"M1"),(300,"M5")):
        bars=candles_from_quotes(quotes,tf)
        if len(bars)<50:
            raise SourceQualityError("Missing XAUUSD source candles")
        original=scan_signals(bars,tf,base)
        approved=quality_veto(bars,original,tf)
        experiments[label]={}
        for mode,signals in (("control",original),("quality_v1",approved)):
            cost_scenarios={}
            for name,cfg in (("standard",base),("double",double)):
                x=simulate_ticks(quotes,signals,tf,cfg)
                cost_scenarios[name]=x
            if cost_scenarios["standard"]["filled"]!=cost_scenarios["double"]["filled"]:
                raise ValueError("Cost assumptions mysteriously altered fills")
            if (cost_scenarios["double"]["net_usd_per_oz"]>
                    cost_scenarios["standard"]["net_usd_per_oz"]+1e-5):
                raise ValueError("Higher transaction costs increased PnL")
            experiments[label][mode]={
                "signals":len(signals),"costs":cost_scenarios,
            }
        if experiments[label]["quality_v1"]["signals"]>experiments[label]["control"]["signals"]:
            raise ValueError("Quality veto created artificial trades")
    return {
      "day":day,"source":source,
      "modes":experiments,
      "parameters":{
          "control":"Original XAU Price Action M1/M5 (no changes)",
          "quality_v1":"Signal-candle close strength/wick+range-to-ATR+quote-update threshold",
          "standard":{"commission":base.commission_roundtrip_usd_per_oz,
                      "market_side_slippage":base.slippage_usd_each_market_side},
          "double":{"commission":double.commission_roundtrip_usd_per_oz,
                    "market_side_slippage":double.slippage_usd_each_market_side},
      },
      "broker_mt5_account_verification":False,
      "auto_order_execution":False,
      "approved_for_live":False,
      "units":"USD per one theoretical ounce, NOT account, lots or BRL",
    }


def cli():
    p=argparse.ArgumentParser()
    p.add_argument("--ticks",required=True)
    p.add_argument("--day",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--quarantine-out",required=True)
    args=p.parse_args()
    try:
        data=run_day(args.ticks,args.day)
    except SourceQualityError as err:
        item={"day":args.day,"whole_day_quarantined":True,
              "reason":str(err),"trades_included":0}
        target=Path(args.quarantine_out)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(item,indent=2)+"\n")
        print("QUALITY QUARANTINE",args.day,str(err))
        return
    target=Path(args.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n")
    for tf,v in data["modes"].items():
        for mode,row in v.items():
            sample=row["costs"]["double"]
            print("PA QUALITY",args.day,tf,mode,"signals",row["signals"],
                  "fills",sample["filled"],"net-double",sample["net_usd_per_oz"],
                  "PF",sample["profit_factor"])


if __name__=="__main__":
    cli()
