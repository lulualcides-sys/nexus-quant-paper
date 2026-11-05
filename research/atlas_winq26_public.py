"""Auditably import the public Profit export for the SINGLE WINQ26 contract.

Source: wesleyzilva/tradetech, dados/candles/2026-2S_Q26/
WINQ26_F_0_1min.csv (public repository, blob 43c50f01882f1ac497a218549e0bff2964d94aa5).

IMPORTANT: 9 columns: Ativo, Data, Hora, OHLC, *financial* Volume,
Quantidade (= actual traded contract count). NEVER use financial volume as
contract count, or use adjusted WINFUT continuous index prices as executable.
This source is not independently exchange-audited and is suitable for
exploratory backtests, not guarantees or brokerage fills.
"""
from __future__ import annotations

import csv
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from research.win_price_data import _number, _tick_check, TZ, read_win_csv

SOURCE_REPO = "wesleyzilva/tradetech"
SOURCE_FILE = "dados/candles/2026-2S_Q26/WINQ26_F_0_1min.csv"
SOURCE_BLOB = "43c50f01882f1ac497a218549e0bff2964d94aa5"
SOURCE_URL = "https://raw.githubusercontent.com/" + SOURCE_REPO + "/main/" + SOURCE_FILE
SYMBOL = "WINQ26"


def fetch(path, *, download=True):
    """User-accessible third-party data: download into local temp workspace."""
    if not download:
        raise ValueError("Network download disabled")
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent":"ATLAS research-data-audit/1.0"})
    with urllib.request.urlopen(req, timeout=50) as resp:
        payload = resp.read(12_000_000)
    if not payload or len(payload) >= 12_000_000:
        raise ValueError("WINQ26 raw file missing/oversized")
    # Pin the public Git *blob content*, not a mutable URL.
    blob_sha1=hashlib.sha1(b"blob " + str(len(payload)).encode() + b"\\x00" + payload).hexdigest()
    if blob_sha1 != SOURCE_BLOB:
        raise ValueError("WINQ26 public dataset changed: pinned Git blob SHA1 mismatch")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return {"source": SOURCE_URL, "sha256": hashlib.sha256(payload).hexdigest(),
            "size": len(payload), "source_blob_sha1": SOURCE_BLOB}


def canonicalize(raw_path, converted_path):
    """Canonical sort, no silent drop; use traded QUANTIDADE as volume."""
    raw_path, converted_path = Path(raw_path), Path(converted_path)
    rows = []
    with raw_path.open(encoding="utf-8-sig", newline="") as fp:
        for index, parts in enumerate(csv.reader(fp, delimiter=";"), 1):
            if not parts or all(not x.strip() for x in parts):
                continue
            if parts[0].strip().lower() == "ativo":
                continue
            if len(parts) != 9:
                raise ValueError(f"linha {index}: CSV Profit esperado com 9 colunas, tem {len(parts)}")
            symbol = parts[0].strip().upper()
            if symbol != SYMBOL:
                raise ValueError(f"linha {index}: símbolo misturado: {symbol}")
            stamp = datetime.strptime(parts[1].strip()+" "+parts[2].strip(), "%d/%m/%Y %H:%M:%S")
            if stamp.replace(tzinfo=TZ).astimezone(timezone.utc).timestamp() > datetime.now(timezone.utc).timestamp():
                raise ValueError(f"linha {index}: data futura")
            o,h,l,c = [_number(s) for s in parts[3:7]]
            for value in (o,h,l,c):
                _tick_check(value)
            if l > min(o,c) or h < max(o,c) or h < l:
                raise ValueError(f"linha {index}: OHLC inválido")
            monetary_volume = _number(parts[7])
            traded_contracts = _number(parts[8])
            if monetary_volume <= 0 or traded_contracts <= 0 or int(traded_contracts)!=traded_contracts:
                raise ValueError(f"linha {index}: volumes inválidos")
            rows.append((stamp, symbol, o,h,l,c,int(traded_contracts),monetary_volume))
    if len(rows) < 1000:
        raise ValueError(f"WINQ26: dados insuficientes ({len(rows)} linhas)")
    rows.sort(key=lambda r: r[0])
    if any(rows[i][0] <= rows[i-1][0] for i in range(1,len(rows))):
        raise ValueError("WINQ26: minutos duplicados ou fora de ordem")
    converted_path.parent.mkdir(parents=True,exist_ok=True)
    with converted_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.writer(fp, delimiter=";")
        writer.writerow(["Ativo","Data","Hora","Open","High","Low","Close","Volume"])
        for stamp, symbol, o,h,l,c,contracts,_ in rows:
            writer.writerow([symbol,stamp.strftime("%d/%m/%Y"),stamp.strftime("%H:%M:%S"),
                             int(o),int(h),int(l),int(c),contracts])
    imported = read_win_csv(converted_path, expected_symbol=SYMBOL)
    if len(imported["bars"]) != len(rows) or imported["timeframe_seconds"] != 60:
        raise ValueError("WINQ26: canonical import mismatch or not M1")
    by_month = {}
    for stamp, _,_,_,_,_,contracts,_ in rows:
        month=stamp.strftime("%Y-%m")
        entry=by_month.setdefault(month, {"candles":0,"contracts":0})
        entry["candles"]+=1
        entry["contracts"]+=contracts
    return {"symbol": SYMBOL, "first":rows[0][0].isoformat(),
            "last":rows[-1][0].isoformat(), "candles":len(rows),
            "source":str(raw_path.name),
            "raw_uses_monetary_volume":True,
            "simulator_uses_traded_contract_quantity":True,
            "monthly_data_quality":by_month}
