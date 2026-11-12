"""Per-trade loss attribution for Nexus Quant paper replay ledgers.

Read-only: never creates signals, changes stops, edits paper state or sends orders.
This describes *observed simulated exits*, not the cause of a losing setup.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from statistics import median


def _number(value, name):
    if isinstance(value, bool):
        raise ValueError(f"{name}: boolean is not a financial amount")
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name}: invalid numeric value") from error
    if not isfinite(result):
        raise ValueError(f"{name}: non-finite numeric value")
    return result


def _timestamp(value, name):
    if value is None:
        return None
    stamp = _number(value, name)
    try:
        return datetime.fromtimestamp(stamp, timezone.utc)
    except (OverflowError, OSError, ValueError) as error:
        raise ValueError(f"{name}: invalid timestamp") from error


def _cost(trade):
    # Different engines use different names; never count both cost_usd and
    # transaction_cost for the same entry. Funding is a separate cost.
    primary = ("cost_usd" if "cost_usd" in trade else
               "transaction_cost" if "transaction_cost" in trade else None)
    if primary is None:
        return None
    total = _number(trade[primary], primary)
    total += _number(trade.get("funding_cost", 0), "funding_cost")
    if total < -1e-9:
        raise ValueError("Negative recorded transaction/funding costs")
    return total


def _aggregate(rows):
    pnls = [row["net"] for row in rows]
    gains = sum(x for x in pnls if x > 0)
    losses = -sum(x for x in pnls if x < 0)
    return {
        "trades": len(rows),
        "wins": sum(x > 0 for x in pnls),
        "losses": sum(x < 0 for x in pnls),
        "flats": sum(x == 0 for x in pnls),
        "net_usd": round(sum(pnls), 5),
        "total_losing_trades_abs_usd": round(losses, 5),
        "avg_net_usd": round(sum(pnls) / len(rows), 5) if rows else None,
        "profit_factor": round(gains / losses, 5) if losses > 0 else None,
    }


def _by(rows, field):
    groups = {}
    for row in rows:
        groups.setdefault(row[field], []).append(row)
    return {key: _aggregate(groups[key]) for key in sorted(groups)}


def attribute_trades(closed):
    """Summarize real *recorded* closed paper trades, not hypothetical trades.

    Unknown exit reasons or timestamps remain explicit unknown categories.
    Missing trade-level costs are not silently converted into zero fees.
    The returned realized-P&L metrics exclude any position still open.
    """
    if not isinstance(closed, list):
        raise ValueError("closed must be a list of paper trade records")
    rows = []
    missing_costs = 0
    missing_times = 0
    holding_hours = []
    for index, trade in enumerate(closed):
        if not isinstance(trade, dict):
            raise ValueError(f"Trade {index}: expected mapping")
        net = _number(trade.get("net_usd"), "net_usd")
        entry = _timestamp(trade.get("entry_ts"), "entry_ts")
        exit_at = _timestamp(trade.get("exit_ts"), "exit_ts")
        if (entry is not None and exit_at is not None
                and exit_at < entry):
            raise ValueError(f"Trade {index}: exit before entry")
        if entry is None or exit_at is None:
            missing_times += 1
        else:
            holding_hours.append((exit_at - entry).total_seconds() / 3600)
        cost = _cost(trade)
        if cost is None:
            missing_costs += 1
        reason = str(trade.get("exit_type") or trade.get("reason")
                     or "UNKNOWN").strip().upper()[:64] or "UNKNOWN"
        rows.append({
            "index": index, "net": net, "cost": cost,
            "entry_utc": entry.isoformat() if entry else None,
            "exit_utc": exit_at.isoformat() if exit_at else None,
            "entry_hour_utc": f"{entry.hour:02d}" if entry else "UNKNOWN",
            "exit_month_utc": exit_at.strftime("%Y-%m") if exit_at else "UNKNOWN",
            "exit_reason": reason,
        })

    summary = _aggregate(rows)
    winning = [r["net"] for r in rows if r["net"] > 0]
    losing = [-r["net"] for r in rows if r["net"] < 0]
    total_cost = sum(r["cost"] for r in rows if r["cost"] is not None)
    cost_erased_wins = sum(
        r["net"] <= 0 and r["net"] + r["cost"] > 0
        for r in rows if r["cost"] is not None
    )

    return {
        "scope": "historical_paper_closed_trades_only",
        "not_live_broker_or_independent_oos": True,
        **summary,
        "mean_winner_usd": round(sum(winning) / len(winning), 5) if winning else None,
        "mean_loser_abs_usd": round(sum(losing) / len(losing), 5) if losing else None,
        "payoff_win_loss": (round((sum(winning) / len(winning)) /
                                 (sum(losing) / len(losing)), 5)
                            if winning and losing else None),
        "median_net_usd": round(median(r["net"] for r in rows), 5) if rows else None,
        "median_holding_hours": (round(median(holding_hours), 3)
                                 if holding_hours else None),
        "recorded_costs_usd": round(total_cost, 5) if not missing_costs else None,
        "trades_missing_cost": missing_costs,
        "trades_missing_entry_or_exit_time": missing_times,
        "cost_erased_positive_gross_trades": cost_erased_wins,
        "by_exit_reason": _by(rows, "exit_reason"),
        "by_entry_hour_utc": _by(rows, "entry_hour_utc"),
        "by_exit_month_utc": _by(rows, "exit_month_utc"),
        "worst_five": [
            {key: row[key] for key in (
                "index", "net", "cost", "entry_utc", "exit_utc", "exit_reason")}
            for row in sorted((r for r in rows if r["net"] < 0),
                              key=lambda r: (r["net"], r["index"]))[:5]
        ],
        "interpretation": (
            "Buckets are descriptive, not causal, and must not be used to "
            "choose retroactive filters. No regime/entry geometry or MAE/MFE "
            "can be inferred without causal candle/tick replay."
        ),
    }
