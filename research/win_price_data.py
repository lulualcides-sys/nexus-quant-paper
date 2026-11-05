"""Strict WIN B3 historical candles from a user-supplied Profit/Nelogica CSV.

This parser does NOT download or fabricate WIN data. It rejects mixed tickers,
inconsistent timestamps, off-tick prices, missing volume and impossible OHLC.
Timezone of the CSV: America/Sao_Paulo; timestamp represents candle OPEN.
The exporter must supply real unadjusted traded prices for the chosen contract.
"""
from __future__ import annotations

import csv
import re
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")
WIN_TICK = 5.0
POINT_VALUE_BRL = 0.20
SYMBOL_RE = re.compile(r"^(WINFUT|WIN[GJMQVZ][0-9]{2})$", re.I)
HEADER = {"ativo", "symbol", "ticker", "contrato"}


def _number(value):
    v = str(value).strip().replace("\ufeff", "").replace(" ", "")
    if not v:
        raise ValueError("valor numérico vazio")
    if "," in v:
        v = v.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\\d{1,3}(\\.\\d{3})+", v):
        v = v.replace(".", "")  # Brazilian thousands grouping, e.g. 141.000
    result = float(v)
    if not isfinite(result):
        raise ValueError("valor não-finito")
    return result


def _tick_check(price):
    if price <= 0 or abs(price / WIN_TICK - round(price / WIN_TICK)) > 1e-7:
        raise ValueError(f"Preço WIN fora da grade de 5 pontos: {price}")


def read_win_csv(path, *, expected_symbol=None, max_rows=1000000):
    """Reads Ativo;Data;Hora;Open;High;Low;Close;Volume.

    No auto-continuous futures concatenation: mixed symbols are rejected.
    Candles must be strictly increasing and on an identical input period.
    """
    path = Path(path)
    if expected_symbol is not None and not SYMBOL_RE.fullmatch(expected_symbol):
        raise ValueError("Ticker esperado não é WINFUT ou contrato WIN válido")
    bars = []
    seen_symbol = None
    with path.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.reader(fp, delimiter=";")
        for lineno, cells in enumerate(reader, 1):
            if not cells or all(not x.strip() for x in cells):
                continue
            if len(cells) < 8:
                raise ValueError(f"Linha {lineno}: 8 colunas obrigatórias")
            symbol = cells[0].strip().upper()
            if symbol.lower() in HEADER:
                continue
            if not SYMBOL_RE.fullmatch(symbol):
                raise ValueError(f"Linha {lineno}: não é contrato WIN: {symbol}")
            if expected_symbol is not None and symbol != expected_symbol.upper():
                raise ValueError("Símbolo não corresponde ao contrato solicitado")
            if seen_symbol is not None and seen_symbol != symbol:
                raise ValueError("Múltiplos vencimentos concatenados: proibido sem ajuste documentado")
            seen_symbol = symbol
            try:
                local = datetime.strptime(cells[1].strip() + " " + cells[2].strip(), "%d/%m/%Y %H:%M")
            except ValueError:
                try:
                    local = datetime.strptime(cells[1].strip() + " " + cells[2].strip(), "%d/%m/%Y %H:%M:%S")
                except ValueError as exc:
                    raise ValueError(f"Linha {lineno}: data/hora inválida") from exc
            if local.weekday() > 4:
                raise ValueError(f"Linha {lineno}: pregão em fim de semana")
            stamp = int(local.replace(tzinfo=TZ).astimezone(timezone.utc).timestamp())
            o, h, lo, c = map(_number, cells[3:7])
            volume = _number(cells[7])
            if not all(x > 0 for x in (o, h, lo, c, volume)):
                raise ValueError(f"Linha {lineno}: preço/volume não positivo")
            for p in (o, h, lo, c):
                _tick_check(p)
            if lo > min(o, c) or h < max(o, c) or lo > h:
                raise ValueError(f"Linha {lineno}: OHLC inconsistente")
            if bars and stamp <= bars[-1]["time"]:
                raise ValueError(f"Linha {lineno}: duplicidade ou cronologia incorreta")
            if stamp > int(datetime.now(timezone.utc).timestamp()):
                raise ValueError(f"Linha {lineno}: candle no futuro")
            bars.append({"time": stamp, "open": o, "high": h, "low": lo,
                         "close": c, "volume": volume})
            if len(bars) > max_rows:
                raise ValueError("Limite de linhas excedido")
    if len(bars) < 100:
        raise ValueError(f"Amostra WIN insuficiente ({len(bars)} candles reais)")
    diffs = {bars[i]["time"] - bars[i - 1]["time"] for i in range(1, len(bars))
             if 0 < bars[i]["time"] - bars[i - 1]["time"] <= 3600}
    if not diffs:
        raise ValueError("Frequência intradiária WIN indisponível")
    base_s = min(diffs)
    if base_s not in (60, 300, 900, 1800, 3600):
        raise ValueError(f"Timeframe base inesperado: {base_s}s")
    if any(b["time"] % base_s for b in bars):
        raise ValueError("Timestamps não alinhados à frequência")
    return {"symbol": seen_symbol, "timeframe_seconds": base_s,
            "source": str(path.name), "bars": bars}


def resample(bars, seconds, *, base_seconds):
    """Resample only contiguous complete groups, never bridge absent bars."""
    if seconds not in (60, 300, 900, 1800, 3600) or seconds < base_seconds or seconds % base_seconds:
        raise ValueError("Timeframe não suportado para estes dados")
    if seconds == base_seconds:
        return [dict(x) for x in bars]
    n = seconds // base_seconds
    buckets = {}
    for b in bars:
        key = (b["time"] // seconds) * seconds
        buckets.setdefault(key, []).append(b)
    result = []
    for start in sorted(buckets):
        group = buckets[start]
        if len(group) != n or any(x["time"] != start + k * base_seconds
                                  for k, x in enumerate(group)):
            continue
        result.append({
            "time": start, "open": group[0]["open"], "high": max(x["high"] for x in group),
            "low": min(x["low"] for x in group), "close": group[-1]["close"],
            "volume": sum(x["volume"] for x in group)
        })
    return result


def win_session(ts, start_h=9, start_m=10, end_h=17, end_m=30):
    t = datetime.fromtimestamp(ts, timezone.utc).astimezone(TZ)
    m = t.hour * 60 + t.minute
    return t.weekday() < 5 and start_h * 60 + start_m <= m < end_h * 60 + end_m


def local_day(ts):
    return datetime.fromtimestamp(ts, timezone.utc).astimezone(TZ).date().isoformat()
