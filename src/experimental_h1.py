"""15 independent experimental H1 paper books across five public proxy markets.

No brokerage connection, no historical backfill, no guaranteed fills or profits.
These rules are UNVALIDATED; results must not be combined with approved bots.
"""
from __future__ import annotations
from copy import deepcopy
import json
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from zoneinfo import ZoneInfo
from src.feed import MARKETS
from src.strategies import make_indicators
from research.backtest_year import COST_BPS
from src.news_guard import entry_permission

FILE = Path("state/experimental_h1_v1.json")
STRATEGIES = {
    "ema20_retest": "EMA20 Retest H1",
    "channel10": "Channel 10 H1",
    "rsi50": "RSI50 Trend H1",
}
CAPITAL = 1000.0
RISK_FRACTION = 0.0025
NOTIONAL_CAP = 1.0
STOP_ATR = 1.5
TRAIL_ATR = 1.5
MAX_HOLD = 36
WARMUP = 75
TZ = ZoneInfo("America/Sao_Paulo")


def local_day(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).astimezone(TZ).date().isoformat()


def bot_key(market, strategy):
    return f"{market}:{strategy}"


def book():
    return {"equity": CAPITAL, "position": None, "closed": [], "entries": [],
            "last_reason": "Iniciado sem operações retroativas",
            "diagnostics": {"no_setup": 0, "gap": 0, "cooldown": 0, "in_position": 0,
                            "entered": 0, "exited": 0, "invalid": 0},
            "last_exit_ts": None}


def fresh():
    return {"schema": 1, "paper_only": True, "experimental_only": True,
            "source": "Yahoo indicative H1, not FBS",
            "watermarks": {}, "books": {}, "unavailable": []}


def setup(strategy, bars, ind, i):
    """Completed bar signal only. Evaluated at i-1 before entry at i open."""
    if i < WARMUP:
        return 0
    p = ind[i]
    q = ind[i - 1]
    b = bars[i]
    bull = p["e20"] > p["e50"] and b["close"] > p["e50"]
    bear = p["e20"] < p["e50"] and b["close"] < p["e50"]
    if strategy == "ema20_retest":
        if bull and b["low"] <= p["e20"] and b["close"] > p["e20"] and b["close"] > b["open"] and 45 <= p["rsi"] <= 75:
            return 1
        if bear and b["high"] >= p["e20"] and b["close"] < p["e20"] and b["close"] < b["open"] and 25 <= p["rsi"] <= 55:
            return -1
    elif strategy == "channel10":
        upper = max(x["high"] for x in bars[i - 10:i])
        lower = min(x["low"] for x in bars[i - 10:i])
        if bull and b["close"] > upper and p["rsi"] >= 52:
            return 1
        if bear and b["close"] < lower and p["rsi"] <= 48:
            return -1
    elif strategy == "rsi50":
        if bull and q["rsi"] <= 50 < p["rsi"]:
            return 1
        if bear and q["rsi"] >= 50 > p["rsi"]:
            return -1
    else:
        raise KeyError(strategy)
    return 0


def _close(b, market, bar, price, why):
    p = b["position"]
    gross_quote = (price - p["entry"]) * p["side"] * p["qty"]
    cost_quote = COST_BPS[market] / 10000 * p["qty"] * (p["entry"] + price) / 2
    # USDJPY is quoted JPY per USD: convert JPY P&L/fees into USD at exit.
    conversion = price if market == "USDJPY" else 1.0
    gross = gross_quote / conversion
    cost = cost_quote / conversion
    net = gross - cost
    b["equity"] += net
    b["closed"].append({"entry_ts": p["start"], "exit_ts": bar["time"],
                        "side": p["side"], "entry": round(p["entry"], 7),
                        "exit": round(price, 7), "net_usd": round(net, 5),
                        "cost_usd": round(cost, 5), "exit_type": why})
    b["last_exit_ts"] = bar["time"]
    b["last_reason"] = f"Saída {why}: US$ {net:+.2f} com custos estimados"
    b["diagnostics"]["exited"] += 1
    b["position"] = None


def step(b, market, strategy, bars, ind, i, *, signal_fn=None, allow_new_entry=True):
    """Stop checks before trailing; execute entry-bar stops, never re-enter."""
    row = bars[i]
    previous = bars[i - 1]
    p = b["position"]
    if p is not None:
        b["diagnostics"]["in_position"] += 1
        p["held_bars"] += 1
        side = p["side"]
        hit = row["low"] <= p["stop"] if side > 0 else row["high"] >= p["stop"]
        if hit:
            fill = min(row["open"], p["stop"]) if side > 0 else max(row["open"], p["stop"])
            _close(b, market, row, fill, "STOP")
            return
        if p["held_bars"] >= MAX_HOLD:
            _close(b, market, row, row["close"], "TIME")
            return
        # This closing-price trailing level is effective NEXT candle only.
        favorable = max(p["best_close"], row["close"]) if side > 0 else min(p["best_close"], row["close"])
        p["best_close"] = favorable
        if side * (favorable - p["entry"]) >= p["initial_r"]:
            new_stop = favorable - side * TRAIL_ATR * ind[i]["atr"]
            tightened = max(p["stop"], new_stop) if side > 0 else min(p["stop"], new_stop)
            if tightened != p["stop"]:
                p["stop"] = tightened
                p["stop_updates"] += 1
        b["last_reason"] = "Posição virtual aberta; stop acompanhado"
        return

    if not allow_new_entry:
        b["last_reason"] = "Reconciliação somente saídas virtuais; nenhuma entrada retroativa"
        return

    # No new entry across a holiday/weekend or incomplete hourly interval.
    if row["time"] - previous["time"] != 3600:
        b["diagnostics"]["gap"] += 1
        b["last_reason"] = "Sem entrada: lacuna entre candles"
        return
    if b["last_exit_ts"] is not None and row["time"] - b["last_exit_ts"] < 2 * 3600:
        b["diagnostics"]["cooldown"] += 1
        b["last_reason"] = "Sem entrada: proteção após saída"
        return
    side = (setup if signal_fn is None else signal_fn)(strategy, bars, ind, i - 1)
    if not side:
        b["diagnostics"]["no_setup"] += 1
        b["last_reason"] = "Aguardando setup H1 com candle fechado"
        return
    if not entry_permission(market,row["time"]):
        b["last_reason"] = "Sem entrada: calendário de notícias oficial indisponível ou evento de alto impacto"
        return
    price, atr = row["open"], ind[i - 1]["atr"]
    if not isfinite(atr) or atr <= 0 or price <= 0 or b["equity"] <= 0:
        b["diagnostics"]["invalid"] += 1
        b["last_reason"] = "Bloqueado: risco/preço inválido"
        return
    stop_dist = STOP_ATR * atr
    # USDJPY base size is USD units; all other reference prices are USD-quoted.
    quote_conversion = price if market == "USDJPY" else 1.0
    qty_risk = b["equity"] * RISK_FRACTION * quote_conversion / stop_dist
    qty_cap = b["equity"] * NOTIONAL_CAP / (1.0 if market == "USDJPY" else price)
    qty = min(qty_risk, qty_cap)
    if qty <= 0 or not isfinite(qty):
        b["diagnostics"]["invalid"] += 1
        return
    b["position"] = {"side": side, "entry": price, "start": row["time"],
                     "qty": qty, "stop": price - side * stop_dist,
                     "initial_r": stop_dist, "best_close": price, "stop_updates": 0,
                     "held_bars": 0}
    b["entries"].append({"entry_ts": row["time"], "side": side, "entry": price,
                         "reason": strategy, "risk_fraction": RISK_FRACTION})
    b["diagnostics"]["entered"] += 1
    b["last_reason"] = "Entrada experimental COMPRA" if side > 0 else "Entrada experimental VENDA"
    # Entry at this candle's open uses only previous completed OHLC.
    # No claim of actual executable brokerage fills.


def reconcile_subhour_watermark(state,market,stamps,mark):
    """Guarded one-time reconciliation of a malformed intra-hour paper mark.

    A noncanonical timestamp can be normalized only when the observed
    signal journal independently proves the previous exact H1 candle has
    already been consumed. This does NOT assert any broker fills.
    """
    if (market not in MARKETS or not isinstance(mark,int) or
            mark%3600==0 or not stamps or mark>stamps[-1]):
        raise ValueError("watermark not eligible for automatic reconciliation")
    anchor=mark-(mark%3600)
    if anchor not in stamps:
        raise ValueError("anchor candle absent: remain quarantined")
    books=[state["books"].get(bot_key(market,s)) for s in STRATEGIES]
    if not all(isinstance(b,dict) for b in books):
        raise ValueError("Incomplete market journal: remain quarantined")
    events=[]
    for b in books:
        for e in b.get("entries",[]):
            events.append(e.get("entry_ts"))
        for e in b.get("closed",[]):
            events.extend((e.get("entry_ts"),e.get("exit_ts")))
        p=b.get("position")
        if p is not None:
            events.append(p.get("start"))
        if b.get("last_exit_ts") is not None:
            events.append(b["last_exit_ts"])
    if (not events or any(not isinstance(ts,(int,float)) or
                          not isfinite(ts) for ts in events) or
            any(ts>anchor for ts in events) or anchor not in events):
        raise ValueError("No anchored evidence of consumed H1 candle")
    return anchor


def update(state, datasets, *, isolate_errors=False):
    """Advance independent H1 markets without sacrificing other books.

    Strict/default API retains old validation errors for tests and research.
    The scheduled paper runner opts in to market-isolation: invalid WTI
    timestamps quarantine WTI ONLY; no backfill/rewind/cancel of its position.
    """
    state = state if state is not None else fresh()
    if state.get("schema") != 1 or not state.get("paper_only") or not state.get("experimental_only"):
        raise ValueError("Estado H1 experimental incompatível; preservar histórico")
    state["unavailable"] = [m for m in MARKETS if m not in datasets]
    if isolate_errors:
        state.pop("market_errors", None)
    for market in MARKETS:
        if market not in datasets:
            continue
        # Snapshot this market only; on failure restore ALL its original
        # positions, closed trades, equity and watermark, even if some
        # earlier candles in this batch were processed before failing.
        prior_stamp = state["watermarks"].get(market)
        prior_repairs = deepcopy(state.get("watermark_repairs")) if isolate_errors else None
        prior_books = ({bot_key(market,s): deepcopy(state["books"].get(bot_key(market,s)))
                        for s in STRATEGIES} if isolate_errors else None)
        try:
            bars = datasets[market]
            stamps = [int(x["time"]) for x in bars]
            if len(bars) <= WARMUP + 2 or stamps != sorted(set(stamps)):
                raise ValueError(f"{market}: histórico H1 inválido")
            if market not in state["watermarks"]:
                state["watermarks"][market] = stamps[-1]
                for strat in STRATEGIES:
                    state["books"][bot_key(market, strat)] = book()
                continue  # prohibit retroactive fills on the first observation
            mark = state["watermarks"][market]
            if mark > stamps[-1]:
                if isolate_errors:
                    raise ValueError(f"{market}: preços atrasados em relação ao estado")
                continue  # old strict-mode behavior: never roll back
            repairing = False
            if mark not in stamps:
                if not isolate_errors:
                    raise ValueError(f"{market}: watermark perdido; não inventar entradas")
                anchor = reconcile_subhour_watermark(state,market,stamps,mark)
                repairing = True
                state.setdefault("watermark_repairs",[]).append({
                    "market":market,"from_ts":mark,"anchored_closed_bar_ts":anchor,
                    "warning":"Yahoo OHLC estimate only; old position exits reconciled retrospectively, no retroactive new trades",
                })
                mark = anchor
            ind = make_indicators(bars)
            start = stamps.index(mark) + 1
            for i in range(max(start, WARMUP + 1), len(bars)):
                for strat in STRATEGIES:
                    if repairing:
                        book_to_reconcile = state["books"][bot_key(market, strat)]
                        previous_closed = len(book_to_reconcile["closed"])
                        step(book_to_reconcile, market, strat, bars, ind, i,
                             allow_new_entry=False)
                        for trade in book_to_reconcile["closed"][previous_closed:]:
                            trade["reconciled_from_feed_gap"] = True
                    else:
                        step(state["books"][bot_key(market, strat)], market, strat, bars, ind, i)
                state["watermarks"][market] = stamps[i]
        except (ValueError, KeyError, TypeError, IndexError, ArithmeticError) as exc:
            if not isolate_errors:
                raise
            # Fail closed ONLY for the corrupted market. No fabricated exit
            # of an existing position, no automatic reset or stale price fill.
            if prior_stamp is None:
                state["watermarks"].pop(market,None)
            else:
                state["watermarks"][market] = prior_stamp
            for key, prior in prior_books.items():
                if prior is None:
                    state["books"].pop(key,None)
                else:
                    state["books"][key] = prior
            if prior_repairs is None:
                state.pop("watermark_repairs",None)
            else:
                state["watermark_repairs"] = prior_repairs
            state["unavailable"].append(market)
            state.setdefault("market_errors",{})[market] = (
                type(exc).__name__ + ": " + str(exc))[:180]
    return state


def process(datasets, path=FILE):
    path = Path(path)
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    result = update(state, datasets, isolate_errors=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def labels():
    return {bot_key(m, s): f"{m} {title}" for m in MARKETS for s, title in STRATEGIES.items()}


def digest(state, day):
    """Compact diagnostic for the existing daily message; books remain independent."""
    if state is None:
        return ["🧪 15 H1 experimentais: sem dados; não presumir resultado zero"]
    lines = ["", "🧪 15 EXPERIMENTAIS H1 | 5 mercados × 3 estratégias",
             "Risco planejado 0,25%/op.; até 1× nocional | NÃO VALIDADOS"]
    total_entries = total_closed = 0
    total_net = 0.0
    for market in MARKETS:
        items = [state["books"].get(bot_key(market, strat)) for strat in STRATEGIES]
        if any(b is None for b in items) or market in state.get("unavailable", []):
            lines.append(f"{market}: SEM DADOS FRESCOS / aguardando inicialização")
            continue
        entries = sum(sum(local_day(e["entry_ts"]) == day for e in b["entries"]) for b in items)
        exits = [t for b in items for t in b["closed"]
                 if local_day(t["exit_ts"]) == day and not t.get("reconciled_from_feed_gap")]
        opened = sum(b["position"] is not None for b in items)
        net = sum(t["net_usd"] for t in exits)
        total_entries += entries
        total_closed += len(exits)
        total_net += net
        lines.append(f"{market}: {entries} entradas | {len(exits)} saídas | {opened}/3 abertas | US$ {net:+.2f}")
    lines.append(f"Experimento hoje: {total_entries} entradas, {total_closed} saídas, US$ {total_net:+.2f} realizado virtual")
    lines.append("Sem setup ≠ erro; estratégias experimentais não são recomendação de operação.")
    return lines


def scorecard(b):
    """All records preserved; distinguish realized returns from open positions."""
    closed = b["closed"]
    gains = sum(t["net_usd"] for t in closed if t["net_usd"] > 0)
    losses = -sum(t["net_usd"] for t in closed if t["net_usd"] < 0)
    high = CAPITAL
    equity = CAPITAL
    dd = 0.0
    for trade in closed:
        equity += trade["net_usd"]
        high = max(high, equity)
        dd = max(dd, 100 * (high - equity) / high) if high else dd
    return {
        "entries": len(b["entries"]),
        "closed": len(closed),
        "open": b["position"] is not None,
        "wins": sum(t["net_usd"] > 0 for t in closed),
        "losses": sum(t["net_usd"] < 0 for t in closed),
        "net_usd": round(b["equity"] - CAPITAL, 5),
        "fees_usd": round(sum(t["cost_usd"] for t in closed), 5),
        "profit_factor": round(gains / losses, 3) if losses > 0 else None,
        "win_rate_pct": round(100 * sum(t["net_usd"] > 0 for t in closed) / len(closed), 2) if closed else None,
        "max_closed_drawdown_pct": round(dd, 3),
        "validated": False,  # requires prospective OOS tests; never infer from short history
        "sample_sufficient_for_review": len(closed) >= 30,
    }


def diagnostics(state):
    """Per-bot blockers and performance after estimated costs; no brokerage fills."""
    return {key: {"reason": b["last_reason"], "diagnostics": b["diagnostics"],
                  "scorecard": scorecard(b)} for key, b in state["books"].items()}
