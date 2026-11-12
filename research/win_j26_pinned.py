"""PINNED third-party WINJ26 Profit M1 export; no continuous roll/fake bars.

The historical source is NOT B3-authenticated. The contract symbol and Git blob
hash are strict; Quantity (contracts) is distinct from financial Volume.
"""
from __future__ import annotations

import csv
import hashlib
import io
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from research.win_price_data import _number, _tick_check, TZ, read_win_csv

SYMBOL = "WINJ26"
SOURCE_URL = ("https://raw.githubusercontent.com/wesleyzilva/tradetech/main/"
              "dados/candles/2024-2025/WINJ26_F_0_1min.csv")
SOURCE_BLOB = "7fcc91ebde3e674f910ac82eef00b6bf19541151"
MAX_SIZE = 1_500_000


def git_blob_hash(payload):
    return hashlib.sha1(b"blob " + str(len(payload)).encode() + b"\x00" + payload).hexdigest()


def canonicalize_payload(payload, destination, *, expect_hash=SOURCE_BLOB):
    actual = git_blob_hash(payload)
    if actual != expect_hash:
        raise ValueError("WINJ26 content changed or does not match expected pinned blob")
    if not payload or len(payload) >= MAX_SIZE:
        raise ValueError("WINJ26 payload length invalid")
    # Some Profit CSV exports encode Portuguese headings with Windows-1252.
    # Decode STRICTLY: no 'errors=replace' or corrupted field bytes.
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = payload.decode("cp1252")
    rows = []
    for lineno, cells in enumerate(csv.reader(io.StringIO(text), delimiter=";"), 1):
        if not cells or all(not v.strip() for v in cells):
            continue
        if cells[0].strip().lower() == "ativo":
            continue
        if len(cells) != 9 or cells[0].strip().upper() != SYMBOL:
            raise ValueError(f"WINJ26 wrong symbol or schema at line {lineno}")
        local = datetime.strptime(cells[1].strip() + " " + cells[2].strip(), "%d/%m/%Y %H:%M:%S")
        if local.weekday() > 4 or local.replace(tzinfo=TZ).astimezone(timezone.utc) > datetime.now(timezone.utc):
            raise ValueError("WINJ26 invalid/future session")
        o, h, l, c = map(_number, cells[3:7])
        for px in (o, h, l, c):
            _tick_check(px)
        if l > min(o, c) or h < max(o, c):
            raise ValueError("WINJ26 invalid OHLC")
        monetary_volume = _number(cells[7])
        traded_contracts = _number(cells[8])
        if monetary_volume <= 0 or traded_contracts <= 0 or traded_contracts != int(traded_contracts):
            raise ValueError("WINJ26 invalid traded quantity or monetary volume")
        rows.append((local, o, h, l, c, int(traded_contracts)))
    if len(rows) < 100:
        raise ValueError("Insufficient historical WINJ26 M1")
    rows.sort(key=lambda r:r[0])
    if any(rows[i][0] <= rows[i-1][0] for i in range(1,len(rows))):
        raise ValueError("WINJ26 M1 duplicate timestamps")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as fp:
        w = csv.writer(fp, delimiter=";")
        w.writerow(["Ativo","Data","Hora","Open","High","Low","Close","Volume"])
        for dt,o,h,l,c,q in rows:
            w.writerow([SYMBOL, dt.strftime("%d/%m/%Y"), dt.strftime("%H:%M:%S"),
                        int(o), int(h), int(l), int(c), q])
    loaded = read_win_csv(destination, expected_symbol=SYMBOL)
    if len(loaded["bars"]) != len(rows) or loaded["timeframe_seconds"] != 60:
        raise ValueError("WINJ26 source not native M1")
    return loaded, {
        "url":SOURCE_URL, "git_blob_sha1":actual,
        "sha256":hashlib.sha256(payload).hexdigest(), "candles":len(rows),
        "first":rows[0][0].isoformat(), "last":rows[-1][0].isoformat(),
        "quantity_column":"Quantidade", "not":"financial Volume",
        "source_verified_by_B3":False,
    }


def fetch(destination):
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent":"NexusQuant research-source-audit/1.0"})
    with urllib.request.urlopen(req, timeout=45) as response:
        payload=response.read(MAX_SIZE)
    return canonicalize_payload(payload,destination)
