"""ATLAS #28: independent, conservative H4 candle-vector PAPER robot.

The published Tracker levels are replicated; the proprietary signal detector is NOT.
A proxy detector uses confirmed structural sweeps, wick rejection and actual
hourly volume where supplied. Missing volume disables signals (fail closed).
No broker orders, no historical fills on bootstrap, no intrabar lookahead.
"""
from __future__ import annotations

import json
from collections import defaultdict
from math import isfinite
from pathlib import Path

from research.backtest_year import COST_BPS
from src.gold_forward import day_of
from src.news_guard import entry_permission

FILE = Path("state/atlas_vector_v1.json")
MARKET = "XAUUSD"
CAPITAL = 5000.0
RISK = 0.0075
NOTIONAL_CAP = 1.0
LOOKBACK = 20
MIN_REL_VOLUME = 1.5
MIN_WICK_FRACTION = 0.30
ORDER_LIFE_BARS = 3
MAX_HOLD_BARS = 90


def aggregate_h4(hourly):
    """Aggregate ONLY four consecutive completed hours; volume must be real."""
    buckets = defaultdict(list)
    for bar in hourly:
        ts = int(bar["time"])
        buckets[(ts // 14400) * 14400].append(bar)
    output = []
    for ts in sorted(buckets):
        group = sorted(buckets[ts], key=lambda r: r["time"])
        if len(group) != 4 or [int(x["time"]) for x in group] != [ts + k * 3600 for k in range(4)]:
            continue
        o, h, l, c = group[0]["open"], max(x["high"] for x in group), min(x["low"] for x in group), group[-1]["close"]
        if not all(isfinite(float(v)) and v > 0 for v in (o, h, l, c)) or l > min(o, c) or h < max(o, c):
            raise ValueError("ATLAS: OHLC inválido")
        row = {"time": ts, "open": float(o), "high": float(h), "low": float(l), "close": float(c)}
        vols = [x.get("volume") for x in group]
        if all(isinstance(v, (int, float)) and isfinite(v) and v >= 0 for v in vols):
            row["volume"] = sum(vols)
        output.append(row)
    return output


def signal(bars, i):
    """A research hypothesis, NOT the original Tracker detection algorithm."""
    if i < LOOKBACK or i >= len(bars):
        return 0
    b = bars[i]
    r = b["high"] - b["low"]
    if r <= 0:
        return 0
    prior = bars[i - LOOKBACK:i]
    vols = [x.get("volume") for x in prior]
    current_volume = b.get("volume")
    if (not isinstance(current_volume, (int, float)) or not isfinite(current_volume)
            or current_volume <= 0
            or not all(isinstance(v, (int, float)) and isfinite(v) and v > 0 for v in vols)):
        return 0  # NO substitute for unavailable volume
    average_volume = sum(vols) / len(vols)
    if current_volume < MIN_REL_VOLUME * average_volume:
        return 0
    lower_wick = min(b["open"], b["close"]) - b["low"]
    upper_wick = b["high"] - max(b["open"], b["close"])
    previous_low = min(x["low"] for x in prior)
    previous_high = max(x["high"] for x in prior)
    if b["low"] < previous_low < b["close"] and lower_wick / r >= MIN_WICK_FRACTION:
        return 1
    if b["high"] > previous_high > b["close"] and upper_wick / r >= MIN_WICK_FRACTION:
        return -1
    return 0


def vector_levels(candle, side):
    """0/50/100/200/-100 in units of the confirmed signal candle range."""
    if side not in (-1, 1):
        raise ValueError("Side must be -1 or +1")
    r = float(candle["high"] - candle["low"])
    if not isfinite(r) or r <= 0:
        raise ValueError("Invalid vector candle")
    origin = float(candle["low"] if side == 1 else candle["high"])
    return {k: origin + side * factor * r for k, factor in
            (("zero", 0), ("entry", 0.5), ("hundred", 1), ("target", 2), ("stop", -1))}


def initial(bars):
    if len(bars) < 60:
        raise ValueError("ATLAS: warmup H4 insuficiente")
    return {
        "schema": 1, "name": "ATLAS", "market": MARKET, "timeframe": "H4",
        "paper_only": True, "experimental_only": True, "validated": False,
        "signal_model": "independent_sweep_wick_relative_volume_v1",
        "source": "Yahoo GC=F proxy, not FBS or B3 broker executions",
        "h4_watermark": bars[-1]["time"], "equity": CAPITAL,
        "pending": None, "position": None, "entries": [], "closed": [],
        "cancelled": [], "last_reason": "initial_observation_no_backfill",
    }


def _close(book, position, price, ts, reason, ambiguous=False):
    side = position["side"]
    gross = side * (price - position["entry"]) * position["qty"]
    # The project's existing indicative XAUUSD trading-cost model.
    cost = COST_BPS[MARKET] / 10000.0 * position["qty"] * (price + position["entry"]) / 2.0
    pnl = gross - cost
    book["equity"] += pnl
    book["closed"].append({
        "entry_ts": position["entry_ts"], "exit_ts": ts, "side": side,
        "entry": position["entry"], "exit": price, "qty": position["qty"],
        "stop": position["stop"], "target": position["target"],
        "net_usd": round(pnl, 5), "cost_usd": round(cost, 5),
        "exit_type": reason, "same_bar_order_uncertain": bool(ambiguous),
    })
    book["position"] = None
    book["last_reason"] = reason


def step(book, bars, i):
    """Only information known by the beginning of bar i may create its order."""
    row = bars[i]
    ts = row["time"]
    position = book["position"]
    if position is not None:
        position["held_bars"] += 1
        side = position["side"]
        stopped = row["low"] <= position["stop"] if side == 1 else row["high"] >= position["stop"]
        targeted = row["high"] >= position["target"] if side == 1 else row["low"] <= position["target"]
        if stopped:
            # Existing stop can be filled worse than its level at the next open.
            price = min(row["open"], position["stop"]) if side == 1 else max(row["open"], position["stop"])
            _close(book, position, price, ts, "STOP", ambiguous=targeted)
        elif targeted:
            _close(book, position, position["target"], ts, "TARGET")
        elif position["held_bars"] >= MAX_HOLD_BARS:
            _close(book, position, row["close"], ts, "TIME")
        return  # Never enter a second position in the same H4 candle.

    pending = book["pending"]
    if pending is None:
        direction = signal(bars, i - 1)
        if direction:
            levels = vector_levels(bars[i - 1], direction)
            pending = {"side": direction, **levels, "signal_ts": bars[i - 1]["time"], "age": 0}
            book["pending"] = pending
            book["last_reason"] = "waiting_50_percent_limit"
    if pending is None:
        if bars[i - 1].get("volume") is None:
            book["last_reason"] = "volume_missing_no_signal"
        else:
            book["last_reason"] = "no_confirmed_signal"
        return

    if pending["age"] >= ORDER_LIFE_BARS:
        book["cancelled"].append({"time": ts, "signal_ts": pending["signal_ts"], "reason": "EXPIRED"})
        book["pending"] = None
        book["last_reason"] = "expired_without_fill"
        return

    side, entry, stop, target = (pending[k] for k in ("side", "entry", "stop", "target"))
    # Reject gaps beyond invalidation before placing the new limit; no false stop fill.
    invalid_open = row["open"] <= stop if side == 1 else row["open"] >= stop
    if invalid_open:
        book["cancelled"].append({"time": ts, "signal_ts": pending["signal_ts"], "reason": "GAP_INVALID"})
        book["pending"] = None
        book["last_reason"] = "gap_invalidated"
        return
    if not entry_permission(MARKET, ts):
        book["cancelled"].append({"time": ts, "signal_ts": pending["signal_ts"], "reason": "NEWS_BLOCK"})
        book["pending"] = None
        book["last_reason"] = "news_blocked"
        return

    touched = row["low"] <= entry if side == 1 else row["high"] >= entry
    if not touched:
        pending["age"] += 1
        book["last_reason"] = "waiting_50_percent_limit"
        return
    risk_per_unit = abs(entry - stop)
    qty = min(book["equity"] * RISK / risk_per_unit,
              book["equity"] * NOTIONAL_CAP / entry) if book["equity"] > 0 and risk_per_unit > 0 else 0
    if not isfinite(qty) or qty <= 0:
        book["pending"] = None
        book["last_reason"] = "equity_or_risk_invalid"
        return
    p = {"side": side, "entry": entry, "entry_ts": ts, "signal_ts": pending["signal_ts"],
         "stop": stop, "target": target, "qty": qty, "held_bars": 0}
    book["pending"] = None
    book["position"] = p
    book["entries"].append({"entry_ts": ts, "signal_ts": p["signal_ts"], "side": side,
                             "entry": entry, "risk_fraction": RISK, "virtual_only": True})
    # OHLC cannot tell if stop was before or after limit fill: pessimistic stop-first.
    stop_touch = row["low"] <= stop if side == 1 else row["high"] >= stop
    target_touch = row["high"] >= target if side == 1 else row["low"] <= target
    if stop_touch:
        _close(book, p, stop, ts, "STOP_SAME_BAR", ambiguous=True)
    else:
        # Target touch on fill bar may have occurred BEFORE entry: do not count a win.
        book["last_reason"] = "entered_target_order_uncertain" if target_touch else "position_open"


def update(book, hourly):
    bars = aggregate_h4(hourly)
    if len(bars) < 60:
        raise ValueError("ATLAS: insuficientes candles H4 completos")
    stamps = [b["time"] for b in bars]
    if stamps != sorted(set(stamps)):
        raise ValueError("ATLAS: H4 fora de ordem")
    if book is None:
        return initial(bars)  # no historical paper trades on first observation
    if (book.get("schema") != 1 or book.get("name") != "ATLAS"
            or not book.get("paper_only") or not book.get("experimental_only")):
        raise ValueError("ATLAS: incompatible persisted paper state")
    previous = book["h4_watermark"]
    if previous not in stamps:
        raise ValueError("ATLAS: watermark lost; no silent reset/backfill")
    for i in range(1, len(bars)):
        if stamps[i] <= previous:
            continue
        step(book, bars, i)
        book["h4_watermark"] = stamps[i]
    return book


def process(hourly, path=FILE):
    path = Path(path)
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    result = update(state, hourly)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def scorecard(book):
    trades = book["closed"]
    wins = sum(t["net_usd"] > 0 for t in trades)
    losses = sum(t["net_usd"] < 0 for t in trades)
    peak = CAPITAL
    equity = CAPITAL
    dd = 0.0
    for t in trades:
        equity += t["net_usd"]
        peak = max(peak, equity)
        dd = max(dd, (peak - equity) * 100 / peak) if peak > 0 else dd
    return {"name": "ATLAS", "wins": wins, "losses": losses, "closed": len(trades),
            "winrate_pct": round(100 * wins / len(trades), 2) if trades else None,
            "net_usd": round(book["equity"] - CAPITAL, 5),
            "max_closed_drawdown_pct": round(dd, 3),
            "open": book["position"] is not None,
            "pending": book["pending"] is not None,
            "sample_sufficient_for_review": len(trades) >= 30,
            "validated": False}


def daily_line(book, day):
    if book is None:
        return "🧪 ATLAS #28 H4: indisponível; winrate N/D (sem inferir zero)"
    stats = scorecard(book)
    entries_today = sum(day_of(x["entry_ts"]) == day for x in book["entries"])
    closed_today = sum(day_of(x["exit_ts"]) == day for x in book["closed"])
    rate = f"{stats['winrate_pct']:.2f}%" if stats["winrate_pct"] is not None else "N/D"
    status = "posição aberta" if stats["open"] else "ordem 50% pendente" if stats["pending"] else "livre"
    return (f"🧪 ATLAS #28 H4 (PAPER, NÃO VALIDADO): "
            f"hoje {entries_today} entradas/{closed_today} saídas; "
            f"V/D {stats['wins']}/{stats['losses']} | winrate {rate} "
            f"({stats['closed']} fechamentos); líquido US$ {stats['net_usd']:+.2f}; "
            f"{status}; {book['last_reason']}")
