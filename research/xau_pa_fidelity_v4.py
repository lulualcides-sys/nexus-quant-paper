"""XAUUSD PA v4 — conservative, causally marked, faithful-structure research.

This is NOT a claim of reproducing user's hand-drawn S/R, LTA/LTD.
The manual mode requires prior timestamped user marks; the proxy mode only
approximates marked levels using repeated, CONFIRMED swing touches before
session trading. No EMA or magic profit indicator.

FROZEN NEW HYPOTHESIS (not tuned on new evaluation dates):
* swing S/R must have >=2 confirmed touches per side, not arbitrary session
  extrema (which could be one aberrant tick);
* breakout must be a real displaced closed candle through LTA/LTD;
* retest must form a visible rejection and close on the correct side;
* one breakout attempt per marked pivot-line anchor pair to avoid re-firing
  identical drawings. Ranges may bounce repeatedly, at least 6 M1 / 3 M5
  bars between same-direction attempts.

Execution uses ORIGINAL quote engine and separate global one-symbol lock,
same BID/ASK, costs, stop/red, target/win, and no future ticks.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path

from research.xau_price_action_m1m5 import (
    Settings,SourceQualityError,atr,candles_from_quotes,parse_quotes,
    simulate_ticks,
)
from research.xau_pa_manual_rules_v3 import (
    MarkedZones,causal_signals,parse_mark_file,one_day as old_day
)
from research.xau_pa_shared_execution import simulate_shared_quotes
from research.xau_pa_frequency_v2 import utc_ms


SEPTEMBER=("20260921","20260922","20260923","20260924","20260925")
OCTOBER=("20261005","20261006","20261007","20261008","20261009")
DAYS=SEPTEMBER+OCTOBER
ARMS=("v3_baseline","v4_confirmed")
COSTS=("standard","double")


def _confirmed_swing_marks(bars,kind):
    """A swing at index j needs two bars of future *within pretrade history*."""
    index="low" if kind=="support" else "high"
    result=[]
    for j in range(2,len(bars)-2):
        price=bars[j][index]
        neighbors=[bars[k][index] for k in (j-2,j-1,j+1,j+2)]
        if (price<min(neighbors) if kind=="support" else price>max(neighbors)):
            result.append((j,price))
    return result


def _cluster_touch(swing_list,atru):
    """Newest two confirmed, separated touches of a nearby marked region."""
    for j in range(len(swing_list)-1,0,-1):
        end,price=swing_list[j]
        for i in range(j-1,-1,-1):
            start,other=swing_list[i]
            if end-start<5:
                continue
            if end-start>90:
                break
            if abs(price-other)<=.40*atru:
                return (price,other)
    return None


def proxy_zones_repeated(pretrade_bars,trade_start_ms):
    """Zone created only at trade start, using two confirmed touches per side."""
    if len(pretrade_bars)<40:return None
    r=atr(pretrade_bars,len(pretrade_bars)-1,14)
    if not r or r<=0:return None
    low_pair=_cluster_touch(_confirmed_swing_marks(pretrade_bars,"support"),r)
    high_pair=_cluster_touch(_confirmed_swing_marks(pretrade_bars,"resistance"),r)
    if low_pair is None or high_pair is None:return None
    low=min(low_pair)-.08*r
    low_top=max(low_pair)+.10*r
    high_bottom=min(high_pair)-.10*r
    high=max(high_pair)+.08*r
    if high_bottom-low_top<1.5*r:return None
    region=MarkedZones(
        low,low_top,high_bottom,high,trade_start_ms,"proxy"
    )
    region.validate(trade_start_ms)
    return region


def confirm_v4(bars,signal):
    """Ex-ante rejection and breakout quality; only completed signal candles."""
    tf=signal["timeframe_seconds"]
    ix={bar["time"]*1000:i for i,bar in enumerate(bars)}
    i=ix.get(signal["signal_ms"])
    if i is None or i>=len(bars)-1:
        raise ValueError("Signal candle absent or not closed")
    if signal["eligible_ms"]!=(bars[i]["time"]+tf)*1000:
        raise ValueError("Lookahead or incorrect closed-candle event time")
    b=bars[i]
    height=b["high"]-b["low"]
    rng=signal["atr"]
    if height<=0 or rng<=0:return False,"invalid_atr_or_candle"
    if not .35*rng<=height<=2.8*rng:
        return False,"unreliable_candle_size"
    close_pos=(b["close"]-b["low"])/height
    side=signal["side"]
    if side==1 and (b["close"]<=b["open"] or close_pos<.67):
        return False,"weak_buy_rejection"
    if side==-1 and (b["close"]>=b["open"] or close_pos>.33):
        return False,"weak_sell_rejection"

    if signal["setup"]=="break_retest":
        breakout_ix=ix.get(signal["breakout_ms"])
        if breakout_ix is None or breakout_ix>=i:
            raise ValueError("Retest must happen AFTER a known breakout bar")
        breakout=bars[breakout_ix]
        brange=breakout["high"]-breakout["low"]
        if brange<=0:return False,"breakout_zero_range"
        bbody=abs(breakout["close"]-breakout["open"])/brange
        if bbody<.42:return False,"weak_breakout_body"
        bpos=(breakout["close"]-breakout["low"])/brange
        if (side==1 and bpos<.66) or (side==-1 and bpos>.34):
            return False,"weak_breakout_close"
        anchors=signal.get("line_anchor_indices")
        values=signal.get("line_anchor_prices")
        if not (isinstance(anchors,list) and len(anchors)==2 and
                isinstance(values,list) and len(values)==2 and
                anchors[1]>anchors[0]):
            raise ValueError("Missing frozen LTA/LTD anchors")
        ax0,ax1=anchors
        y0,y1=values
        broken=y1+(y1-y0)*(breakout_ix-ax1)/(ax1-ax0)
        if side*(breakout["close"]-broken)<.18*rng:
            return False,"marginal_breakout"
        line=signal["line_retest_level"]
        # Must touch the marked line, not just close near it.
        if not (b["low"]<=line+.24*rng and b["high"]>=line-.24*rng):
            return False,"no_contact_with_line"
        # Rejection should emerge from the broken line; wick must be visible.
        wick=(min(b["open"],b["close"])-b["low"] if side==1 else
              b["high"]-max(b["open"],b["close"]))
        if wick/height<.20:
            return False,"weak_retest_wick"
        return True,"qualified_break_retest"

    if signal["setup"]=="range_rejection":
        # Prior zone test already imposed by proxy_zones_repeated or manual.
        wick=(min(b["open"],b["close"])-b["low"] if side==1 else
              b["high"]-max(b["open"],b["close"]))
        if wick/height<.30:
            return False,"weak_range_rejection_wick"
        return True,"qualified_range_rejection"

    raise ValueError("Not user's manual price-action setup")


def gate_signals(bars,signals,tf):
    """Veto weak signals and reuse of already-traded identical marked line."""
    seen_markers=set()
    last_range={"buy":-1000,"sell":-1000}
    index={b["time"]*1000:i for i,b in enumerate(bars)}
    accepted=[]
    reasons=Counter()
    for s in signals:
        if s["timeframe_seconds"]!=tf:raise ValueError("Mixed frames")
        ok,reason=confirm_v4(bars,s)
        if not ok:
            reasons[reason]+=1
            continue
        i=index[s["signal_ms"]]
        if s["setup"]=="break_retest":
            key=(s["line_kind"],tuple(s["line_anchor_indices"]),
                 tuple(s["line_anchor_prices"]))
            if key in seen_markers:
                reasons["repeated_same_marked_microtrend"]+=1
                continue
            seen_markers.add(key)
        else:
            key="buy" if s["side"]==1 else "sell"
            if i-last_range[key]<(6 if tf==60 else 3):
                reasons["repeated_same_range_touch"]+=1
                continue
            last_range[key]=i
        accepted.append(s)
        reasons[reason]+=1
    assert len(accepted)<=len(signals)
    return accepted,dict(sorted(reasons.items()))


def experiment_day(path,day,*,marking_mode="proxy",marks_path=None):
    if day not in DAYS:
        raise ValueError("Only predeclared research dates, no chosen winners")
    if marking_mode not in ("proxy","manual"):
        raise ValueError("Require explicitly labeled mark provenance")
    if marking_mode=="manual" and marks_path is None:
        raise ValueError("User's manual marks must be supplied; no invented levels")
    quote,source=parse_quotes(path,day)
    start=utc_ms(day,9);open_ms=utc_ms(day,12);end=utc_ms(day,21)
    if (quote[0][0]<start or quote[-1][0]>end+59999 or
        quote[0][0]>start+60000 or quote[-1][0]<end-120000):
        raise SourceQualityError("Incomplete 09-21 UTC quote tape")
    trading=[q for q in quote if open_ms<=q[0]<end]
    if len(trading)<1500 or trading[0][0]>open_ms+60000:
        raise SourceQualityError("Incomplete identical execution session")
    settings=Settings()
    stressed=replace(settings,commission_roundtrip_usd_per_oz=.60,
                     slippage_usd_each_market_side=.20)
    both= {"v3_baseline":[],"v4_confirmed":[]}
    report={}
    for tf,name in ((60,"M1"),(300,"M5")):
        candles=candles_from_quotes(quote,tf)
        if len(candles)<(360 if tf==60 else 110):
            raise SourceQualityError("Warmup candles incomplete")
        if marking_mode=="manual":
            lines,zones=parse_mark_file(marks_path,day,tf,open_ms,candles)
        else:lines=();zones=None
        args=dict(marking_mode=marking_mode,manual_lines=lines,manual_zones=zones)
        original,events=causal_signals(candles,tf,open_ms,end,**args)
        updated,quality_events=causal_signals(
            candles,tf,open_ms,end,**args,
            proxy_zones_fn=proxy_zones_repeated if marking_mode=="proxy" else None
        )
        filtered,veto=gate_signals(candles,updated,tf)
        report[name]={}
        for label,signals,why in (
            ("v3_baseline",original,events),
            ("v4_confirmed",filtered,{**quality_events,
                                    "quality_veto_counts":veto})
        ):
            both[label].extend(signals)
            item={"signals":len(signals),
                  "setup_signals":dict(sorted(Counter(x["setup"] for x in signals).items())),
                  "diagnostics":why,"costs":{}}
            for cost,cfg in (("standard",settings),("double",stressed)):
                item["costs"][cost]=simulate_ticks(trading,signals,tf,cfg)
            report[name][label]=item
    report["SHARED"]={}
    for label,signals in both.items():
        row={"signals":len(signals),
             "setup_signals":dict(sorted(Counter(s["setup"] for s in signals).items())),
             "diagnostics":{"symbol_global_lock":True},
             "costs":{}}
        for cost,cfg in (("standard",settings),("double",stressed)):
            row["costs"][cost]=simulate_shared_quotes(trading,signals,cfg)
        report["SHARED"][label]=row
    return {
        "day":day,"source":source,"marking_mode":marking_mode,
        "actual_user_markings_present":marking_mode=="manual",
        "same_quoted_bid_ask_execution":True,
        "market_feed_not_mt5_broker":True,
        "profits_usd_per_theoretical_ounce":True,
        "one_position_globally":True,
        "live_trading_approved":False,
        "warmup_utc":"09:00-12:00","execution_utc":"12:00-21:00",
        "hypothesis":"strong breakout and retest, repeated prior S/R touches, one line use",
        "results":report,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--ticks",required=True)
    p.add_argument("--day",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--quarantine",required=True)
    p.add_argument("--mode",choices=("proxy","manual"),default="proxy")
    p.add_argument("--manual-marks")
    a=p.parse_args()
    try:
        data=experiment_day(a.ticks,a.day,marking_mode=a.mode,
                            marks_path=a.manual_marks)
    except SourceQualityError as e:
        q={"day":a.day,"whole_source_excluded":True,"reason":str(e),
           "trades_included":0}
        out=Path(a.quarantine);out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(q,ensure_ascii=False,indent=2)+"\n")
        print("WHOLE SESSION QUARANTINED",a.day,e)
        return
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
    for tf in ("M1","M5","SHARED"):
        for label in ARMS:
            item=data["results"][tf][label]
            sim=item["costs"]["double"]
            print("PA_FIDELITY_V4",a.day,tf,label,
                  "signals",item["signals"],"fills",sim["filled"],
                  "wins",sim["wins"],"losses",sim["losses"],
                  "net_USD_oz",sim["net_usd_per_oz"])


if __name__=="__main__":
    main()
