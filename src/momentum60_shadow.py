"""Independent prospective Momentum60 H4 paper book.

Never backfills trades on first observation, never touches existing 26 books,
never connects to FBS or wallets. A new candidate remains unvalidated.
"""
from __future__ import annotations

import json
from math import isfinite
from pathlib import Path

from research.screen_v2 import aggregate_hourly_to_h4
from research.backtest_year import COST_BPS
from research.entry_frequency_lab import candidate_signal
from src.gold_forward import day_of
from src.strategies import make_indicators

FILE = Path("state/momentum60_shadow_v1.json")
CAPITAL = 5000.0
RISK = 0.0075
NOTIONAL_CAP = 1.0
STOP_ATR = 2.0
TARGET_ATR = 3.5
MAX_HOLD_BARS = 90
STRATEGY = "momentum60_lab"
MARKET = "XAUUSD"


def fresh(bars):
    if len(bars) < 245:
        raise ValueError("H4 warmup insufficient")
    return {
        "schema": 1, "paper_only": True, "experimental_only": True,
        "market": MARKET, "strategy": STRATEGY,
        "source": "Yahoo GC=F proxy, no FBS fills",
        "h4_watermark": bars[-1]["time"],
        "equity": CAPITAL, "position": None,
        "entries": [], "closed": [],
    }


def step(book, bars, indicators, i):
    row = bars[i]
    opened = row["open"]
    prev = book["position"]
    if prev is not None:
        pos = prev
        pos["held_bars"] += 1
        side = pos["side"]
        if side == 1:
            stop_hit = row["low"] <= pos["stop"]
            target_hit = row["high"] >= pos["target"]
            stop_price = min(opened, pos["stop"])
        else:
            stop_hit = row["high"] >= pos["stop"]
            target_hit = row["low"] <= pos["target"]
            stop_price = max(opened, pos["stop"])
        price = None
        why = None
        if stop_hit:  # conservative if target and stop both touched
            price, why = stop_price, "STOP"
        elif target_hit:
            price, why = pos["target"], "TARGET"
        elif pos["held_bars"] >= MAX_HOLD_BARS:
            price, why = row["close"], "TIME"
        if price is not None:
            gross = side * (price - pos["entry"]) * pos["qty"]
            fee = COST_BPS[MARKET] / 10000 * pos["qty"] * (price + pos["entry"]) / 2
            pnl = gross - fee
            book["equity"] += pnl
            book["closed"].append({
                "entry_ts": pos["start"], "exit_ts": row["time"],
                "side": side, "entry": pos["entry"], "exit": price,
                "net_usd": round(pnl, 5), "cost_usd": round(fee, 5),
                "exit_type": why,
            })
            book["position"] = None
        return  # no reopen on the same H4 candle, even following an exit

    if not isfinite(book["equity"]) or book["equity"] <= 0:
        return
    current = candidate_signal(STRATEGY, bars, indicators, i - 1)
    previous = candidate_signal(STRATEGY, bars, indicators, i - 2)
    if current not in (-1, 0, 1) or previous not in (-1, 0, 1):
        raise ValueError("Invalid candidate direction")
    if not current or current == previous:
        return
    atr = indicators[i - 1]["atr"]
    if not isfinite(atr) or atr <= 0 or not isfinite(opened) or opened <= 0:
        return
    qty = min(book["equity"] * RISK / (STOP_ATR * atr),
              NOTIONAL_CAP * book["equity"] / opened)
    if qty <= 0 or not isfinite(qty):
        return
    book["position"] = {
        "side": current, "entry": opened, "start": row["time"],
        "qty": qty, "stop": opened - current * STOP_ATR * atr,
        "target": opened + current * TARGET_ATR * atr, "held_bars": 0,
    }
    book["entries"].append({
        "entry_ts": row["time"], "entry": opened, "side": current,
        "risk_fraction": RISK, "source": "next H4 open, virtual only",
    })


def update(state, hourly):
    bars = aggregate_hourly_to_h4(hourly)
    stamps = [b["time"] for b in bars]
    if len(bars) < 245 or stamps != sorted(set(stamps)):
        raise ValueError("Gold H4 incomplete, unordered, or duplicate")
    if state is None:
        return fresh(bars)  # absolutely no retroactive virtual entries
    if (state.get("schema") != 1 or not state.get("paper_only")
            or not state.get("experimental_only") or state.get("strategy") != STRATEGY):
        raise ValueError("Momentum60 state incompatible; never reset silently")
    old = state["h4_watermark"]
    if old not in stamps:
        raise ValueError("Momentum60 watermark lost; no silent historical restart")
    indicators = make_indicators(bars)
    for i in range(242, len(bars)):
        if stamps[i] <= old:
            continue
        step(state, bars, indicators, i)
        state["h4_watermark"] = stamps[i]
    return state


def process(hourly, path=FILE):
    path = Path(path)
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    result = update(state, hourly)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def daily_line(state, day):
    if state is None:
        return "🧪 Momentum60 H4: experimento sem dados"
    exit_today = [t for t in state["closed"] if day_of(t["exit_ts"]) == day]
    entry_today = [t for t in state["entries"] if day_of(t["entry_ts"]) == day]
    net = sum(t["net_usd"] for t in exit_today)
    wins = sum(t["net_usd"] > 0 for t in state["closed"])
    losses = sum(t["net_usd"] < 0 for t in state["closed"])
    status = "aberta" if state["position"] else "sem posição"
    return (f"🧪 EXTRA Momentum60 H4 (NÃO VALIDADO): "
            f"{len(entry_today)} entradas, {len(exit_today)} saídas hoje, "
            f"US$ {net:+.2f}; total US$ {state['equity']-CAPITAL:+.2f}, "
            f"V/D {wins}/{losses}, {status}")
