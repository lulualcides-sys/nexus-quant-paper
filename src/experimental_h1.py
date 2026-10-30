"""15 independent experimental H1 paper books across five public proxy markets.

No brokerage connection, no historical backfill, no guaranteed fills or profits.
These rules are UNVALIDATED; results must not be combined with approved bots.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from zoneinfo import ZoneInfo
from src.feed import MARKETS
from src.strategies import make_indicators
from research.backtest_year import COST_BPS

FILE = Path("state/experimental_h1_v1.json")
STRATEGIES = {
    "ema20_retest": "EMA20 Retest H1",
    "channel10": "Channel 10 H1",
    "rsi50": "RSI50 Trend H1",
}
CAPITAL = 1000.0
RISK_FRACTION = 0.0025
NOTIONAL_CAP = 1.0
STOP_ATR = 1.5
TRAIL_ATR = 1.5
MAX_HOLD = 36
WARMUP = 75
TZ = ZoneInfo("America/Sao_Paulo")


def local_day(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).astimezone(TZ).date().isoformat()


def bot_key(market, strategy):
    return f"{market}:{strategy}"


def book():
    return {"equity": CAPITAL, "position": None, "closed": [], "entries": [],
            "last_reason": "Iniciado sem operações retroativas",
            "diagnostics": {"no_setup": 0, "gap": 0, "cooldown": 0, "in_position": 0,
                            "entered": 0, "exited": 0, "invalid": 0},
            "last_exit_ts": None}


def fresh():
    return {"schema": 1, "paper_only": True, "experimental_only": True,
            "source": "Yahoo indicative H1, not FBS",
            "watermarks": {}, "books": {}, "unavailable": []}


def setup(strategy, bars, ind, i):
    """Completed bar signal only. Evaluated at i-1 before entry at i open."""
    if i < WARMUP:
        return 0
    p = ind[i]
    q = ind[i - 1]
    b = bars[i]
    bull = p["e20"] > p["e50"] and b["close"] > p["e50"]
    bear = p["e20"] < p["e50"] and b["close"] < p["e50"]
    if strategy == "ema20_retest":
        if bull and b["low"] <= p["e20"] and b["close"] > p["e20"] and b["close"] > b["open"] and 45 <= p["rsi"] <= 75:
            return 1
        if bear and b["high"] >= p["e20"] and b["close"] < p["e20"] and b["close"] < b["open"] and 25 <= p["rsi"] <= 55:
            return -1
    elif strategy == "channel10":
        upper = max(x["high"] for x in bars[i - 10:i])
        lower = min(x["low"] for x in bars[i - 10:i])
        if bull and b["close"] > upper and p["rsi"] >= 52:
            return 1
        if bear and b["close"] < lower and p["rsi"] <= 48:
            return -1
    elif strategy == "rsi50":
        if bull and q["rsi"] <= 50 < p["rsi"]:
            return 1
        if bear and q["rsi"] >= 50 > p["rsi"]:
            return -1
    else:
        raise KeyError(strategy)
    return 0


def _close(b, market, bar, price, why):
    p = b["position"]
    gross = (price - p["entry"]) * p["side"] * p["qty"]
    cost = COST_BPS[market] / 10000 * p["qty"] * (p["entry"] + price) / 2
    net = gross - cost
    b["equity"] += net
    b["closed"].append({"entry_ts": p["start"], "exit_ts": bar["time"],
                        "side": p["side"], "entry": round(p["entry"], 7),
                        "exit": round(price, 7), "net_usd": round(net, 5),
                        "cost_usd": round(cost, 5), "exit_type": why})
    b["last_exit_ts"] = bar["time"]
    b["last_reason"] = f"Saída {why}: US$ {net:+.2f} com custos estimados"
    b["diagnostics"]["exited"] += 1
    b["position"] = None


def step(b, market, strategy, bars, ind, i):
    """Stop checks before trailing; do not enter and exit on same candle."""
    row = bars[i]
    previous = bars[i - 1]
    p = b["position"]
    if p is not None:
        b["diagnostics"]["in_position"] += 1
        p["held_bars"] += 1
        side = p["side"]
        hit = row["low"] <= p["stop"] if side > 0 else row["high"] >= p["stop"]
        if hit:
            fill = min(row["open"], p["stop"]) if side > 0 else max(row["open"], p["stop"])
            _close(b, market, row, fill, "STOP")
            return
        if p["held_bars"] >= MAX_HOLD:
            _close(b, market, row, row["close"], "TIME")
            return
        # This closing-price trailing level is effective NEXT candle only.
        favorable = max(p["best_close"], row["close"]) if side > 0 else min(p["best_close"], row["close"])
        p["best_close"] = favorable
        if side * (favorable - p["entry"]) >= p["initial_r"]:
            new_stop = favorable - side * TRAIL_ATR * ind[i]["atr"]
            tightened = max(p["stop"], new_stop) if side > 0 else min(p["stop"], new_stop)
            if tightened != p["stop"]:
                p["stop"] = tightened
                p["stop_updates"] += 1
        b["last_reason"] = "Posição virtual aberta; stop acompanhado"
        return

    # No new entry across a holiday/weekend or incomplete hourly interval.
    if row["time"] - previous["time"] != 3600:
        b["diagnostics"]["gap"] += 1
        b["last_reason"] = "Sem entrada: lacuna entre candles"
        return
    if b["last_exit_ts"] is not None and row["time"] - b["last_exit_ts"] < 2 * 3600:
        b["diagnostics"]["cooldown"] += 1
        b["last_reason"] = "Sem entrada: proteção após saída"
        return
    side = setup(strategy, bars, ind, i - 1)
    if not side:
        b["diagnostics"]["no_setup"] += 1
        b["last_reason"] = "Aguardando setup H1 com candle fechado"
        return
    price, atr = row["open"], ind[i - 1]["atr"]
    if not isfinite(atr) or atr <= 0 or price <= 0 or b["equity"] <= 0:
        b["diagnostics"]["invalid"] += 1
        b["last_reason"] = "Bloqueado: risco/preço inválido"
        return
    stop_dist = STOP_ATR * atr
    qty = min(b["equity"] * RISK_FRACTION / stop_dist, b["equity"] * NOTIONAL_CAP / price)
    if qty <= 0 or not isfinite(qty):
        b["diagnostics"]["invalid"] += 1
        return
    b["position"] = {"side": side, "entry": price, "start": row["time"],
                     "qty": qty, "stop": price - side * stop_dist,
                     "initial_r": stop_dist, "best_close": price, "stop_updates": 0,
                     "held_bars": 0}
    b["entries"].append({"entry_ts": row["time"], "side": side, "entry": price,
                         "reason": strategy, "risk_fraction": RISK_FRACTION})
    b["diagnostics"]["entered"] += 1
    b["last_reason"] = "Entrada experimental COMPRA" if side > 0 else "Entrada experimental VENDA"
    # Entry at this candle's open uses only previous completed OHLC.
    # No claim of actual executable brokerage fills.


def update(state, datasets):
    state = state if state is not None else fresh()
    if state.get("schema") != 1 or not state.get("paper_only") or not state.get("experimental_only"):
        raise ValueError("Estado H1 experimental incompatível; preservar histórico")
    missing = [m for m in MARKETS if m not in datasets]
    state["unavailable"] = missing
    for market in MARKETS:
        if market not in datasets:
            continue
        bars = datasets[market]
        stamps = [int(x["time"]) for x in bars]
        if len(bars) <= WARMUP + 2 or stamps != sorted(set(stamps)):
            raise ValueError(f"{market}: histórico H1 inválido")
        if market not in state["watermarks"]:
            state["watermarks"][market] = stamps[-1]
            for strat in STRATEGIES:
                state["books"][bot_key(market, strat)] = book()
            continue  # prohibit retroactive fills on the first observation
        mark = state["watermarks"][market]
        if mark > stamps[-1]:
            continue  # lagging feed; never roll back
        if mark not in stamps:
            raise ValueError(f"{market}: watermark perdido; não inventar entradas")
        ind = make_indicators(bars)
        start = stamps.index(mark) + 1
        for i in range(max(start, WARMUP + 1), len(bars)):
            for strat in STRATEGIES:
                step(state["books"][bot_key(market, strat)], market, strat, bars, ind, i)
            state["watermarks"][market] = stamps[i]
        if start > WARMUP and start >= len(bars):
            continue
    return state


def process(datasets, path=FILE):
    path = Path(path)
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    result = update(state, datasets)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def labels():
    return {bot_key(m, s): f"{m} {title}" for m in MARKETS for s, title in STRATEGIES.items()}


def digest(state, day):
    """Compact diagnostic for the existing daily message; books remain independent."""
    if state is None:
        return ["🧪 15 H1 experimentais: sem dados; não presumir resultado zero"]
    lines = ["", "🧪 15 EXPERIMENTAIS H1 | 5 mercados × 3 estratégias",
             "Risco planejado 0,25%/op.; até 1× nocional | NÃO VALIDADOS"]
    total_entries = total_closed = 0
    total_net = 0.0
    for market in MARKETS:
        items = [state["books"].get(bot_key(market, strat)) for strat in STRATEGIES]
        if any(b is None for b in items) or market in state.get("unavailable", []):
            lines.append(f"{market}: SEM DADOS FRESCOS / aguardando inicialização")
            continue
        entries = sum(sum(local_day(e["entry_ts"]) == day for e in b["entries"]) for b in items)
        exits = [t for b in items for t in b["closed"] if local_day(t["exit_ts"]) == day]
        opened = sum(b["position"] is not None for b in items)
        net = sum(t["net_usd"] for t in exits)
        total_entries += entries
        total_closed += len(exits)
        total_net += net
        lines.append(f"{market}: {entries} entradas | {len(exits)} saídas | {opened}/3 abertas | US$ {net:+.2f}")
    lines.append(f"Experimento hoje: {total_entries} entradas, {total_closed} saídas, US$ {total_net:+.2f} realizado virtual")
    lines.append("Sem setup ≠ erro; estratégias experimentais não são recomendação de operação.")
    return lines


def diagnostics(state):
    """Per-bot reasons and counts, for audit or further tuning."""
    return {key: {"reason": b["last_reason"], "diagnostics": b["diagnostics"],
                  "equity": b["equity"], "open": b["position"] is not None,
                  "closed": len(b["closed"])} for key, b in state["books"].items()}
