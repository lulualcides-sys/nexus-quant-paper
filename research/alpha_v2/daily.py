"""Daily Binance SPOT M1 archives for the strictly unseen November 1-7 check.

Never uses exchange API keys; fails closed on missing days, row/price/timestamp
corruption or mismatched official SHA256. No filling missing days.
"""
from datetime import datetime,timezone
from decimal import Decimal
from hashlib import sha256
from io import BytesIO,TextIOWrapper
from zipfile import ZipFile
import csv
from research.alpha.data import SYMBOLS,TICK,retrieve

DAYS=tuple(f"2026-11-{i:02d}" for i in range(1,8))
ROOT="https://data.binance.vision/data/spot/daily/klines"

def read_day(data,symbol,day):
    if symbol not in SYMBOLS or day not in DAYS:
        raise ValueError("unapproved daily sample")
    start=int(datetime.strptime(day,"%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    records=[]
    with ZipFile(BytesIO(data)) as archive:
        names=[n for n in archive.namelist() if n.endswith(".csv")]
        if len(names)!=1:
            raise ValueError("invalid archive inventory")
        with archive.open(names[0]) as source:
            for fields in csv.reader(TextIOWrapper(source,encoding="utf-8")):
                if len(fields)<12:
                    raise ValueError("unexpected Binance SPOT format")
                micros=int(fields[0])
                if micros<10**14 or micros%1_000_000:
                    raise ValueError("unexpected 2026 microsecond M1 open")
                ts=micros//1_000_000
                o,h,l,c=(Decimal(x) for x in fields[1:5])
                volume=Decimal(fields[5])
                if not start<=ts<start+86400 or ts%60:
                    raise ValueError("cross-day/time-grid mismatch")
                if min(o,h,l,c)<=0 or volume<0 or h<max(o,c) or l>min(o,c):
                    raise ValueError("corrupted OHLCV")
                if any(x%TICK[symbol] for x in (o,h,l,c)):
                    raise ValueError("invalid crypto spot price grid")
                records.append(dict(time=ts,open=float(o),high=float(h),
                                    low=float(l),close=float(c),volume=float(volume)))
    if len(records)!=1440 or any(b["time"]!=start+60*i for i,b in enumerate(records)):
        raise ValueError("incomplete/duplicate daily SPOT archive")
    return records

def load_week(symbol):
    if symbol not in SYMBOLS: raise ValueError("unapproved symbol")
    result=[];manifest=[]
    for day in DAYS:
        archive=f"{symbol}-1m-{day}.zip"
        url=f"{ROOT}/{symbol}/1m/{archive}"
        checksum=retrieve(url+".CHECKSUM").decode("utf8").strip().split()[0].lower()
        if len(checksum)!=64 or any(x not in "0123456789abcdef" for x in checksum):
            raise ValueError("bad provider checksum")
        payload=retrieve(url)
        digest=sha256(payload).hexdigest()
        if digest!=checksum:raise ValueError("provider SHA256 mismatch")
        rows=read_day(payload,symbol,day)
        result.extend(rows)
        manifest.append(dict(provider="Binance public SPOT daily klines",symbol=symbol,
                             timeframe="1m",day_utc=day,source=url,sha256=digest,
                             rows=len(rows),verified=True,timezone="UTC"))
    if len(result)!=1440*len(DAYS):
        raise ValueError("partial week")
    return result,manifest
