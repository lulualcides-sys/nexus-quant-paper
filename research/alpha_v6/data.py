"""Official Binance SPOT full-minute monthly ZIPs with exact SHA256, no fill-in.

XRP/BNB are new evaluation markets, SOL was already inspected. 8 decimal
digit price parsing is a sanity bound, not proof of archived executable tick.
"""
from __future__ import annotations
import csv
from datetime import datetime,timezone
from decimal import Decimal
from hashlib import sha256
from io import BytesIO,TextIOWrapper
from zipfile import ZipFile
from research.alpha.data import month_seconds,retrieve

MARKETS=("SOLUSDT","BNBUSDT","XRPUSDT")
MONTHS=tuple(f"{year}-{mo:02d}" for year,last in ((2025,12),(2026,10))
             for mo in range(1,last+1))
BASE="https://data.binance.vision/data/spot/monthly/klines"
DECIMALS=Decimal("0.00000001")

def load_month(symbol,period):
    if symbol not in MARKETS or period not in MONTHS:
        raise ValueError("research source not approved")
    file=f"{symbol}-1m-{period}.zip"
    url=f"{BASE}/{symbol}/1m/{file}"
    response=retrieve(url+".CHECKSUM").decode("utf-8").split()
    if not response:
        raise ValueError("no official SHA256")
    checksum=response[0].lower()
    if len(checksum)!=64 or any(x not in "0123456789abcdef" for x in checksum):
        raise ValueError("bad checksum file")
    payload=retrieve(url)
    actual=sha256(payload).hexdigest()
    if actual!=checksum:raise ValueError("official ZIP SHA256 mismatch")
    begin,stop=month_seconds(period)
    candles=[]
    with ZipFile(BytesIO(payload)) as z:
        names=[name for name in z.namelist() if name.endswith(".csv")]
        if len(names)!=1:raise ValueError("bad monthly ZIP inventory")
        with z.open(names[0]) as f:
            for row in csv.reader(TextIOWrapper(f,encoding="utf-8")):
                if len(row)<12:raise ValueError("bad SPOT M1 fields")
                timestamp=int(row[0])
                if timestamp<10**14 or timestamp%1_000_000:
                    raise ValueError("open time not aligned microseconds")
                t=timestamp//1_000_000
                if not begin<=t<stop or t%60:
                    raise ValueError("open time outside month M1 grid")
                o,h,l,c=map(Decimal,row[1:5])
                volume=Decimal(row[5])
                if min(o,h,l,c)<=0 or volume<0 or h<max(o,c) or l>min(o,c):
                    raise ValueError("invalid OHLCV")
                if any(x%DECIMALS for x in (o,h,l,c)):
                    raise ValueError("over-precision price, do not round source")
                candles.append(dict(time=t,open=float(o),high=float(h),
                                    low=float(l),close=float(c),volume=float(volume)))
    expected=(stop-begin)//60
    if len(candles)!=expected:
        raise ValueError(f"incomplete M1 source, {len(candles)} != {expected}")
    for i,b in enumerate(candles):
        if b["time"]!=begin+60*i:raise ValueError("source gap or duplicate")
    return candles,dict(provider="Binance public SPOT monthly M1",symbol=symbol,
                        date_utc=period,timeframe="M1",url=url,sha256=actual,
                        official_checksum=True,rows=expected,timezone="UTC",
                        price_precision_validation="0.00000001",
                        historical_exchange_tick_filters_verified=False)

def continuous(symbol):
    candles=[];manifest=[]
    for period in MONTHS:
        rows,provenance=load_month(symbol,period)
        if candles and rows[0]["time"]-candles[-1]["time"]!=60:
            raise ValueError("cross-month missing candles or untrusted source")
        candles.extend(rows)
        manifest.append(provenance)
    return candles,manifest
