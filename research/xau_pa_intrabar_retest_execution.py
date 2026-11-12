"""Gold Price Action: execute the SAME LTA/LTD break-and-retest sooner.

NOT a new indicator, not a new direction strategy, and not a profitability
filter. Existing confirmed LTA/LTD + candle breakout are unchanged:
A) mark line using only two ALREADY CONFIRMED prior pivots;
B) a completed M1 candle must close through that marked line;
C) subsequent live BID ticks must touch that same line, then REACT
   away in the breakout direction;
D) submit on the NEXT tick, never on the detecting tick and never
   retroactively at the best price in the already-seen candle.

Compared with prior implementation which waits until an entire retest
candle closes, this tests whether entering after the observed reaction,
near the line, prevents chasing the move. No hindsight, no order live.

Unconfirmed assumption: 0.08 ATR move away from the line. It corresponds
to the existing technical retest tolerance and is NOT claimed to be the
user's own exact intrabar entry rule. Report negative outcomes too.
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
from research.xau_pa_manual_rules_v3 import proxy_line,line_crossed
from research.xau_pa_m5_context_m1_v6 import utc_ms
from research.xau_pa_stop_geometry_audit import replay_signals
from research.xau_pa_m5_context_m1_v6 import evaluate_day as v6_day

# Dates deliberately different from June22-26 / July27-31 forensic analysis.
MAY=("20260518","20260519","20260520","20260521","20260522")
OCT=("20260928","20260929","20260930","20261001","20261002")
DAYS=MAY+OCT
ARMS=("close_of_retest_market_entry","after_intrabar_retest_reaction")
COSTS=("standard","double")


def observed_breakouts(bars,trade_start,trade_end):
    """All candidate breakouts depend ONLY on completed M1 OHLC and pivots.

    Scan complete bars only (exclude last possibly unfinished source bar).
    A candidate is visible at its M1 close, never before.
    """
    out=[]
    for i in range(35,len(bars)-1):
        b=bars[i]
        eligible=(b["time"]+60)*1000
        if not trade_start<=eligible<trade_end:continue
        rng=atr(bars,i,14)
        if rng is None or rng<=0:continue
        for kind in ("LTD","LTA"):
            line=proxy_line(bars,i-1,60,kind)
            if line is None or line.x2>=i-2:continue
            if abs(b["close"]-line.value(i))>2.5*rng:
                continue
            if not line_crossed(bars[i-1],b,line,i,rng):
                continue
            out.append({
                "known_ms":eligible,"index":i,"line":line,
                "side":1 if kind=="LTD" else -1,"atr":rng,
                "kind":kind,
            })
            break  # One breakout direction per completed bar.
    return sorted(out,key=lambda x:x["known_ms"])


def reactive_retest_signals(quotes,bars,trade_start,trade_end):
    """Causal single-state event stream. No pre-entry future candle values.

    Quotes ordered by ms. A closed breakout may create ONE pending retest;
    an invalidated completed candle or 8-minute expiry cancels it. Both
    price contact and a later favorable BID movement are required.
    """
    events=observed_breakouts(bars,trade_start,trade_end)
    closes=[(b["time"]+60)*1000 for b in bars]
    mapped={b["time"]:i for i,b in enumerate(bars)}
    signals=[];counts=Counter()
    current=None;pos=0;last_fired=-100000000
    last_bid=None;last_closed_checked=-1
    for ms,bid,ask in quotes:
        if ms<trade_start or ms>=trade_end:
            last_bid=bid
            continue
        while pos<len(events) and events[pos]["known_ms"]<=ms:
            e=events[pos];pos+=1
            if current is not None:
                counts["breakout_ignored_during_retest"]+=1
                continue
            if ms-last_fired<3*60000:
                counts["cooldown"]+=1
                continue
            current={
                **e,"touch_ms":None,
                "touch_min":float("inf"),"touch_max":float("-inf"),
                "last_checked_closed":e["index"],
            }
            counts["breakout_wait_retest"]+=1
        if current is None:
            last_bid=bid
            continue
        e=current
        if ms-e["known_ms"]>8*60000:
            counts["retest_expired"]+=1
            current=None;last_bid=bid
            continue
        # A bar is closed only if its end has passed CURRENT observed tick.
        upto=bisect_right(closes,ms)-1
        for j in range(max(e["last_checked_closed"]+1,e["index"]+1),upto+1):
            line_j=e["line"].value(j)
            if e["side"]*(bars[j]["close"]-line_j)<-.25*e["atr"]:
                current=None;counts["close_invalidated_line"]+=1
                break
        if current is None:
            last_bid=bid
            continue
        e["last_checked_closed"]=max(e["last_checked_closed"],upto)
        # Current tick only selects the M1 candle INDEX; it never loads its
        # precomputed future OHLC, only the frozen breakout ATR/line.
        minute=(ms//60000)*60
        i=mapped.get(minute)
        if i is None or i<=e["index"]:
            last_bid=bid;continue
        line_px=e["line"].value(i)
        tolerance=.24*e["atr"]
        if e["touch_ms"] is None:
            if abs(bid-line_px)<=tolerance:
                e["touch_ms"]=ms
                e["touch_min"]=bid
                e["touch_max"]=bid
                counts["retouched_line"]+=1
        else:
            e["touch_min"]=min(e["touch_min"],bid)
            e["touch_max"]=max(e["touch_max"],bid)
            # Price must first touch then visibly turn away in a new quote.
            if ms>e["touch_ms"] and last_bid is not None:
                reaction=.08*e["atr"]
                turned=(e["side"]*(bid-last_bid)>0 and
                        e["side"]*(bid-line_px)>=reaction and
                        e["side"]*(bid-(e["touch_min"] if e["side"]==1
                                         else e["touch_max"]))>=reaction)
                if turned:
                    stop=(min(e["touch_min"],line_px-.10*e["atr"]) if e["side"]==1
                          else max(e["touch_max"],line_px+.10*e["atr"]))
                    signals.append({
                        "setup":"break_retest",
                        "side":e["side"],
                        "stop":stop,"atr":e["atr"],
                        "signal_ms":ms,
                        "eligible_ms":ms+1,
                        "timeframe_seconds":60,
                        "breakout_ms":bars[e["index"]]["time"]*1000,
                        "line_kind":e["kind"],"line_source":"proxy",
                        "line_retest_level":round(line_px,6),
                        "line_anchor_indices":[e["line"].x1,e["line"].x2],
                        "line_anchor_prices":[e["line"].y1,e["line"].y2],
                        "touch_ms":e["touch_ms"],
                        "trigger_quote_ms":ms,
                        "execution_assumption":"next quote after observed reaction",
                    })
                    last_fired=ms
                    counts["intrabar_reaction_signal"]+=1
                    current=None
        last_bid=bid
    counts["signals_emitted"]=len(signals)
    if any(s["breakout_ms"]>=s["touch_ms"] or
           s["touch_ms"]>=s["signal_ms"] or
           s["eligible_ms"]<=s["signal_ms"]
           for s in signals):
        raise ValueError("Non-causal breakout/retest/reaction chronology")
    return signals,dict(sorted(counts.items()))


def day_study(path,day):
    if day not in DAYS:
        raise ValueError("Historical research days are preregistered")
    quotes,source=parse_quotes(path,day)
    feed_start=utc_ms(day,9);start=utc_ms(day,12);end=utc_ms(day,21)
    if (quotes[0][0]>feed_start+60000 or
        quotes[-1][0]<end-120000 or quotes[-1][0]>end+59999):
        raise SourceQualityError("Missing complete source period")
    execution=[q for q in quotes if start<=q[0]<end]
    if len(execution)<1500 or execution[0][0]>start+60000:
        raise SourceQualityError("Insufficient comparable execution ticks")
    bars=candles_from_quotes(quotes,60)
    if len(bars)<350:raise SourceQualityError("Insufficient M1 candle history")
    # Both are the same *concept* (confirmed LTA/LTD -> real retest).
    # Original benchmark uses the already existing strategy engine as-is.
    original=replay_signals(quotes,day)
    reactive_breaks,reason=reactive_retest_signals(execution,bars,start,end)
    # Preserve all RANGE decisions from the v6 reference unchanged.
    # This comparison only alters the entry timing of LTA/LTD break/retest.
    unchanged_ranges=[s for s in original if s["setup"]=="range_rejection"]
    reactive=sorted(reactive_breaks+unchanged_ranges,
                    key=lambda s:s["eligible_ms"])
    if any(x["eligible_ms"]==y["eligible_ms"]
           for x,y in zip(reactive,reactive[1:])):
        raise ValueError("Cannot resolve simultaneous range and retest entries")
    reason["unchanged_range_signals_carried_over"]=len(unchanged_ranges)
    settings=Settings()
    doubled=replace(settings,commission_roundtrip_usd_per_oz=.60,
                    slippage_usd_each_market_side=.20)
    outcomes={}
    for label,signs in zip(ARMS,(original,reactive)):
        result={"signals":len(signs),
                "signal_setups":dict(sorted(Counter(s["setup"] for s in signs).items())),
                "costs":{}}
        for cost,options in (("standard",settings),("double",doubled)):
            test=simulate_ticks(execution,signs,60,options)
            result["costs"][cost]=test
        outcomes[label]=result
    return {
        "day":day,"source":source,
        "same_BID_ASK_execution_quotes":True,
        "same_stop_target_cost_rules":True,
        "causal_intrabar_reaction_only":True,
        "user_manual_levels_verified":False,
        "exact_manual_entry_timing_verified":False,
        "not_MT5_broker_execution":True,
        "approved_for_live":False,
        "trading_utc":"12:00-21:00",
        "warmup_utc":"09:00-12:00",
        "retest_event_counters":reason,
        "results":outcomes,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--ticks",required=True)
    p.add_argument("--day",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--quarantine",required=True)
    a=p.parse_args()
    try:
        r=day_study(a.ticks,a.day)
    except SourceQualityError as exc:
        q={"day":a.day,"full_day_quarantine":True,"trades_counted":0,
           "reason":str(exc)}
        f=Path(a.quarantine);f.parent.mkdir(parents=True,exist_ok=True)
        f.write_text(json.dumps(q,indent=2)+"\n")
        print("QUARANTINE",a.day,exc)
        return
    f=Path(a.out);f.parent.mkdir(parents=True,exist_ok=True)
    f.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
    for name,item in r["results"].items():
        x=item["costs"]["double"]
        print("INTRABAR_PA",a.day,name,"signals",x["signals"],
              "fills",x["filled"],"wins",x["wins"],"losses",x["losses"],
              "net_USD_oz",x["net_usd_per_oz"])
    print("INTRABAR_EVENT_AUDIT",r["retest_event_counters"])


if __name__=="__main__":
    main()
