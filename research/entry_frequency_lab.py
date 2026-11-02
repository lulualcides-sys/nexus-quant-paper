"""Pre-registered H4 frequency comparison, research only, never broker execution.

Compare two immutable candidate variants to three existing rules on GC=F 60m
Yahoo proxy aggregated to complete H4 bars. This is a *revisited* historical
period, not genuinely unseen out-of-sample evidence. No strategy is promoted.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from json import dumps
from pathlib import Path
from math import isfinite

from research.backtest_year import get_history
from research.screen_v2 import (
    aggregate_hourly_to_h4, evaluate, sign, COST_BPS,
)
from src.feed import MARKETS
from src.strategies import make_indicators

MARKET = "XAUUSD"
RULES = ("channel20", "channel35_lab", "momentum100", "momentum60_lab", "momentum40")
TRAIN_START = int(datetime(2025, 2, 1, tzinfo=timezone.utc).timestamp())
TRAIN_END = int(datetime(2025, 10, 24, tzinfo=timezone.utc).timestamp())
TEST_END = int(datetime(2026, 10, 25, tzinfo=timezone.utc).timestamp())
OUTPUT = Path("research/results/entry_frequency_h4_2026-11-01")
BASELINES = {"channel35_lab": "channel20", "momentum60_lab": "momentum100"}
MINIMUM_TRAIN_BARS = 600
MINIMUM_REVIEW_BARS = 900


def candidate_signal(rule, bars, indicators, i):
    """Uses only bar i and older; the backtester enters at i+1 open.

    Existing baseline signs always delegate to the approved research rules.
    """
    if rule not in RULES:
        raise KeyError(rule)
    if rule in ("channel20", "momentum100", "momentum40"):
        return sign(rule, bars, indicators, i)
    if i < 240:
        return 0
    p = indicators[i]
    q = indicators[i-1]
    c = bars[i]["close"]
    bull = p["e50"] > p["e200"]
    bear = p["e50"] < p["e200"]
    if rule == "channel35_lab":
        # Only the lookback differs from the existing Channel20; same ATR gate.
        ceiling = max(x["high"] for x in bars[i-35:i])
        floor = min(x["low"] for x in bars[i-35:i])
        if bull and c > ceiling and p["atr"] > .8 * p["avg_atr"]:
            return 1
        if bear and c < floor and p["atr"] > .8 * p["avg_atr"]:
            return -1
        return 0
    # Momentum60 threshold is pre-specified at 3 ATR between Momentum40's
    # 2 ATR / 40 bars and Momentum100's 4 ATR / 100 bars.
    if rule == "momentum60_lab":
        if not p["atr"] or not q["atr"]:
            return 0
        momentum = (c - bars[i-60]["close"]) / p["atr"]
        previous = (bars[i-1]["close"] - bars[i-61]["close"]) / q["atr"]
        if bull and previous <= 3 < momentum:
            return 1
        if bear and previous >= -3 > momentum:
            return -1
        return 0
    raise KeyError(rule)


def count_signals(bars, indicators, rule, start, end):
    count = 0
    for i in range(242, len(bars)):
        # Signal generated on previous completed H4, available at next open.
        if not start <= bars[i]["time"] < end:
            continue
        now = candidate_signal(rule, bars, indicators, i-1)
        prior = candidate_signal(rule, bars, indicators, i-2)
        if now and now != prior:
            count += 1
    return count


def _metrics(result):
    """Restrict persisted output to comparable metrics, not megabyte ledgers."""
    return {key: result[key] for key in (
        "trades", "wins", "win_pct", "pnl_usd", "return_pct",
        "max_dd_pct", "fees_usd", "pf",
    )}


def compare(bars):
    """Pure analysis: no account state, no forecasting, no networking."""
    stamps = [x["time"] for x in bars]
    if len(bars) < 240 or stamps != sorted(set(stamps)):
        raise ValueError("H4 bars must be sufficiently long, unique and ordered")
    if any(not isfinite(float(x[k])) or float(x[k]) <= 0 for x in bars for k in ("open", "high", "low", "close")):
        raise ValueError("Invalid OHLC; do not invent market data")
    train_n = sum(TRAIN_START <= t < TRAIN_END for t in stamps)
    test_n = sum(TRAIN_END <= t < TEST_END for t in stamps)
    if train_n < MINIMUM_TRAIN_BARS or test_n < MINIMUM_REVIEW_BARS:
        raise ValueError(f"Insufficient complete H4 candles in splits: train={train_n}, review={test_n}")
    if stamps[0] > TRAIN_START - 55*86400:
        raise ValueError("Insufficient H4 warmup prior to training window")
    indicators = make_indicators(bars)
    comparisons = {}
    for rule in RULES:
        train = evaluate(bars, indicators, rule, MARKET, TRAIN_START, TRAIN_END,
                         signal_function=candidate_signal)
        review = evaluate(bars, indicators, rule, MARKET, TRAIN_END, TEST_END,
                          signal_function=candidate_signal)
        stressed = evaluate(bars, indicators, rule, MARKET, TRAIN_END, TEST_END,
                            cost_multiplier=2., signal_function=candidate_signal)
        comparisons[rule] = {
            "status": "candidate_unvalidated" if rule in BASELINES else "reference_existing",
            "reference": BASELINES.get(rule),
            "signals_train": count_signals(bars, indicators, rule, TRAIN_START, TRAIN_END),
            "signals_review": count_signals(bars, indicators, rule, TRAIN_END, TEST_END),
            "train": _metrics(train),
            "review_revisited_not_unseen": _metrics(review),
            "review_double_cost": _metrics(stressed),
        }
    # Compare like-for-like with fixed rules, not just a higher signal count.
    for variant, original in BASELINES.items():
        candidate = comparisons[variant]
        ref = comparisons[original]
        candidate["vs_reference"] = {
            "additional_review_signals": candidate["signals_review"] - ref["signals_review"],
            "additional_closed_trades": candidate["review_revisited_not_unseen"]["trades"] - ref["review_revisited_not_unseen"]["trades"],
            "change_in_revisited_net_usd": round(candidate["review_revisited_not_unseen"]["pnl_usd"] - ref["review_revisited_not_unseen"]["pnl_usd"], 2),
            "change_in_revisited_drawdown_pct": round(candidate["review_revisited_not_unseen"]["max_dd_pct"] - ref["review_revisited_not_unseen"]["max_dd_pct"], 2),
        }
    normalized = dumps(bars, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "study": "H4 signal frequency - controlled historical study",
        "market": "GC=F proxy for XAUUSD (NOT FBS order prices)",
        "paper_only": True, "no_live_orders": True,
        "auto_promote": False, "historical_period_already_inspected": True,
        "training_window_utc": ["2025-02-01", "2025-10-24"],
        "revisited_window_utc": ["2025-10-24", "2026-10-25"],
        "h4_train_bars": train_n, "h4_revisited_bars": test_n,
        "data_sha256": sha256(normalized).hexdigest(),
        "data_last_bar_utc": datetime.fromtimestamp(stamps[-1],timezone.utc).isoformat(),
        "cost_bps_original": COST_BPS[MARKET], "cost_bps_stress": 2*COST_BPS[MARKET],
        "comparisons": comparisons,
        "decision": "NO PROMOTION: require new forward/paper history after pre-registration",
    }


def markdown(result):
    lines = [
        "# Nexus Quant — H4 frequency research (GC=F)",
        "", "**Research-only; old windows already inspected, NOT fresh out-of-sample.**",
        "No broker orders, no allocation, no auto-promotion.",
        f"Data SHA-256: \`{result['data_sha256']}\`",
        f"Train H4 bars: {result['h4_train_bars']}; revisited H4 bars: {result['h4_revisited_bars']}.",
        "",
        "| Rule | Train signals | Revisited signals | Revisited closed trades | Net US$ | Net US$ costs ×2 | Max DD% |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, entry in result["comparisons"].items():
        row = entry["review_revisited_not_unseen"]
        stressed = entry["review_double_cost"]
        lines.append(f"| {name} | {entry['signals_train']} | {entry['signals_review']} | "
                     f"{row['trades']} | {row['pnl_usd']:+.2f} | "
                     f"{stressed['pnl_usd']:+.2f} | {row['max_dd_pct']:.2f} |")
    lines += [
        "", "## Decision gate",
        "An increase in signal count alone is NOT an improvement. Compare net result,",
        "cost ×2, drawdown, number of exits, and later prospective observations.",
        "Historical review windows are already known to the team and may be overfit.",
        "**Existing live/paper books remain unchanged.**",
        "Sources: Yahoo GC=F 60m reference, aggregated to complete H4;",
        "entry at next bar open, stop-first intrabar ordering, estimated costs.",
    ]
    return "\n".join(lines) + "\n"


def main():
    rows = get_history(MARKETS[MARKET], retries=1)
    bars = aggregate_hourly_to_h4(rows)
    result = compare(bars)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.with_suffix(".json").write_text(dumps(result,indent=2,ensure_ascii=False)+"\n", encoding="utf-8")
    OUTPUT.with_suffix(".md").write_text(markdown(result), encoding="utf-8")
    print("ENTRY_FREQUENCY_H4_COMPLETE", result["data_sha256"],
          [(name,x["signals_review"],x["review_revisited_not_unseen"]["pnl_usd"]) for name,x in result["comparisons"].items()])


if __name__ == "__main__":
    main()
