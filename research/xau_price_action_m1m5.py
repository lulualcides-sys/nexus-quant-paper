"""XAUUSD Price Action M1/M5: independent adaptation of the WIN concept.

SETUPS: microtrendline breakout/retest, or rejection at a touched range edge.
Signals use only completed current/HTF candles, never future M1 prices.
Execution is sequential on actual Dukascopy historical BID/ASK quotes, at the
NEXT quote after the signal closes. Entry and market exit incur adverse assumed
slippage; stops may gap; targets are limit exits. No live broker orders.

All amounts are hypothetical USD *per one troy ounce*, not any broker account.
No claim of equivalence with the WIN futures strategy or proprietary Tracker.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path


class SourceQualityError(ValueError):
    """Invalid external quote data. Quarantine the WHOLE session."""


@dataclass(frozen=True)
class Settings:
    reward_risk: float = 2.0
    min_stop_atr: float = 0.15
    max_stop_atr: float = 2.5
    min_net_rr: float = 0.85
    min_range_atr: float = 1.4
    max_range_atr: float = 9.0
    line_tolerance_atr: float = 0.24
    pivot_slope_atr: float = 0.012
    max_entry_spread_usd: float = 0.90
    max_entry_delay_seconds: int = 30
    max_hold_bars: int = 20
    commission_roundtrip_usd_per_oz: float = 0.30
    slippage_usd_each_market_side: float = 0.10

    def validate(self):
        if not (1 <= self.reward_risk <= 5 and
                0 < self.min_stop_atr < self.max_stop_atr <= 8 and
                0 <= self.min_net_rr <= 3 and
                self.min_range_atr < self.max_range_atr and
                0 < self.line_tolerance_atr <= 2 and
                0 < self.pivot_slope_atr <= 1 and
                0 < self.max_entry_spread_usd <= 12 and
                0 < self.max_entry_delay_seconds <= 300 and
                1 <= self.max_hold_bars <= 200 and
                self.commission_roundtrip_usd_per_oz >= 0 and
                self.slippage_usd_each_market_side >= 0):
            raise ValueError("Invalid fixed XAUUSD PA assumptions")


def parse_quotes(path: str | Path, day: str):
    """Strict CSV: UTC milliseconds, bid, ask. No excising individual bad ticks."""
    path=Path(path)
    if not (len(day)==8 and day.isdigit()):
        raise ValueError("day must be YYYYMMDD")
    if not path.is_file() or not 0 < path.stat().st_size <= 250_000_000:
        raise SourceQualityError("No valid source file or source exceeds size limit")
    quotes=[]
    digest=hashlib.sha256()
    with path.open("rb") as fp:
        for block in iter(lambda: fp.read(2**20), b""):
            digest.update(block)
    with path.open(newline="",encoding="utf-8-sig") as fp:
        reader=csv.DictReader(fp)
        if not {"timestamp","askPrice","bidPrice"}.issubset(reader.fieldnames or []):
            raise SourceQualityError("Expected raw Dukascopy bid/ask quote CSV")
        previous=-1
        for count,row in enumerate(reader,1):
            if count>1_500_000:
                raise SourceQualityError("Quote input exceeds verified capacity")
            try:
                ms=int(row["timestamp"])
                ask=float(row["askPrice"])
                bid=float(row["bidPrice"])
            except (ValueError,TypeError,KeyError,OverflowError) as exc:
                raise SourceQualityError(f"Invalid quote CSV record {count}") from exc
            if not (ms>946684800000 and math.isfinite(bid) and
                    math.isfinite(ask) and bid>0 and 0<ask-bid<=12):
                raise SourceQualityError(f"Invalid crossed/unbounded BID ASK at row {count}")
            if ms<previous:
                raise SourceQualityError(f"Quotes reordered at row {count}")
            if datetime.fromtimestamp(ms/1000,timezone.utc).strftime("%Y%m%d")!=day:
                raise SourceQualityError("Quote record outside selected UTC date")
            previous=ms
            quotes.append((ms,bid,ask))
    if len(quotes)<1500:
        raise SourceQualityError("Insufficient real quote data")
    return quotes,{"raw_quote_rows":len(quotes),"sha256":digest.hexdigest(),
                   "date_utc":day,"first_quote_ms":quotes[0][0],
                   "last_quote_ms":quotes[-1][0],
                   "source":"Dukascopy historical spot XAUUSD BID/ASK; not user's MT5 feed"}


def candles_from_quotes(quotes, timeframe_seconds):
    if timeframe_seconds not in (60,300):
        raise ValueError("Only XAU M1 and M5 candles supported")
    bars=[]
    cur=None
    frame_ms=timeframe_seconds*1000
    for ms,bid,ask in quotes:
        stamp=(ms//frame_ms)*timeframe_seconds
        if cur is None or cur["time"]!=stamp:
            if cur is not None:
                bars.append(cur)
            cur={"time":stamp,"open":bid,"high":bid,"low":bid,"close":bid,
                 "quote_updates":0}
        cur["high"]=max(cur["high"],bid)
        cur["low"]=min(cur["low"],bid)
        cur["close"]=bid
        cur["quote_updates"]+=1
    if cur is not None: bars.append(cur)
    return bars


def resample_completed(bars, i, tf_seconds, context_seconds):
    """Only preceding or JUST-CLOSED context bars; never unfinished HTF."""
    cutoff=bars[i]["time"]+tf_seconds
    rows=[];cur=None
    for b in bars[:i+1]:
        start=b["time"]//context_seconds*context_seconds
        if cur is None or start!=cur["time"]:
            if cur is not None and cur["time"]+context_seconds<=cutoff:
                rows.append(cur)
            cur={**b,"time":start}
        else:
            cur["high"]=max(cur["high"],b["high"])
            cur["low"]=min(cur["low"],b["low"])
            cur["close"]=b["close"]
    if cur is not None and cur["time"]+context_seconds<=cutoff:
        rows.append(cur)
    return rows


def atr(bars, upto, window=14):
    if upto<window:
        return None
    window_bars=bars[upto-window+1:upto+1]
    ranges=[max(b["high"]-b["low"],
                abs(b["high"]-bars[upto-window+k]["close"]),
                abs(b["low"]-bars[upto-window+k]["close"]))
            for k,b in enumerate(window_bars)]
    return sum(ranges)/len(ranges)


def regime(context, min_step):
    if len(context)<12:
        return "unknown"
    old=context[-12:-6];new=context[-6:]
    old_hi=max(x["high"] for x in old);old_lo=min(x["low"] for x in old)
    new_hi=max(x["high"] for x in new);new_lo=min(x["low"] for x in new)
    if new_hi>old_hi+min_step*.14 and new_lo>=old_lo+min_step*.14:
        return "up"
    if new_hi<=old_hi-min_step*.14 and new_lo<old_lo-min_step*.14:
        return "down"
    if new_hi<=old_hi+min_step*.65 and new_lo>=old_lo-min_step*.65:
        return "range"
    return "mixed"


def pivot_line(bars,j,side,min_slope):
    """Two CONFIRMED peaks/troughs, both strictly older than breakout candle j."""
    key="high" if side==1 else "low"
    piv=[]
    for k in range(max(2,j-38),j-2):
        value=bars[k][key]
        neighbors=[bars[n][key] for n in (k-2,k-1,k+1,k+2)]
        if (value>max(neighbors) if side==1 else value<min(neighbors)):
            piv.append((k,value))
    if len(piv)<2:return None
    (x0,y0),(x1,y1)=piv[-2:]
    slope=(y1-y0)/(x1-x0)
    if (side==1 and slope>=-min_slope) or (side==-1 and slope<=min_slope):
        return None
    return lambda index:y1+slope*(index-x1)


def break_retest(bars,i,side,settings,rng):
    if i<45: return None
    b=bars[i];tol=rng*settings.line_tolerance_atr
    eps=rng*.025
    for j in range(i-1,max(i-5,38),-1):
        line=pivot_line(bars,j,side,settings.pivot_slope_atr*rng)
        if line is None:continue
        candle=bars[j];prev=bars[j-1]
        if side==1:
            crossed=(prev["close"]<=line(j-1)+eps and
                     candle["close"]>=line(j)+eps and
                     candle["close"]>max(x["high"] for x in bars[j-3:j]))
            retained=all(bars[k]["close"]>=line(k)-tol for k in range(j+1,i))
            retest=(abs(b["low"]-line(i))<=tol and
                    b["close"]>line(i)+eps and b["close"]>b["open"])
            stop=b["low"]-.06*rng
        else:
            crossed=(prev["close"]>=line(j-1)-eps and
                     candle["close"]<=line(j)-eps and
                     candle["close"]<min(x["low"] for x in bars[j-3:j]))
            retained=all(bars[k]["close"]<=line(k)+tol for k in range(j+1,i))
            retest=(abs(b["high"]-line(i))<=tol and
                    b["close"]<line(i)-eps and b["close"]<b["open"])
            stop=b["high"]+.06*rng
        if crossed and retained and retest:
            return {"setup":"break_retest","side":side,"stop":stop,
                    "breakout_utc":candle["time"]}
    return None


def range_rejection(bars,i,context,settings,rng):
    if len(context)<12:return None
    recent=context[-12:]
    low=min(x["low"] for x in recent)
    high=max(x["high"] for x in recent)
    width=high-low
    if not settings.min_range_atr*rng<=width<=settings.max_range_atr*rng:
        return None
    tol=settings.line_tolerance_atr*rng
    if sum(x["low"]<=low+tol for x in recent)<2:return None
    if sum(x["high"]>=high-tol for x in recent)<2:return None
    b=bars[i]
    span=b["high"]-b["low"]
    if span<=0:return None
    if (b["low"]<=low+tol and b["close"]>low+.04*rng and
        b["close"]>b["open"] and
        (min(b["open"],b["close"])-b["low"])/span>=.22):
        return {"setup":"range_rejection","side":1,"stop":b["low"]-.06*rng,
                "room_limit":high-.05*rng}
    if (b["high"]>=high-tol and b["close"]<high-.04*rng and
        b["close"]<b["open"] and
        (b["high"]-max(b["open"],b["close"]))/span>=.22):
        return {"setup":"range_rejection","side":-1,"stop":b["high"]+.06*rng,
                "room_limit":low+.05*rng}
    return None


def candidate(bars,i,tf,settings):
    """WIN strategy concept adapted to XAU/USD; context M5 for M1, M15 for M5."""
    if i< (85 if tf==60 else 31):return None
    rng=atr(bars,i,14)
    if rng is None or rng<=0:return None
    context=resample_completed(bars,i,tf,tf*(5 if tf==60 else 3))
    ctx_range=atr(context,len(context)-1,8) if len(context)>8 else rng
    state=regime(context,ctx_range or rng)
    result=None
    if state=="up":
        result=break_retest(bars,i,1,settings,rng)
    elif state=="down":
        result=break_retest(bars,i,-1,settings,rng)
    elif state=="range":
        result=range_rejection(bars,i,context,settings,rng)
    if result is None:return None
    return {**result,"atr":rng,"signal_ms":bars[i]["time"]*1000,
            "eligible_ms":(bars[i]["time"]+tf)*1000,"timeframe_seconds":tf}


def scan_signals(bars,tf,settings):
    # Final candle may still be incomplete; exclude it.
    return [s for i in range(len(bars)-1)
            if (s:=candidate(bars,i,tf,settings)) is not None]


def simulate_ticks(quotes,signals,tf,settings,*,time_stop_enabled=True):
    """One position max; next-quote MARKET entry, BID/ASK exit, gap-aware stop.

    The time-based exit is an OPTIONAL simulation assumption, NOT a trader
    confirmed Stop Win/Red rule. Preserve previous default for all prior
    reports; run time_stop_enabled=False only as an explicitly labeled audit.
    """
    settings.validate()
    if tf not in (60,300):raise ValueError("Invalid timeframe")
    signals=sorted(signals,key=lambda v:v["eligible_ms"])
    if any(signals[i]["eligible_ms"]==signals[i-1]["eligible_ms"]
           for i in range(1,len(signals))):
        raise ValueError("Overlapping same-bar signals")
    position=None;idx=0
    trades=[]
    rejected={"delayed":0,"wide_spread":0,"stop_geometry":0,
              "uneconomic":0,"already_in_position":0}
    last_quote=None
    for ms,bid,ask in quotes:
        if last_quote is not None and ms<last_quote[0]:
            raise ValueError("Tick chronology reversed")
        last_quote=(ms,bid,ask)
        closed_on_tick=False
        if position is not None:
            p=position;side=p["side"]
            stop_trigger=(bid<=p["stop"] if side==1 else ask>=p["stop"])
            target_trigger=(bid>=p["target"] if side==1 else ask<=p["target"])
            timed=(time_stop_enabled and
                   ms>=p["entry_ms"]+tf*settings.max_hold_bars*1000)
            why=None
            if stop_trigger:
                why="STOP"
                exit_px=(min(bid,p["stop"]) if side==1 else max(ask,p["stop"]))
                exit_px-=side*settings.slippage_usd_each_market_side
            elif target_trigger:
                why="TARGET";exit_px=p["target"]
            elif timed:
                why="TIME";exit_px=(bid if side==1 else ask)-side*settings.slippage_usd_each_market_side
            if why:
                pnl=round(side*(exit_px-p["entry"])-settings.commission_roundtrip_usd_per_oz,6)
                trades.append({**p,"exit_ms":ms,"exit":round(exit_px,6),
                               "reason":why,"net_usd_per_oz":pnl})
                position=None;closed_on_tick=True

        while idx<len(signals) and signals[idx]["eligible_ms"]<=ms:
            s=signals[idx];idx+=1
            if position is not None or closed_on_tick:
                rejected["already_in_position"]+=1
                continue
            if ms-s["eligible_ms"]>settings.max_entry_delay_seconds*1000:
                rejected["delayed"]+=1
                continue
            if ask-bid>settings.max_entry_spread_usd:
                rejected["wide_spread"]+=1
                continue
            side=s["side"]
            entry=(ask if side==1 else bid)+side*settings.slippage_usd_each_market_side
            stop=round(s["stop"],3)
            dist=side*(entry-stop)
            if (not settings.min_stop_atr*s["atr"]<=dist<=settings.max_stop_atr*s["atr"]
                or dist<=0):
                rejected["stop_geometry"]+=1
                continue
            target=entry+side*settings.reward_risk*dist
            if s["setup"]=="range_rejection":
                room=side*(s["room_limit"]-entry)
                if room<1.5*dist:
                    rejected["stop_geometry"]+=1
                    continue
                target=entry+side*min(settings.reward_risk*dist,room)
            # Do not mistake nominal R:R for realized after costs and spread.
            net_goal=side*(target-entry)-settings.commission_roundtrip_usd_per_oz
            net_stop=dist+settings.commission_roundtrip_usd_per_oz+settings.slippage_usd_each_market_side
            if net_goal<settings.min_net_rr*net_stop:
                rejected["uneconomic"]+=1
                continue
            position={**s,"entry_ms":ms,"entry":round(entry,6),
                      "stop":stop,"target":round(target,6)}
        # Quotes that fell beyond session are never inferred.
    if position is not None and last_quote is not None:
        ms,bid,ask=last_quote;side=position["side"]
        exit_px=(bid if side==1 else ask)-side*settings.slippage_usd_each_market_side
        pnl=round(side*(exit_px-position["entry"])-settings.commission_roundtrip_usd_per_oz,6)
        trades.append({**position,"exit_ms":ms,"exit":round(exit_px,6),
                       "reason":"SESSION_END","net_usd_per_oz":pnl})
    rejected["not_seen_before_end"]=len(signals)-idx
    win=sum(t["net_usd_per_oz"]>0 for t in trades)
    lose=sum(t["net_usd_per_oz"]<0 for t in trades)
    profit=sum(t["net_usd_per_oz"] for t in trades if t["net_usd_per_oz"]>0)
    loss=-sum(t["net_usd_per_oz"] for t in trades if t["net_usd_per_oz"]<0)
    net=round(profit-loss,6)
    return {
        "signals":len(signals),"filled":len(trades),"wins":win,"losses":lose,
        "net_usd_per_oz":net,
        "profit_factor":round(profit/loss,5) if loss>0 else None,
        "expectancy_usd_per_oz":round(net/len(trades),5) if trades else None,
        "rejected":rejected,
        "by_setup":{name:{
            "trades":sum(t["setup"]==name for t in trades),
            "net_usd_per_oz":round(sum(t["net_usd_per_oz"] for t in trades
                                     if t["setup"]==name),6),
        } for name in ("break_retest","range_rejection")},
        "trades":trades,
    }


def backtest_session(path,day,settings=Settings()):
    settings.validate()
    quotes,source=parse_quotes(path,day)
    results={}
    for tf,name in ((60,"M1"),(300,"M5")):
        bars=candles_from_quotes(quotes,tf)
        if len(bars)<50:
            raise SourceQualityError(f"Insufficient full {name} candles")
        signals=scan_signals(bars,tf,settings)
        results[name]={
            "candles":len(bars),
            "context":"M5" if tf==60 else "M15",
            **simulate_ticks(quotes,signals,tf,settings),
        }
    return {
        "day":day,"source":source,
        "settings":asdict(settings),
        "results":results,
        "spread_included_bid_ask":True,
        "is_actual_broker_backtest":False,
        "gold_contract_size_confirmed":False,
        "not_original_greenhouse_tracker":True,
        "approval_for_live":False,
        "pnl_units":"Hypothetical US dollars per one troy ounce, not brokerage lots",
    }


def cli():
    p=argparse.ArgumentParser(description="XAUUSD M1/M5 Price Action market quote backtest")
    p.add_argument("--ticks",required=True)
    p.add_argument("--day",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--quarantine-output")
    args=p.parse_args()
    try:
        report=backtest_session(args.ticks,args.day)
    except SourceQualityError as err:
        if not args.quarantine_output:
            raise
        record={"day":args.day,"reason":str(err),"whole_session_excluded":True,
                "trades_included":0}
        dest=Path(args.quarantine_output);dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
        print("QUARANTINED ENTIRE SESSION",args.day,err)
        return
    dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("XAUUSD PA",args.day,"quotes",report["source"]["raw_quote_rows"],
          "SHA",report["source"]["sha256"])
    for tf,row in report["results"].items():
        print(tf,"signal_count",row["signals"],"filled",row["filled"],
              "net_USD_per_oz",row["net_usd_per_oz"],
              "PF",row["profit_factor"],"setups",row["by_setup"])


if __name__=="__main__":
    cli()
