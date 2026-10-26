"""USD/CAD BB20 central-mean rebound: H1 confirmation, M15 trigger.

Paper research only. No broker connectivity, historical backfill or FBS fills.
The central moving average is SMA20 of completed H1 closes (BB 20, 2).
"""
from __future__ import annotations

import json
import math
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev

from src.strategies import make_indicators

FILE = Path("state/bb20_mtf_usdcad_v1.json")
TICKER = "CAD=X"  # Yahoo USD/CAD reference; not FBS executable prices
NAME = "BB20 Pullback H1/M15"
CAPITAL = 1000.0
RISK_FRACTION = 0.0075
MAX_NOTIONAL = 1.0  # 1x USD base notional, no borrowing
PIP = 0.0001
ROUNDTRIP_PIPS = 1.5  # illustrative costs, NOT FBS observed spreads
STOP_ATR = 1.2
TARGET_R = 1.6
MAX_HOLD_M15 = 32  # 8 hours
MIN_M15 = 240


def parse_15m(payload, now=None):
    now = int(now if now is not None else time.time())
    result = ((payload.get("chart") or {}).get("result") or [])
    if not result:
        raise ValueError("USD/CAD: resposta do provedor sem preços")
    entry = result[0]
    quote = ((entry.get("indicators") or {}).get("quote") or [None])[0]
    if not isinstance(quote, dict):
        raise ValueError("USD/CAD: OHLC ausente")
    rows = {}
    for i, timestamp in enumerate(entry.get("timestamp") or []):
        ts = int(timestamp)
        if ts % 900 or ts + 900 > now - 120:
            continue  # never use an incomplete or just-closed M15 bar
        try:
            o, h, l, c = (float(quote[k][i]) for k in ("open", "high", "low", "close"))
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        if not all(math.isfinite(v) and v > 0 for v in (o, h, l, c)):
            continue
        if h < max(o, c) or l > min(o, c):
            continue
        rows[ts] = {"time": ts, "open": o, "high": h, "low": l, "close": c}
    bars = [rows[t] for t in sorted(rows)]
    if len(bars) < MIN_M15:
        raise ValueError(f"USD/CAD: apenas {len(bars)} candles M15 válidos (mínimo {MIN_M15})")
    return bars


def fetch_15m(now=None):
    url = "https://query1.finance.yahoo.com/v8/finance/chart/CAD%3DX?interval=15m&range=1mo"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.load(response)
    return parse_15m(payload, now)


def to_h1(m15):
    buckets = defaultdict(list)
    for bar in m15:
        buckets[(bar["time"] // 3600) * 3600].append(bar)
    out = []
    for start in sorted(buckets):
        rows = sorted(buckets[start], key=lambda b: b["time"])
        if len(rows) != 4 or [b["time"] for b in rows] != [start + 900 * j for j in range(4)]:
            continue
        out.append({
            "time": start, "open": rows[0]["open"],
            "high": max(x["high"] for x in rows), "low": min(x["low"] for x in rows),
            "close": rows[-1]["close"],
        })
    return out


def h1_rejection(h1, indicators, j):
    """H1 touch of BB20 middle SMA; directional close and EMA50 trend."""
    if j < 50:
        return 0
    candle = h1[j]
    closes = [row["close"] for row in h1[j-19:j+1]]
    middle = mean(closes)
    deviation = pstdev(closes)
    pct_b = (candle["close"] - (middle - 2 * deviation)) / (4 * deviation) if deviation else 0.5
    ema50 = indicators[j]["e50"]
    if (candle["low"] <= middle <= candle["high"]
            and candle["close"] > middle
            and candle["close"] > candle["open"]
            and candle["close"] > ema50
            and pct_b > 0.5):
        return 1
    if (candle["low"] <= middle <= candle["high"]
            and candle["close"] < middle
            and candle["close"] < candle["open"]
            and candle["close"] < ema50
            and pct_b < 0.5):
        return -1
    return 0


def initial(bars):
    return {
        "schema": 1, "paper_only": True, "ticker": TICKER,
        "watermark_m15": bars[-1]["time"],
        "equity": CAPITAL, "position": None, "closed": [],
        "last_entry_h1": None, "last_reason": "Inicializado sem operações retroativas",
    }


def exit_position(book, bar):
    pos = book["position"]
    if pos is None:
        return False
    direction = pos["side"]
    stop = bar["low"] <= pos["stop"] if direction > 0 else bar["high"] >= pos["stop"]
    target = bar["high"] >= pos["target"] if direction > 0 else bar["low"] <= pos["target"]
    elapsed = (bar["time"] - pos["entry_ts"]) // 900
    if stop:
        price = min(bar["open"], pos["stop"]) if direction > 0 else max(bar["open"], pos["stop"])
        why = "STOP"
    elif target:
        price = pos["target"]
        why = "TARGET"
    elif elapsed >= MAX_HOLD_M15:
        price = bar["close"]
        why = "TIME"
    else:
        return False
    gross_cad = (price - pos["entry"]) * direction * pos["qty_usd"]
    costs_cad = ROUNDTRIP_PIPS * PIP * pos["qty_usd"]
    net_usd = (gross_cad - costs_cad) / price
    book["equity"] += net_usd
    book["closed"].append({
        "entry_ts": pos["entry_ts"], "exit_ts": bar["time"],
        "entry": pos["entry"], "exit": price, "side": direction,
        "net_usd": round(net_usd, 5), "cost_usd": round(costs_cad / price, 5),
        "exit_type": why,
    })
    book["position"] = None
    book["last_reason"] = "Saída virtual " + why
    return True


def step(book, bars, i, h1, inds):
    current, prior = bars[i], bars[i-1]
    # An order determined by the previous closed M15 bar is modelled at this
    # candle's opening. Stops/targets are then checked conservatively on this bar.
    if book["position"] is not None:
        exit_position(book, current)
        return  # no re-entry on an exit candle
    if book["equity"] <= 0:
        book["last_reason"] = "Banca virtual esgotada"
        return

    # Only H1 candles fully closed BEFORE the triggering M15 candle opened.
    eligible = [j for j, b in enumerate(h1) if b["time"] + 3600 <= prior["time"]]
    if not eligible:
        book["last_reason"] = "Aguardando H1 completo"
        return
    j = eligible[-1]
    confirmed_h1 = h1[j]
    closed_at = confirmed_h1["time"] + 3600
    if prior["time"] >= closed_at + 3600:
        book["last_reason"] = "Confirmação H1 expirada"
        return
    side = h1_rejection(h1, inds, j)
    if not side:
        book["last_reason"] = "H1 sem toque e rejeição confirmados na SMA20"
        return
    if book["last_entry_h1"] == confirmed_h1["time"]:
        book["last_reason"] = "Sinal H1 já utilizado"
        return

    middle = mean(x["close"] for x in h1[j-19:j+1])
    older = bars[i-2]
    atr = inds[j]["atr"]
    opening = current["open"]
    if atr <= 0 or opening <= 0:
        book["last_reason"] = "ATR/preço inválido"
        return

    # TRUE PULLBACK: the completed H1 candle already touched and rejected
    # the BB20 central line. On M15 enter the reaction AWAY from that line,
    # not a breakout beyond the previous candle's high/low.
    # Keep the reaction near the central mean; avoid chasing late moves.
    proximity = 0.25 * atr
    max_rebound_distance = 0.75 * atr
    long_trigger = (
        prior["low"] <= middle + proximity
        and 0 < prior["close"] - middle <= max_rebound_distance
        and prior["close"] > prior["open"]
        and prior["close"] > older["close"]
    )
    short_trigger = (
        prior["high"] >= middle - proximity
        and 0 < middle - prior["close"] <= max_rebound_distance
        and prior["close"] < prior["open"]
        and prior["close"] < older["close"]
    )
    if not (long_trigger if side > 0 else short_trigger):
        book["last_reason"] = "H1 confirmou; aguardando retorno M15 junto à SMA20"
        return
    distance = max(STOP_ATR * atr, 6 * PIP)
    # Quantity is USD base units. Convert quote-currency stop loss back to USD.
    qty_risk = (book["equity"] * RISK_FRACTION * opening) / distance
    qty = min(book["equity"] * MAX_NOTIONAL, qty_risk)
    if qty <= 0:
        return
    book["position"] = {
        "side": side, "entry": opening, "entry_ts": current["time"], "entry_rule": "bb20_h1_m15_pullback_v2",
        "qty_usd": qty, "stop": opening - side * distance,
        "target": opening + side * TARGET_R * distance,
        "confirm_h1": confirmed_h1["time"],
    }
    book["last_entry_h1"] = confirmed_h1["time"]
    book["last_reason"] = "Entrada virtual COMPRA" if side > 0 else "Entrada virtual VENDA"
    exit_position(book, current)


def update(state, bars):
    if len(bars) < MIN_M15:
        raise ValueError("USD/CAD: histórico M15 insuficiente")
    h1 = to_h1(bars)
    if len(h1) < 53:
        raise ValueError("USD/CAD: histórico H1 completo insuficiente")
    if state is None:
        return initial(bars)
    if state.get("schema") != 1 or not state.get("paper_only") or state.get("ticker") != TICKER:
        raise ValueError("Estado BB20 incompatível; não reiniciar silenciosamente")
    times = {b["time"]: i for i, b in enumerate(bars)}
    watermark = state["watermark_m15"]
    if watermark not in times:
        raise ValueError("USD/CAD: lacuna no histórico; não reconstruir fills retrospectivos")
    inds = make_indicators(h1)
    for i in range(max(2, times[watermark] + 1), len(bars)):
        # Skip gaps: the previous quarter-hour must be contiguous for confirmation.
        if bars[i]["time"] - bars[i-1]["time"] != 900 or bars[i-1]["time"] - bars[i-2]["time"] != 900:
            state["watermark_m15"] = bars[i]["time"]
            state["last_reason"] = "Intervalo M15 com lacuna; entrada ignorada"
            continue
        step(state, bars, i, h1, inds)
        state["watermark_m15"] = bars[i]["time"]
    return state


def process(bars, path=FILE):
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    new = update(old, bars)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(new, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return new


def digest(book, day):
    from src.gold_forward import day_of
    closed_today = [p for p in book["closed"] if day_of(p["exit_ts"] + 900) == day]
    pnl = sum(p["net_usd"] for p in closed_today)
    total = book["equity"] - CAPITAL
    wins = sum(p["net_usd"] > 0 for p in book["closed"])
    losses = sum(p["net_usd"] < 0 for p in book["closed"])
    state = "posição virtual aberta" if book["position"] else "sem posição"
    return [
        "🟨 11º ROBÔ — BB20 Pullback H1/M15 | USD/CAD",
        f"{len(closed_today)} fech. hoje | dia US$ {pnl:+.2f} | total US$ {total:+.2f} | V/D {wins}/{losses} | {state}",
        f"📍 {book.get('last_reason', 'Sem diagnóstico')} | banca US$ {CAPITAL:,.0f} virtual",
        "⚠️ SMA20 central (BB 20,2), toque/rejeição H1 + retorno M15 junto à média; preço CAD=X indicativo.",
    ]
