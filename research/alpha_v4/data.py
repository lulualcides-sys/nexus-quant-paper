"""Official Binance SPOT M1 monthly archives; fail closed, hash verified.

All prices remain raw SPOT data. SOL grid 0.001 is a historical precision
sanity threshold, NOT a verified 2026 exchange PRICE_FILTER for real orders.
"""
from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from io import BytesIO, TextIOWrapper
from zipfile import ZipFile
import csv
from research.alpha.data import retrieve, month_seconds

SYMBOLS=("BTCUSDT","ETHUSDT","SOLUSDT")
MONTHS=("2026-07","2026-08","2026-09","2026-10")
TRANSFER_MONTHS=("2026-01","2026-02","2026-03","2026-04","2026-05","2026-06")
V5_BLIND_SOL_MONTHS=tuple(f"2025-{n:02d}" for n in range(1,13))  # unseen retrospective SOL stress
PRECISION={"BTCUSDT":Decimal("0.01"),"ETHUSDT":Decimal("0.01"),
           "SOLUSDT":Decimal("0.001")}
SOURCE="https://data.binance.vision/data/spot/monthly/klines"

def month(symbol,period):
    if symbol not in SYMBOLS or period not in (*MONTHS,*TRANSFER_MONTHS,*V5_BLIND_SOL_MONTHS):
        raise ValueError("not an approved SPOT dataset")
    filename=f"{symbol}-1m-{period}.zip"
    url=f"{SOURCE}/{symbol}/1m/{filename}"
    published=retrieve(url+".CHECKSUM").decode("ascii").strip().split()[0].lower()
    if len(published)!=64 or any(x not in "0123456789abcdef" for x in published):
        raise ValueError("malformed provider checksum")
    raw=retrieve(url)
    digest=sha256(raw).hexdigest()
    if digest!=published:
        raise ValueError("provider SHA256 mismatch")
    start,stop=month_seconds(period)
    rows=[]
    with ZipFile(BytesIO(raw)) as zipped:
        members=[s for s in zipped.namelist() if s.endswith(".csv")]
        if len(members)!=1:
            raise ValueError("unexpected CSV inventory")
        with zipped.open(members[0]) as f:
            for fields in csv.reader(TextIOWrapper(f,encoding="utf-8")):
                if len(fields)<12:raise ValueError("unexpected SPOT kline schema")
                micros=int(fields[0])
                if micros<10**14 or micros%1000000:
                    raise ValueError("expected 2026 microsecond aligned open")
                ts=micros//1000000
                if not start<=ts<stop or ts%60:
                    raise ValueError("date or M1 grid mismatch")
                o,h,l,c=map(Decimal,fields[1:5])
                volume=Decimal(fields[5])
                if min(o,h,l,c)<=0 or volume<0 or h<max(o,c) or l>min(o,c):
                    raise ValueError("invalid OHLCV")
                if any(x%PRECISION[symbol] for x in (o,h,l,c)):
                    raise ValueError("unexpected price precision, no rounding")
                rows.append(dict(time=ts,open=float(o),high=float(h),
                                 low=float(l),close=float(c),volume=float(volume)))
    expected=(stop-start)//60
    if len(rows)!=expected:
        raise ValueError(f"missing or duplicated candles: {len(rows)} vs {expected}")
    if any(item["time"]!=start+60*i for i,item in enumerate(rows)):
        raise ValueError("noncontinuous or duplicate timestamp")
    return rows,dict(venue="Binance",market="SPOT",symbol=symbol,period_utc=period,
                     timeframe="M1",url=url,sha256=digest,official_checksum_verified=True,
                     bars=len(rows),timezone="UTC",
                     precision_validation=str(PRECISION[symbol]),
                     precision_is_historical_tick_proof=False)

def aggregate(bars,minutes):
    if minutes not in (5,60):raise ValueError("unsupported aggregation")
    if len(bars)%minutes:raise ValueError("partial MTF candle")
    result=[]
    for i in range(0,len(bars),minutes):
        q=bars[i:i+minutes]
        if q[0]["time"]%(minutes*60):
            raise ValueError("unaligned candle")
        for j in range(1,len(q)):
            if q[j]["time"]-q[j-1]["time"]!=60:
                raise ValueError("missing child candle")
        result.append(dict(time=q[0]["time"],open=q[0]["open"],
                           high=max(x["high"] for x in q),
                           low=min(x["low"] for x in q),
                           close=q[-1]["close"],
                           volume=sum(x["volume"] for x in q)))
    return result
