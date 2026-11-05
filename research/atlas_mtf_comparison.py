"""ATLAS timeframe research: M5, M15, M30, H1 on SAME 5m GC=F feed.

Historical backtest, not paper-forward and not brokerage performance. No model
optimization or cross-market substitutions. All signals are based on closed bars.
For the ambiguous entry candle the actual ATLAS step() uses stop-first.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from urllib.parse import quote
from unittest.mock import patch
import json
import os
import time
import urllib.request

from src import atlas_vector as atlas

SYMBOL = "GC=F"
INTERVAL_S = 300
TIMEFRAMES = {"M5": 300, "M15": 900, "M30": 1800, "H1": 3600}
COST_SCENARIOS_BPS = (7, 14, 28)
MIN_M5_BARS = 500
MIN_H1_BARS = 180


def utc(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def parse_5m(payload, now):
    charts = (payload.get("chart") or {}).get("result") or []
    if not charts:
        error = (payload.get("chart") or {}).get("error")
        raise ValueError("Yahoo sem resultado: " + str(error)[:150])
    item = charts[0]
    quotes = ((item.get("indicators") or {}).get("quote") or [])
    stamps = item.get("timestamp") or []
    if not quotes:
        raise ValueError("Yahoo sem OHLCV")
    q = quotes[0]
    result = {}
    for i, raw in enumerate(stamps):
        ts = int(raw)
        if ts % INTERVAL_S != 0 or ts + INTERVAL_S > now - 180:
            continue
        try:
            o, h, l, c = (float(q[k][i]) for k in ("open", "high", "low", "close"))
        except (IndexError, TypeError, ValueError, KeyError):
            continue
        if not all(isfinite(v) and v > 0 for v in (o, h, l, c)):
            continue
        if l > min(o, c) or h < max(o, c) or h < l:
            continue
        row = {"time": ts, "open": o, "high": h, "low": l, "close": c}
        vol = q.get("volume", [])
        if vol is not None and i < len(vol):
            try:
                v = float(vol[i])
                if isfinite(v) and v >= 0:
                    row["volume"] = v
            except (ValueError, TypeError):
                pass
        result[ts] = row
    bars = [result[t] for t in sorted(result)]
    if len(bars) < MIN_M5_BARS:
        raise ValueError(f"Histórico M5 insuficiente ({len(bars)} candles)")
    if now - bars[-1]["time"] - INTERVAL_S > 4 * 86400:
        raise ValueError("M5 antigo: feed possivelmente desatualizado")
    return bars


def download_m5(now=None):
    now = int(now or time.time())
    # Within Yahoo's ~60 day limit for M5; ~1 month common comparison window.
    errors = []
    for host in ("query1.finance.yahoo.com", "query2.finance.yahoo.com"):
        url = ("https://" + host + "/v8/finance/chart/" + quote(SYMBOL, safe="")
               + "?interval=5m&range=1mo")
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as response:
                payload = json.load(response)
            return parse_5m(payload, now)
        except Exception as exc:
            errors.append(host + ": " + type(exc).__name__ + ": " + str(exc)[:120])
    raise RuntimeError("GC=F M5 indisponível; não calcular winrate: " + " | ".join(errors))


def resample_m5(m5, seconds):
    """Keep ONLY complete UTC-aligned, contiguous blocks; never interpolate."""
    if seconds not in TIMEFRAMES.values():
        raise ValueError("Timeframe not allowed")
    if seconds == 300:
        return [dict(x) for x in m5]
    factor = seconds // INTERVAL_S
    buckets = {}
    for x in m5:
        buckets.setdefault(x["time"] // seconds * seconds, []).append(x)
    result = []
    for start in sorted(buckets):
        group = sorted(buckets[start], key=lambda r: r["time"])
        if len(group) != factor or any(
            x["time"] != start + j * INTERVAL_S for j, x in enumerate(group)
        ):
            continue
        row = {"time": start, "open": group[0]["open"], "close": group[-1]["close"],
               "high": max(x["high"] for x in group),
               "low": min(x["low"] for x in group)}
        vols = [x.get("volume") for x in group]
        if all(isinstance(v, (int, float)) and isfinite(v) and v >= 0 for v in vols):
            row["volume"] = sum(vols)
        result.append(row)
    return result


def simulate(bars, *, timeframe, cost_bps):
    """Apply unchanged ATLAS step/levels/detector on completed candles only."""
    if timeframe not in TIMEFRAMES:
        raise ValueError("Timeframe unsupported")
    if len(bars) < (MIN_H1_BARS if timeframe == "H1" else 60):
        return {"status": "insufficient_history", "candles": len(bars),
                "winrate_pct": None}
    positive_vol = sum(isinstance(x.get("volume"), (int, float))
                       and isfinite(x["volume"]) and x["volume"] > 0 for x in bars)
    coverage = positive_vol / len(bars)
    # Nonpositive/missing volume cannot masquerade as real signals.
    if coverage < 0.90:
        return {"status": "insufficient_volume", "candles": len(bars),
                "positive_volume_pct": round(100 * coverage, 2),
                "winrate_pct": None, "closed": None, "net_usd": None}

    book = atlas.initial(bars[:60])
    book["timeframe"] = timeframe
    # Model settings frozen. The project's macro calendar is deliberately NOT
    # used for this baseline historical comparison, uniformly across frames.
    with patch.dict(atlas.COST_BPS, {atlas.MARKET: cost_bps}), \
         patch.object(atlas, "entry_permission", return_value=True):
        for i in range(60, len(bars)):
            atlas.step(book, bars, i)
    stats = atlas.scorecard(book)
    trades = book["closed"]
    wins = sum(t["net_usd"] > 0 for t in trades)
    gross_wins = sum(t["net_usd"] for t in trades if t["net_usd"] > 0)
    gross_losses = -sum(t["net_usd"] for t in trades if t["net_usd"] < 0)
    if abs(sum(t["net_usd"] for t in trades) - stats["net_usd"]) > 0.01:
        raise AssertionError("ATLAS backtest ledger did not reconcile")

    # Chronological final 30% is a diagnostic holdout, NOT independently
    # validated forward trading; don't reoptimize parameters from it.
    split_idx = max(60, int(len(bars) * 0.70))
    split_ts = bars[split_idx]["time"]
    tail = [t for t in trades if t["exit_ts"] >= split_ts]
    tw = sum(t["net_usd"] > 0 for t in tail)
    return {
        "status": "experimental_backtest" if len(trades) >= 30 else "low_trade_count",
        "timeframe": timeframe, "candles": len(bars),
        "first_utc": utc(bars[0]["time"]), "last_utc": utc(bars[-1]["time"]),
        "positive_volume_pct": round(100 * coverage, 2),
        "signals": sum(bool(atlas.signal(bars, i)) for i in range(60, len(bars))),
        "orders_filled": len(book["entries"]),
        "unfilled_cancelled": len(book["cancelled"]),
        "closed": stats["closed"], "wins": stats["wins"], "losses": stats["losses"],
        "winrate_pct": stats["winrate_pct"], "net_usd": stats["net_usd"],
        "profit_factor": round(gross_wins / gross_losses, 3) if gross_losses > 0 else None,
        "max_closed_drawdown_pct": stats["max_closed_drawdown_pct"],
        "roundtrip_cost_bps": cost_bps,
        "total_estimated_cost_usd": round(sum(t["cost_usd"] for t in trades), 2),
        "uncertain_same_bar_exits": sum(t["same_bar_order_uncertain"] for t in trades),
        "position_open_at_end": bool(book["position"]),
        "pending_order_at_end": bool(book["pending"]),
        "tail_30pct": {
            "from_utc": utc(split_ts), "closed": len(tail), "wins": tw,
            "winrate_pct": round(100 * tw / len(tail), 2) if tail else None,
            "net_usd": round(sum(t["net_usd"] for t in tail), 2),
        },
        "trades_ledger": trades,
    }


def run(m5):
    if not m5:
        raise ValueError("Empty dataset")
    report = {
        "name": "ATLAS M5–H1 experimental retrospective comparison",
        "market": "GC=F futures proxy for XAUUSD, NOT B3 mini index",
        "source": "Yahoo Finance GC=F, raw closed 5m candles resampled locally",
        "first_m5_utc": utc(m5[0]["time"]),
        "last_m5_utc": utc(m5[-1]["time"]),
        "m5_bars": len(m5),
        "paper_only": True, "validated": False, "lookahead": False,
        "model": "same ATLAS detector: lookback 20, relative volume 1.5x, wick 30%",
        "entry_levels": "entry 50%, target 200%, stop -100%, candle range, 1:1 nominal R:R",
        "risk_fraction": atlas.RISK, "notional_limit": atlas.NOTIONAL_CAP,
        "order_lifetime_bars": atlas.ORDER_LIFE_BARS,
        "max_hold_bars": atlas.MAX_HOLD_BARS,
        "news_filter": "disabled identically in all research scenarios",
        "fees": "indicative all-in round-trip bps of notional; not broker fills",
        "limitations": [
            "M5 Yahoo intraday is limited to recent history; 1 month cannot validate future profitability",
            "Bar OHLC cannot establish precise order of stop, entry and target",
            "Partial interval groups and missing volumes are excluded, never synthesized",
            "No tick-based spread/slippage, no Brazilian mini-index data, no real FBS fills",
            "GC=F continuous futures may include contract-roll irregularities",
            "M5/M15/M30/H1 have different absolute lifetime for the same 3/90-bar rules",
            "Terminal open positions are excluded from realized winrate",
            "Volume absent or zero for >10% of candles invalidates timeframe comparison",
        ],
        "timeframes": {},
    }
    for name, span in TIMEFRAMES.items():
        candles = resample_m5(m5, span)
        report["timeframes"][name] = {
            "source_bar_count": len(candles),
            "fraction_complete_vs_m5": round(
                100 * len(candles) * (span // 300) / len(m5), 2),
            "scenarios": {str(bps): simulate(candles, timeframe=name, cost_bps=bps)
                          for bps in COST_SCENARIOS_BPS},
        }
    return report


def summary(result):
    lines = [
        "# ATLAS | M5, M15, M30, H1 — estudo retrospectivo",
        "",
        f"**Dados:** GC=F (futuro de ouro; não mini-índice WIN/B3). "
        f"{result['first_m5_utc']} a {result['last_m5_utc']} UTC.",
        "**Regras:** modelo independente ATLAS; sinal fechado, entrada 50%, "
        "alvo 200%, stop -100%. 1:1 de risco/retorno nominal.",
        "**Não são resultados prospectivos ou operações de corretora.**",
        "",
        "| TF | M5 equivalentes íntegros | Volume válido | Fechadas | Winrate | P&L US$ | PF | DD fechado | Estado |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    def display(v, suffix=""):
        return "N/D" if v is None else str(v) + suffix
    for tf, item in result["timeframes"].items():
        d = item["scenarios"]["7"]
        lines.append(
            f"| {tf} | {item['fraction_complete_vs_m5']}% | "
            f"{display(d.get('positive_volume_pct'), '%')} | "
            f"{display(d.get('closed'))} | {display(d.get('winrate_pct'), '%')} | "
            f"{display(d.get('net_usd'))} | {display(d.get('profit_factor'))} | "
            f"{display(d.get('max_closed_drawdown_pct'), '%')} | {d['status']} |")
    lines += ["", "## Sensibilidade a custos (bps ida+volta)", "",
              "| TF | 7 bps | 14 bps | 28 bps |",
              "|---|---:|---:|---:|"]
    for tf, item in result["timeframes"].items():
        entries = []
        for bps in COST_SCENARIOS_BPS:
            d = item["scenarios"][str(bps)]
            entries.append(display(d.get("net_usd"), " US$"))
        lines.append("| " + tf + " | " + " | ".join(entries) + " |")
    lines += ["", "## Limitações", ""]
    lines += ["- " + s for s in result["limitations"]]
    lines += ["", "Parâmetros congelados entre os quatro timeframes. "
              "Não escolher por maior winrate com menos de 30 operações; "
              "priorizar robustez líquida após custos e validação prospectiva.",
              ""]
    return "\n".join(lines)


def main():
    try:
        data = download_m5()
        result = run(data)
    except Exception as exc:
        # Never silently turn unavailable prices into 0% winrate or profits.
        result = {"name": "ATLAS M5–H1", "status": "unavailable",
                  "market": SYMBOL, "error": str(exc)[:500], "validated": False}
        print("ATLAS_BACKTEST_UNAVAILABLE " + json.dumps(result, ensure_ascii=False), flush=True)
        raise
    print("ATLAS_RESULT_SUMMARY_START", flush=True)
    print(summary(result), flush=True)
    print("ATLAS_RESULT_SUMMARY_END", flush=True)
    out = Path("research/results")
    out.mkdir(parents=True, exist_ok=True)
    (out / "atlas_m5_h1_latest.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "atlas_m5_h1_latest.md").write_text(summary(result), encoding="utf-8")
    print("ATLAS_RESULT_WRITTEN", flush=True)


if __name__ == "__main__":
    main()
