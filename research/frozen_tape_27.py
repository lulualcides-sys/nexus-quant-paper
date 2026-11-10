"""Freeze exact public OHLC inputs for reproducible 27-bot paper replays.

No broker connections, trades or state mutations. The compressed artifact
allows future candidates to use the SAME candle tape instead of a moving
Yahoo lookback window or silently revised data.
"""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path


def _fingerprint(rows):
    return hashlib.sha256(json.dumps(
        rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def save_tape(path, *, datasets, m15rows, price_data, created_utc,
              hist_start, hist_end):
    if not isinstance(datasets, dict) or not isinstance(price_data, dict):
        raise ValueError("Data/price provenance must be mappings")
    data = dict(datasets)
    if m15rows is not None:
        data["USDCAD_M15"] = m15rows
    if not data:
        raise ValueError("Refusing to freeze an empty market tape")
    for market, rows in data.items():
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"{market}: missing market candles")
        expected = price_data.get(market, {}).get("sha256")
        if not expected or _fingerprint(rows) != expected:
            raise ValueError(f"{market}: input does not match replay provenance")
    if set(data) != set(price_data):
        raise ValueError("Provenance market list differs from frozen tape")
    if hist_start >= hist_end:
        raise ValueError("Invalid historical window")

    payload = {
        "schema": 1,
        "source": "historical public Yahoo OHLC, not executable broker bid/ask",
        "paper_only": True,
        "created_utc": created_utc,
        "hist_start": hist_start,
        "hist_end_exclusive": hist_end,
        "price_data": price_data,
        "datasets": data,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=6) as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
    return path


def load_tape(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("schema") != 1 or payload.get("paper_only") is not True:
        raise ValueError("Unknown or untrusted tape schema")
    markets = payload.get("datasets")
    provenance = payload.get("price_data")
    if not isinstance(markets, dict) or not markets or not isinstance(provenance, dict):
        raise ValueError("Frozen tape missing candles/provenance")
    if set(markets) != set(provenance):
        raise ValueError("Frozen tape coverage differs from metadata")
    if payload.get("hist_start", 0) >= payload.get("hist_end_exclusive", 0):
        raise ValueError("Frozen tape has invalid historical window")
    for market, rows in markets.items():
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"{market}: invalid rows")
        if _fingerprint(rows) != provenance[market].get("sha256"):
            raise ValueError(f"{market}: SHA-256 mismatch; frozen tape changed")
    return payload
