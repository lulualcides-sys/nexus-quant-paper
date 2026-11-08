"""V4 research-only trading system: H1 primary signals, next-hour M5 execution.

Long-only Binance spot. No authenticated APIs, real orders, cron or Telegram.
Policies frozen BEFORE reading V4 results; NEVER relabel seen samples as OOS.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import asdict, dataclass

from .engine import (
    CAPITAL, MAX_DAILY_LOSS, MAX_DRAWDOWN, SCENARIOS, _summary, local_date,
)
from .strategies import build_features
from .v3_policy import aggregate_closed_h1

HOUR_MS = 3_600_000
M5_MS = 300_000
MAX_NOTIONAL_FRACTION = .40
RISK_FRACTION = .005  # max 0.5% equity at modeled stop incl commissions
COOLDOWN_BARS = 144  # 12-hour minimum wait after last entry
MIN_CLOSED_HOURS = 240


@dataclass(frozen=True)
class V4Policy:
    name: str
    setup: str
    exit_mode: str
    target_r: float
    stop_atr: float
    stop_pct_floor: float
    max_hold_h: int


POLICIES = (
    V4Policy("h1_channel24_fixed", "channel", "fixed", 2.8, 1.40, .012, 72),
    V4Policy("h1_channel24_trail", "channel", "trail", 2.8, 1.40, .012, 72),
    V4Policy("h1_ema_pullback_fixed", "pullback", "fixed", 2.4, 1.20, .010, 72),
    V4Policy("h1_ema_pullback_trail", "pullback", "trail", 2.4, 1.20, .010, 72),
)


def detect_closed_hour(hourly, f, h, policy):
    """Use ONLY fully closed H1 index h and earlier; no forward bars."""
    if h < MIN_CLOSED_HOURS or h >= len(hourly):
        return None
    b, prev = hourly[h], hourly[h - 1]
    atr = f.atr[h]
    if not (b.c > 0 and atr > 0 and f.vol20[h] > 0):
        return None
    atr_fraction = atr / b.c
    if not (.004 <= atr_fraction <= .028):
        return None
    if not (f.ema20[h] >= f.ema50[h] > f.ema200[h] and
            f.ema50[h] > f.ema50[h - 12] and
            f.ema200[h] >= f.ema200[h - 24] and
            b.c > f.ema50[h]):
        return None
    spread = max(1e-12, b.h - b.l)
    if (b.c - b.l) / spread < .64 or b.c <= b.o:
        return None
    if policy.setup == "channel":
        prev_high24 = max(x.h for x in hourly[h - 24:h])
        before_high24 = max(x.h for x in hourly[h - 25:h - 1])
        if not (b.c > prev_high24 and
                prev.c <= before_high24 and
                b.v >= 1.10 * f.vol20[h] and
                b.c <= f.ema20[h] + 2.0 * atr):
            return None
        efficiency_path = sum(
            abs(hourly[j].c - hourly[j - 1].c) for j in range(h - 11, h + 1))
        if efficiency_path <= 0 or (b.c - hourly[h - 12].c) / efficiency_path < .23:
            return None
        low = min(x.l for x in hourly[h - 2:h + 1])
        return {
            "reason": "closed_h1_donchian_24h_breakout",
            "hour_i": h, "signal_t": b.t,
            "signal_close": b.c, "atr": atr, "structure_low": low,
        }
    if policy.setup == "pullback":
        if not (
            f.ema20[h] > f.ema50[h] and
            prev.l <= f.ema20[h - 1] + .15 * atr and
            b.c > prev.h and b.c > f.ema20[h] and
            0 <= b.c - f.ema20[h] <= .90 * atr and
            b.v >= .90 * f.vol20[h]
        ):
            return None
        return {
            "reason": "closed_h1_ema20_pullback_reclaim",
            "hour_i": h, "signal_t": b.t,
            "signal_close": b.c, "atr": atr,
            "structure_low": min(prev.l, b.l),
        }
    raise ValueError("Unknown V4 setup")


def aligned_closed_hour_at_entry(m5_bar, hour_ends):
    """Only H1 whose last M5 closed at or before next hour's OPEN."""
    if m5_bar.t % HOUR_MS:
        return -1
    h = bisect_right(hour_ends, m5_bar.t) - 1
    if h < 0 or hour_ends[h] != m5_bar.t:
        return -1
    return h


def _entry_signal(signal, policy, b, cash, fee, dev):
    """Full modeled net risk, 40% max spot notional and no leverage."""
    ref = b.o
    fill = ref * (1 + dev)
    if not (ref > 0 and abs(ref - signal["signal_close"]) <= .55 * signal["atr"]):
        return None
    atr = signal["atr"]
    structure = max(0., fill - signal["structure_low"] + .10 * atr)
    # Overly tight stops were a measurable V1/V2 failure.
    distance = max(policy.stop_atr * atr, policy.stop_pct_floor * fill,
                   min(2.5 * atr, structure))
    if not (.005 <= distance / fill <= .06):
        return None
    stop = fill - distance
    conservative_stop_fill = stop * (1 - dev)
    unit_loss = fill * (1 + fee) - conservative_stop_fill * (1 - fee)
    if unit_loss <= 0:
        return None
    units = min(
        cash * RISK_FRACTION / unit_loss,
        cash * MAX_NOTIONAL_FRACTION / (fill * (1 + fee)),
        cash / (fill * (1 + fee)),
    )
    if units <= 0:
        return None
    target = fill + policy.target_r * distance
    entry_fee = units * fill * fee
    return {
        "signal_t": signal["signal_t"], "entry_t": b.t,
        "hour_i": signal["hour_i"], "reference_entry": ref, "entry": fill,
        "entry_fee": entry_fee, "entry_deviation": units * (fill - ref),
        "qty": units, "spent": units * fill + entry_fee,
        "stop": stop, "initial_stop": stop, "distance": distance,
        "target": target, "atr": atr, "reason": signal["reason"],
        "max_price": fill, "trailing_armed": False,
    }


def _close(p, b, refexit, reason, fee, dev):
    """Conservative reference and execution fills; no hidden zero fee cases."""
    exit_fill = refexit * (1 - dev)
    exit_fee = p["qty"] * exit_fill * fee
    pnl = p["qty"] * exit_fill - exit_fee - p["spent"]
    gross = p["qty"] * (refexit - p["reference_entry"])
    fees = p["entry_fee"] + exit_fee
    exec_dev = p["entry_deviation"] + p["qty"] * (refexit - exit_fill)
    if abs(pnl - (gross - fees - exec_dev)) > 1e-6:
        raise AssertionError("P&L/cost ledger fails reconciliation")
    return {
        "signal_t": p["signal_t"], "entry_t": p["entry_t"],
        "exit_t": b.t, "entry_ref": round(p["reference_entry"], 9),
        "exit_ref": round(refexit, 9), "entry": round(p["entry"], 9),
        "exit": round(exit_fill, 9), "qty": round(p["qty"], 9),
        "initial_stop": round(p["initial_stop"], 8),
        "final_stop": round(p["stop"], 8), "target": round(p["target"], 8),
        "gross_usd": round(gross, 7), "fees_usd": round(fees, 7),
        "execution_deviation_usd": round(exec_dev, 7),
        "pnl_usd": round(pnl, 7), "exit_reason": reason,
        "signal_reason": p["reason"],
        "regime": "closed_h1_bull_trend",
        "initial_stop_pct": round(p["distance"] / p["entry"] * 100, 5),
    }


def replay_v4(m5, hours, f, policy, scenario="base", *, start=0, stop=None,
              h4=None, h4_features=None, h4_closes=None, entry_gate=None):
    """Independent spot account, predeclared H1 signal at next H1 M5 open."""
    if policy not in POLICIES:
        raise ValueError("Unregistered V4 policy")
    if entry_gate is not None:
        from .v5_policy import H4_POLICIES
        if entry_gate not in H4_POLICIES:
            raise ValueError("Unregistered V5 macro policy")
        if not (h4 and h4_features and h4_closes):
            raise ValueError("V5 requires complete H4 data and closed-time index")
    if scenario not in SCENARIOS:
        raise ValueError("Unsupported fee model")
    if stop is None:
        stop = len(m5)
    if start < 0 or stop > len(m5) or stop <= start:
        raise ValueError("Invalid replay interval")
    fee = SCENARIOS[scenario]["fee"]
    dev = SCENARIOS[scenario]["slip"] + SCENARIOS[scenario]["impact"]
    hour_ends = [x.t + HOUR_MS for x in hours]
    if any(hour_ends[j] != hour_ends[j - 1] + HOUR_MS
           for j in range(1, len(hour_ends))):
        raise ValueError("Discontinuous hourly history")
    cash, position, ledger = CAPITAL, None, []
    peak, max_dd = CAPITAL, 0.
    current_date, day_start, day_lock, breaker = None, CAPITAL, False, False
    last_entry_index = -COOLDOWN_BARS - 1
    entries_per_day = 0
    signals, vetoes, executions = 0, 0, 0
    macro_rejections = {}
    prior_equity = CAPITAL
    daily = []
    for i in range(start, stop):
        b = m5[i]
        if b.t % M5_MS:
            raise ValueError("M5 candles misaligned")
        if i > start and b.t != m5[i - 1].t + M5_MS:
            raise ValueError("Missing M5 candle")
        d = local_date(b.t)
        if d != current_date:
            if current_date is not None:
                daily.append(prior_equity)
            day_start = cash + (position["qty"] * b.o if position else 0)
            current_date, day_lock, entries_per_day = d, False, 0

        # Decide at the OPEN of the first M5 bar after an H1 close.
        # Do not observe this bar's high/low/close before deciding to enter.
        open_equity = cash + (position["qty"] * b.o if position else 0)
        if open_equity <= day_start * (1 - MAX_DAILY_LOSS):
            day_lock = True
        if peak > 0 and 1 - open_equity / peak >= MAX_DRAWDOWN:
            breaker = True
        h = aligned_closed_hour_at_entry(b, hour_ends)
        if h >= MIN_CLOSED_HOURS and i != stop - 1:
            sig = detect_closed_hour(hours, f, h, policy)
            if sig is not None:
                signals += 1
                rejection = None
                if entry_gate is not None:
                    from .v5_policy import h4_rejection_reason
                    rejection = h4_rejection_reason(
                        entry_open_ms=b.t, entry_ref_price=b.o,
                        h4=h4, features=h4_features, h4_closes=h4_closes,
                        policy=entry_gate)
                    if rejection is not None:
                        macro_rejections[rejection] = macro_rejections.get(rejection, 0) + 1
                if (rejection is None and position is None
                    and not breaker and not day_lock
                    and entries_per_day == 0 and i - last_entry_index > COOLDOWN_BARS):
                    new_position = _entry_signal(sig, policy, b, cash, fee, dev)
                    if new_position is not None:
                        position = new_position
                        cash -= position["spent"]
                        last_entry_index = i
                        entries_per_day += 1
                        executions += 1
                    else:
                        vetoes += 1
                else:
                    vetoes += 1

        # Conservative INTRABAR execution also applies to a position
        # just opened at b.o. Stop is prioritized over target on b.h/b.l.
        if position is not None:
            p = position
            why, refexit = None, None
            if b.o <= p["stop"]:
                why, refexit = "gap_stop", b.o
            elif b.l <= p["stop"]:
                why, refexit = "stop", p["stop"]
            elif b.h >= p["target"]:
                why, refexit = "target", p["target"]
            elif b.t - p["entry_t"] >= policy.max_hold_h * HOUR_MS:
                why, refexit = "max_hold", b.c
            elif i == stop - 1:
                why, refexit = "fold_end", b.c
            if why is not None:
                tr = _close(p, b, refexit, why, fee, dev)
                ledger.append(tr)
                cash += p["qty"] * tr["exit"] - p["qty"] * tr["exit"] * fee
                position = None
            elif policy.exit_mode == "trail":
                # Trail on CLOSED M5, effective NEXT bar only. Never use intrabar
                # high to tighten a stop on the very candle of that high.
                p["max_price"] = max(p["max_price"], b.c)
                if b.c >= p["entry"] + 1.2 * p["distance"]:
                    p["trailing_armed"] = True
                if p["trailing_armed"]:
                    net_break_even_ref = (p["entry"] * (1 + fee) /
                                          ((1 - fee) * (1 - dev)))
                    candidate_stop = max(net_break_even_ref,
                                         p["max_price"] - 1.15 * p["atr"])
                    p["stop"] = min(p["target"], max(p["stop"], candidate_stop))
        equity = cash + (position["qty"] * b.c if position else 0)
        if equity < 0:
            raise AssertionError("No shorting or leverage allowed")
        peak = max(peak, equity)
        max_dd = max(max_dd, 1 - equity / peak)
        if equity <= day_start * (1 - MAX_DAILY_LOSS):
            day_lock = True
        if max_dd >= MAX_DRAWDOWN:
            breaker = True
        prior_equity = equity

    if position is not None:
        # Cannot create a free option by leaving an open position uncounted.
        b = m5[stop - 1]
        tr = _close(position, b, b.c, "fold_end", fee, dev)
        ledger.append(tr)
        cash += position["qty"] * tr["exit"] * (1 - fee)
        prior_equity = cash
    if not daily or daily[-1] != prior_equity:
        daily.append(prior_equity)
    if abs(cash - CAPITAL - sum(x["pnl_usd"] for x in ledger)) > 5e-3:
        raise AssertionError("Ending balance differs from sum of individual trades")
    metrics = _summary(ledger, equity=cash, max_dd=max_dd, daily=daily,
                       rejected=vetoes, signals=signals, breaker=breaker,
                       scenario=scenario)
    metrics.update({
        "ending_equity_usd": round(cash, 4),
        "signals": signals, "entries": executions, "vetoes": vetoes,
        "start_t": m5[start].t, "end_t": m5[stop - 1].t,
        "policy": asdict(policy), "notional_cap_fraction": MAX_NOTIONAL_FRACTION,
        "h4_veto_counts": dict(sorted(macro_rejections.items())),
        "entry_gate": asdict(entry_gate) if entry_gate else None,
    })
    return metrics, ledger
