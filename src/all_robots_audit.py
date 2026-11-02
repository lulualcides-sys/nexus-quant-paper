"""Read-only unified audit for the 27 planned Nexus Quant financial paper robots.

10 gold H4 + 15 experimental H1 + 1 USD/CAD M15 + 1 Momentum60 H4.
Never executes trades, changes state, loads keys, or fabricates missing data.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from math import isfinite

from src.feed import MARKETS
from src.gold_forward import STUDY, DISPLAY, CAPITAL as GOLD_CAPITAL
from src.leveraged_gold import CONFIG as LEV_CONFIG, CAPITAL as LEV_CAPITAL
from src.experimental_h1 import STRATEGIES as H1_STRATEGIES, CAPITAL as H1_CAPITAL, bot_key
from src.bb_rebound_mtf import CAPITAL as M15_CAPITAL
from src.momentum60_shadow import CAPITAL as MOMENTUM_CAPITAL

TOTAL = 27
GROUP_SIZES = {"gold_h4": 5, "leveraged_h4": 5, "experimental_h1": 15,
               "usdcad_m15": 1, "momentum60_h4": 1}
NO_DATA = "unavailable"
DATA_MAX_AGE_S = {"gold_h4": 12*3600, "leveraged_h4": 12*3600,
                  "experimental_h1": 12*3600, "usdcad_m15": 12*3600,
                  "momentum60_h4": 12*3600}


def _entries(book):
    """Only actual recorded paper entries; no historical reconstruction."""
    if "entries" in book:
        return len(book["entries"])
    if "closed" not in book:
        return None
    starts = [t["entry_ts"] for t in book["closed"] if "entry_ts" in t]
    pos = book.get("position")
    if pos:
        opened = pos.get("start", pos.get("entry_ts"))
        if opened is not None:
            starts.append(opened)
    # M15 paper books do not store every entry separately, but all closed
    # trades have entry_ts; this is an observed lower bound, not a signal count.
    return len(starts)


def _last_entry(book):
    stamps = [t.get("entry_ts") for t in book.get("entries", [])]
    stamps += [t.get("entry_ts") for t in book.get("closed", [])]
    pos = book.get("position")
    if pos:
        stamps.append(pos.get("start", pos.get("entry_ts")))
    valid = [ts for ts in stamps if isinstance(ts, (int, float)) and isfinite(ts)]
    return max(valid) if valid else None


def _stale(observed_close, now, group):
    if not isinstance(observed_close, (int, float)) or not isfinite(observed_close):
        return None
    return now - observed_close > DATA_MAX_AGE_S[group]


def _record(group, label, *, book=None, capital=None, status=None,
            reason=None, observed_close=None, now=None, entries_exact=False):
    if book is None:
        return {
            "group": group, "name": label, "status": NO_DATA,
            "reason": str(reason or "Estado não disponível")[:180],
            "paper_only": True, "metrics_available": False,
            "last_observed_close_ts": observed_close,
            "data_stale": _stale(observed_close, now, group),
            "entries_observed": None, "entries_complete": False,
            "closed": None, "open": None,
            "net_realized_usd": None, "wins": None, "losses": None,
        }
    if not isinstance(book, dict):
        return _record(group,label,reason="Estado inválido",observed_close=observed_close,now=now)
    equity = book.get("equity")
    if not isinstance(equity, (int, float)) or not isfinite(equity):
        return _record(group,label,reason="Equity ausente/inválido",observed_close=observed_close,now=now)
    closed = book.get("closed", [])
    if not isinstance(closed, list):
        return _record(group,label,reason="Histórico de fechamentos inválido",observed_close=observed_close,now=now)
    net = equity - capital if capital is not None else None
    stale = _stale(observed_close, now, group)
    if status is None:
        status = "in_position" if book.get("position") else ("data_stale" if stale else "no_new_signal")
    if status != "in_position" and stale is True and status not in ("frozen_drawdown","daily_loss_limit","invalid_equity"):
        status = "data_stale"
    return {
        "group": group, "name": label, "status": status,
        "reason": str(reason or "")[:180], "paper_only": True, "metrics_available": True,
        "last_observed_close_ts": observed_close, "data_stale": stale,
        "entries_observed": _entries(book), "entries_complete": entries_exact,
        "last_entry_ts": _last_entry(book), "closed": len(closed),
        "open": bool(book.get("position")), "net_realized_usd": round(net, 5),
        "wins": sum(t.get("net_usd",0)>0 for t in closed),
        "losses": sum(t.get("net_usd",0)<0 for t in closed),
    }


def build(*, now, conventional, leveraged, h4_result, h1_state, mtf_state,
          momentum_state, errors=None):
    """Assemble a complete, immutable 27-slot snapshot from existing paper states."""
    if not isinstance(now, (int,float)) or not isfinite(now):
        raise ValueError("Invalid timestamp")
    errors = errors or {}
    robots = {}

    # When a shared H4 audit failed, fail closed for its entire group:
    # showing 10 false clean statuses would conceal missing data.
    h4_items = h4_result.get("robots", {}) if h4_result else {}
    h4_close = h4_result.get("last_h4_close_ts") if h4_result else None
    for key in STUDY:
        id = "gold_h4:" + key
        diagnostic = h4_items.get(key)
        book = conventional.get("books", {}).get(key) if conventional and conventional.get("paper_only") else None
        robots[id] = _record(
            "gold_h4", DISPLAY[key], book=book if diagnostic else None,
            capital=GOLD_CAPITAL, status=diagnostic.get("status") if diagnostic else None,
            reason=diagnostic.get("explanation") if diagnostic else errors.get("h4"),
            observed_close=h4_close, now=now, entries_exact=False)
    for key, (_, name) in LEV_CONFIG.items():
        id = "leveraged_h4:" + key
        diagnostic = h4_items.get(key)
        book = leveraged.get("books", {}).get(key) if leveraged and leveraged.get("paper_only") else None
        robots[id] = _record(
            "leveraged_h4", name, book=book if diagnostic else None,
            capital=LEV_CAPITAL, status=diagnostic.get("status") if diagnostic else None,
            reason=diagnostic.get("explanation") if diagnostic else errors.get("h4"),
            observed_close=h4_close, now=now, entries_exact=False)

    # Each H1 book has its own equity and diagnostic; a missing market must not
    # be misrepresented as an unprofitable (zero-return) strategy.
    h1_books = h1_state.get("books", {}) if h1_state and h1_state.get("paper_only") else {}
    missing_markets = set(h1_state.get("unavailable", [])) if h1_state else set()
    watermarks = h1_state.get("watermarks", {}) if h1_state else {}
    for market in MARKETS:
        close_ts = watermarks.get(market)
        close_ts = close_ts + 3600 if isinstance(close_ts, (int,float)) else None
        for strategy, label in H1_STRATEGIES.items():
            key = bot_key(market, strategy)
            b = h1_books.get(key) if market not in missing_markets else None
            reason = b.get("last_reason", "") if b else errors.get("h1", "Mercado sem dados/estado H1")
            status = None
            if b:
                if b.get("position"):
                    status = "in_position"
                elif "lacuna" in reason.lower():
                    status = "data_gap"
                elif "proteção após saída" in reason.lower():
                    status = "cooldown"
                elif "inválid" in reason.lower() or "bloqueado" in reason.lower():
                    status = "blocked"
                else:
                    status = "no_new_signal"
            robots["experimental_h1:"+key] = _record(
                "experimental_h1", f"{market} {label}", book=b,
                capital=H1_CAPITAL, status=status, reason=reason,
                observed_close=close_ts, now=now, entries_exact=True)

    # M15 stored state does not have a complete entries journal. Entry counts
    # from closures/open position are a lower bound, never "total entries".
    m15_close = None
    if mtf_state and isinstance(mtf_state.get("watermark_m15"), (int,float)):
        m15_close = mtf_state["watermark_m15"] + 900
    m15_status = None
    m15_reason = mtf_state.get("last_reason", "") if mtf_state else errors.get("mtf")
    if mtf_state:
        if mtf_state.get("position"):
            m15_status = "in_position"
        elif "lacuna" in str(m15_reason).lower():
            m15_status = "data_gap"
        elif mtf_state.get("equity", 0) <= 0:
            m15_status = "blocked"
        else:
            m15_status = "no_new_signal"
    robots["usdcad_m15:bb20"] = _record(
        "usdcad_m15", "USD/CAD BB20 H1/M15",
        book=mtf_state if mtf_state and mtf_state.get("paper_only") else None,
        capital=M15_CAPITAL, status=m15_status, reason=m15_reason,
        observed_close=m15_close, now=now, entries_exact=False)

    momentum_close = None
    if momentum_state and isinstance(momentum_state.get("h4_watermark"), (int,float)):
        momentum_close = momentum_state["h4_watermark"]+14400
    mom_book = (momentum_state if momentum_state and momentum_state.get("paper_only")
                and momentum_state.get("experimental_only") else None)
    mom_status = None
    if mom_book:
        mom_status = "in_position" if mom_book.get("position") else "no_new_signal"
    robots["momentum60_h4:momentum60"] = _record(
        "momentum60_h4", "Momentum 60 H4 (não validado)",
        book=mom_book, capital=MOMENTUM_CAPITAL, status=mom_status,
        reason="Acompanhamento prospectivo" if mom_book else errors.get("momentum60"),
        observed_close=momentum_close, now=now, entries_exact=True)

    counts = Counter(x["status"] for x in robots.values())
    by_group = Counter(x["group"] for x in robots.values())
    if len(robots) != TOTAL or dict(by_group) != GROUP_SIZES:
        raise AssertionError("27 expected distinct bots with exact group sizes")
    available = sum(x["metrics_available"] for x in robots.values())
    return {
        "schema": 1, "as_of_utc": datetime.fromtimestamp(now,timezone.utc).isoformat(),
        "paper_only": True, "read_only": True,
        "planned_robots": TOTAL, "with_observed_state": available,
        "missing_or_invalid": TOTAL-available,
        "configured_groups": GROUP_SIZES.copy(),
        "status_counts": dict(counts), "robots": robots,
        "claims": "No real orders, no verified brokerage profit, missing data != zero P&L",
        "validated_for_real_money": False,
    }


def telegram_line(result):
    """One short daily-only line; never an event or entry/exit alert."""
    if result["planned_robots"] != TOTAL:
        raise ValueError("Incorrect configured robot count")
    statuses = result["status_counts"]
    opened = statuses.get("in_position", 0)
    awaiting = statuses.get("no_new_signal", 0) + statuses.get("persistent_signal", 0)
    blocked = (statuses.get("blocked",0) + statuses.get("frozen_drawdown",0)
               + statuses.get("daily_loss_limit",0) + statuses.get("invalid_equity",0))
    candidate = statuses.get("candidate_next_bar",0)
    gap = statuses.get("data_gap",0)+statuses.get("data_stale",0)
    return (f"🩺 27 previstos: {result['with_observed_state']} com estado, "
            f"{opened} abertos, {candidate} pré-sinais, {awaiting} sem setup, "
            f"{blocked} bloqueados, {gap} dados antigos/lacunas, "
            f"{result['missing_or_invalid']} indisponíveis")
