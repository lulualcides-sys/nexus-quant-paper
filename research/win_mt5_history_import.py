"""Import MetaTrader 5 native M1 Bars CSV for research, OFFLINE ONLY.

MetaQuotes native Bars export: <DATE> <TIME> <OPEN> <HIGH> <LOW>
<CLOSE> <TICKVOL> <VOL> <SPREAD>, typically tab separated.
Only REAL volume (<VOL>) is a contract count; tick volume is NOT a substitute.
The user must supply an explicit server UTC offset and matching single WIN symbol.
No broker connection or order routing. Never append adjusted continuous futures.
See: https://www.metatrader5.com/en/terminal/help/trading_advanced/custom_instruments
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research.win_price_data import (
    TZ, _number, _tick_check, SYMBOL_RE, read_win_csv, local_day, win_session
)


def _decode(source):
    payload=Path(source).read_bytes()
    if not payload or len(payload)>150_000_000:
        raise ValueError("MT5 M1 export absent or exceeds 150 MB")
    try:
        value=payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        value=payload.decode("cp1252")  # Strict, no replacement
    return value,hashlib.sha256(payload).hexdigest()


def import_mt5_bars(source, output, *, expected_symbol, server_utc_offset_hours):
    """CSV -> audited native WIN M1 canonical CSV and quality metadata.

    Server UTC offset is REQUIRED; guesswork or use of PC clock is forbidden.
    The user must confirm their Rico MetaTrader server timezone.
    """
    symbol=expected_symbol.upper()
    if not SYMBOL_RE.fullmatch(symbol) or symbol=="WINFUT":
        raise ValueError("Expected explicit single WIN expiry, e.g. WINZ26, not WINFUT")
    if not isinstance(server_utc_offset_hours,(int,float)) or not -12<=server_utc_offset_hours<=14:
        raise ValueError("Confirm exact server time offset vs UTC, hours -12..+14")
    src_tz=timezone(timedelta(hours=server_utc_offset_hours))
    source=Path(source)
    if source.resolve()==Path(output).resolve():
        raise ValueError("Do not overwrite the raw MT5 export")
    # MT5 CSV lacks per-row ticker: original filename must name one expiry.
    name=source.stem.upper()
    if symbol not in name or re.search(r"WIN[GJMQVZ]\d{2}",name.replace(symbol,"")):
        raise ValueError("MT5 export filename must identify exactly the expected single-expiry WIN")
    text,digest=_decode(source)
    first_line=text.splitlines()[0]
    sep="\t" if "\t" in first_line else (";" if ";" in first_line else ",")
    entries=[]
    for lineno,cells in enumerate(csv.reader(text.splitlines(),delimiter=sep),1):
        if not cells or all(not v.strip() for v in cells):
            continue
        if cells[0].strip().upper().strip("<>")=="DATE":
            continue
        if len(cells)!=9:
            raise ValueError(f"MT5 line {lineno}: expected 9 native Bars CSV columns; got {len(cells)}")
        try:
            moment=datetime.strptime(cells[0].strip()+" "+cells[1].strip(), "%Y.%m.%d %H:%M:%S")
        except ValueError as exc:
            raise ValueError(f"MT5 line {lineno}: invalid native timestamp") from exc
        local=moment.replace(tzinfo=src_tz).astimezone(TZ)
        if local.weekday()>4:
            raise ValueError(f"MT5 line {lineno}: weekend under supplied timezone")
        prices=list(map(_number,cells[2:6]))
        for px in prices:
            _tick_check(px)
        o,h,lo,c=prices
        if lo>min(o,c) or h<max(o,c) or lo>h:
            raise ValueError(f"MT5 line {lineno}: inconsistent OHLC")
        tickvol=_number(cells[6])
        realvol=_number(cells[7])
        spread=_number(cells[8])
        if tickvol<0 or realvol<=0 or int(realvol)!=realvol or spread<0:
            raise ValueError("MT5 native M1 real_volume must be positive contract count; "
                             "tick_volume cannot substitute for missing real_volume")
        ts=int(local.astimezone(timezone.utc).timestamp())
        if ts%60:
            raise ValueError(f"MT5 line {lineno}: M1 timestamp not minute aligned")
        if entries and ts<=entries[-1][0]:
            raise ValueError("MT5 export must be chronological, unique; cannot silently sort")
        entries.append((ts,local,o,h,lo,c,int(realvol)))
        if len(entries)>1_000_000:
            raise ValueError("MT5 export has too many candles")
    if len(entries)<100:
        raise ValueError("At least 100 native M1 bars required")
    destination=Path(output)
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open("w",encoding="utf-8",newline="") as fp:
        writer=csv.writer(fp,delimiter=";")
        writer.writerow(["Ativo","Data","Hora","Open","High","Low","Close","Volume"])
        for _,local,o,h,lo,c,vol in entries:
            writer.writerow([symbol,local.strftime("%d/%m/%Y"),
                             local.strftime("%H:%M:%S"),
                             int(o),int(h),int(lo),int(c),vol])
    canonical=read_win_csv(destination,expected_symbol=symbol)
    if len(canonical["bars"])!=len(entries) or canonical["timeframe_seconds"]!=60:
        raise ValueError("MT5 native M1 normalization did not preserve candles")
    gaps=[(entries[i][0]-entries[i-1][0])//60-1 for i in range(1,len(entries))
          if local_day(entries[i][0])==local_day(entries[i-1][0]) and
          entries[i][0]-entries[i-1][0]>60]
    days={}
    for _,local,*_ in entries:
        ts=int(local.timestamp())
        if win_session(ts):
            label=local.date().isoformat()
            days[label]=days.get(label,0)+1
    return {
        "symbol":symbol,"source_file":source.name,"source_sha256":digest,
        "source_format":"MT5 native Bars CSV real volume, no adjusted continuous futures",
        "server_utc_offset_hours_confirmed_by_user":server_utc_offset_hours,
        "output_canonical":str(destination),
        "candles_m1":len(entries),
        "first_local":entries[0][1].isoformat(),
        "last_local":entries[-1][1].isoformat(),
        "trading_days_with_session_quotes":len(days),
        "days_with_300_or_more_session_candles":sum(x>=300 for x in days.values()),
        "intraday_gaps":len(gaps),
        "intraday_missing_minutes":sum(gaps),
        "warning":"Source is broker export not independently B3 authenticated; "
                  "Rico server time offset must be confirmed externally; "
                  "unobserved minutes invalidate trades spanning them; "
                  "no fills, fees, bid/ask or real orders are proven by bars."
    }


def main():
    parser=argparse.ArgumentParser(description="MT5 native WIN M1 quote import, offline research only")
    parser.add_argument("--csv",required=True)
    parser.add_argument("--symbol",required=True,help="Explicit original contract, e.g. WINZ26")
    parser.add_argument("--server-utc-offset",type=float,required=True,
                        help="Rico MT5 server UTC offset; MUST be checked, not guessed")
    parser.add_argument("--out",required=True)
    args=parser.parse_args()
    report=import_mt5_bars(args.csv,args.out,expected_symbol=args.symbol,
                           server_utc_offset_hours=args.server_utc_offset)
    target=Path(args.out).with_suffix(".audit.json")
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
