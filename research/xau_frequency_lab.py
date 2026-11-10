"""Frozen, independent XAUUSD signal-frequency experiment.

This laboratory proposes *new* sweep/rejection presets; it does not reproduce
the commercial Greenhouse Tracker. Quote tick activity is NOT traded volume.
No strategies automatically approved or sent to a broker. Test ALL presets and
ALL session windows, preserving losses and failed/invalid feeds.

Tick execution is delegated to the previously audited bid/ask engine.
Dates and strategy variants must be fixed before any evaluation.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import json
from math import isfinite
from pathlib import Path

from research.xau_dukascopy_replay import aggregate_real_quotes
from research.xau_quote_execution_backtest import (
    ExecutionAssumptions, _ticks, simulate_quote_execution,
)
from research.xau_quote_tracker_reference import (
    QuotePolicy, scan_closed, fib_levels,
)


@dataclass(frozen=True)
class Variant:
    name: str
    policy: str
    entry_fraction: float
    target_fraction: float

    def validate(self):
        if not (0 <= self.entry_fraction < self.target_fraction
                and self.target_fraction <= 4.0
                and self.policy in POLICY_OVERRIDES):
            raise ValueError("Invalid frozen research variant")


# These are research hypotheses; do not claim original Tracker settings.
# No per-day or per-timeframe threshold selection.
POLICY_OVERRIDES = {
    "reference": {},
    "balanced": dict(
        lookback=14, min_tick_updates=12, activity_factor=1.10,
        min_range_atr=0.50, max_range_atr=2.75,
        min_wick_fraction=0.22, close_location=0.58,
        sweep_atr=0.025, max_spread_atr=0.32,
    ),
    "active": dict(
        lookback=10, min_tick_updates=10, activity_factor=1.02,
        min_range_atr=0.40, max_range_atr=3.00,
        min_wick_fraction=0.18, close_location=0.55,
        sweep_atr=0.015, max_spread_atr=0.30,
    ),
}

VARIANTS = (
    Variant("reference_F50", "reference", 0.50, 2.00),
    Variant("balanced_F50", "balanced", 0.50, 2.00),
    Variant("active_F50", "active", 0.50, 2.00),
    Variant("balanced_F75", "balanced", 0.75, 2.00),
    Variant("active_F75_RR1", "active", 0.75, 2.50),
    Variant("balanced_F75_RR1", "balanced", 0.75, 2.50),
)

# Price progression mirrored for BUY/SELL.
# F50 target200 stop-100 => nominal 1:1.
# F75 target200 stop-100 => nominal 0.714:1.
# F75 target250 stop-100 => nominal 1:1.
STOP_FRACTION = -1.0


def policies_for(timeframe_seconds: int, point: float = 0.001):
    base = QuotePolicy(timeframe_seconds=timeframe_seconds, point=point, tick_size=point)
    return {
        name: replace(base, **changes)
        for name, changes in POLICY_OVERRIDES.items()
    }


def levels_for(candle: dict, direction: int, variant: Variant, tick_size: float) -> dict:
    variant.validate()
    if direction not in (-1, 1):
        raise ValueError("Invalid BUY/SELL")
    lows, highs = float(candle["low"]), float(candle["high"])
    if not 0 < lows < highs:
        raise ValueError("Invalid signal candle")
    origin = lows if direction == 1 else highs
    span = highs - lows
    from decimal import Decimal, ROUND_HALF_UP
    grid = Decimal(str(tick_size))
    if grid <= 0:
        raise ValueError("Broker tick size must be positive")
    def price(multiplier):
        value = Decimal(str(origin)) + Decimal(direction) * Decimal(str(multiplier)) * Decimal(str(span))
        return float((value / grid).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * grid)
    return {"entry": price(variant.entry_fraction),
            "target": price(variant.target_fraction),
            "stop": price(STOP_FRACTION)}


def planned_for(bars: list[dict], tf: int, variant: Variant,
                policy: QuotePolicy) -> list[dict]:
    sigs = scan_closed(bars, len(bars) - 2, policy)
    # Recalculate levels from the same closed-bar OHLC used to generate signals.
    by_time = {int(b["time"]): b for b in bars}
    planned = []
    for s in sigs:
        stamp = int(datetime.fromisoformat(s["time_utc"]).timestamp())
        side = 1 if s["side"] == "BUY" else -1
        levels = levels_for(by_time[stamp], side, variant, policy.tick_size)
        planned.append({
            "signal_ms": stamp * 1000,
            "eligible_ms": (stamp + tf) * 1000,
            "side": side,
            **levels,
        })
    return planned


def run_day(path: str | Path, day: str, *,
            commission: float = 0.30,
            slippage: float = 0.10,
            point: float = 0.001,
            variants: tuple[Variant, ...] = VARIANTS) -> dict:
    """Run ALL predeclared candidates with identical inputs, no optimization."""
    if not (len(day) == 8 and day.isdigit()):
        raise ValueError("Day must be YYYYMMDD")
    if len({v.name for v in variants}) != len(variants):
        raise ValueError("Duplicate strategy names")
    if commission < 0 or slippage < 0 or point <= 0:
        raise ValueError("Invalid cost assumptions")
    quotes = list(_ticks(Path(path)))
    if len(quotes) < 1000:
        raise ValueError("Insufficient historical bid/ask ticks")
    out = {
        "day": day, "source": "Dukascopy public bid/ask quotes",
        "original_greenhouse_tracker_match": False,
        "real_broker_backtest": False,
        "trading_approved": False,
        "commission_roundtrip_usd_per_oz": commission,
        "slippage_stop_or_market_usd_per_oz": slippage,
        "tick_size_and_point_assumed_usd": point,
        "variants": {},
        "historical_account_profit_usd": None,
    }
    file_sha = None
    bar_counts = {}
    policies_ = {}
    all_plans = {}
    for tf in (60, 300):
        bars, audit = aggregate_real_quotes(path, tf, point)
        if not audit["first_candle_utc"].startswith(
            f"{day[:4]}-{day[4:6]}-{day[6:]}"
        ):
            raise ValueError("Feed date does not match predeclared session")
        if file_sha is None:
            file_sha = audit["source_sha256"]
        elif file_sha != audit["source_sha256"]:
            raise ValueError("M1/M5 feed checksum mismatch")
        bar_counts[tf] = len(bars)
        policies_[tf] = policies_for(tf, point)
        all_plans[tf] = {}
        for var in variants:
            var.validate()
            plans = planned_for(bars, tf, var, policies_[tf][var.policy])
            all_plans[tf][var.name] = plans
            for scenario in ("no_costs", "friction", "double_friction"):
                if scenario == "no_costs":
                    fee = slip = 0.
                elif scenario == "friction":
                    fee, slip = commission, slippage
                else:
                    fee, slip = 2 * commission, 2 * slippage
                cfg = ExecutionAssumptions(timeframe_seconds=tf,
                    commission_roundtrip_usd_per_oz=fee,
                    slippage_usd_per_side=slip)
                result = simulate_quote_execution(iter(quotes), plans, cfg)
                key = f"{var.name}_{'M1' if tf == 60 else 'M5'}"
                entry = out["variants"].setdefault(key, {
                    "variant": asdict(var), "timeframe_seconds": tf,
                    "signals": len(plans), "scenarios": {},
                })
                if result["filled"] != result["closed"]:
                    raise ValueError("Unclosed position result")
                entry["scenarios"][scenario] = {
                    "filled":result["filled"],"expired":result["unfilled_expired"],
                    "skipped":result["skipped_busy_or_unseen"],
                    "wins":result["wins"],"losses":result["losses"],
                    "net_usd_per_oz":result["net_usd_per_oz"],
                    "max_closed_drawdown_usd_per_oz":result["max_closed_drawdown_usd_per_oz"],
                    "ledger":result["ledger"],
                }
                del result
            a=entry["scenarios"]
            if not (a["no_costs"]["filled"] == a["friction"]["filled"] == a["double_friction"]["filled"]):
                raise ValueError("Cost-only scenario changed fills")
            if not (a["no_costs"]["net_usd_per_oz"] + 1e-6 >= a["friction"]["net_usd_per_oz"]
                    >= a["double_friction"]["net_usd_per_oz"] - 1e-6):
                raise ValueError("Greater costs cannot improve expected net P&L")
    out["source_sha256"] = file_sha
    out["quote_rows"] = len(quotes)
    out["m1_bars"] = bar_counts[60]
    out["m5_bars"] = bar_counts[300]
    return out


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--ticks",required=True)
    p.add_argument("--day",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    report=run_day(args.ticks,args.day)
    dest=Path(args.out)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"DAY {args.day} QUOTES {report['quote_rows']} SHA256 {report['source_sha256']}")
    for name,row in sorted(report["variants"].items()):
        a=row["scenarios"]["friction"]
        b=row["scenarios"]["double_friction"]
        print(name, "signals",row["signals"],"fills",a["filled"],
              "net USD/oz",a["net_usd_per_oz"],"double costs",b["net_usd_per_oz"])

if __name__=="__main__":
    main()
