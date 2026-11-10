"""Replay genuine Dukascopy XAUUSD bid/ask quote updates through NQ Tracker research.

Reads CSV from the open-source dukascopy-node downloader (timestamp UTC ms,
askPrice, bidPrice). No fake aggression, no trading, no broker credentials.
Does NOT prove matching Greenhouse Tracker or broker fills. Excludes last
possibly incomplete candle. Broker feeds produce different tick counts.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

from research.xau_quote_tracker_reference import QuotePolicy, scan_closed


HEADER = {"timestamp", "askPrice", "bidPrice"}
MAX_LINES = 1_500_000
MAX_SPREAD_USD = 12.0
MAX_TIME_GAP_MS = 15 * 60 * 1000


def _sha256(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def _utc(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def aggregate_real_quotes(path: str | Path, timeframe_seconds: int = 60,
                          point: float = 0.001) -> tuple[list[dict], dict]:
    """Build OHLC BID candles and quote-update counts from raw recorded quotes.

    Not exchange-traded volume. Spread is the MAXIMUM observed in each candle;
    an accurate live MT5 chart must use its *own* broker feed instead.
    """
    path = Path(path)
    if not point > 0 or timeframe_seconds not in (60, 300, 900):
        raise ValueError("Invalid timeframe/point")
    size = path.stat().st_size
    if size <= 0 or size > 250_000_000:
        raise ValueError("Missing or oversized source CSV")
    bars: list[dict] = []
    previous = None
    active = None
    total = 0
    ignored_unchanged = 0
    min_spread = float("inf")
    max_spread = 0.0
    frame_ms = timeframe_seconds * 1000
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not HEADER.issubset(reader.fieldnames or []):
            raise ValueError("dukascopy-node tick CSV must include timestamp,askPrice,bidPrice")
        for item in reader:
            total += 1
            if total > MAX_LINES:
                raise ValueError("Exceeded controlled quote budget")
            try:
                ms = int(item["timestamp"])
                bid = float(item["bidPrice"])
                ask = float(item["askPrice"])
            except (TypeError, ValueError, KeyError, OverflowError) as exc:
                raise ValueError(f"Malformed quote at record {total}") from exc
            spread = ask - bid
            if (ms < 946684800000 or not math.isfinite(bid) or
                not math.isfinite(ask) or bid <= 0 or not 0 < spread <= MAX_SPREAD_USD):
                raise ValueError(f"Invalid or crossed XAUUSD bid/ask at record {total}")
            if previous:
                if ms < previous[0]:
                    raise ValueError(f"Out-of-order Dukascopy source at record {total}")
                if ms - previous[0] > MAX_TIME_GAP_MS and ms // frame_ms == previous[0] // frame_ms:
                    raise ValueError("Quote time anomaly")
                if bid == previous[1] and ask == previous[2]:
                    ignored_unchanged += 1
                    continue  # A quote volume update is NOT a quote price update.
            bar_time = (ms // frame_ms) * timeframe_seconds
            if active is None or bar_time != active["time"]:
                if active is not None:
                    bars.append(active)
                active = {
                    "time": bar_time,
                    "open": bid, "high": bid, "low": bid, "close": bid,
                    "tick_volume": 0, "spread_points": 0,
                }
            active["high"] = max(active["high"], bid)
            active["low"] = min(active["low"], bid)
            active["close"] = bid
            active["tick_volume"] += 1
            spread_pts = max(1, math.ceil((spread - 1e-10) / point))
            active["spread_points"] = max(active["spread_points"], spread_pts)
            min_spread = min(min_spread, spread)
            max_spread = max(max_spread, spread)
            previous = (ms, bid, ask)
    if active is not None:
        bars.append(active)
    if not bars:
        raise ValueError("No valid independent historical quotes")
    if len(bars) < 50:
        raise ValueError("Insufficient quote history for research: need at least 50 candles")
    if all(b["high"] == b["low"] for b in bars):
        raise ValueError("No historical bid-price movement")
    audit = {
        "origin": "dukascopy-node downloaded XAUUSD historical tick CSV",
        "market": "XAUUSD spot bid/ask quotes (not COMEX futures, not MT5 broker)",
        "source_sha256": _sha256(path),
        "source_bytes": size,
        "source_rows": total,
        "repeated_price_quotes_ignored": ignored_unchanged,
        "aggregated_closed_or_open_bars": len(bars),
        "timeframe_seconds": timeframe_seconds,
        "first_candle_utc": _utc(bars[0]["time"] * 1000),
        "last_candle_utc": _utc(bars[-1]["time"] * 1000),
        "spread_min_usd": round(min_spread, 4),
        "spread_max_usd": round(max_spread, 4),
        "activity_type": "observed bid/ask quote-price changes (not traded contracts)",
        "execution_model": None,
    }
    return bars, audit


def replay_historical_quotes(path: str | Path, timeframe_seconds: int = 60,
                             point: float = 0.001) -> dict:
    bars, audit = aggregate_real_quotes(path, timeframe_seconds, point)
    policy = QuotePolicy(timeframe_seconds=timeframe_seconds, point=point,
                         tick_size=point)
    # The final source candle might be unfinished, NEVER score it.
    signals = scan_closed(bars, len(bars) - 2, policy)
    audit["excluded_potentially_open_last_candle"] = True
    audit["evaluated_closed_bars"] = max(0, len(bars)-2)
    audit["candidates_total"] = len(signals)
    audit["signals_buy"] = sum(s["side"] == "BUY" for s in signals)
    audit["signals_sell"] = sum(s["side"] == "SELL" for s in signals)
    audit["example_signals"] = signals[:15]
    audit["exact_original_tracker_match_verified"] = False
    audit["bid_ask_quotes_not_trades"] = True
    audit["profitability_untested"] = True
    audit["orders_sent"] = 0
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only independent XAUUSD historical quote replay")
    parser.add_argument("--ticks", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeframe", choices=("M1", "M5"), default="M1")
    parser.add_argument("--point", type=float, default=0.001)
    args = parser.parse_args()
    report = replay_historical_quotes(args.ticks, 60 if args.timeframe == "M1" else 300,
                                      args.point)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "source_sha256", "source_rows", "aggregated_closed_or_open_bars",
        "candidates_total", "signals_buy", "signals_sell", "profitability_untested"
    )}, indent=2))


if __name__ == "__main__":
    main()
