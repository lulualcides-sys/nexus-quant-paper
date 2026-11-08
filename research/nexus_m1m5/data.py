"""Fail-closed Binance SPOT kline ingestion; no synthetic candles or trading API."""
from __future__ import annotations

import csv
import hashlib
import io
import re
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = "https://data.binance.vision/data/spot/monthly/klines"
ALLOWED = {"BTCUSDT", "ETHUSDT"}
INTERVAL_MS = {"1m": 60_000, "5m": 300_000}
SINCE_US = 1_735_689_600_000  # 2025-01-01T00:00:00Z in milliseconds


@dataclass(frozen=True, slots=True)
class Bar:
    t: int  # UTC milliseconds, OPEN time
    o: float
    h: float
    l: float
    c: float
    v: float  # BASE volume
    taker: float  # taker-buy BASE volume
    qv: float = 0.0
    trades: int = 0


def normalize_time(raw: str) -> tuple[int, int]:
    """Return UTC milliseconds and original unit factor (1 or 1000)."""
    x = int(raw)
    if x >= 10**15:  # microseconds, starting Jan 2025 for spot
        if x % 1000:  # close time can contain 999 microseconds
            return x // 1000, 1000
        return x // 1000, 1000
    if x >= 10**12:
        return x, 1
    raise ValueError("Invalid epoch scale; must be milliseconds or microseconds")


def parse_rows(rows, interval: str, *, expected_month: str | None = None):
    """Strictly ordered; reject any gaps/duplicates rather than invent fills."""
    if interval not in INTERVAL_MS:
        raise ValueError("Unsupported interval")
    step = INTERVAL_MS[interval]
    previous = None
    output = []
    for n, row in enumerate(rows, 1):
        if len(row) != 12:
            raise ValueError(f"Wrong Binance kline field count on row {n}")
        t, factor = normalize_time(row[0])
        ct, close_factor = normalize_time(row[6])
        if factor != close_factor or (t >= SINCE_US and factor != 1000):
            raise ValueError(f"Incorrect time units at row {n}")
        if expected_month and datetime.fromtimestamp(t / 1000, timezone.utc).strftime("%Y-%m") != expected_month:
            raise ValueError(f"Candle outside requested month, row {n}")
        if t % step or ct != t + step - 1:
            raise ValueError(f"Misaligned candle open/close time at row {n}")
        o, h, l, c, v = [float(row[i]) for i in (1, 2, 3, 4, 5)]
        qv, taker = float(row[7]), float(row[9])
        trades = int(row[8])
        if not (0 < l <= min(o, c) <= max(o, c) <= h and v >= 0 and
                0 <= taker <= v + max(1e-8, v * 1e-8) and qv >= 0 and trades >= 0):
            raise ValueError(f"Invalid OHLCV / taker-buy on row {n}")
        if previous is not None and t != previous + step:
            raise ValueError(f"Gap, reorder or duplicate at row {n}: {previous} -> {t}")
        output.append(Bar(t, o, h, l, c, v, taker, qv, trades))
        previous = t
    if not output:
        raise ValueError("Empty Binance archive")
    return output


def month_range(end: str, count: int):
    if not re.fullmatch(r"20\d\d-(0[1-9]|1[0-2])", end) or not 1 <= count <= 48:
        raise ValueError("Invalid month selection")
    y, m = map(int, end.split("-"))
    for k in range(count - 1, -1, -1):
        ordinal = y * 12 + m - 1 - k
        yield f"{ordinal // 12:04d}-{ordinal % 12 + 1:02d}"


def _get(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": "NexusQuantResearch/1.0"})
    with urllib.request.urlopen(request, timeout=120) as f:
        return f.read()


def get_month(symbol: str, interval: str, month: str, cache: Path):
    if symbol not in ALLOWED or interval not in INTERVAL_MS or not re.fullmatch(r"20\d\d-\d\d", month):
        raise ValueError("Unsupported source parameters")
    filename = f"{symbol}-{interval}-{month}.zip"
    url = f"{ROOT}/{symbol}/{interval}/{filename}"
    folder = cache / symbol / interval
    folder.mkdir(parents=True, exist_ok=True)
    zpath = folder / filename
    chkpath = folder / (filename + ".CHECKSUM")
    if not zpath.exists():
        zpath.write_bytes(_get(url))
    # Always obtain the authoritative published checksum, even for cached files.
    if not chkpath.exists():
        chkpath.write_bytes(_get(url + ".CHECKSUM"))
    found = re.fullmatch(rb"\s*([a-fA-F0-9]{64})\s+\*?([A-Za-z0-9_.-]+)\s*", chkpath.read_bytes())
    if not found or found.group(2).decode() != filename:
        raise ValueError(f"Invalid checksum manifest: {filename}")
    digest = hashlib.sha256(zpath.read_bytes()).hexdigest()
    if digest.lower() != found.group(1).decode().lower():
        zpath.unlink(missing_ok=True)
        raise ValueError(f"Checksum mismatch: {filename}")
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
        if names != [filename.replace(".zip", ".csv")]:
            raise ValueError("Unexpected ZIP content")
        with z.open(names[0]) as content:
            rows = parse_rows(csv.reader(io.TextIOWrapper(content, encoding="utf-8-sig")),
                              interval, expected_month=month)
    # Published MONTHLY archives must cover the full UTC calendar month.
    y, m = map(int, month.split("-"))
    start_utc = int(datetime(y, m, 1, tzinfo=timezone.utc).timestamp() * 1000)
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    end_utc = int(datetime(ny, nm, 1, tzinfo=timezone.utc).timestamp() * 1000)
    if rows[0].t != start_utc or rows[-1].t + INTERVAL_MS[interval] != end_utc:
        raise ValueError(f"Incomplete calendar month: {filename}")
    return rows, {"url": url, "sha256": digest, "candles": len(rows),
                  "first_open_utc_ms": rows[0].t, "last_open_utc_ms": rows[-1].t}


def load_history(symbol: str, interval: str, months, cache: Path):
    data = []
    sources = []
    for month in months:
        rows, manifest = get_month(symbol, interval, month, cache)
        if data and rows[0].t != data[-1].t + INTERVAL_MS[interval]:
            raise ValueError(f"Gap across months: {symbol} {interval} {month}")
        data.extend(rows)
        sources.append(manifest)
    return data, sources


def aggregate_closed_m15(bars):
    """Only contiguous and aligned triplets of M5 bars can create M15 bars."""
    if not bars:
        return []
    output = []
    for start in range(0, len(bars) - 2):
        a, b, c = bars[start:start + 3]
        if (a.t % 900_000 != 0 or b.t != a.t + 300_000 or c.t != a.t + 600_000):
            continue
        output.append(Bar(a.t, a.o, max(a.h, b.h, c.h), min(a.l, b.l, c.l),
                          c.c, a.v + b.v + c.v, a.taker + b.taker + c.taker,
                          a.qv + b.qv + c.qv, a.trades + b.trades + c.trades))
    return output
