"""Conservative, long-only SPOT execution simulator and paper portfolio guards.

Trades and P&L are research simulations, NOT observed fills.
Never place orders; never read Telegram secrets or existing project state.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timezone
from math import sqrt
from random import Random
from statistics import mean, pstdev
from zoneinfo import ZoneInfo

from .strategies import signal

TZ = ZoneInfo("America/Sao_Paulo")
CAPITAL = 10_000.0
SCENARIOS = {
    # Binance regular spot 10 bps per side. Execution deviation already
    # represents spread/slippage; spread is NOT charged a second time.
    "base": {"fee": .001, "slip": .0002, "impact": 0.0},
    "double_cost": {"fee": .002, "slip": .0004, "impact": 0.0},
    "adverse": {"fee": .001, "slip": .0008, "impact": .0003},
}
MAX_DAILY_LOSS = .02
MAX_DRAWDOWN = .10
MAX_POSITIONS = 2
MAX_SHARED_NOTIONAL = .60
MAX_CORRELATED_CRYPTO_NOTIONAL = .40


def local_date(t_ms):
    return datetime.fromtimestamp(t_ms / 1000, timezone.utc).astimezone(TZ).date()


class PortfolioGate:
    """For prospective COMBINED paper use; not implicitly active in solo replay."""
    def __init__(self):
        self.positions = {}

    def can_open(self, key, symbol, notional, equity, *, stale=False, sync_ok=True):
        if stale or not sync_ok or equity <= 0 or notional <= 0:
            return False
        if key in self.positions or len(self.positions) >= MAX_POSITIONS:
            return False
        if any(p[0] == symbol for p in self.positions.values()):
            return False
        total = sum(p[1] for p in self.positions.values()) + notional
        if symbol in ("BTCUSDT", "ETHUSDT"):
            crypto = sum(p[1] for p in self.positions.values()
                         if p[0] in ("BTCUSDT", "ETHUSDT")) + notional
            if crypto > MAX_CORRELATED_CRYPTO_NOTIONAL * equity:
                return False
        return total <= MAX_SHARED_NOTIONAL * equity

    def opened(self, key, symbol, notional, equity, **checks):
        if not self.can_open(key, symbol, notional, equity, **checks):
            raise ValueError("Portfolio risk gate denied new exposure")
        self.positions[key] = (symbol, notional)

    def closed(self, key):
        self.positions.pop(key, None)


def _summary(trades, *, initial=CAPITAL, equity=CAPITAL, max_dd=0, daily=None,
             rejected=0, signals=0, breaker=False, scenario="base"):
    wins = [x["pnl_usd"] for x in trades if x["pnl_usd"] > 0]
    losses = [x["pnl_usd"] for x in trades if x["pnl_usd"] <= 0]
    net = sum(x["pnl_usd"] for x in trades)
    gross_win, gross_loss = sum(wins), -sum(losses)
    pf = gross_win / gross_loss if gross_loss > 0 else None
    n = len(trades)
    monthly, regime, grouped = defaultdict(float), defaultdict(float), defaultdict(list)
    for t in trades:
        d = local_date(t["exit_t"])
        monthly[d.strftime("%Y-%m")] += t["pnl_usd"]
        regime[t["regime"]] += t["pnl_usd"]
        grouped[str(d)].append(t["pnl_usd"])
    # Bootstrap whole exit-days, not individual trades, to retain intra-day clustering.
    interval = None
    if n >= 30 and len(grouped) >= 30:
        days = list(grouped.values())
        rng = Random(0xC0FFEE)
        trials = []
        for _ in range(300):
            draws = [days[rng.randrange(len(days))] for __ in range(len(days))]
            count = sum(len(d) for d in draws)
            if count:
                trials.append(sum(map(sum, draws)) / count)
        if trials:
            trials.sort()
            interval = [round(trials[int(len(trials) * .025)], 6),
                        round(trials[int(len(trials) * .975)], 6)]
    daily = daily or []
    returns = [daily[i] / daily[i - 1] - 1 for i in range(1, len(daily)) if daily[i - 1] > 0]
    sharpe = sortino = None
    if len(returns) >= 60:
        sd = pstdev(returns)
        downside = sqrt(mean([min(x, 0)**2 for x in returns]))
        sharpe = mean(returns) / sd * sqrt(365) if sd > 0 else None
        sortino = mean(returns) / downside * sqrt(365) if downside > 0 else None
    # Approximate serial-dependence correction; don't imply independent samples.
    pnl = [t["pnl_usd"] for t in trades]
    eff = None
    if len(pnl) >= 3:
        center = mean(pnl)
        denom = sum((x - center)**2 for x in pnl)
        rho = (sum((pnl[k] - center) * (pnl[k - 1] - center)
                   for k in range(1, n)) / denom) if denom else 0
        rho = max(0, min(.95, rho))
        eff = round(n * (1 - rho) / (1 + rho), 1)
    return {
        "scenario": scenario, "trades_closed": n, "wins": len(wins),
        "losses": len(losses), "winrate": len(wins) / n if n else None,
        "avg_win_usd": gross_win / len(wins) if wins else None,
        "avg_loss_usd": gross_loss / len(losses) if losses else None,
        "payoff": ((gross_win / len(wins)) / (gross_loss / len(losses))
                   if wins and losses and gross_loss else None),
        "profit_factor": pf, "gross_win_usd": round(gross_win, 4),
        "gross_loss_usd": round(gross_loss, 4),
        "net_usd": round(net, 4), "return_pct": round((equity / initial - 1) * 100, 4),
        "expectancy_usd": round(net / n, 6) if n else None,
        "max_drawdown_pct_mark_to_market": round(max_dd * 100, 4),
        "fees_usd": round(sum(t["fees_usd"] for t in trades), 4),
        "execution_deviation_usd": round(sum(t["execution_deviation_usd"] for t in trades), 4),
        "costs_total_usd": round(sum(t["fees_usd"] + t["execution_deviation_usd"] for t in trades), 4),
        "concentration_top3_of_positive_pnl": (round(sum(sorted(wins, reverse=True)[:3]) / gross_win, 4)
                                               if wins else None),
        "ci95_expectancy_day_bootstrap_usd": interval,
        "effective_n_lag1_approx": eff,
        "sharpe_daily": round(sharpe, 4) if sharpe is not None else None,
        "sortino_daily": round(sortino, 4) if sortino is not None else None,
        "monthly_net_usd": dict(sorted(monthly.items())),
        "regimes_net_usd": dict(sorted(regime.items())),
        "signals": signals, "rejected_or_unfilled": rejected,
        "circuit_breaker_tripped": breaker,
    }


def _regime(bars, f, i):
    if abs(f.ema50[i] - f.ema200[i]) > 1.5 * f.atr[i]:
        return "trending"
    if f.atr[i] / bars[i].c > .0035:
        return "high_volatility"
    return "range"


def replay(bars, f, name, scenario="base", *, start=210, stop=None,
           higher=None, higher_features=None, higher_closes=None,
           breakout_mode="immediate", simple=False, sensitivity=1.0,
           research_policy=None):
    if scenario not in SCENARIOS:
        raise ValueError("Unknown cost scenario")
    if stop is None:
        stop = len(bars)
    if start < 210 or stop > len(bars) or start >= stop:
        raise ValueError("Invalid replay bounds")
    cost = SCENARIOS[scenario]
    fee_rate, dev = cost["fee"], cost["slip"] + cost["impact"]
    risk = .0025 if name in ("sweep", "vwap") else .005
    max_hold = (research_policy["max_hold"] if research_policy else
                (90 if name in ("sweep", "vwap") else 72))
    cash = CAPITAL
    position = None
    pending = None
    trades = []
    peak = CAPITAL
    max_dd = 0.0
    breaker = False
    blocked_day = False
    this_day = None
    day_start = CAPITAL
    day_closes = []
    rejected = signals = gate_vetoes = 0
    # At start, no earlier signal is backfilled into this fold.
    for i in range(start, stop):
        b = bars[i]
        d = local_date(b.t)
        if d != this_day:
            if this_day is not None:
                day_closes.append(prior_equity)
            this_day, day_start, blocked_day = d, cash + (position["qty"] * b.o if position else 0), False

        if pending is not None:
            if position is None and not blocked_day and not breaker:
                sig, sign_i = pending
                ref = b.o  # first available next candle open, NEVER prior close
                slip_entry = ref * (1 + dev)
                atr = f.atr[sign_i]
                if abs(b.o - bars[sign_i].c) <= 1.5 * atr:
                    structure = max(0, slip_entry - sig.structure_low + .10 * atr)
                    distance = max(sig.stop_atr * atr, min(2.5 * atr, structure))
                    if distance > 0 and distance / slip_entry >= .0003:
                        # Size against the FULL modeled stop loss, including both
                        # commissions and exit execution deviation (not just ATR).
                        stop_fill = (slip_entry - distance) * (1 - dev)
                        per_unit_stop_loss = (slip_entry * (1 + fee_rate)
                                              - stop_fill * (1 - fee_rate))
                        units_risk = (cash * risk) / per_unit_stop_loss
                        units_cash = cash / (slip_entry * (1 + fee_rate))
                        units = min(units_risk, units_cash)
                        if units > 0:
                            buy_fee = units * slip_entry * fee_rate
                            cash -= units * slip_entry + buy_fee
                            position = {
                                "name": sig.name, "signal_t": bars[sign_i].t,
                                "entry_t": b.t, "entry": slip_entry, "reference_entry": ref,
                                "qty": units, "stop": slip_entry - distance,
                                "target": slip_entry + sig.target_r * distance,
                                "entry_fee": buy_fee, "entry_deviation": units * (slip_entry - ref),
                                "spent": units * slip_entry + buy_fee, "reason": sig.reason,
                                "regime": _regime(bars, f, sign_i), "entry_i": i,
                            }
                        else:
                            rejected += 1
                    else:
                        rejected += 1
                else:
                    rejected += 1  # gap / unfillable at assumed trigger
            else:
                rejected += 1
            pending = None

        if position is not None:
            p = position
            reason = None
            refexit = None
            # Stop may gap down: do NOT grant the stale stop price.
            if b.o <= p["stop"]:
                refexit, reason = b.o, "gap_stop"
            elif b.l <= p["stop"]:
                refexit, reason = p["stop"], "stop"
            elif b.h >= p["target"]:
                refexit, reason = p["target"], "target"
            elif i - p["entry_i"] >= max_hold or i == stop - 1:
                refexit, reason = b.c, "time_or_fold_end"
            if reason is not None:
                exit_fill = refexit * (1 - dev)
                exit_fee = p["qty"] * exit_fill * fee_rate
                cash += p["qty"] * exit_fill - exit_fee
                pnl = p["qty"] * exit_fill - exit_fee - p["spent"]
                trades.append({
                    "robot": p["name"], "signal_t": p["signal_t"],
                    "entry_t": p["entry_t"], "exit_t": b.t,
                    "entry": round(p["entry"], 9), "exit": round(exit_fill, 9),
                    "qty": round(p["qty"], 9), "pnl_usd": round(pnl, 7),
                    "fees_usd": round(p["entry_fee"] + exit_fee, 7),
                    "execution_deviation_usd": round(
                        p["entry_deviation"] + p["qty"] * (refexit - exit_fill), 7),
                    "stop": round(p["stop"], 8), "target": round(p["target"], 8),
                    "exit_reason": reason, "signal_reason": p["reason"], "regime": p["regime"],
                })
                position = None

        equity = cash + (position["qty"] * b.c if position else 0)
        peak = max(peak, equity)
        max_dd = max(max_dd, 1 - equity / peak)
        if equity <= day_start * (1 - MAX_DAILY_LOSS):
            blocked_day = True
        if max_dd >= MAX_DRAWDOWN:
            breaker = True
        prior_equity = equity

        # Generate signals only AFTER end-of-candle settlement.
        if position is None and pending is None and not blocked_day and not breaker and i < stop - 1:
            if simple:
                # Predeclared simple-control signal: EMA20 crosses above EMA50.
                s = (i > 210 and f.ema20[i] > f.ema50[i] and
                     f.ema20[i - 1] <= f.ema50[i - 1])
                if s:
                    from .strategies import Signal
                    sig = Signal("ema20_50_baseline", 1.5, 2.0, b.l, "simple_ema_crossover")
                else:
                    sig = None
            else:
                sig = signal(name, bars, f, i, higher=higher,
                             higher_features=higher_features,
                             breakout_mode=breakout_mode,
                             higher_closes=higher_closes, strength=sensitivity)
            if sig is not None and research_policy is not None:
                # A deliberately *counterfactual* research filter using only
                # closed-bar volatility, predeclared costs and trend. No future.
                from .v2_policy import approve_closed_signal
                permitted = approve_closed_signal(
                    name, sig, bars, f, i,
                    cost=SCENARIOS["base"],  # freeze gate across cost stresses
                    reward_to_cost=research_policy["reward_to_cost"],
                    trend_gate=research_policy["trend_gate"],
                    target_r=research_policy["target_r"],
                )
                if permitted:
                    sig = replace(sig, target_r=research_policy["target_r"],
                                  reason=sig.reason + "|cost_aware_v2")
                else:
                    gate_vetoes += 1
                    sig = None
            if sig is not None:
                signals += 1
                pending = sig, i

    day_closes.append(prior_equity)
    report = _summary(trades, equity=cash, max_dd=max_dd, daily=day_closes,
                      rejected=rejected, signals=signals, breaker=breaker,
                      scenario=scenario)
    report["gate_vetoes"] = gate_vetoes
    report["research_policy"] = research_policy
    report["ending_equity_usd"] = round(cash, 4)
    report["start_utc_ms"] = bars[start].t
    report["end_utc_ms"] = bars[stop - 1].t
    return report, trades


def buy_hold(bars, start, stop, scenario="base"):
    cost = SCENARIOS[scenario]
    first, last = bars[start], bars[stop - 1]
    buy_price = first.o * (1 + cost["slip"] + cost["impact"])
    sell_price = last.c * (1 - cost["slip"] - cost["impact"])
    qty = CAPITAL / (buy_price * (1 + cost["fee"]))
    equity = qty * sell_price * (1 - cost["fee"])
    return {"start_utc_ms": first.t, "end_utc_ms": last.t,
            "net_usd": round(equity - CAPITAL, 4),
            "return_pct": round(100 * (equity / CAPITAL - 1), 4),
            "cash_baseline_net_usd": 0.0}
