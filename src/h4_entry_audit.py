"""Read-only H4 entry diagnostics for the ten existing virtual gold strategies.

Inspired by research agents (Vibe-Trading) and a separate risk-review stage
(AutoHedge), without importing their dependencies or delegating execution.
No brokerage access, model calls, position changes, or historical backfills.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite

from research.screen_v2 import aggregate_hourly_to_h4, sign
from src.strategies import make_indicators
from src.gold_forward import STUDY, DISPLAY
from src.leveraged_gold import CONFIG, DAILY_ENTRY_LOSS_LIMIT

STALE_AFTER_SECONDS = 12 * 3600
STATUS = {
    "in_position": "posição virtual aberta",
    "frozen_drawdown": "pausado por drawdown",
    "daily_loss_limit": "limite de perda diária",
    "invalid_equity": "saldo virtual inválido",
    "feed_stale": "candle antigo/mercado fechado",
    "candidate_next_bar": "nova transição; aguarda próxima abertura H4",
    "persistent_signal": "sinal persistente; sem cruzamento novo",
    "no_new_signal": "sem novo setup",
}


def _last_entry(book):
    """Use observed paper entries only; never infer missing events."""
    stamps = [t["entry_ts"] for t in book.get("closed", []) if isinstance(t.get("entry_ts"), (int, float))]
    position = book.get("position")
    if position and isinstance(position.get("start"), (int, float)):
        stamps.append(position["start"])
    return max(stamps) if stamps else None


def _classify(book, rule, bars, indicators, *, stale, leveraged):
    """Preview next bar, never call the order-entry or bookkeeping functions."""
    if book.get("position") is not None:
        return "in_position", 0
    if leveraged:
        if book.get("frozen"):
            return "frozen_drawdown", 0
        day_start = book.get("day_start_equity")
        if (isinstance(day_start, (int, float)) and isfinite(day_start) and day_start > 0
                and book["equity"] <= day_start * (1 - DAILY_ENTRY_LOSS_LIMIT)):
            return "daily_loss_limit", 0
    equity = book.get("equity")
    if not isinstance(equity, (int, float)) or not isfinite(equity) or equity <= 0:
        return "invalid_equity", 0
    if stale:
        return "feed_stale", 0
    idx = len(bars) - 1
    current = sign(rule, bars, indicators, idx)
    previous = sign(rule, bars, indicators, idx - 1)
    if current not in (-1, 0, 1) or previous not in (-1, 0, 1):
        raise ValueError("Sinal fora do domínio -1/0/1")
    if current and current != previous:
        return "candidate_next_bar", current
    if current:
        return "persistent_signal", 0
    return "no_new_signal", 0


def audit(hourly, conventional, leveraged, now):
    """Observational snapshot after both existing paper books have updated.

    A candidate is NOT a fill: existing engines can enter only at the next
    eligible H4 open. Zero candidates does not indicate a broken bot.
    """
    if not isinstance(now, (int, float)) or not isfinite(now):
        raise ValueError("Timestamp da auditoria inválido")
    bars = aggregate_hourly_to_h4(hourly)
    times = [row["time"] for row in bars]
    if len(bars) < 245 or times != sorted(set(times)):
        raise ValueError("Histórico H4 insuficiente, duplicado ou fora da ordem")
    latest_close = times[-1] + 14400
    if latest_close > now:
        raise ValueError("Há candle H4 futuro/incompleto")
    if conventional.get("h4_watermark") != times[-1] or leveraged.get("h4_watermark") != times[-1]:
        raise ValueError("Watermark diferente do último H4; não inferir entradas")
    if not conventional.get("paper_only") or not leveraged.get("paper_only"):
        raise ValueError("Estados devem ser exclusivamente virtuais")
    if set(conventional.get("books", {})) != set(STUDY) or set(leveraged.get("books", {})) != set(CONFIG):
        raise ValueError("Auditoria exige exatamente 5+5 robôs H4")
    stale = now - latest_close > STALE_AFTER_SECONDS
    indicators = make_indicators(bars)
    robots = {}
    for key in STUDY:
        book = conventional["books"][key]
        status, preview = _classify(book, key, bars, indicators, stale=stale, leveraged=False)
        robots[key] = {"group": "conventional", "label": DISPLAY[key],
                       "status": status, "explanation": STATUS[status],
                       "preview_direction": preview, "last_virtual_entry_ts": _last_entry(book)}
    for key, (rule, label) in CONFIG.items():
        book = leveraged["books"][key]
        status, preview = _classify(book, rule, bars, indicators, stale=stale, leveraged=True)
        robots[key] = {"group": "leveraged", "label": label,
                       "status": status, "explanation": STATUS[status],
                       "preview_direction": preview, "last_virtual_entry_ts": _last_entry(book)}
    counts = {name: sum(x["status"] == name for x in robots.values()) for name in STATUS}
    return {
        "schema": 1, "paper_only": True, "read_only": True,
        "source": "Yahoo GC=F H1 proxy agregado em H4; sem preço executável FBS",
        "as_of_utc": datetime.fromtimestamp(now, timezone.utc).isoformat(),
        "last_h4_open_ts": times[-1], "last_h4_close_ts": latest_close,
        "data_age_seconds": int(now - latest_close), "stale_or_closed": stale,
        "candidates_are_orders": False, "counts": counts, "robots": robots,
    }


def telegram_summary(result):
    """One compact line in the existing DAILY digest, never an extra alert."""
    c = result["counts"]
    pending = c["candidate_next_bar"]
    opened = c["in_position"]
    risk = c["frozen_drawdown"] + c["daily_loss_limit"] + c["invalid_equity"]
    waiting = c["persistent_signal"] + c["no_new_signal"]
    stale = c["feed_stale"]
    return (f"🩺 Ouro H4: {opened} abertos · {pending} pré-sinais (não ordens)"
            f" · {waiting} sem transição · {risk} risco · {stale} dado antigo")
