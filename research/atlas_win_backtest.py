"""Separate retrospective ATLAS simulator for real WIN/B3 1-minute CSV data.

No B3 feed is invented or quietly substituted with gold. The benchmark uses
real B3 point-value (R$0.20), 5-point tick, integer contracts and fee/slippage
stress assumptions, not the USD notional sizing of the GC=F paper observer.
This is research-only. No live orders or profit claims.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from math import ceil, floor
from pathlib import Path
from zoneinfo import ZoneInfo

from research.atlas_tracker_v2 import VARIANTS, candidate
from research.win_price_data import (
    POINT_VALUE_BRL, WIN_TICK, TZ, local_day, read_win_csv, resample, win_session
)
from src.atlas_vector import vector_levels

CAPITAL_BRL = 5000.0
RISK = 0.0075
MAX_CONTRACTS = 3
ORDER_LIFE_BARS = 3
MAX_HOLD_BARS = 90
COST_SCENARIOS = ((4.0, 0), (4.0, 1), (4.0, 2))  # BRL fee roundtrip/contract + slip ticks per side
SECONDS = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600}


def _round_levels(levels, direction):
    def down(x):
        return floor(x / WIN_TICK + 1e-9) * WIN_TICK
    def up(x):
        return ceil(x / WIN_TICK - 1e-9) * WIN_TICK
    # Worst-way tick rounding for limit, take-profit and stop reference.
    return {
        "entry": up(levels["entry"]) if direction == 1 else down(levels["entry"]),
        "target": down(levels["target"]) if direction == 1 else up(levels["target"]),
        "stop": down(levels["stop"]) if direction == 1 else up(levels["stop"])
    }


def _end_of_session(ts, seconds):
    local = datetime.fromtimestamp(ts + seconds, timezone.utc).astimezone(TZ)
    return local.hour * 60 + local.minute >= 18 * 60


def simulate(bars, *, timeframe, variant, fee_brl=4.0, slip_ticks=1):
    if variant not in VARIANTS or timeframe not in SECONDS or slip_ticks < 0 or fee_brl < 0:
        raise ValueError("Invalid WIN research parameters")
    if len(bars) < 80:
        return {"status": "insufficient_bars", "closed": None, "winrate_pct": None}
    equity, peak, dd = CAPITAL_BRL, CAPITAL_BRL, 0.0
    position = None
    pending = None
    closed, entries, cancelled = [], [], []
    uncertain = 0
    split_ts = bars[max(60, int(0.7 * len(bars)))]["time"]

    def close_pos(ts, price, reason, *, ambiguous=False):
        nonlocal equity, peak, dd, position, uncertain
        p = position
        contracts = p["contracts"]
        gross = p["side"] * (price - p["entry"]) * POINT_VALUE_BRL * contracts
        cost = contracts * (fee_brl + 2 * slip_ticks * WIN_TICK * POINT_VALUE_BRL)
        net = gross - cost
        equity += net
        peak = max(peak, equity)
        dd = max(dd, (peak - equity) * 100 / peak) if peak > 0 else dd
        closed.append({
            "signal_ts": p["signal_ts"], "entry_ts": p["entry_ts"], "exit_ts": ts,
            "side": p["side"], "entry": p["entry"], "exit": price,
            "contracts": contracts, "net_brl": round(net, 4),
            "estimated_cost_brl": round(cost, 4), "reason": reason,
            "same_bar_order_uncertain": bool(ambiguous),
        })
        uncertain += int(ambiguous)
        position = None

    for i in range(60, len(bars)):
        b = bars[i]
        ts = b["time"]
        date = local_day(ts)

        # Any accidental cross-session position is carried honestly to next
        # actual bar OPEN as a bad-gap exit; never fabricate prior closing fill.
        if position is not None and position["day"] != date:
            price = (min(b["open"], position["stop"]) if position["side"] == 1
                     else max(b["open"], position["stop"]))
            close_pos(ts, price, "MISSING_SESSION_CLOSE_OVERNIGHT_GAP", ambiguous=True)
            pending = None
            continue
        if position is not None:
            position["held_bars"] += 1
            side = position["side"]
            stop_hit = b["low"] <= position["stop"] if side == 1 else b["high"] >= position["stop"]
            target_hit = b["high"] >= position["target"] if side == 1 else b["low"] <= position["target"]
            if stop_hit:
                exit_price = (min(b["open"], position["stop"]) if side == 1
                              else max(b["open"], position["stop"]))
                close_pos(ts, exit_price, "STOP", ambiguous=target_hit)
            elif target_hit:
                close_pos(ts, position["target"], "TARGET")
            elif _end_of_session(ts, SECONDS[timeframe]):
                close_pos(ts, b["close"], "SESSION_CLOSE")
            elif position["held_bars"] >= MAX_HOLD_BARS:
                close_pos(ts, b["close"], "TIME")
            continue  # never reenter on this bar
        if pending is not None and pending["day"] != date:
            cancelled.append({"ts": ts, "reason": "NEW_SESSION"})
            pending = None
        # No new entries outside liquid session or when current bar ends at 18h.
        if not win_session(ts) or _end_of_session(ts, SECONDS[timeframe]):
            if pending is not None:
                cancelled.append({"ts": ts, "reason": "SESSION_END"})
                pending = None
            continue

        if pending is None:
            # Same session and only previous COMPLETED candle's signal.
            if local_day(bars[i-1]["time"]) != date:
                continue
            direction = candidate(bars, i-1, variant)
            if direction:
                lvl = _round_levels(vector_levels(bars[i-1], direction), direction)
                if not (lvl["stop"] < lvl["entry"] < lvl["target"] if direction == 1
                        else lvl["target"] < lvl["entry"] < lvl["stop"]):
                    continue
                pending = {"side": direction, **lvl, "signal_ts": bars[i-1]["time"],
                           "age": 0, "day": date}
        if pending is None:
            continue
        if pending["age"] >= ORDER_LIFE_BARS:
            cancelled.append({"ts": ts, "reason": "EXPIRED"})
            pending = None
            continue
        side, entry, stop = pending["side"], pending["entry"], pending["stop"]
        if (b["open"] <= stop if side == 1 else b["open"] >= stop):
            cancelled.append({"ts": ts, "reason": "GAP_INVALID"})
            pending = None
            continue
        filled = b["low"] <= entry if side == 1 else b["high"] >= entry
        if not filled:
            pending["age"] += 1
            continue
        per_contract_risk = abs(entry - stop) * POINT_VALUE_BRL
        contracts = (min(MAX_CONTRACTS, floor(equity * RISK / per_contract_risk))
                     if per_contract_risk > 0 and equity > 0 else 0)
        if contracts <= 0:
            cancelled.append({"ts": ts, "reason": "RISK_TOO_LARGE_FOR_ONE_CONTRACT"})
            pending = None
            continue
        position = {"side": side, "entry": entry, "stop": stop,
                    "target": pending["target"], "contracts": contracts, "entry_ts": ts,
                    "signal_ts": pending["signal_ts"], "day": date, "held_bars": 0}
        entries.append({"time": ts, "entry": entry, "contracts": contracts, "side": side})
        pending = None
        stop_touch = b["low"] <= stop if side == 1 else b["high"] >= stop
        if stop_touch:
            close_pos(ts, stop, "STOP_SAME_BAR", ambiguous=True)
        # Same-bar target does not count as win: could precede entry.

    wins = sum(t["net_brl"] > 0 for t in closed)
    losses = sum(t["net_brl"] < 0 for t in closed)
    positives = sum(t["net_brl"] for t in closed if t["net_brl"] > 0)
    negatives = -sum(t["net_brl"] for t in closed if t["net_brl"] < 0)
    tail = [t for t in closed if t["exit_ts"] >= split_ts]
    return {
        "status": "experimental_backtest" if len(closed) >= 30 else "low_trade_count",
        "timeframe": timeframe, "variant": variant,
        "first_utc": datetime.fromtimestamp(bars[0]["time"], timezone.utc).isoformat(),
        "last_utc": datetime.fromtimestamp(bars[-1]["time"], timezone.utc).isoformat(),
        "candles": len(bars), "entries": len(entries), "closed": len(closed),
        "wins": wins, "losses": losses,
        "winrate_pct": round(100 * wins / len(closed), 2) if closed else None,
        "net_brl": round(equity - CAPITAL_BRL, 2),
        "profit_factor": round(positives / negatives, 3) if negatives else None,
        "max_realized_drawdown_pct": round(dd, 3),
        "uncertain_same_bar_exits": uncertain,
        "unfilled_or_cancelled": len(cancelled),
        "open_at_end": bool(position), "pending_at_end": bool(pending),
        "fee_brl_roundtrip_contract": fee_brl, "slip_ticks_each_way": slip_ticks,
        "last_30pct": {"closed": len(tail),
                       "net_brl": round(sum(t["net_brl"] for t in tail), 2),
                       "winrate_pct": round(100 * sum(t["net_brl"] > 0 for t in tail) / len(tail), 2)
                                      if tail else None},
        "closed_ledger": closed,
    }


def compare(csv_path):
    imported = read_win_csv(csv_path)
    if imported["timeframe_seconds"] > 60:
        raise ValueError("Para comparar M1–H1, WIN CSV deve ser nativo M1")
    base = imported["bars"]
    result = {"title": "ATLAS WIN — research only", "market": imported["symbol"],
              "source_file": imported["source"],
              "base_rows": len(base), "paper_only": True,
              "validated": False,
              "not_proprietary_tracker": True,
              "capital_brl": CAPITAL_BRL, "risk_fraction": RISK,
              "point_value_brl": POINT_VALUE_BRL, "tick_points": WIN_TICK,
              "max_contracts": MAX_CONTRACTS,
              "cost_model": "BRL roundtrip fee per contract plus tick slippage each side",
              "scenarios": {}, "warnings": [
                  "No order-book delta or aggressor volume: exhaustion is an OHLCV proxy",
                  "Overnight gaps and ambiguous OHLC events counted pessimistically",
                  "No margin, broker execution or exchange fees independently verified",
                  "Mixed-expiry continuous contracts disallowed by the importer",
                  "Last 30% of the same downloaded data is a diagnostic, not forward validation",
              ]}
    for tf, duration in SECONDS.items():
        rows = resample(base, duration, base_seconds=60)
        result["scenarios"][tf] = {}
        for variant in VARIANTS:
            result["scenarios"][tf][variant] = {
                f"fee4_slip{ticks}": simulate(rows, timeframe=tf, variant=variant,
                                             fee_brl=4.0, slip_ticks=ticks)
                for ticks in (0, 1, 2)
            }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--win-csv", required=True, help="Path to real Profit WINFUT M1 CSV")
    parser.add_argument("--out", default="research/results/atlas_win_latest.json")
    args = parser.parse_args()
    result = compare(args.win_csv)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(json.dumps({"source":result["source_file"],"market":result["market"],
                      "base_rows":result["base_rows"],
                      "status":"EXPERIMENTAL_ONLY",
                      "result_file":str(out)},ensure_ascii=False))


if __name__ == "__main__":
    main()
