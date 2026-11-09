"""Four independent, spot-long-only BTC/ETH H1 virtual research bots.

No exchange authentication, broker orders, retroactive initialization, margin,
short selling, or profit claims. Next-candle-open prices and stops are
HYPOTHETICAL paper fills, never exchange execution confirmations.
"""
from __future__ import annotations
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from src.market_quality import validate_bars
from src.strategies import make_indicators

FILE = Path("state/crypto_paper_v1.json")
SYMBOLS = ("BTCUSDT", "ETHUSDT")
STRATEGIES = ("ema_pullback", "channel20")
INTERVAL = 3600
CAPITAL = 1000.0
RISK = 0.005
FEE = 0.001
SLIPPAGE = 0.0005
STOP_ATR = 1.5
TRAIL_ATR = 2.0
MAX_HOLD = 72
WARMUP = 240
MAX_AGE = 7200
TZ = ZoneInfo("America/Sao_Paulo")
PROVIDERS = ("https://data-api.binance.vision", "https://api.binance.com")


def parse_klines(payload, now):
    """Binance's last, still-forming hourly kline must never enter research."""
    if not isinstance(payload, list):
        raise ValueError("formato de candle Binance invalido")
    data = []
    for candle in payload:
        if not isinstance(candle, list) or len(candle) < 7:
            raise ValueError("linha de kline invalida")
        ts = int(candle[0])
        close_ms = int(candle[6])
        if close_ms >= now * 1000 - 120000:
            continue
        o, h, l, c = [float(v) for v in candle[1:5]]
        data.append({"time": ts // 1000, "open": o, "high": h,
                     "low": l, "close": c})
    validate_bars(data, now=now, interval=INTERVAL,
                  min_bars=WARMUP + 2, max_age=MAX_AGE, continuous=True)
    return data


def fetch_klines(symbol, now=None, opener=None):
    if symbol not in SYMBOLS:
        raise ValueError("par nao aprovado")
    now = int(time.time() if now is None else now)
    opener = opener or urllib.request.urlopen
    errors = []
    for host in PROVIDERS:
        url = host + "/api/v3/klines?symbol=" + symbol + "&interval=1h&limit=500"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "NexusQuantPaper/1.0"})
            with opener(req, timeout=20) as res:
                return parse_klines(json.load(res), now)
        except Exception as err:
            errors.append(type(err).__name__)
    raise RuntimeError("%s: Binance indisponivel/invalidada (%s)" %
                       (symbol, ",".join(errors)))


def book():
    return {"equity": CAPITAL, "position": None, "closed": [],
            "entries": 0, "last_reason": "Inicializado sem operacoes retroativas"}


def fresh():
    return {"schema": 1, "paper_only": True, "spot_only": True,
            "source": "Binance SPOT USDT H1; indicative paper fills",
            "watermarks": {}, "books": {}, "unavailable": []}


def key(symbol, strategy):
    return symbol + ":" + strategy


def signal(strategy, bars, ind, i):
    if i < WARMUP:
        return False
    x = ind[i]
    if x["e50"] <= x["e200"] or bars[i]["close"] <= x["e50"]:
        return False
    if strategy == "ema_pullback":
        return (bars[i-1]["close"] <= ind[i-1]["e20"]
                and bars[i]["close"] > x["e20"] and 45 <= x["rsi"] <= 75)
    if strategy == "channel20":
        return (bars[i]["close"] > max(b["high"] for b in bars[i-20:i])
                and x["rsi"] < 85)
    raise KeyError(strategy)


def signal_block_reason(strategy, bars, ind, i):
    """Explicação somente diagnóstica. Não altera a regra de entrada."""
    if i < WARMUP:
        return "Histórico H1 insuficiente"
    x = ind[i]
    if x["e50"] <= x["e200"]:
        return "Tendência H1 sem alta: EMA50 <= EMA200"
    if bars[i]["close"] <= x["e50"]:
        return "Fechamento H1 abaixo da EMA50"
    if strategy == "ema_pullback":
        if bars[i-1]["close"] > ind[i-1]["e20"]:
            return "Sem toque/retorno à EMA20"
        if bars[i]["close"] <= x["e20"]:
            return "Sem recuperação da EMA20"
        if not 45 <= x["rsi"] <= 75:
            return "RSI fora da faixa 45-75"
        return "Sem setup H1 confirmado"
    if strategy == "channel20":
        if bars[i]["close"] <= max(b["high"] for b in bars[i-20:i]):
            return "Sem rompimento do canal de 20 candles"
        if x["rsi"] >= 85:
            return "RSI >= 85; entrada bloqueada"
        return "Sem setup H1 confirmado"
    return "Estratégia desconhecida"


def close_position(b, candle, fill, why):
    p = b["position"]
    sell_price = fill * (1 - SLIPPAGE)
    net = (sell_price - p["entry"]) * p["qty"]
    fees = FEE * p["qty"] * (sell_price + p["entry"])
    exit_slip_cost = (fill - sell_price) * p["qty"]
    pnl = net - fees
    b["equity"] += pnl
    b["closed"].append({"entry_ts": p["start"], "exit_ts": candle["time"],
                        "entry": round(p["entry"], 6),
                        "exit": round(sell_price, 6), "qty": round(p["qty"], 8),
                        "cost_usdt": round(fees + p["slip_cost"] + exit_slip_cost, 4),
                        "net_usd": round(pnl, 4), "exit_type": why})
    b["position"] = None
    b["last_reason"] = "Saida virtual " + why


def step(b, strategy, bars, ind, i):
    candle = bars[i]
    p = b["position"]
    if p is not None:
        p["held"] += 1
        if candle["low"] <= p["stop"]:
            # At an opening gap, the stop fills at the worse price.
            close_position(b, candle, min(candle["open"], p["stop"]), "STOP")
            return
        if p["held"] >= MAX_HOLD or candle["close"] < ind[i]["e50"]:
            close_position(b, candle, candle["close"], "TIME/TREND")
            return
        # Trailing based on COMPLETED close, effective from NEXT candle.
        p["best_close"] = max(p["best_close"], candle["close"])
        if p["best_close"] - p["entry"] >= p["initial_r"]:
            p["stop"] = max(p["stop"], p["best_close"] - TRAIL_ATR * ind[i]["atr"])
        return
    if not signal(strategy, bars, ind, i-1):
        b["last_reason"] = signal_block_reason(strategy, bars, ind, i-1)
        return
    open_price = candle["open"]
    entry = open_price * (1 + SLIPPAGE)
    distance = STOP_ATR * ind[i-1]["atr"]
    if distance <= 0 or b["equity"] <= 0:
        return
    stop = max(0.00000001, open_price - distance)
    initial_r = entry - stop
    qty = min(b["equity"] * RISK / initial_r,
              b["equity"] / (entry * (1 + FEE)))
    if qty <= 0:
        return
    b["position"] = {"entry": entry, "start": candle["time"], "qty": qty,
                     "stop": stop, "initial_r": initial_r,
                     "best_close": entry, "held": 0,
                     "slip_cost": (entry - open_price) * qty}
    b["entries"] += 1
    b["last_reason"] = "Entrada virtual COMPRA (sem ordem)"


def update(state, datasets):
    state = state if state is not None else fresh()
    if state.get("schema") != 1 or not state.get("paper_only") or not state.get("spot_only"):
        raise ValueError("estado cripto incompativel")
    state["unavailable"] = [s for s in SYMBOLS if s not in datasets]
    for symbol, bars in datasets.items():
        if symbol not in SYMBOLS:
            raise ValueError("simbolo nao aprovado")
        stamps = [row["time"] for row in bars]
        if len(stamps) < WARMUP + 2 or stamps != sorted(set(stamps)):
            raise ValueError("historico cripto invalido")
        if symbol not in state["watermarks"]:
            state["watermarks"][symbol] = stamps[-1]
            for strat in STRATEGIES:
                state["books"][key(symbol, strat)] = book()
            continue
        watermark = state["watermarks"][symbol]
        if watermark > stamps[-1]:
            continue
        if watermark not in stamps:
            raise ValueError("watermark perdido: %s; sem backfill automatico" % symbol)
        ind = make_indicators(bars)
        for i in range(stamps.index(watermark)+1, len(bars)):
            if i <= WARMUP:
                continue
            for strat in STRATEGIES:
                step(state["books"][key(symbol, strat)], strat, bars, ind, i)
            state["watermarks"][symbol] = stamps[i]
    return state


def process(datasets, path=FILE):
    path = Path(path)
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    state = update(state, datasets)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return state


def local_day(ts):
    return datetime.fromtimestamp(ts, timezone.utc).astimezone(TZ).date().isoformat()


def digest(state, day):
    """Resumo HTML compacto: apenas valores observados, sem operações inventadas."""
    from html import escape
    display_day = datetime.strptime(day, "%Y-%m-%d").strftime("%d/%m/%Y")
    books = state.get("books", {})
    unavailable = set(state.get("unavailable", []))
    inspected = [books[key(s, strategy)] for s in SYMBOLS for strategy in STRATEGIES
                 if key(s, strategy) in books]
    closed_today = [t for book in inspected for t in book.get("closed", [])
                    if local_day(t["exit_ts"]) == day]
    pnl_today = sum(float(t["net_usd"]) for t in closed_today)
    total_pnl = sum(float(book["equity"]) - CAPITAL for book in inspected)
    entries = sum(int(book.get("entries", 0)) for book in inspected)
    open_count = sum(book.get("position") is not None for book in inspected)
    wins = sum(sum(t["net_usd"] > 0 for t in book.get("closed", [])) for book in inspected)
    losses = sum(sum(t["net_usd"] < 0 for t in book.get("closed", [])) for book in inspected)
    partial = bool(unavailable)
    lines = [
        "<b>🪙 NEXUS CRIPTO | " + display_day + "</b>",
        "<i>4 robôs H1 • BTC/ETH SPOT • SOMENTE SIMULACAO</i>",
        "",
        "<b>📊 RESUMO</b>",
        f"Hoje: <b>USDT {pnl_today:+.2f}</b> · Acumulado: <b>USDT {total_pnl:+.2f}</b>",
        f"Entradas acumuladas: {entries} · Fechamentos hoje: {len(closed_today)}",
        f"Vitórias/derrotas: {wins}/{losses} · Posições abertas: {open_count}",
    ]
    if partial:
        lines.append("⚠️ Resultado com dados parciais: " + escape(", ".join(sorted(unavailable))))
    labels = {"ema_pullback": "Retorno à EMA20", "channel20": "Rompimento Canal 20"}
    for symbol in SYMBOLS:
        lines.extend(["", "<b>" + escape(symbol.replace("USDT", "/USDT")) + "</b>"])
        if symbol in unavailable or symbol not in state.get("watermarks", {}):
            lines.append("⚠️ Dados indisponíveis; posições e P&L não atualizados.")
            continue
        stamp = state["watermarks"][symbol]
        if isinstance(stamp, int) and stamp > 0:
            observed = datetime.fromtimestamp(stamp, timezone.utc).astimezone(TZ)
            lines.append("<i>Última vela H1: " + observed.strftime("%d/%m %H:%M") + " BRT</i>")
        blockers = []
        for strat in STRATEGIES:
            b = books.get(key(symbol, strat))
            if not isinstance(b, dict):
                lines.append("⚠️ " + escape(labels.get(strat, strat)) + ": estado indisponível.")
                continue
            closed = b.get("closed", [])
            today = sum(t["net_usd"] for t in closed if local_day(t["exit_ts"]) == day)
            acc = float(b["equity"]) - CAPITAL
            position = "aberta" if b.get("position") else "livre"
            lines.append(
                "• <b>" + escape(labels.get(strat, strat)) + "</b>: "
                + f"hoje {today:+.2f} · total {acc:+.2f} USDT · {position}"
            )
            if not b.get("position"):
                reason = str(b.get("last_reason", "")).strip()
                if reason and reason not in blockers:
                    blockers.append(reason)
        if blockers and all(not books.get(key(symbol, s), {}).get("position") for s in STRATEGIES):
            summary = "; ".join(blockers[:2])
            lines.append("<i>Sem sinal: " + escape(summary[:175]) + "</i>")
    lines.extend([
        "",
        "<i>Risco planejado 0,5%/entrada, sem alavancagem. P&L virtual após custos estimados.</i>",
        "<i>Nenhuma ordem enviada à Binance ou FBS; não há lucro garantido.</i>",
    ])
    message = "\n".join(lines)
    if len(message) > 4096:
        raise ValueError("Resumo cripto excedeu limite Telegram")
    return message
