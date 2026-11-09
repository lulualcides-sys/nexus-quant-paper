"""WIN M1 collector from a LOCAL logged-in MetaTrader 5 Windows terminal.

Read-only: only initialize(), terminal_info(), symbol_info(), symbol_select(),
copy_rates_range(), last_error() and shutdown() are permitted. This module does
not place orders, configure EAs, read account credentials or call a broker API
over the internet. The historical series stays on the user's own computer.

MetaQuotes copy_rates_range returns UNIX UTC timestamps. It is preferable to
a manually exported CSV whose terminal-server timezone may be ambiguous.
Requires the official 'MetaTrader5' Python package (Windows), not in GitHub CI.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from research.win_price_data import (
    SYMBOL_RE, TZ, WIN_TICK, _tick_check, local_day, read_win_csv, win_session
)

MAX_ROWS = 250000
MIN_ROWS = 100
MAX_DAYS = 180


def _value(row, name):
    """Supports the official numpy structured row and deterministic mock data."""
    return row[name]


def canonicalize_mt5_rates(rates, *, symbol, now_utc, destination):
    """Validate actual MT5 bars, write official WIN CSV; never manufacture bars."""
    symbol = symbol.upper()
    if not SYMBOL_RE.fullmatch(symbol) or symbol == "WINFUT":
        raise ValueError("Expected exactly one WIN expiry such as WINZ26, not WINFUT")
    if now_utc.tzinfo is None or now_utc.utcoffset() != timedelta():
        raise ValueError("A timezone-aware UTC timestamp is mandatory")
    if len(rates) > MAX_ROWS:
        raise ValueError("Too many WIN M1 bars")
    now_s = int(now_utc.timestamp())
    cleaned = []
    previous = None
    dropped_live_bar = 0
    for n, row in enumerate(rates, 1):
        stamp = int(_value(row,"time"))
        # A completed bar can only be used after its entire M1 window ends.
        if stamp > now_s:
            raise ValueError(f"WIN bar {n}: future market timestamp")
        if stamp % 60:
            raise ValueError(f"WIN bar {n}: timestamp is not M1-aligned")
        if previous is not None and stamp <= previous:
            raise ValueError(f"WIN bar {n}: duplicate/out-of-order MT5 history")
        previous = stamp
        if stamp + 60 > now_s:
            dropped_live_bar += 1
            continue
        o,h,l,c=(float(_value(row,k)) for k in ("open","high","low","close"))
        for p in (o,h,l,c):
            _tick_check(p)
        if l>min(o,c) or h<max(o,c) or l>h:
            raise ValueError(f"WIN bar {n}: impossible OHLC")
        real_vol=float(_value(row,"real_volume"))
        if not real_vol.is_integer() or real_vol<=0:
            raise ValueError(f"WIN bar {n}: real_volume missing; tick_volume is NOT tradable contract quantity")
        if float(_value(row,"tick_volume"))<0 or float(_value(row,"spread"))<0:
            raise ValueError(f"WIN bar {n}: invalid tick volume or spread")
        local=datetime.fromtimestamp(stamp, timezone.utc).astimezone(TZ)
        if local.weekday()>4:
            raise ValueError(f"WIN bar {n}: weekend under documented UTC MT5 timestamp")
        cleaned.append((stamp, local, o,h,l,c,int(real_vol)))
    if len(cleaned)<MIN_ROWS:
        raise ValueError(f"Insufficient COMPLETE genuine M1 bars (received {len(cleaned)})")
    # Only ever write in local private folder, never to GitHub.
    target=Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Safe atomic write avoids leaving a half-valid exported series after error.
    tmp=None
    try:
        with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",newline="",
                                         dir=target.parent,prefix=".win_m1_",suffix=".tmp",
                                         delete=False) as fp:
            tmp=Path(fp.name)
            writer=csv.writer(fp, delimiter=";")
            writer.writerow(["Ativo","Data","Hora","Open","High","Low","Close","Volume"])
            for _,local,o,h,l,c,v in cleaned:
                writer.writerow([symbol,local.strftime("%d/%m/%Y"),
                                 local.strftime("%H:%M:%S"),
                                 int(o),int(h),int(l),int(c),v])
        confirmed=read_win_csv(tmp, expected_symbol=symbol)
        if confirmed["timeframe_seconds"]!=60 or len(confirmed["bars"])!=len(cleaned):
            raise ValueError("Canonical M1 roundtrip did not preserve input history")
        os.replace(tmp,target)
        tmp=None
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
    day_counts={}
    gap_events=gap_minutes=0
    for i,(stamp,local,*_) in enumerate(cleaned):
        if win_session(stamp):
            day=local.date().isoformat()
            day_counts[day]=day_counts.get(day,0)+1
        if i:
            prev_stamp=cleaned[i-1][0]
            if local_day(prev_stamp)==local_day(stamp) and stamp-prev_stamp>60:
                gap_events+=1
                gap_minutes+=(stamp-prev_stamp)//60-1
    audit={
        "status":"MT5_LOCAL_READONLY_HISTORY_NOT_LIVE_PROFIT",
        "contract":symbol,
        "market":"WIN",
        "timeframe":"M1",
        "timestamp_interpretation":"UTC per MetaTrader5 Python copy_rates_range documentation",
        "local_display_timezone":"America/Sao_Paulo",
        "real_volume_units":"contracts; NEVER tick_volume",
        "candles_complete":len(cleaned),
        "discarded_incomplete_current_bar":dropped_live_bar,
        "start_local":cleaned[0][1].isoformat(),
        "end_local":cleaned[-1][1].isoformat(),
        "days_with_session_candles":len(day_counts),
        "session_days_at_least_300_bars":sum(v>=300 for v in day_counts.values()),
        "same_day_gap_events":gap_events,
        "same_day_missing_minutes":gap_minutes,
        "canonical_csv_sha256":hashlib.sha256(target.read_bytes()).hexdigest(),
        "history_location":str(target),
        "no_orders_sent":True,
        "broker_fills_verified":False,
        "warning":"MT5 server history is not a verified B3 tick feed; bars do not prove queue/fills, "
                  "the terminal may limit history to Max. bars in chart; "
                  "missing periods must not be interpreted as flat prices."
    }
    return confirmed,audit


def collect_from_terminal(mt5, *, symbol, days, destination, now_utc):
    """Pure dependency-injected orchestration: MT5 access is read-only."""
    if not isinstance(days,int) or not 1<=days<=MAX_DAYS:
        raise ValueError(f"days must be in [1,{MAX_DAYS}]")
    if not isinstance(symbol,str) or not SYMBOL_RE.fullmatch(symbol) or symbol.upper()=="WINFUT":
        raise ValueError("Use an explicit single-expiry WIN contract")
    terminal=mt5.terminal_info()
    if terminal is None or not bool(terminal.connected):
        raise ValueError("MT5 terminal is not connected to market data")
    info=mt5.symbol_info(symbol)
    if info is None:
        raise ValueError(f"Contract {symbol} is not available in this MT5 terminal")
    # WIN tick grid is 5 index points. Reject another financial product.
    tick=float(info.trade_tick_size)
    if abs(tick-WIN_TICK)>1e-6:
        raise ValueError(f"MT5 symbol tick size {tick} is not WIN's 5 points")
    if not mt5.symbol_select(symbol,True):
        raise ValueError(f"MT5 cannot select contract {symbol}: {mt5.last_error()}")
    start=now_utc-timedelta(days=days)
    # Official MetaTrader5 stores and returns bar timestamps as UTC.
    bars=mt5.copy_rates_range(symbol,mt5.TIMEFRAME_M1,start,now_utc)
    if bars is None:
        raise ValueError(f"MT5 historical M1 retrieval failed: {mt5.last_error()}")
    data,audit=canonicalize_mt5_rates(bars,symbol=symbol,now_utc=now_utc,
                                     destination=destination)
    audit["requested_days"]=days
    audit["official_source_method"]="MetaTrader5.copy_rates_range, read-only"
    return data,audit


def run_research(bars, *, contract, fee_roundtrip_brl=1.40):
    """Frozen sweep policy, two cost/slippage scenarios; no automated approval."""
    from research.win_liquidity_sweep import Parameters,simulate
    if not 0<=fee_roundtrip_brl<=20:
        raise ValueError("Invalid modeled fee")
    # Separate chronological windows, no model fitting or optimization.
    days=sorted({local_day(bar["time"]) for bar in bars})
    if len(days)<3:
        raise ValueError("Need at least three trading days for chronological report")
    split_idx=max(1,min(len(days)-1,int(len(days)*0.7)))
    split=days[split_idx]
    windows={"early_research":(None,split),"later_evaluation":(split,None)}
    results={}
    for window,(start,end) in windows.items():
        scenarios={}
        for label,slippage,gate in (("normal_original",1,0.0),
                                     ("normal_net_rr1",1,1.0),
                                     ("stress_original",2,0.0),
                                     ("stress_net_rr1",2,1.0)):
            # No RLP assumed; fee is an EXPLICIT hypothesis, not account quote.
            cfg=Parameters(fee_roundtrip_brl=fee_roundtrip_brl,
                           slippage_ticks_each_side=slippage,
                           min_net_rr=gate,
                           capital_brl=2000,per_trade_risk=0.01)
            output=simulate(bars,cfg,start_date=start,end_date=end)
            ledger=output.pop("ledger")
            if any((start is not None and local_day(x["entry_time"])<start) or
                   (end is not None and local_day(x["entry_time"])>=end)
                   for x in ledger):
                raise AssertionError("Trade entered outside its own period")
            output["max_sequential_losses"]=max(
                (len(s) for s in "".join("L" if x["net_brl"]<0 else "W" for x in ledger).split("W")),
                default=0)
            output["ledger"]=ledger
            scenarios[label]=output
        results[window]=scenarios
    return {
        "status":"RESEARCH_ONLY_NO_LIVE_TRADING",
        "contract":contract,
        "timeframe":"M1 signals, M5 completed only",
        "chronological_split_day":split,
        "starting_brl_each_window":2000,
        "contracts_at_once":1,
        "daily_loss_lockout":False,
        "cost_roundtrip_fee_assumption_brl":fee_roundtrip_brl,
        "slippage_per_side_ticks_tested":[1,2],
        "historical_data_only":True,
        "strategy_unchanged":True,
        "approved_live":False,
        "results":results,
        "limitations":[
            "Cost estimate must be replaced by user's actual Rico fee statement.",
            "MT5 history and 1-minute OHLC do not verify orders, queue priority or slippage.",
            "One contract, no daily stop can lose entire reference capital.",
            "Even positive later-window P&L without many independent trades is insufficient.",
            "No parameter fitting or true out-of-sample claim unless source and dates are unused."
        ],
    }


def main():
    p=argparse.ArgumentParser(description="Offline read-only MetaTrader5 WIN data collector")
    p.add_argument("--symbol",required=True,help="A single WIN expiry, e.g. WINZ26")
    p.add_argument("--days",type=int,default=90)
    p.add_argument("--terminal",default=None,help="Optional path to local MT5 terminal64.exe")
    p.add_argument("--output-dir",default="private_mt5")
    p.add_argument("--fee-roundtrip",type=float,default=1.40,
                   help="Hypothesized brokerage+exchange fee, not a verified Rico charge")
    args=p.parse_args()
    if not isinstance(args.symbol,str) or not SYMBOL_RE.fullmatch(args.symbol) or args.symbol.upper()=="WINFUT":
        p.error("Use a single WIN expiration code only")
    if not 1<=args.days<=MAX_DAYS:
        p.error("days out of bounds (1-180)")
    # No orders, passwords, brokerage account IDs or remote upload.
    try:
        import MetaTrader5 as mt5
    except ImportError as exc:
        raise SystemExit("Python MetaTrader5 package not installed. Use Windows with MT5 and 'py -m pip install MetaTrader5'") from exc
    symbol=args.symbol.upper()
    now_utc=datetime.now(timezone.utc)
    dest=Path(args.output_dir)
    dest.mkdir(parents=True,exist_ok=True)
    target=dest/f"{symbol}_M1_{now_utc:%Y%m%dT%H%M%SZ}.csv"
    connected=False
    try:
        connected=(mt5.initialize(args.terminal) if args.terminal else mt5.initialize())
        if not connected:
            raise ValueError(f"MT5 initialize failed: {mt5.last_error()}")
        source,audit=collect_from_terminal(mt5,symbol=symbol,days=args.days,
                                           destination=target,now_utc=now_utc)
    finally:
        if connected:
            mt5.shutdown()
    result=run_research(source["bars"],contract=symbol,
                        fee_roundtrip_brl=args.fee_roundtrip)
    file_report=dest/f"{symbol}_research_{now_utc:%Y%m%dT%H%M%SZ}.json"
    file_report.write_text(json.dumps({"source_audit":audit,"research":result},
                                      ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    # Do not print account IDs, credentials, raw trade data, or expose report remotely.
    print("Saved private MT5 history:",target)
    print("Saved read-only research:",file_report)
    print("Data quality:",audit["candles_complete"],"complete M1 bars;",
          audit["same_day_missing_minutes"],"missing intraday minutes")
    for window,scenarios in result["results"].items():
        print(window,":",
              ", ".join(f"{k}: {v['trades']} trades, {v['net_brl']:+.2f} BRL"
                        for k,v in scenarios.items()))
    print("NOT APPROVED FOR LIVE EXECUTION. No MT5 orders sent.")


if __name__=="__main__":
    main()
