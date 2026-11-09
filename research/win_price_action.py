"""WIN M1/M5: price-action setups and conservative historical paper research.

No brokerage execution. Only authentic, user-supplied, single-expiry WIN M1
candles are accepted by research.win_price_data. Stops can slip in live markets.
Signals use COMPLETED M1 and M5 candles; fills are at the NEXT M1 open.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from research.win_price_data import (
    POINT_VALUE_BRL, WIN_TICK, local_day, read_win_csv, resample, win_session
)


@dataclass(frozen=True)
class Settings:
    starting_brl: float = 2000.0
    risk_fraction: float = 0.01
    daily_loss_fraction: float = 0.02
    fee_brl_roundtrip: float = 4.0
    slip_ticks_per_side: int = 1
    reward_risk: float = 2.0
    min_range_points: float = 250.0
    line_tolerance_points: float = 15.0
    fibonacci_filter: bool = False


def _m5_closed(m1, i):
    """Use a bounded historical slice; omit an incomplete M5 candle."""
    end = m1[i]["time"] + 60
    slice_ = m1[max(0, i - 149):i + 1]
    return [b for b in resample(slice_, 300, base_seconds=60)
            if b["time"] + 300 <= end]


def _regime(m5):
    if len(m5) < 12:
        return "unknown"
    old, new = m5[-12:-6], m5[-6:]
    old_hi, new_hi = max(b["high"] for b in old), max(b["high"] for b in new)
    old_lo, new_lo = min(b["low"] for b in old), min(b["low"] for b in new)
    if new_hi >= old_hi + 2 * WIN_TICK and new_lo >= old_lo + 2 * WIN_TICK:
        return "up"
    if new_hi <= old_hi - 2 * WIN_TICK and new_lo <= old_lo - 2 * WIN_TICK:
        return "down"
    if (new_hi <= old_hi + 6 * WIN_TICK
            and new_lo >= old_lo - 6 * WIN_TICK):
        return "range"
    return "mixed"


def _pivot_line(m1, breakout, side):
    """Confirmed descending pivot highs (buy) or ascending pivot lows (sell)."""
    key = "high" if side == 1 else "low"
    pivots = []
    for j in range(max(2, breakout - 34), breakout - 2):
        v = m1[j][key]
        neighbors = [m1[k][key] for k in (j - 2, j - 1, j + 1, j + 2)]
        if (v > max(neighbors) if side == 1 else v < min(neighbors)):
            pivots.append((j, v))
    if len(pivots) < 2:
        return None
    (x0, y0), (x1, y1) = pivots[-2:]
    slope = (y1 - y0) / (x1 - x0)
    if (side == 1 and slope >= -0.5) or (side == -1 and slope <= 0.5):
        return None
    return lambda index: y1 + slope * (index - x1)


def _break_retest(m1, i, side, cfg):
    """At bar i close, detect a breakout 1-4 bars earlier and retest now."""
    if i < 45:
        return None
    b = m1[i]
    for j in range(i - 1, max(i - 5, 34), -1):
        line = _pivot_line(m1, j, side)
        if line is None:
            continue
        c, prev = m1[j], m1[j - 1]
        if side == 1:
            crossed = (prev["close"] <= line(j - 1) + WIN_TICK
                       and c["close"] >= line(j) + WIN_TICK
                       and c["close"] > max(x["high"] for x in m1[j - 3:j]))
            retained = all(m1[k]["close"] >= line(k) - cfg.line_tolerance_points
                           for k in range(j + 1, i))
            retest = (b["low"] <= line(i) + cfg.line_tolerance_points
                      and b["low"] >= line(i) - cfg.line_tolerance_points
                      and b["close"] > line(i) + WIN_TICK
                      and b["close"] > b["open"])
            stop = b["low"] - WIN_TICK
        else:
            crossed = (prev["close"] >= line(j - 1) - WIN_TICK
                       and c["close"] <= line(j) - WIN_TICK
                       and c["close"] < min(x["low"] for x in m1[j - 3:j]))
            retained = all(m1[k]["close"] <= line(k) + cfg.line_tolerance_points
                           for k in range(j + 1, i))
            retest = (b["high"] >= line(i) - cfg.line_tolerance_points
                      and b["high"] <= line(i) + cfg.line_tolerance_points
                      and b["close"] < line(i) - WIN_TICK
                      and b["close"] < b["open"])
            stop = b["high"] + WIN_TICK
        if crossed and retained and retest:
            return {"setup": "break_retest", "side": side, "stop": stop,
                    "signal_time": b["time"], "breakout_time": c["time"]}
    return None


def _range_rejection(m1, i, m5, cfg):
    recent = m5[-12:]
    if len(recent) < 12:
        return None
    support = min(x["low"] for x in recent)
    resistance = max(x["high"] for x in recent)
    width = resistance - support
    if width < cfg.min_range_points:
        return None
    tol = cfg.line_tolerance_points
    if sum(x["low"] <= support + tol for x in recent) < 2:
        return None
    if sum(x["high"] >= resistance - tol for x in recent) < 2:
        return None
    b = m1[i]
    if b["low"] <= support + tol and b["close"] >= support + WIN_TICK and b["close"] > b["open"]:
        return {"setup": "range_rejection", "side": 1, "stop": b["low"] - WIN_TICK,
                "ceiling": resistance - 2 * WIN_TICK, "signal_time": b["time"]}
    if b["high"] >= resistance - tol and b["close"] <= resistance - WIN_TICK and b["close"] < b["open"]:
        return {"setup": "range_rejection", "side": -1, "stop": b["high"] + WIN_TICK,
                "floor": support + 2 * WIN_TICK, "signal_time": b["time"]}
    return None


def _fibonacci_ok(m5, price, cfg):
    """Optional automated approximation; not the user's hand-drawn Fibonacci."""
    high = max(x["high"] for x in m5[-12:])
    low = min(x["low"] for x in m5[-12:])
    return any(abs(price - (low + (high - low) * fraction)) <= 5 * WIN_TICK
               for fraction in (0.382, 0.5, 0.618))


def candidate(m1, i, cfg=Settings()):
    """A signal at the close of M1 index i, never using later data."""
    if i < 65 or not win_session(m1[i]["time"]):
        return None
    m5 = _m5_closed(m1, i)
    mode = _regime(m5)
    if mode == "up":
        choice = _break_retest(m1, i, 1, cfg)
    elif mode == "down":
        choice = _break_retest(m1, i, -1, cfg)
    elif mode == "range":
        choice = _range_rejection(m1, i, m5, cfg)
    else:
        choice = None
    if choice and cfg.fibonacci_filter and not _fibonacci_ok(m5, m1[i]["close"], cfg):
        return None
    return choice


def simulate(m1, cfg=Settings()):
    """One WIN max. A next-open entry; conservative intrabar stop priority."""
    if not 0 < cfg.risk_fraction <= 0.05 or not 0 < cfg.daily_loss_fraction <= 0.1:
        raise ValueError("Invalid risk fractions")
    if cfg.fee_brl_roundtrip < 0 or cfg.slip_ticks_per_side < 0 or cfg.reward_risk < 1:
        raise ValueError("Invalid costs or reward")
    if len(m1) < 100:
        raise ValueError("At least 100 real M1 bars are required")
    if any(m1[k]["time"] <= m1[k - 1]["time"] for k in range(1, len(m1))):
        raise ValueError("Chronology must be increasing")

    equity = cfg.starting_brl
    peak = equity
    max_dd = 0.0
    day = None
    daily_net = 0.0
    position = None
    trades = []
    rejected = {"risk": 0, "daily_stop": 0, "gap": 0, "no_room": 0}
    estimated_cost = cfg.fee_brl_roundtrip + (
        2 * cfg.slip_ticks_per_side * WIN_TICK * POINT_VALUE_BRL)

    def exit_at(bar, price, why, ambiguous=False):
        nonlocal equity, peak, max_dd, daily_net, position
        pnl = position["side"] * (price - position["entry"]) * POINT_VALUE_BRL - estimated_cost
        equity += pnl
        daily_net += pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak * 100) if peak else max_dd
        trades.append({**position, "exit_time": bar["time"], "exit": price,
                       "reason": why, "ambiguous_same_candle": ambiguous,
                       "net_brl": round(pnl, 2)})
        position = None

    for i in range(66, len(m1)):
        b = m1[i]
        today = local_day(b["time"])
        if today != day:
            day = today
            daily_net = 0.0
        if position:
            side = position["side"]
            if today != position["day"]:
                # Missing closing data: carry the uncertainty and close on the next actual open.
                exit_at(b, min(b["open"], position["stop"]) if side == 1
                        else max(b["open"], position["stop"]), "GAP_OVERNIGHT")
                continue
            stop_hit = b["low"] <= position["stop"] if side == 1 else b["high"] >= position["stop"]
            goal_hit = b["high"] >= position["target"] if side == 1 else b["low"] <= position["target"]
            if stop_hit:
                fill = min(b["open"], position["stop"]) if side == 1 else max(b["open"], position["stop"])
                exit_at(b, fill, "STOP", goal_hit)
            elif goal_hit:
                exit_at(b, position["target"], "TARGET")
            elif not win_session(b["time"] + 60):
                exit_at(b, b["close"], "SESSION_EXIT")
            continue
        if (not win_session(b["time"]) or not win_session(b["time"] + 60)
                or local_day(m1[i - 1]["time"]) != today):
            continue
        if daily_net <= -(cfg.starting_brl * cfg.daily_loss_fraction):
            rejected["daily_stop"] += 1
            continue
        if b["time"] - m1[i - 1]["time"] != 60:
            rejected["gap"] += 1
            continue
        setup = candidate(m1, i - 1, cfg)
        if not setup:
            continue
        entry, stop, side = b["open"], setup["stop"], setup["side"]
        if abs(entry - m1[i - 1]["close"]) > 4 * WIN_TICK:
            rejected["gap"] += 1
            continue
        distance = side * (entry - stop)
        # A stop must be on the other side of entry and fit inside 1% INCLUDING costs.
        if distance <= WIN_TICK or (distance * POINT_VALUE_BRL + estimated_cost
                                    > min(cfg.starting_brl, equity) * cfg.risk_fraction):
            rejected["risk"] += 1
            continue
        target = entry + side * cfg.reward_risk * distance
        if setup["setup"] == "range_rejection":
            ceiling = setup.get("ceiling") if side == 1 else setup.get("floor")
            room = side * (ceiling - entry)
            if room < 1.5 * distance:
                rejected["no_room"] += 1
                continue
            if side == 1:
                target = min(target, ceiling)
            else:
                target = max(target, ceiling)
        # Floor target distance to a valid WIN tick (never overstate expected profit).
        target = (int(target // WIN_TICK) * WIN_TICK if side == 1
                  else -int((-target) // WIN_TICK) * WIN_TICK)
        if side * (target - entry) < 1.5 * distance:
            rejected["no_room"] += 1
            continue
        position = {**setup, "entry_time": b["time"], "day": day,
                    "entry": entry, "stop": stop, "target": target}
        # A stop reached in the entry candle is a loss; no assumed intrabar target first.
        stop_hit = b["low"] <= stop if side == 1 else b["high"] >= stop
        target_hit = b["high"] >= target if side == 1 else b["low"] <= target
        if stop_hit:
            exit_at(b, stop, "STOP_ENTRY_BAR", target_hit)
        elif target_hit:
            exit_at(b, target, "TARGET_ENTRY_BAR")

    profits = sum(t["net_brl"] for t in trades if t["net_brl"] > 0)
    losses = -sum(t["net_brl"] for t in trades if t["net_brl"] < 0)
    return {
        "status": "EXPERIMENTAL_PAPER_NOT_VALIDATED",
        "capital_brl": cfg.starting_brl,
        "ending_equity_brl": round(equity, 2),
        "net_brl": round(equity - cfg.starting_brl, 2),
        "closed": len(trades),
        "win_rate_pct": round(100 * sum(t["net_brl"] > 0 for t in trades) / len(trades), 2)
                        if trades else None,
        "profit_factor": round(profits / losses, 3) if losses else None,
        "max_realized_drawdown_pct": round(max_dd, 2),
        "open_at_end": bool(position),
        "rejected": rejected,
        "one_contract_only": True,
        "estimated_cost_brl_per_roundtrip": estimated_cost,
        "fibonacci_filter": cfg.fibonacci_filter,
        "warnings": [
            "OHLC cannot prove intraminute fill sequence or order-book priority",
            "Fee and slippage are assumptions, not broker quotes",
            "CSV contract rollovers, historical gaps, data licensing and live fills require review",
            "Reported performance, if any, is historical simulation and NOT a live profit claim",
        ],
        "trades": trades,
    }


def main():
    p = argparse.ArgumentParser(description="WIN PA M1/M5 offline paper-only backtest")
    p.add_argument("--win-csv", required=True, help="Real single-expiry WIN M1 Profit CSV")
    p.add_argument("--out", default="research/results/win_price_action_local.json")
    p.add_argument("--fibonacci", action="store_true", help="Optional automatic retracement filter")
    a = p.parse_args()
    imported = read_win_csv(a.win_csv)
    if imported["timeframe_seconds"] != 60:
        p.error("Input must be native M1 WIN candles")
    cfg = Settings(fibonacci_filter=a.fibonacci)
    result = simulate(imported["bars"], cfg)
    result["source_file"] = imported["source"]
    result["symbol"] = imported["symbol"]
    result["candles"] = len(imported["bars"])
    dest = Path(a.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "symbol", "candles", "closed", "net_brl")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
