"""XAUUSD PA v3 — auditable interpretation of user's explicit manual rules.

User-specified logic (no EMA):
  1) Mark support, resistance, LTA and LTD BEFORE the trade.
  2) In a directional/microtrend break, enter only AFTER an actual break
     of a marked LTA/LTD followed by a subsequent completed-candle retest.
  3) Trade direct touches of marked support/resistance ONLY while ranging.
  4) Both buy/sell, one position at a time, technical stop and target.

An automated `proxy` of markings is NOT the user's hand-drawn analysis.
`manual` mode fails CLOSED if there are no prior user-supplied marks.
Technical choices not specified by the user are explicitly research assumptions.

Every signal is created after a CLOSED candle; any quote-based fill uses
research.xau_price_action_m1m5.simulate_ticks (BID/ASK, adverse costs).
No auto-trading or brokerage-connected source.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from dataclasses import dataclass
from dataclasses import replace
import json
import math
from pathlib import Path

from research.xau_price_action_m1m5 import (
    Settings,SourceQualityError,atr,candles_from_quotes,parse_quotes,simulate_ticks,
)
from research.xau_pa_frequency_v2 import utc_ms

# Fixed dates, both historical and NOT a prospective live holdout.
OCTOBER = ("20261026","20261027","20261028","20261029","20261030")
NOVEMBER = ("20261102","20261103","20261104","20261105","20261106")
DAYS=OCTOBER+NOVEMBER
POLICIES=("prior_manual_marks","causal_proxy_marks")
COSTS=("standard","double")


@dataclass(frozen=True)
class Trendline:
    kind: str  # LTD descending tops, break UP -> BUY; LTA ascending lows, break DOWN -> SELL
    x1: int
    y1: float
    x2: int
    y2: float
    created_ms: int
    source: str

    def value(self, index):
        if self.x2<=self.x1:
            raise ValueError("Invalid line anchor chronology")
        return self.y2+(self.y2-self.y1)*(index-self.x2)/(self.x2-self.x1)

    def assert_valid(self, trade_start_ms: int, tf: int):
        if self.kind not in ("LTD","LTA") or self.source not in ("user","proxy"):
            raise ValueError("Invalid trendline identity")
        if not (self.x1<self.x2 and self.x2>=0 and
                all(math.isfinite(x) and x>0 for x in (self.y1,self.y2))):
            raise ValueError("Invalid line anchors")
        if self.kind=="LTD" and not self.y2<self.y1:
            raise ValueError("LTD must descend")
        if self.kind=="LTA" and not self.y2>self.y1:
            raise ValueError("LTA must ascend")
        if self.created_ms>trade_start_ms:
            raise ValueError("Cannot use a marking created after trading starts")


@dataclass(frozen=True)
class MarkedZones:
    support_low: float
    support_high: float
    resistance_low: float
    resistance_high: float
    created_ms: int
    source: str

    def validate(self,trade_start):
        a,b,c,d=(self.support_low,self.support_high,
                   self.resistance_low,self.resistance_high)
        if (self.source not in ("user","proxy") or
            not all(math.isfinite(x) and x>0 for x in (a,b,c,d)) or
            not a<=b<c<=d or
            self.created_ms>trade_start):
            raise ValueError("Invalid, overlapping or future support/resistance marks")


def parse_mark_file(path: str|Path|None, day: str, timeframe: int,
                    trade_start_ms: int, bars: list[dict]):
    """User marks must be supplied, time-anchored, and PRE-EXIST trading.

    Format permits one range rectangle and several marked LTA/LTD lines.
    x1_ms, x2_ms refer to candle start epochs in milliseconds. NEVER guess
    user's levels from their later trades, and never read future marked data.
    """
    if path is None:
        return [],None
    content=json.loads(Path(path).read_text(encoding="utf-8"))
    if content.get("symbol")!="XAUUSD" or content.get("day")!=day:
        raise ValueError("User's mark file does not match symbol/day")
    if "by_timeframe" in content:
        by_tf=content["by_timeframe"]
        if not isinstance(by_tf,dict) or not by_tf:
            raise ValueError("Manual file needs timeframe-specific marks")
        label="M1" if timeframe==60 else "M5"
        selected=by_tf.get(label)
        if selected is None:
            # Explicitly leave the unmarked timeframe with ZERO signals.
            return [],None
        if not isinstance(selected,dict):
            raise ValueError("Malformed timeframe-specific mark object")
    else:
        if content.get("timeframe_seconds")!=timeframe:
            return [],None
        selected=content
    date_marker=content.get("created_ms")
    if not isinstance(date_marker,int) or date_marker>trade_start_ms:
        raise ValueError("Manual marking must precede trading start")
    # Map timestamps to actual candle indices in this identical source tape.
    # Absolute epoch-bar numbers cannot be compared to array indices.
    bar_index={bar["time"]*1000:i for i,bar in enumerate(bars)}
    lines=[]
    for raw in selected.get("trendlines",[]):
        if not isinstance(raw,dict):
            raise ValueError("Malformed manual trendline")
        x1_ms=raw.get("x1_ms");x2_ms=raw.get("x2_ms")
        if (not isinstance(x1_ms,int) or not isinstance(x2_ms,int) or
            x1_ms<0 or x2_ms<0 or x1_ms>=x2_ms or
            x2_ms+timeframe*1000>date_marker or
            x1_ms not in bar_index or x2_ms not in bar_index):
            raise ValueError("Line anchors must be closed candles predating the marking")
        line=Trendline(kind=raw.get("kind",""),
                       x1=bar_index[x1_ms],
                       y1=float(raw.get("y1",0)),x2=bar_index[x2_ms],
                       y2=float(raw.get("y2",0)),created_ms=date_marker,
                       source="user")
        line.assert_valid(trade_start_ms,timeframe)
        lines.append(line)
    zones=None
    if selected.get("range") is not None:
        z=selected["range"]
        zones=MarkedZones(
            support_low=float(z["support_low"]),
            support_high=float(z["support_high"]),
            resistance_low=float(z["resistance_low"]),
            resistance_high=float(z["resistance_high"]),
            created_ms=date_marker,source="user")
        zones.validate(trade_start_ms)
    if not lines and zones is None:
        raise ValueError("Manual mode needs at least one user-provided line or range")
    return lines,zones


def closed_pivots(bars,cutoff: int,kind: str,window: int=65):
    """Confirmed two-left two-right: pivot at index j known only from j+2."""
    if kind not in ("LTA","LTD"):raise ValueError("Unknown line side")
    key="high" if kind=="LTD" else "low"
    out=[]
    for j in range(max(2,cutoff-window),cutoff-2):
        sample=[bars[k][key] for k in (j-2,j-1,j+1,j+2)]
        value=bars[j][key]
        if (value>max(sample) if kind=="LTD" else value<min(sample)):
            out.append((j,value))
    return out


def proxy_line(bars, last_closed_idx: int, tf: int,kind: str):
    """Dynamic causal proxy, NEVER label as a user's drawn mark."""
    pivots=closed_pivots(bars,last_closed_idx,kind)
    if len(pivots)<2:return None
    (a,v),(b,w)=pivots[-2:]
    if b-a<3 or b-a>48:return None
    slope=(w-v)/(b-a)
    r=atr(bars,last_closed_idx,14)
    if not r or r<=0:return None
    if kind=="LTD" and not (-.40*r<=slope<=-.012*r):return None
    if kind=="LTA" and not (.012*r<=slope<=.40*r):return None
    return Trendline(kind,a,v,b,w,
                     created_ms=(bars[last_closed_idx]["time"]+tf)*1000,
                     source="proxy")


def proxy_zones(pretrade_bars, trade_start_ms):
    """Pretrade-only high/low proxy; never retune bands using later prices."""
    if len(pretrade_bars)<20:return None
    data=pretrade_bars[-48:]
    high=max(b["high"] for b in data)
    low=min(b["low"] for b in data)
    if high<=low:return None
    width=high-low
    zone_width=max(.05,.03*width)
    z=MarkedZones(low,low+zone_width,high-zone_width,high,
                  created_ms=trade_start_ms,source="proxy")
    z.validate(trade_start_ms)
    return z


def sideways(bars, i: int, rng: float):
    """Lateralization requires overlapping candles + weak displacement.

    Uses LAST completed 18 candles EXCLUDING the signal candle.
    Opposing breaks cannot be traded as zone touches in a trending market.
    """
    if i<19:return False
    prev=bars[i-18:i]
    total=sum(abs(prev[k]["close"]-prev[k-1]["close"])
              for k in range(1,len(prev)))
    efficiency=(abs(prev[-1]["close"]-prev[0]["close"])/total) if total>0 else 0
    hi=max(x["high"] for x in prev);lo=min(x["low"] for x in prev)
    mid=(hi+lo)/2
    crossings=sum((prev[k]["close"]-mid)*(prev[k-1]["close"]-mid)<=0
                  for k in range(1,len(prev)))
    return efficiency<=.33 and crossings>=2 and 1.50*rng<=hi-lo<=14*rng


def line_crossed(prev,candle,line: Trendline,index,rng):
    side=1 if line.kind=="LTD" else -1
    price=line.value(index);old=line.value(index-1)
    buffer=.08*rng
    if side==1:
        return (prev["close"]<=old+buffer and
                candle["close"]>price+buffer and candle["close"]>candle["open"])
    return (prev["close"]>=old-buffer and
            candle["close"]<price-buffer and candle["close"]<candle["open"])


def retest_signal(bars,i,tf,line,breakout_i,rng):
    if i<=breakout_i:raise ValueError("Retest must be subsequent to breakout")
    candle=bars[i];level=line.value(i)
    tol=.24*rng
    side=1 if line.kind=="LTD" else -1
    height=candle["high"]-candle["low"]
    if height<=0:return None
    if side==1:
        touched=(candle["low"]<=level+tol and candle["high"]>=level-tol)
        affirmed=(candle["close"]>level+.08*rng and
                  candle["close"]>candle["open"] and
                  (candle["close"]-candle["low"])/height>=.62)
        stop=candle["low"]-.10*rng
    else:
        touched=(candle["high"]>=level-tol and candle["low"]<=level+tol)
        affirmed=(candle["close"]<level-.08*rng and
                  candle["close"]<candle["open"] and
                  (candle["high"]-candle["close"])/height>=.62)
        stop=candle["high"]+.10*rng
    if not touched or not affirmed:return None
    return {
        "setup":"break_retest","side":side,"stop":stop,"atr":rng,
        "signal_ms":candle["time"]*1000,
        "eligible_ms":(candle["time"]+tf)*1000,
        "timeframe_seconds":tf,
        "breakout_ms":bars[breakout_i]["time"]*1000,
        "line_kind":line.kind,"line_source":line.source,
        "line_retest_level":round(level,5),
    }


def range_signal(bars,i,tf,zone,sideways_only=True):
    if zone is None:return None
    b=bars[i]
    rng=atr(bars,i,14)
    if not rng or rng<=0:return None
    if sideways_only and not sideways(bars,i,rng):
        return None
    span=b["high"]-b["low"]
    if span<=0:return None
    buy=(b["low"]<=zone.support_high+.12*rng and
         b["high"]>=zone.support_low and
         b["close"]>zone.support_high+.08*rng and
         b["close"]>b["open"] and
         (b["close"]-b["low"])/span>=.62)
    sell=(b["high"]>=zone.resistance_low-.12*rng and
          b["low"]<=zone.resistance_high and
          b["close"]<zone.resistance_low-.08*rng and
          b["close"]<b["open"] and
          (b["high"]-b["close"])/span>=.62)
    if buy and sell:return None
    if not buy and not sell:return None
    side=1 if buy else -1
    stop=(min(b["low"],zone.support_low)-.10*rng if buy else
          max(b["high"],zone.resistance_high)+.10*rng)
    return {
        "setup":"range_rejection","side":side,"stop":stop,"atr":rng,
        "signal_ms":b["time"]*1000,"eligible_ms":(b["time"]+tf)*1000,
        "timeframe_seconds":tf,
        "room_limit":(zone.resistance_low if buy else zone.support_high),
        "marks_source":zone.source,
    }


def causal_signals(bars,tf,trade_start_ms,trade_end_ms,
                   *,marking_mode,manual_lines=(),manual_zones=None):
    """Confirmed breakout -> persistent pending state -> confirmed retest.

    One attempt per line/crossing, no same-bar breakout + retest, expires
    after 8 bars M1 / 5 bars M5, invalidates on closing back through line.
    Completely disallows direct-touch trades when not sideways.
    """
    if marking_mode not in ("manual","proxy"):
        raise ValueError("Marking mode requires explicit manual or proxy")
    if marking_mode=="manual":
        if not manual_lines and manual_zones is None:
            return [],{"missing_user_marks":1}
        if any(l.source!="user" for l in manual_lines):
            raise ValueError("Proxy trendline presented as manual")
        if manual_zones is not None and manual_zones.source!="user":
            raise ValueError("Proxy zones presented as manual")
    pre=[b for b in bars if (b["time"]+tf)*1000<=trade_start_ms]
    zone=manual_zones if marking_mode=="manual" else proxy_zones(pre,trade_start_ms)
    pending=None;last_fired=-100;events=Counter()
    out=[]
    for i in range(35,len(bars)-1):
        b=bars[i];time=(b["time"]+tf)*1000
        if not trade_start_ms<=time<trade_end_ms:
            continue
        rng=atr(bars,i,14)
        if not rng or rng<=0:
            events["missing_atr"]+=1;continue

        # Process PENDING before allowing fresh breakouts. Thus retest MUST
        # be a later candle; break/retest cannot execute on breakout candle.
        if pending is not None:
            line,breakout_i=pending
            ttl=8 if tf==60 else 5
            price=line.value(i)
            side=1 if line.kind=="LTD" else -1
            if i-breakout_i>ttl:
                events["retest_expired"]+=1
                pending=None
            elif side*(b["close"]-price)<-.25*rng:
                events["false_breakout"]+=1
                pending=None
            else:
                sig=retest_signal(bars,i,tf,line,breakout_i,rng)
                if sig is not None:
                    if i-last_fired>=3:
                        out.append(sig);last_fired=i
                        events["confirmed_break_retests"]+=1
                    else:events["cooldown"]+=1
                    pending=None
                else:events["awaiting_retest"]+=1
            # Even on cancellation, do not open a new breakout in same bar.
            continue

        # "Bater na linha": permitted only in a measured lateral range.
        if zone is not None and sideways(bars,i,rng):
            direct=range_signal(bars,i,tf,zone)
            if direct is not None:
                if i-last_fired>=3:
                    out.append(direct);last_fired=i
                    events["confirmed_range_rejections"]+=1
                else:events["cooldown"]+=1
                continue
        elif zone is not None:
            events["not_sideways_no_line_touch"]+=1

        # No range-touch trading here. Wait to CLOSE beyond marked LTA/LTD.
        old=bars[i-1]
        lines=(manual_lines if marking_mode=="manual" else
               tuple(l for kind in ("LTD","LTA")
                     if (l:=proxy_line(bars,i-1,tf,kind)) is not None))
        for line in lines:
            # Disallow a mark created after the breakout candle.
            if line.created_ms>b["time"]*1000:
                events["future_mark_rejected"]+=1;continue
            if line.x2>=i-2:
                events["unconfirmed_pivots"]+=1;continue
            if abs(b["close"]-line.value(i))>2.5*rng:
                events["line_too_far"]+=1;continue
            if line_crossed(old,b,line,i,rng):
                pending=(line,i)
                events["breakout_waiting_retest"]+=1
                break
    return out,dict(sorted(events.items()))


def one_day(path,day,*,marking_mode="proxy",marks_path=None):
    if day not in DAYS:raise ValueError("Day not in fixed historical set")
    if marking_mode=="manual" and marks_path is None:
        raise ValueError("No user-supplied drawing file; no guessing manual marks")
    quotes,source=parse_quotes(path,day)
    start=utc_ms(day,9);trade_start=utc_ms(day,12);end=utc_ms(day,21)
    if (quotes[0][0]<start or quotes[-1][0]>end+59999 or
        quotes[0][0]>start+60000 or quotes[-1][0]<end-120000):
        raise SourceQualityError("Insufficient 09-21 UTC quote coverage")
    trading=[q for q in quotes if trade_start<=q[0]<end]
    if not trading or trading[0][0]>trade_start+60000:
        raise SourceQualityError("Missing comparable 12-21 UTC quotes")
    settings=Settings()
    stressed=replace(settings,commission_roundtrip_usd_per_oz=.60,
                     slippage_usd_each_market_side=.20)
    result={}
    for tf,label in ((60,"M1"),(300,"M5")):
        bars=candles_from_quotes(quotes,tf)
        if len(bars)<(360 if tf==60 else 110):
            raise SourceQualityError("Too few candles")
        if marking_mode=="manual":
            manual_lines,manual_zone=parse_mark_file(marks_path,day,tf,trade_start,bars)
        else:
            manual_lines=();manual_zone=None
        signals,events=causal_signals(bars,tf,trade_start,end,
                                     marking_mode=marking_mode,
                                     manual_lines=manual_lines,
                                     manual_zones=manual_zone)
        from research.xau_price_action_m1m5 import scan_signals
        legacy=[s for s in scan_signals(bars,tf,settings)
                if trade_start<=s["eligible_ms"]<end]
        result[label]={}
        for name,pool,diagnostics in (
            ("legacy",legacy,{"original_strategy_proxy_only":1}),
            ("marked_rules_v3",signals,events)
        ):
            row={"signals":len(pool),"events":diagnostics,
                 "signal_setups":dict(sorted(Counter(s["setup"] for s in pool).items())),
                 "costs":{}}
            for cost,cfg in (("standard",settings),("double",stressed)):
                outcome=simulate_ticks(trading,pool,tf,cfg)
                if outcome["filled"]>len(pool) or any(
                    t["entry_ms"]<trade_start or t["entry_ms"]>=end
                    for t in outcome["trades"]
                ):
                    raise ValueError("Trade outside session or false fills")
                row["costs"][cost]=outcome
            result[label][name]=row
    return {
        "day":day,"source":source,"marking_mode":marking_mode,
        "manual_mark_file_present":marking_mode=="manual",
        "user_drawn_marking_fidelity_verified":False,
        "symbol":"XAUUSD","warmup_utc":"09:00-12:00",
        "trade_utc":"12:00-21:00",
        "one_concurrent_position":True,
        "not_an_MT5_broker_backtest":True,
        "live_approval":False,
        "results":result,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--ticks",required=True)
    p.add_argument("--day",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--quarantine",required=True)
    p.add_argument("--marking-mode",choices=("manual","proxy"),default="proxy")
    p.add_argument("--manual-marks")
    args=p.parse_args()
    try:
        record=one_day(args.ticks,args.day,
                       marking_mode=args.marking_mode,
                       marks_path=args.manual_marks)
    except SourceQualityError as exc:
        q={"day":args.day,"whole_day_excluded":True,
           "reason":str(exc),"included_trades":0}
        dest=Path(args.quarantine);dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(q,indent=2)+"\n",encoding="utf-8")
        print("ENTIRE SESSION QUARANTINED",args.day,exc)
        return
    target=Path(args.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(record,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    for tf,modes in record["results"].items():
        for name,part in modes.items():
            e=part["costs"]["double"]
            print("PA_V3",args.day,tf,name,"signals",part["signals"],
                  "fills",e["filled"],"net_USD_per_oz",e["net_usd_per_oz"],
                  "events",part["events"])


if __name__=="__main__":
    main()
