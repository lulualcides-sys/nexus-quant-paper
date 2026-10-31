"""Public OHLC observations; not FBS executable quotes."""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from urllib.parse import quote
import json, time, urllib.request
from src.market_quality import validate_bars

@dataclass(frozen=True)
class Asset:
    name: str
    ticker: str
    proxy: str

MARKETS = {
    "EURUSD": Asset("EUR/USD", "EURUSD=X", "Indicative FX quote, not FBS bid/ask"),
    "USDJPY": Asset("USD/JPY", "JPY=X", "Indicative FX quote, not FBS bid/ask"),
    "XAUUSD": Asset("Ouro (XAUUSD)", "GC=F", "Gold future proxy, not FBS spot"),
    "US500": Asset("S&P 500 (US500)", "ES=F", "E-mini future proxy, not FBS CFD"),
    "XTIUSD": Asset("Petróleo WTI (XTIUSD)", "CL=F", "Oil future proxy, not FBS CFD"),
}

def parse_yahoo(data, now):
    items = (data.get("chart") or {}).get("result") or []
    if not items:
        raise ValueError("Sem cotações")
    item=items[0]
    stamp=item.get("timestamp") or []
    quotes=((item.get("indicators") or {}).get("quote") or [])
    if not quotes:
        raise ValueError("OHLC ausente")
    quote0=quotes[0]
    rows={}
    for i,ts in enumerate(stamp):
        if int(ts)+3600 > now-180: # no incomplete candles
            continue
        try:
            values={k:float(quote0[k][i]) for k in ("open","high","low","close")}
        except (KeyError,IndexError,TypeError,ValueError):
            continue
        if not all(isfinite(v) and v>0 for v in values.values()):
            continue
        if values["high"] < max(values["open"],values["close"]) or values["low"]>min(values["open"],values["close"]):
            continue
        rows[int(ts)]={"time":int(ts),**values}
    out=[rows[k] for k in sorted(rows)]
    if len(out)<245:
        raise ValueError(f"Histórico insuficiente: {len(out)} candles")
    return out

def get_bars(asset, now=None):
    """Indicative Yahoo OHLC, two host mirrors, fail-closed on stale/invalid data.

    Both hosts are Yahoo, NOT independent pricing sources. Never substitute an
    ETF, stock, spot, or an unrelated future for the requested instrument.
    """
    now = int(now if now is not None else time.time())
    query = "?interval=60m&range=3mo" if asset.ticker == "GC=F" else "?interval=60m&range=1mo"
    errors = []
    for host in ("query1.finance.yahoo.com", "query2.finance.yahoo.com"):
        url = "https://" + host + "/v8/finance/chart/" + quote(asset.ticker, safe="") + query
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=20) as response:
                bars = parse_yahoo(json.load(response), now)
            validate_bars(bars, now=now, interval=3600, min_bars=245,
                          max_age=12 * 3600, continuous=False)
            return bars
        except Exception as err:
            errors.append(host + ": " + type(err).__name__)
    raise RuntimeError("%s: Yahoo indisponivel ou invalido; sem atualizar sinais (%s)" %
                       (asset.name, "; ".join(errors)))
