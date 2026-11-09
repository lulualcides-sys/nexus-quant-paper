"""Independent WIN M1/M5 liquidity-sweep reversal robot — OFFLINE RESEARCH ONLY.

Unlike microtrendline breakout/retest, this detects failed excursions beyond
recent confirmed price extremes ("liquidity sweep" proxy), a reclaim close and
volume / M5-vs-session-VWAP context. No broker orders or live trading.

Authentic WIN M1 candles only; price is R$0.20/point, 5-point tick.
No intrabar lookahead: signals use completed candles, next-open simulated fill.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import floor, ceil
from statistics import median

from research.win_price_data import (
    POINT_VALUE_BRL, TZ, WIN_TICK, local_day, resample, win_session
)


@dataclass(frozen=True)
class Parameters:
    capital_brl: float = 2000.0
    per_trade_risk: float = 0.01
    fee_roundtrip_brl: float = 4.0
    slippage_ticks_each_side: int = 1
    lookback_bars: int = 20
    volume_median_min_ratio: float = 0.90
    close_location_threshold: float = 0.65
    reward_risk: float = 1.8
    max_hold_bars: int = 35
    max_gap_points: float = 20.0
    require_vwap_context: bool = True
    min_net_rr: float = 0.0  # Optional research guard, 0 preserves original strategy


def _valid_history(bars, i, lookback):
    if i < lookback or not win_session(bars[i]["time"]):
        return None
    sample = bars[i - lookback:i + 1]
    if any(local_day(b["time"]) != local_day(bars[i]["time"]) for b in sample):
        return None
    if any(sample[k]["time"] - sample[k - 1]["time"] != 60
           for k in range(1, len(sample))):
        return None
    return sample


def _m5_filter(bars, i, side):
    """Only complete M5 candles, never look into the next M5 bar."""
    subset = [b for b in bars[max(0, i - 54):i + 1]
              if local_day(b["time"]) == local_day(bars[i]["time"])]
    m5 = [b for b in resample(subset, 300, base_seconds=60)
          if b["time"] + 300 <= bars[i]["time"] + 60]
    if len(m5) < 5:
        return False
    recent = m5[-5:]
    # Do not fade an aggressively directional M5 move.
    avg_rng = median([x["high"] - x["low"] for x in recent])
    if avg_rng <= 0:
        return False
    change = recent[-1]["close"] - recent[-4]["close"]
    return side * change > -1.5 * avg_rng


def _session_vwap_proxy(bars, i):
    """M1 OHLC x contracts proxy, NOT order-book/tick VWAP."""
    day = local_day(bars[i]["time"])
    total_pv = total_volume = 0.0
    for b in reversed(bars[max(0,i-650):i + 1]):
        if local_day(b["time"]) != day:
            break
        if b["volume"] <= 0:
            return None
        tp = (b["high"] + b["low"] + b["close"]) / 3
        total_pv += tp * b["volume"]
        total_volume += b["volume"]
    return total_pv / total_volume if total_volume else None


def signal(bars, i, cfg=Parameters()):
    """Returns an M1 close-confirmed sweep rejection or None."""
    history = _valid_history(bars, i, cfg.lookback_bars)
    if not history:
        return None
    previous, b = history[:-1], history[-1]
    prev_low = min(x["low"] for x in previous)
    prev_high = max(x["high"] for x in previous)
    rng = b["high"] - b["low"]
    if rng < 2 * WIN_TICK or not b["volume"]:
        return None
    volume_base = median([x["volume"] for x in previous])
    if volume_base <= 0 or b["volume"] < cfg.volume_median_min_ratio * volume_base:
        return None
    close_pct = (b["close"] - b["low"]) / rng
    swept_down = (
        b["low"] <= prev_low - WIN_TICK
        and b["close"] >= prev_low + WIN_TICK
        and b["close"] > b["open"]
        and close_pct >= cfg.close_location_threshold
    )
    swept_up = (
        b["high"] >= prev_high + WIN_TICK
        and b["close"] <= prev_high - WIN_TICK
        and b["close"] < b["open"]
        and close_pct <= 1 - cfg.close_location_threshold
    )
    if swept_down == swept_up:
        return None
    side = 1 if swept_down else -1
    if not _m5_filter(bars, i, side):
        return None
    if cfg.require_vwap_context:
        vwap = _session_vwap_proxy(bars, i)
        # Buying sweeps below the session proxy; selling above it.
        if vwap is None or side * (b["close"] - vwap) >= 0:
            return None
    stop = b["low"] - WIN_TICK if side == 1 else b["high"] + WIN_TICK
    return {
        "setup": "liquidity_sweep_reclaim",
        "side": side,
        "stop": stop,
        "signal_time": b["time"],
        "swept_level": prev_low if side == 1 else prev_high,
    }


def simulate(bars, cfg=Parameters(), *, start_date=None, end_date=None):
    """Retrospective, one WIN at a time, stop-red and stop-win; no daily lockout."""
    if not 0 < cfg.per_trade_risk <= 0.05:
        raise ValueError("per_trade_risk outside allowed research range")
    if cfg.fee_roundtrip_brl < 0 or cfg.slippage_ticks_each_side < 0:
        raise ValueError("negative costs")
    if not 0 <= cfg.min_net_rr <= 3:
        raise ValueError("min_net_rr out of valid range")
    if cfg.lookback_bars < 5 or cfg.max_hold_bars < 1 or cfg.reward_risk < 1:
        raise ValueError("invalid strategy parameters")
    if len(bars) < 100:
        raise ValueError("minimum 100 real M1 candles")
    if any(bars[j]["time"] <= bars[j-1]["time"] for j in range(1,len(bars))):
        raise ValueError("candles not chronologically ordered")
    equity = cfg.capital_brl
    peak = equity
    maximum_dd = 0.0
    position = None
    trades = []
    uncertain_position_gaps = 0
    rejects = {"risk":0, "gap":0, "insufficient_room":0, "uneconomic_rr":0}
    cost = cfg.fee_roundtrip_brl + 2 * cfg.slippage_ticks_each_side * WIN_TICK * POINT_VALUE_BRL

    def close(b, price, reason, ambiguous=False):
        nonlocal position, equity, peak, maximum_dd
        p=position
        gross = p["side"] * (price - p["entry"]) * POINT_VALUE_BRL
        net = round(gross - cost, 2)
        equity += net
        peak = max(peak, equity)
        maximum_dd = max(maximum_dd, (peak-equity) / peak * 100) if peak > 0 else maximum_dd
        trades.append({**p, "exit_time":b["time"], "exit":price, "why":reason,
                       "gross_brl":round(gross,2),"net_brl":net,
                       "ambiguous_stop_before_target":bool(ambiguous)})
        position = None

    for i in range(cfg.lookback_bars + 1, len(bars)):
        b = bars[i]
        today = local_day(b["time"])
        if position is not None:
            side = position["side"]
            # An unobserved M1 interval could have hit either exit order.
            # Do not silently carry a position across a hole in the data.
            # Worst of recorded next-open versus the planned stop is a
            # hypothetical liquidation, NOT an independently verified fill.
            if b["time"] - bars[i - 1]["time"] != 60:
                uncertain_position_gaps += 1
                adverse = (min(position["stop"], b["open"]) if side == 1
                           else max(position["stop"], b["open"]))
                close(b, adverse, "UNVERIFIABLE_DATA_GAP")
                continue
            if today != position["day"]:
                adverse = min(position["stop"], b["open"]) if side == 1 else max(position["stop"], b["open"])
                close(b, adverse, "OVERNIGHT_MISSING_EXIT")
                continue
            stop_hit = b["low"] <= position["stop"] if side == 1 else b["high"] >= position["stop"]
            target_hit = b["high"] >= position["target"] if side == 1 else b["low"] <= position["target"]
            position["bars_held"] += 1
            if stop_hit:
                adverse = min(position["stop"], b["open"]) if side == 1 else max(position["stop"], b["open"])
                close(b, adverse, "STOP_RED", target_hit)
            elif target_hit:
                close(b, position["target"], "STOP_WIN")
            elif not win_session(b["time"] + 60):
                close(b, b["close"], "SESSION_END")
            elif position["bars_held"] >= cfg.max_hold_bars:
                close(b, b["close"], "MAX_HOLD")
            continue

        # End-of-study: still process exits, but not any new entries.
        if ((start_date is not None and today < start_date) or
                (end_date is not None and today >= end_date)):
            continue
        if not win_session(b["time"]) or not win_session(b["time"]+60):
            continue
        if b["time"] - bars[i-1]["time"] != 60:
            rejects["gap"] += 1
            continue
        sig = signal(bars, i-1, cfg)
        if sig is None or local_day(bars[i-1]["time"]) != today:
            continue
        entry = b["open"]
        if abs(entry-bars[i-1]["close"]) > cfg.max_gap_points:
            rejects["gap"] += 1
            continue
        side, stop = sig["side"], sig["stop"]
        distance = side * (entry-stop)
        # Include modeled fees and slippage in R$ risk per 1-contract position.
        if (distance <= WIN_TICK or distance * POINT_VALUE_BRL + cost >
                min(cfg.capital_brl, equity) * cfg.per_trade_risk):
            rejects["risk"] += 1
            continue
        raw_target = entry + side * cfg.reward_risk * distance
        target = (floor(raw_target / WIN_TICK) * WIN_TICK if side == 1
                  else ceil(raw_target / WIN_TICK) * WIN_TICK)
        if side * (target-entry) < 1.25 * distance:
            rejects["insufficient_room"] += 1
            continue
        # Nominal reward/risk in points overstates the reward/risk after costs.
        # Record economics at the actual modeled entry rather than claiming 1.8R net.
        planned_net_win = side * (target-entry) * POINT_VALUE_BRL - cost
        planned_net_red = distance * POINT_VALUE_BRL + cost
        if cfg.min_net_rr and planned_net_win < cfg.min_net_rr * planned_net_red:
            rejects["uneconomic_rr"] += 1
            continue
        position={**sig,"entry_time":b["time"],"entry":entry,"stop":stop,
                  "target":target,"day":today,"bars_held":0,
                  "planned_net_reward_brl":round(planned_net_win,2),
                  "planned_net_loss_brl":round(planned_net_red,2),
                  "planned_net_rr":round(planned_net_win/planned_net_red,3)}
        # Entry next-open; stop hit inside entry candle takes precedence.
        on_stop = b["low"] <= stop if side == 1 else b["high"] >= stop
        on_target = b["high"] >= target if side == 1 else b["low"] <= target
        if on_stop:
            close(b, stop, "STOP_RED_ENTRY", on_target)
        elif on_target:
            # With OHLC we cannot prove target came after open; open is the
            # first chronological price, so target after open is plausible.
            close(b, target, "STOP_WIN_ENTRY")

    # Never report an unclosed position as if its risk were zero. This is
    # a marked estimate, not a fill or a realized backtest operation.
    open_mark = (round(position["side"] *
                       (bars[-1]["close"] - position["entry"]) * POINT_VALUE_BRL - cost, 2)
                 if position is not None else None)
    gains = sum(t["net_brl"] for t in trades if t["net_brl"] > 0)
    losses = -sum(t["net_brl"] for t in trades if t["net_brl"] < 0)
    return {
        "status":("BACKTEST_HAS_UNVERIFIABLE_POSITION_GAPS" if uncertain_position_gaps
                  else "BACKTEST_EXPERIMENTAL_ONLY"),
        "starting_capital_brl":cfg.capital_brl,
        "equity_closed_brl":round(equity,2),
        "net_brl":round(equity-cfg.capital_brl,2),
        "trades":len(trades),
        "winrate_pct":round(100*sum(t["net_brl"]>0 for t in trades)/len(trades),2) if trades else None,
        "profit_factor":round(gains/losses,3) if losses else None,
        "max_realized_drawdown_pct":round(maximum_dd,3),
        "one_contract_only":True,
        "no_daily_loss_limit":True,
        "stop_red_and_win":True,
        "cost_roundtrip_brl":cost,
        "minimum_net_rr_filter":cfg.min_net_rr,
        "rejected":rejects,
        "open_at_end":position is not None,
        "open_position_mark_to_market_net_brl":open_mark,
        "equity_including_open_mark_brl":round(equity + open_mark, 2) if open_mark is not None else round(equity, 2),
        "unverifiable_position_gap_exits":uncertain_position_gaps,
        "exit_reasons":{kind: sum(t["why"] == kind for t in trades) for kind in sorted({t["why"] for t in trades})},
        "ledger":trades,
    }
