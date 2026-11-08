"""Fail-closed Binance SPOT monthly 1m OHLCV download, not derivatives/WINFUT.

2025+ Binance SPOT archives use microsecond timestamps. No missing bar filling.
SHA256 of the zip must match the provider's CHECKSUM before any signal evaluation.
"""
from __future__ import annotations
from datetime import datetime,timezone
from decimal import Decimal
from hashlib import sha256
from io import BytesIO,TextIOWrapper
from urllib.request import Request,urlopen
from zipfile import ZipFile
import csv

SOURCE="https://data.binance.vision/data/spot/monthly/klines"
SYMBOLS=("BTCUSDT","ETHUSDT")
MONTHS=("2026-08","2026-09","2026-10")
TICK={"BTCUSDT":Decimal("0.01"),"ETHUSDT":Decimal("0.01")}
SOURCE_REPOSITORY="https://github.com/binance/binance-public-data"

def retrieve(url):
    req=Request(url,headers={"User-Agent":"NexusQuant-Alpha-Research/1.0"})
    with urlopen(req,timeout=50) as response:
        return response.read()

def month_seconds(s):
    y,m=(int(x) for x in s.split("-"))
    start=int(datetime(y,m,1,tzinfo=timezone.utc).timestamp())
    stop=int(datetime(y+1,1,1,tzinfo=timezone.utc).timestamp()) if m==12 else int(datetime(y,m+1,1,tzinfo=timezone.utc).timestamp())
    return start,stop

def parse_archive(data,symbol,month):
    if symbol not in SYMBOLS or month not in (*MONTHS,"2026-07"):
        raise ValueError("unapproved market or month")
    start,end=month_seconds(month)
    rows=[]
    with ZipFile(BytesIO(data)) as archive:
        names=[n for n in archive.namelist() if n.endswith(".csv")]
        if len(names)!=1:
            raise ValueError("unexpected CSV archive")
        with archive.open(names[0]) as raw:
            reader=csv.reader(TextIOWrapper(raw,encoding="utf-8"))
            for row in reader:
                if len(row)<12:
                    raise ValueError("invalid SPOT kline CSV schema")
                n=int(row[0])
                if n<10**14:
                    raise ValueError("SPOT 2026 must use microsecond timestamp")
                if n%1000000:
                    raise ValueError("off-grid 1m source open timestamp")
                ts=n//1000000
                o,h,l,c=(Decimal(v) for v in row[1:5])
                v=Decimal(row[5])
                if not start<=ts<end or ts%60:
                    raise ValueError("month/time-grid mismatch")
                if min(o,h,l,c)<=0 or v<0 or h<max(o,c) or l>min(o,c):
                    raise ValueError("OHLCV corrupt")
                if any(price%TICK[symbol]!=0 for price in (o,h,l,c)):
                    raise ValueError("SPOT tick size mismatch, verify historical filters")
                rows.append(dict(time=ts,open=float(o),high=float(h),low=float(l),
                                 close=float(c),volume=float(v)))
    if len(rows)!=(end-start)//60:
        raise ValueError("partial month or duplicate observations")
    if rows[0]["time"]!=start or rows[-1]["time"]!=end-60:
        raise ValueError("partial market day or wrong source")
    for left,right in zip(rows,rows[1:]):
        if right["time"]-left["time"]!=60:
            raise ValueError("missing/duplicated 1m candles")
    return rows

def download_month(symbol,month):
    if symbol not in SYMBOLS or month not in (*MONTHS,"2026-07"):
        raise ValueError("unapproved market or month")
    name=f"{symbol}-1m-{month}.zip"
    url=f"{SOURCE}/{symbol}/1m/{name}"
    checksum_text=retrieve(url+".CHECKSUM").decode("utf-8").strip()
    digest=checksum_text.split()[0].lower()
    if len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("provider checksum malformed")
    zipped=retrieve(url)
    hash_value=sha256(zipped).hexdigest()
    if hash_value!=digest:
        raise ValueError("official SHA256 checksum mismatch")
    candles=parse_archive(zipped,symbol,month)
    return candles,dict(provider="Binance public SPOT archive",symbol=symbol,contract=None,
                        interval="1m",month_utc=month,zip_url=url,sha256=hash_value,
                        official_checksum=checksum_text,source_repository=SOURCE_REPOSITORY,
                        timezone="UTC",rows=len(candles),checksum_verified=True,
                        license_note="Public provider export; verify usage terms before redistribution")

def load_symbol(symbol):
    all_rows=[]; manifest=[]
    for month in MONTHS:
        bars,meta=download_month(symbol,month)
        all_rows.extend(bars)
        manifest.append(meta)
    for a,b in zip(all_rows,all_rows[1:]):
        if b["time"]-a["time"]!=60:
            raise ValueError("gap across source months")
    return all_rows,manifest

def aggregate_5m(bars):
    """Five completed M1 candles only; never interpolate missing rows."""
    if len(bars)%5:
        raise ValueError("partial five-minute aggregate")
    out=[]
    for i in range(0,len(bars),5):
        q=bars[i:i+5]
        if len(q)!=5 or q[0]["time"]%300 or any(q[j]["time"]-q[j-1]["time"]!=60 for j in range(1,5)):
            raise ValueError("M5 incomplete/out of order")
        out.append(dict(time=q[0]["time"],open=q[0]["open"],
                        high=max(x["high"] for x in q),low=min(x["low"] for x in q),
                        close=q[-1]["close"],volume=sum(x["volume"] for x in q)))
    return out
