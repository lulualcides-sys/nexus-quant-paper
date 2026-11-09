"""Read-only, local MT5 WIN M1 + trade-tick provenance & classified-flow audit.

This is NOT a Greenhouse Tracker replica. It obtains real broker-provided
trade ticks only when the user's own connected MetaTrader 5 Windows terminal
has them, and NEVER invents aggressors from OHLC/tick_volume.

No account IDs, logins, trade orders, cloud uploads, secrets, or browser access.
Raw tick transactions are kept in memory only; output is local 1-minute
aggregates for signal research. Source terminal history is NOT guaranteed B3
complete, and no fills or profitability can be inferred.

Usage after connecting MT5 to market data:
  py -3 -m research.win_mt5_tick_provenance --symbol WINZ26 --date 2026-11-03 --date 2026-11-04
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import tempfile
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SP=ZoneInfo("America/Sao_Paulo")
WIN=re.compile(r"WIN[GJMQVZ]\d{2}\Z", re.ASCII)
FLAG_LAST=4
FLAG_VOLUME=16
FLAG_BUY=32
FLAG_SELL=64
MAX_TICKS_PER_DAY=1_500_000
CHUNK_MINUTES=10
# Scheduled minutes, not assertion about the B3 exchange opening time.
WINDOW_START=time(9,0)
WINDOW_END=time(19,0)

def field(row,name):
    if isinstance(row,dict):return row[name]
    return row[name]

def valid_symbol(symbol:str)->str:
    s=symbol.upper()
    if not WIN.fullmatch(s):
        raise ValueError("Use a single WIN expiry, e.g. WINZ26; never WINFUT")
    return s

def local_window(day:str):
    d=date.fromisoformat(day)
    if d.weekday()>4:
        raise ValueError("Refusing a weekend date")
    local_start=datetime.combine(d,WINDOW_START,SP)
    local_end=datetime.combine(d,WINDOW_END,SP)
    return local_start.astimezone(timezone.utc),local_end.astimezone(timezone.utc)

def _finite_price(n):
    f=float(n)
    if not math.isfinite(f) or f<=0 or abs(f/5-round(f/5))>1e-7:
        raise ValueError("WIN price must be positive and align to 5-point grid")
    return f

def canonical_m1(bars,start_utc,end_utc):
    """Reject bad M1 chronology and do not silently repair broker data."""
    if bars is None:raise ValueError("Terminal returned no M1 rates")
    left=int(start_utc.timestamp())
    right=int(end_utc.timestamp())
    out=[]
    previous=None
    for r in bars:
        stamp=int(field(r,"time"))
        if not left<=stamp<right:continue
        if stamp%60 or (previous is not None and stamp<=previous):
            raise ValueError("MT5 M1 timestamps non-minute-aligned, duplicate or unordered")
        prev=previous
        previous=stamp
        oo,hh,ll,cc=(_finite_price(field(r,x)) for x in ("open","high","low","close"))
        if ll>min(oo,cc) or hh<max(oo,cc):
            raise ValueError("Invalid OHLC candle")
        real=float(field(r,"real_volume"))
        if not math.isfinite(real) or real<0 or not real.is_integer():
            raise ValueError("Invalid M1 traded-contract volume")
        out.append({"time":stamp,"open":oo,"high":hh,"low":ll,"close":cc,
                    "real_volume":int(real),"gap_before":bool(prev and stamp-prev!=60)})
    return out

def aggregate_trade_ticks(ticks,start_utc,end_utc,*, max_events=MAX_TICKS_PER_DAY):
    """Aggregate genuine volume by minute and trade direction. Preserve unknowns.

    Require LAST/VOLUME event flags and actual volume_real. Reject BOTH BUY+SELL.
    A price-only quote with cached volume is not a new trade.
    """
    lo=int(start_utc.timestamp()*1000)
    hi=int(end_utc.timestamp()*1000)
    counters=defaultdict(lambda:{"buy":0.,"sell":0.,"unknown":0.,"classified_events":0,
                                  "unknown_events":0,"bad_side_events":0,"first_ms":None,
                                  "last_ms":None,"price_volume_by_tick":{},
                                  "last_quarter_buy":0.,"last_quarter_sell":0.})
    seen=0
    last_stamp=None
    for tick in ticks:
        ts=int(field(tick,"time_msc"))
        if ts<lo or ts>=hi:continue
        if last_stamp is not None and ts<last_stamp:
            raise ValueError("MT5 ticks are out of order; cannot use for flow evidence")
        last_stamp=ts
        seen+=1
        if seen>max_events:raise ValueError("Tick cap reached; no silent truncation")
        flags=int(field(tick,"flags"))
        if not (flags&(FLAG_LAST|FLAG_VOLUME)):
            continue
        vol=float(field(tick,"volume_real"))
        if not math.isfinite(vol) or vol<=0:
            continue
        price=float(field(tick,"last"))
        if not math.isfinite(price) or price<=0 or abs(price/5-round(price/5))>1e-7:
            continue
        minute=ts//60000*60
        a=counters[minute]
        if a["first_ms"] is None:a["first_ms"]=ts
        a["last_ms"]=ts
        a["price_volume_by_tick"][int(round(price/5)*5)]=(
            a["price_volume_by_tick"].get(int(round(price/5)*5),0)+vol)
        buying=bool(flags&FLAG_BUY)
        selling=bool(flags&FLAG_SELL)
        if buying and selling:
            a["bad_side_events"]+=1
            a["unknown"]+=vol
        elif buying:
            a["buy"]+=vol
            a["classified_events"]+=1
            if ts%60000>=45000:a["last_quarter_buy"]+=vol
        elif selling:
            a["sell"]+=vol
            a["classified_events"]+=1
            if ts%60000>=45000:a["last_quarter_sell"]+=vol
        else:
            a["unknown"]+=vol
            a["unknown_events"]+=1
    return dict(counters),seen

def attach_quality(bars,tick_agg,*,require_coverage=0.60,
                   volume_rel_tolerance=0.20,min_events=25):
    """Strict provenance flags; no synthetic deltas or zero-volume substitutions.

    Broker rate real_volume and summed tick trade volume should broadly agree.
    Positive volume on the bar with zero classified tick history remains missing.
    """
    out=[]
    previous=None
    for b in bars:
        a=tick_agg.get(b["time"])
        evidence={
            "time":b["time"],"open":b["open"],"high":b["high"],
            "low":b["low"],"close":b["close"],"real_volume":b["real_volume"],
            "valid_flow":False,"reject_reasons":[],"buy_volume":None,"sell_volume":None,
            "unknown_volume":None,"delta":None,"delta_fraction":None,
            "classified_share":None,"tick_volume_agreement_pct":None,
            "classified_trade_count":0,"last_15s_delta":None,
            "vwap":None,"poc_price":None
        }
        reasons=evidence["reject_reasons"]
        if previous is not None and b["time"]-previous!=60:reasons.append("missing_m1_before")
        previous=b["time"]
        if b["real_volume"]<=0:reasons.append("no_real_candle_volume")
        if a is None:
            reasons.append("no_real_trade_ticks")
            out.append(evidence)
            continue
        total=a["buy"]+a["sell"]+a["unknown"]
        classified=a["buy"]+a["sell"]
        evidence["buy_volume"]=round(a["buy"],4)
        evidence["sell_volume"]=round(a["sell"],4)
        evidence["unknown_volume"]=round(a["unknown"],4)
        evidence["classified_trade_count"]=a["classified_events"]
        evidence["classified_share"]=round(classified/total,4) if total else 0.
        evidence["delta"]=round(a["buy"]-a["sell"],4)
        evidence["delta_fraction"]=round((a["buy"]-a["sell"])/classified,4) if classified else None
        evidence["last_15s_delta"]=round(a["last_quarter_buy"]-a["last_quarter_sell"],4)
        evidence["tick_volume_agreement_pct"]=round(
            100*abs(total-b["real_volume"])/b["real_volume"],2) if b["real_volume"]>0 else None
        prices=a["price_volume_by_tick"]
        if total>0 and prices:
            evidence["vwap"]=round(sum(price*qty for price,qty in prices.items())/sum(prices.values()),3)
            evidence["poc_price"]=min(prices, key=lambda p:(-prices[p],p))
        if a["classified_events"]<min_events:reasons.append("too_few_side_classified_trades")
        if total==0 or classified/total<require_coverage:
            reasons.append("insufficient_aggressor_classification")
        if b["real_volume"] and abs(total-b["real_volume"])/b["real_volume"]>volume_rel_tolerance:
            reasons.append("m1_vs_tick_volume_mismatch")
        # In the first+last 15 seconds: conservative sanity check, not proof
        # of true feed completeness. A low-liquidity period can fail legitimately.
        start=b["time"]*1000
        if (a["first_ms"] is None or a["first_ms"]>start+15000 or
            a["last_ms"] is None or a["last_ms"]<start+45000):
            reasons.append("incomplete_minute_tick_coverage")
        if not reasons:
            evidence["valid_flow"]=True
        out.append(evidence)
    return out

def extract_day(mt5,*,symbol,date_string,now_utc):
    symbol=valid_symbol(symbol)
    start,end=local_window(date_string)
    if end>now_utc:
        raise ValueError("Cannot audit future or incomplete day")
    terminal=mt5.terminal_info()
    if terminal is None or not bool(terminal.connected):
        raise ValueError("Local MT5 not connected to a history server")
    si=mt5.symbol_info(symbol)
    if si is None or abs(float(si.trade_tick_size)-5)>1e-6:
        raise ValueError("Requested symbol absent or not a 5-point WIN contract")
    if not mt5.symbol_select(symbol,True):
        raise ValueError(f"Failed to select {symbol}: {mt5.last_error()}")
    rates=mt5.copy_rates_range(symbol,mt5.TIMEFRAME_M1,start,end-timedelta(milliseconds=1))
    bars=canonical_m1(rates,start,end)
    if len(bars)<50:
        raise ValueError("Not enough M1 data; verify market history and symbol")
    # Pull chunks rather than one huge request. Using COPY_TICKS_TRADE still
    # exposes status flags; no buy/sell side is imputed if absent.
    seen=0
    cumulative={}
    intervals=0
    ptr=start
    while ptr<end:
        upto=min(ptr+timedelta(minutes=CHUNK_MINUTES),end)
        ticks=mt5.copy_ticks_range(symbol,ptr,upto,mt5.COPY_TICKS_TRADE)
        if ticks is None:
            raise ValueError(f"MT5 tick download failed at {ptr.isoformat()}: {mt5.last_error()}")
        piece,n=aggregate_trade_ticks(ticks,ptr,upto,max_events=MAX_TICKS_PER_DAY-seen)
        seen+=n
        for ts,v in piece.items():
            if ts in cumulative:
                raise ValueError("Tick chunk overlap: duplicate minute would corrupt delta")
            cumulative[ts]=v
        intervals+=1
        ptr=upto
    assessed=attach_quality(bars,cumulative)
    valid=sum(x["valid_flow"] for x in assessed)
    missing=sum(x["reject_reasons"]!=[] for x in assessed)
    reasons={}
    for a in assessed:
        for reason in a["reject_reasons"]:reasons[reason]=reasons.get(reason,0)+1
    report={
        "status":"LOCAL_BROKER_HISTORY_ONLY_NOT_TRACKER_OR_B3_ATTESTED",
        "date":date_string,"contract":symbol,
        "client_timezone":"America/Sao_Paulo",
        "download_time_utc":now_utc.isoformat(),
        "source":"MetaTrader5.copy_rates_range + copy_ticks_range(COPY_TICKS_TRADE)",
        "cash_trades_executed":0,"orders_sent":0,"live_approved":False,
        "candles":len(assessed),"tick_updates_examined":seen,
        "ten_minute_chunks":intervals,"valid_flow_minutes":valid,
        "rejected_minutes":missing,"rejection_reason_counts":reasons,
        "limits":"No exchange validation, partial broker tick data may be unavailable; no order fills.",
    }
    return assessed,report

def save_private(day_reports,*,output_directory):
    outdir=Path(output_directory).resolve()
    outdir.mkdir(parents=True,exist_ok=True)
    if not outdir.is_dir():raise ValueError("Invalid output directory")
    created=[]
    for record in day_reports:
        data=record["minutes"]
        meta=record["quality"]
        file=outdir/f"{meta['contract']}_{meta['date']}_flow_audit.json"
        payload={"quality":meta,"minutes":data}
        raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")
        descriptor=None
        try:
            with tempfile.NamedTemporaryFile(dir=outdir,prefix=".m1flow_",suffix=".tmp",delete=False) as fp:
                fp.write(raw)
                descriptor=Path(fp.name)
            os.replace(descriptor,file)
            descriptor=None
        finally:
            if descriptor is not None:descriptor.unlink(missing_ok=True)
        created.append({"file":str(file),"sha256":hashlib.sha256(raw).hexdigest(),
                        "valid_flow_minutes":meta["valid_flow_minutes"],
                        "rejected_minutes":meta["rejected_minutes"]})
    return created

def main():
    parser=argparse.ArgumentParser(description="Read-only MT5 WIN tick/volume provenance audit; no orders")
    parser.add_argument("--symbol",default="WINZ26")
    parser.add_argument("--date",action="append",dest="dates",required=True,
                        help="Past YYYY-MM-DD; repeat for each specific session")
    parser.add_argument("--private-dir",default="private_mt5")
    opts=parser.parse_args()
    symbol=valid_symbol(opts.symbol)
    days=sorted(set(opts.dates))
    if len(days)>5:parser.error("Up to 5 calendar dates per run")
    try:import MetaTrader5 as mt5
    except ImportError as e:raise SystemExit("Install official MetaTrader5 in a local Windows virtualenv") from e
    now=datetime.now(timezone.utc)
    initialized=False
    results=[]
    try:
        initialized=mt5.initialize()
        if not initialized:raise RuntimeError(f"MT5 local initialize failed: {mt5.last_error()}")
        for day in days:
            minutes,report=extract_day(mt5,symbol=symbol,date_string=day,now_utc=now)
            results.append({"quality":report,"minutes":minutes})
    finally:
        if initialized:mt5.shutdown()
    # Only after all sessions pass: no partial claims for missing dates.
    paths=save_private(results,output_directory=opts.private_dir)
    for file in paths:
        print(f"LOCAL_READONLY_OUTPUT {file['file']} SHA256={file['sha256']} "
              f"valid_m1={file['valid_flow_minutes']} invalid_m1={file['rejected_minutes']}")
    print("NO ORDERS, NO TRACKER SOURCE, NO PERFORMANCE CLAIMS, NO CLOUD UPLOAD")

if __name__=="__main__":main()
