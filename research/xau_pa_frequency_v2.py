"""XAUUSD Price Action v2: three *distinct* higher-frequency research setups.

This is NOT a loosening of the accepted WIN bot or a replica of Greenhouse.
The former trendline breakout detector required multiple rare consecutive
pivot and regime conditions. Here we compare exactly four FIXED alternatives:
  baseline          - existing untouched warm Price Action
  structural        - recent horizontal level breakout + completed-bar retest
  pullback          - EMA9/EMA21 trend + genuine rejection of pullback
  combined          - union, with min 3-bar signal spacing, no double entries

The first 3h are history only. Entries may occur 12:00-21:00 UTC, on the
first later quote; no pre-noon signal, fills on ASK/BID with actual spread and
adverse costs. Never equate signal count, profitability, or account PnL.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict,replace
from datetime import datetime,timezone
import json
from pathlib import Path

from research.xau_price_action_m1m5 import (
    Settings,SourceQualityError,parse_quotes,candles_from_quotes,
    atr,scan_signals,simulate_ticks
)

# Hypotheses fixed BEFORE examining the new April / August price feeds.
APRIL=("20260406","20260407","20260408","20260409","20260410",
       "20260413","20260414","20260415","20260416","20260417")
AUGUST=("20260803","20260804","20260805","20260806","20260807",
        "20260810","20260811","20260812","20260813","20260814")
DAYS=APRIL+AUGUST
ARMS=("baseline","structural","pullback","combined")
COSTS=("standard","double")


def utc_ms(day: str, hour: int) -> int:
    return int(datetime(int(day[:4]),int(day[4:6]),int(day[6:]),hour,
                        tzinfo=timezone.utc).timestamp()*1000)


def moving_average(bars, upto: int, period: int):
    """EMA of only complete bars through upto, never using the next candle."""
    if period<2 or upto<period-1:
        return None
    value=sum(b["close"] for b in bars[:period])/period
    k=2/(period+1)
    for j in range(period,upto+1):
        value=k*bars[j]["close"]+(1-k)*value
    return value


def _make_signal(bars,i,tf,side,stop,rng,setup,**details):
    b=bars[i]
    return {"setup":setup,"side":side,"stop":stop,"atr":rng,
            "signal_ms":b["time"]*1000,
            "eligible_ms":(b["time"]+tf)*1000,
            "timeframe_seconds":tf,**details}


def structural_candidate(bars,i,tf):
    """Break a horizontal 12-bar level, then revisit it 1-4 candles later.

    Prior breakout and level are derived from closed candles strictly older
    than the retest. Rejection candle must close on breakout side.
    """
    if i<35:return None
    rng=atr(bars,i,14)
    if not rng or rng<=0:return None
    last=bars[i]
    for k in range(i-1,max(20,i-5),-1):
        previous=bars[k-12:k]
        if len(previous)!=12:continue
        c=bars[k]
        top=max(b["high"] for b in previous)
        bottom=min(b["low"] for b in previous)
        for side,level in ((1,top),(-1,bottom)):
            if side==1:
                breakout=(c["close"]>level+.08*rng and
                          c["close"]>c["open"] and
                          c["close"]<=level+1.6*rng)
                stayed=all(bars[t]["close"]>level-.30*rng for t in range(k+1,i))
                retest=(level-.28*rng<=last["low"]<=level+.35*rng and
                        last["close"]>level+.08*rng and
                        last["close"]>last["open"])
                stop=min(last["low"],level-.22*rng)-.10*rng
            else:
                breakout=(c["close"]<level-.08*rng and
                          c["close"]<c["open"] and
                          c["close"]>=level-1.6*rng)
                stayed=all(bars[t]["close"]<level+.30*rng for t in range(k+1,i))
                retest=(level-.35*rng<=last["high"]<=level+.28*rng and
                        last["close"]<level-.08*rng and
                        last["close"]<last["open"])
                stop=max(last["high"],level+.22*rng)+.10*rng
            if breakout and stayed and retest:
                return _make_signal(bars,i,tf,side,stop,rng,
                                    "level_break_retest",breakout_ms=c["time"]*1000,
                                    broken_level=round(level,5))
    return None


def pullback_candidate(bars,i,tf):
    """EMA-aligned continuation only after actual touch and recovery.

    EMA9/EMA21 from *the same completed timeframe*, with previous EMA9
    direction and rejection candle. Never buys simply for being above EMA.
    """
    if i<32:return None
    b=bars[i];rng=atr(bars,i,14)
    if not rng or rng<=0:return None
    fast=moving_average(bars,i-1,9)
    slow=moving_average(bars,i-1,21)
    fast_prior=moving_average(bars,i-3,9)
    if fast is None or slow is None or fast_prior is None:return None
    if abs(fast-slow)<.15*rng:return None
    size=b["high"]-b["low"]
    if not .45*rng<=size<=2.50*rng:return None
    close_pos=(b["close"]-b["low"])/size
    if (fast>slow and fast>fast_prior+.035*rng and
        b["low"]<=fast+.20*rng and
        b["low"]>=fast-1.25*rng and
        b["close"]>=fast+.15*rng and
        b["close"]>b["open"] and close_pos>=.64):
        stop=b["low"]-.10*rng
        return _make_signal(bars,i,tf,1,stop,rng,"ema_pullback",
                            reference_ema=round(fast,5))
    if (fast<slow and fast<fast_prior-.035*rng and
        b["high"]>=fast-.20*rng and
        b["high"]<=fast+1.25*rng and
        b["close"]<=fast-.15*rng and
        b["close"]<b["open"] and close_pos<=.36):
        stop=b["high"]+.10*rng
        return _make_signal(bars,i,tf,-1,stop,rng,"ema_pullback",
                            reference_ema=round(fast,5))
    return None


def signals_v2(bars,tf,settings):
    """All source candles except the final potentially incomplete one."""
    candidates={"baseline":scan_signals(bars,tf,settings),
                "structural":[],"pullback":[],"combined":[]}
    last_combined_index=-100
    for i in range(len(bars)-1):
        s=structural_candidate(bars,i,tf)
        p=pullback_candidate(bars,i,tf)
        if s is not None:candidates["structural"].append(s)
        if p is not None:candidates["pullback"].append(p)
        if i-last_combined_index>=3 and (s is not None or p is not None):
            # Prefer stricter explicit breakout/retest over the EMA pullback.
            candidates["combined"].append(s if s is not None else p)
            last_combined_index=i
    return candidates


def experiment_day(path: str|Path,day: str):
    if day not in DAYS:raise ValueError("Only predeclared historical test sessions")
    quotes,source=parse_quotes(path,day)
    start=utc_ms(day,9);trade_start=utc_ms(day,12);end=utc_ms(day,21)
    if (quotes[0][0]<start or quotes[-1][0]>end+59999 or
        quotes[0][0]>start+60000 or quotes[-1][0]<end-120000):
        raise SourceQualityError("Incomplete 09-21 UTC quote coverage")
    trading=[q for q in quotes if trade_start<=q[0]<end]
    if len(trading)<1500 or trading[0][0]>trade_start+60000:
        raise SourceQualityError("Incomplete comparable execution tape")
    cfg=Settings()
    stressed=replace(cfg,
        commission_roundtrip_usd_per_oz=.60,
        slippage_usd_each_market_side=.20)
    frames={}
    for tf,label in ((60,"M1"),(300,"M5")):
        bars=candles_from_quotes(quotes,tf)
        if len(bars)<(360 if tf==60 else 110):
            raise SourceQualityError("Not enough complete candles for both timeframes")
        pools=signals_v2(bars,tf,cfg)
        frames[label]={}
        for mode in ARMS:
            # Signals generated from the 09-12 period NEVER become orders.
            signals=[s for s in pools[mode]
                     if trade_start<=s["eligible_ms"]<end]
            item={"signals":len(signals),"setups":{},"costs":{}}
            for s in signals:
                name=s["setup"]
                item["setups"][name]=item["setups"].get(name,0)+1
            for cost,opts in (("standard",cfg),("double",stressed)):
                outcome=simulate_ticks(trading,signals,tf,opts)
                if outcome["signals"]!=len(signals):
                    raise ValueError("Signal mismatch after quote execution")
                if any(t["entry_ms"]<trade_start or t["entry_ms"]>=end
                       for t in outcome["trades"]):
                    raise ValueError("Trade outside predeclared session")
                item["costs"][cost]=outcome
            frames[label][mode]=item
        if (frames[label]["combined"]["signals"] >
            frames[label]["structural"]["signals"]+
            frames[label]["pullback"]["signals"]):
            raise ValueError("Combined duplicated or invented signals")
    return {
        "day":day,"source":source,
        "independent_price_action_hypotheses":True,
        "historical_not_forward_trading":True,
        "identical_execution_bid_ask_tape":True,
        "train_history_utc":"09:00-12:00",
        "trade_window_utc":"12:00-21:00",
        "costs":"standard 0.30+0.10 each market side; double 0.60+0.20 each market side USD/oz plus spread",
        "original_win_bot_unchanged":True,
        "connected_broker_validated":False,
        "live_approval":False,
        "USD_per_one_theoretical_ounce":True,
        "arms":frames,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--ticks",required=True)
    ap.add_argument("--day",required=True)
    ap.add_argument("--out",required=True)
    ap.add_argument("--quarantine",required=True)
    args=ap.parse_args()
    try:
        record=experiment_day(args.ticks,args.day)
    except SourceQualityError as exc:
        row={"day":args.day,"whole_day_excluded":True,
             "reason":str(exc),"included_trades":0}
        dest=Path(args.quarantine);dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(row,indent=2)+"\n")
        print("PA V2 FULL DAY QUARANTINE",args.day,exc)
        return
    target=Path(args.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n")
    print("DAY",args.day,"QUOTES",record["source"]["raw_quote_rows"],
          "SHA",record["source"]["sha256"])
    for tf,variants in record["arms"].items():
        for mode,v in variants.items():
            sim=v["costs"]["double"]
            print("PA_V2",args.day,tf,mode,"signals",v["signals"],
                  "fills",sim["filled"],"wins",sim["wins"],
                  "losses",sim["losses"],"net_USD_per_oz",sim["net_usd_per_oz"])


if __name__=="__main__":
    main()
