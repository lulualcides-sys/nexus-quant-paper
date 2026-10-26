"""Five-market historical paper replay of the *same* H1/M15 Bollinger pullback.

Fixed markets and entry rules: EUR/USD, USD/JPY, GC=F, ES=F, CL=F.
Each independent 1,000-USD paper book; 30-day evaluation, 13-day warmup.
No brokerage quotes or orders. Futures use fractional notional for research
only; these are NOT actual contract-sized executable trades.
"""
from __future__ import annotations

import bisect
import hashlib
import json
import math
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlencode

from src import bb_rebound_mtf as bot
from src.strategies import make_indicators

OUT = Path("research/results")
DAYS = 30
WARMUP_DAYS = 13
# Round-trip friction in QUOTED PRICE UNITS. Hypothetical, not FBS.
MARKETS = {
    "EURUSD": {"name": "EUR/USD", "ticker": "EURUSD=X", "cost_price": 0.00015,
               "min_tick": 0.0001, "quote_currency": "USD", "kind": "FX indicative"},
    "USDJPY": {"name": "USD/JPY", "ticker": "JPY=X", "cost_price": 0.015,
               "min_tick": 0.01, "quote_currency": "JPY", "kind": "FX indicative"},
    "XAUUSD": {"name": "Ouro", "ticker": "GC=F", "cost_price": 0.8,
               "min_tick": 0.1, "quote_currency": "USD", "kind": "gold futures proxy"},
    "US500": {"name": "S&P 500", "ticker": "ES=F", "cost_price": 1.0,
               "min_tick": 0.25, "quote_currency": "USD", "kind": "E-mini futures proxy"},
    "XTIUSD": {"name": "WTI", "ticker": "CL=F", "cost_price": 0.08,
               "min_tick": 0.01, "quote_currency": "USD", "kind": "WTI futures proxy"},
}
BANK = 1000.0
RISK = 0.0075
MAX_NOTIONAL = 1.0


def utcstamp(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def fetch_one(name, config, now):
    endpoint = "/v8/finance/chart/" + quote(config["ticker"], safe="") + "?" + urlencode({
        "period1": now - (DAYS + WARMUP_DAYS) * 86400,
        "period2": now + 900,
        "interval": "15m",
    })
    problems = []
    for host in ("query1.finance.yahoo.com", "query2.finance.yahoo.com"):
        request = urllib.request.Request(
            "https://" + host + endpoint,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=24) as response:
                payload = json.load(response)
            bars = bot.parse_15m(payload, now=now)
            return bars, host
        except Exception as exc:
            problems.append(host + ": " + type(exc).__name__ + " " + str(exc)[:110])
    raise RuntimeError("Fonte pública indisponível: " + " | ".join(problems))


def convert_to_usd(config, quoted, exit_price):
    """Quoted P&L to USD; USDJPY must be converted from JPY, unlike EURUSD."""
    return quoted / exit_price if config["quote_currency"] == "JPY" else quoted


def close_if_stopped(book, bar, config):
    pos = book["position"]
    if not pos:
        return False
    side = pos["side"]
    stop = bar["low"] <= pos["stop"] if side == 1 else bar["high"] >= pos["stop"]
    if not stop:
        return False
    fill = min(bar["open"], pos["stop"]) if side == 1 else max(bar["open"], pos["stop"])
    gross_quote = (fill-pos["entry"])*side*pos["quantity_base"]
    costs_quote = config["cost_price"]*pos["quantity_base"]
    net = convert_to_usd(config, gross_quote-costs_quote, fill)
    book["equity"] += net
    book["closed"].append({
        "entry_ts":pos["entry_ts"],"exit_ts":bar["time"],"side":side,
        "entry":pos["entry"],"exit":fill,
        "pnl_usd":round(net,7),"costs_usd":round(convert_to_usd(config,costs_quote,fill),7),
        "exit_type":"TRAIL_STOP" if pos["updates"] else "INITIAL_STOP",
    })
    book["position"] = None
    return True


def trail_from_close(book, bar):
    """Old stop has ALREADY been tested on this M15; new stop is for NEXT bar."""
    pos = book["position"]
    if pos is None:
        return
    side = pos["side"]
    if side == 1:
        pos["best_close"] = max(pos["best_close"], bar["close"])
        new_stop = max(pos["stop"], pos["best_close"] - pos["risk_distance"])
        if new_stop > pos["stop"]:
            pos["stop"] = new_stop
            pos["updates"] += 1
    else:
        pos["best_close"] = min(pos["best_close"], bar["close"])
        new_stop = min(pos["stop"], pos["best_close"] + pos["risk_distance"])
        if new_stop < pos["stop"]:
            pos["stop"] = new_stop
            pos["updates"] += 1


def position_units(config, equity, entry, risk_distance):
    # Dollar-value of one quoted price unit for one underlying unit.
    dollar_per_quote = 1.0 / entry if config["quote_currency"] == "JPY" else 1.0
    risk_qty = equity*RISK/(risk_distance*dollar_per_quote)
    max_qty = equity*MAX_NOTIONAL/(entry*dollar_per_quote)
    return min(risk_qty, max_qty)


def replay(bars, config, now):
    start = now - DAYS*86400
    warm = [b for b in bars if b["time"] < start]
    observed = [b for b in bars if b["time"] >= start]
    if len(warm) < 240 or len(bot.to_h1(warm)) < 53:
        raise ValueError("Aquecimento H1 insuficiente: " + str(len(bot.to_h1(warm))) + " horas")
    if len(observed) < 500 or observed[0]["time"] > start + 4*86400:
        raise ValueError("Cobertura M15 insuficiente: " + str(len(observed)) + " candles")
    if observed[-1]["time"] < now - 3*86400:
        raise ValueError("Cotações defasadas mais de 3 dias")
    if any(bars[i]["time"] <= bars[i-1]["time"] for i in range(1,len(bars))):
        raise ValueError("Candles duplicados/não ordenados")
    h1 = bot.to_h1(bars)
    feat_h1 = make_indicators(h1)
    feat_m15 = make_indicators(bars)
    times = [r["time"] for r in bars]
    h1_completed = [r["time"]+3600 for r in h1]
    watermark = bisect.bisect_left(times, observed[0]["time"])
    book = {"equity":BANK, "position":None, "closed":[], "last_h1":None}
    for i in range(max(2,watermark),len(bars)):
        current, prev = bars[i], bars[i-1]
        contiguous = current["time"]-prev["time"] == 900 and prev["time"]-bars[i-2]["time"] == 900
        if book["position"] is not None:
            if not close_if_stopped(book,current,config):
                trail_from_close(book,current)
            continue
        if not contiguous or book["equity"] <= 0:
            continue
        j = bisect.bisect_right(h1_completed, prev["time"])-1
        if j < 55:
            continue
        if prev["time"] >= h1_completed[j]+3600:
            continue
        if h1[j]["time"] == book["last_h1"]:
            continue
        side = bot.h1_trend_confirmation(h1,feat_h1,j)
        if not side or not bot.m15_sma20_pullback(bars,feat_m15,i,side):
            continue
        entry = current["open"]
        distance = max(bot.STOP_ATR * feat_h1[j]["atr"], 6*config["min_tick"])
        if distance <= 0 or entry <= 0:
            continue
        qty = position_units(config,book["equity"],entry,distance)
        if not (math.isfinite(qty) and qty>0):
            continue
        book["position"] = {
            "side":side,"entry":entry,"entry_ts":current["time"],
            "quantity_base":qty,"risk_distance":distance,
            "stop":entry-side*distance,"best_close":entry,"updates":0,
        }
        book["last_h1"] = h1[j]["time"]
        if not close_if_stopped(book,current,config):
            trail_from_close(book,current)
    closed = book["closed"]
    wins = [x for x in closed if x["pnl_usd"]>0]
    losses = [x for x in closed if x["pnl_usd"]<0]
    gain = sum(x["pnl_usd"] for x in wins)
    loss = sum(x["pnl_usd"] for x in losses)
    position = book["position"]
    mark = None
    if position is not None:
        final_close = bars[-1]["close"]
        mark = convert_to_usd(config, (
            (final_close-position["entry"])*position["side"]-config["cost_price"]
        )*position["quantity_base"],final_close)
    equity,peak,drawdown = BANK,BANK,0.0
    for trade in closed:
        equity += trade["pnl_usd"]
        peak = max(peak,equity)
        drawdown = max(drawdown,100*(peak-equity)/peak)
    realized = book["equity"]-BANK
    return {
        "status":"ok","m15_warmup":len(warm),"h1_warmup":len(bot.to_h1(warm)),
        "m15_test":len(observed),"first_test":utcstamp(observed[0]["time"]),
        "last_test":utcstamp(observed[-1]["time"]),
        "closed_n":len(closed),"wins":len(wins),"losses":len(losses),
        "win_rate_pct":100*len(wins)/len(closed) if closed else None,
        "realized_pnl_usd":realized,"realized_return_pct":100*realized/BANK,
        "pnl_open_usd":mark,"pnl_including_open_usd":realized+(mark or 0),
        "max_realized_drawdown_pct":drawdown,
        "profit_factor":gain/(-loss) if loss<0 else None,
        "total_estimated_friction_usd":sum(x["costs_usd"] for x in closed),
        "best_trade_usd":max((x["pnl_usd"] for x in closed), default=None),
        "worst_trade_usd":min((x["pnl_usd"] for x in closed), default=None),
        "open_position":position, "exit_reasons":dict(Counter(x["exit_type"] for x in closed)),
        "closed_trades":closed,
    }


def verify_against_usdcad_frozen():
    """Control: the market-agnostic engine must reproduce deployed USD/CAD."""
    import gzip
    from pathlib import Path
    old = Path("research/results/bb20_usdcad_m15_1mo_2026-10-26_bars.json.gz")
    val = Path("research/results/bb20_m15_v3_engine_validation_2026-10-26.json")
    if not old.exists() or not val.exists():
        raise RuntimeError("Falta amostra-controle histórica USD/CAD")
    with gzip.open(old,"rt",encoding="utf-8") as f:
        rows=json.load(f)["candles"]
    prior=json.loads(val.read_text(encoding="utf-8"))
    now=int(datetime.strptime(prior["timestamp_utc"], "%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc).timestamp())
    config={"name":"USD/CAD","ticker":"CAD=X","cost_price":0.00015,
            "min_tick":0.0001,"quote_currency":"CAD"}
    # USD/CAD has CAD quotes and USD base. Match the previous bot's P&L conversion.
    config["quote_currency"]="JPY"  # conversion 1/close is structurally identical (CAD per USD).
    r=replay(rows,config,now)
    if r["closed_n"]!=prior["closed_n"] or abs(r["realized_pnl_usd"]-prior["realized_pnl_usd"])>0.03:
        raise AssertionError(
            "Replay differs from deployed engine: %s trades %.5f USD vs %s trades %.5f USD" %
            (r["closed_n"],r["realized_pnl_usd"],prior["closed_n"],prior["realized_pnl_usd"])
        )
    return {"trades":r["closed_n"],"pnl_usd":r["realized_pnl_usd"],
            "frozen_pnl_usd":prior["realized_pnl_usd"],
            "frozen_sha256":prior["source_sha256"]}


def save_report(results,now):
    OUT.mkdir(parents=True,exist_ok=True)
    path = OUT/"bb20_5_markets_2026-10-26.json"
    report = OUT/"bb20_5_markets_2026-10-26.md"
    path.write_text(json.dumps(results, indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    lines=[
        "# Nexus Quant — cinco gráficos H1/M15, mesma estratégia de pullback",
        "",
        "**Janela:** 30 dias até " + utcstamp(now),
        "**Regra:** EMA50/EMA200 e inclinação H1; toque/rejeição da SMA20 Bollinger no M15;",
        "entrada na abertura M15 seguinte, risco planejado 0,75%, nocional 1×,",
        "trailing stop 1R com fechamentos M15, sem alvo fixo.",
        "",
        "Mercados pré-escolhidos: EUR/USD, USD/JPY, GC=F, ES=F, CL=F.",
        "Cada gráfico possui banca INDEPENDENTE de US$ 1.000 virtuais.",
        "",
        "| Gráfico | Status | Fechadas | Greens/Reds | Acerto | P&L realizado USD | P&L incluindo aberta USD |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for key,config in MARKETS.items():
        r=results["markets"][key]
        if r["status"]!="ok":
            lines.append("| %s | SEM DADOS: %s | — | — | — | — | — |" % (
                config["name"],r["error"].replace("|",";")[:100]))
            continue
        hit="—" if r["win_rate_pct"] is None else "%.1f%%" % r["win_rate_pct"]
        lines.append("| %s | testado | %s | %s/%s | %s | %+.2f | %+.2f |" % (
            config["name"],r["closed_n"],r["wins"],r["losses"],hit,
            r["realized_pnl_usd"],r["pnl_including_open_usd"]))
    lines.extend(["",
        "## Integridade e limites",
        "- Preços OHLC públicos (Yahoo Finance) não equivalem a spreads/preços executáveis FBS.",
        "- EUR/USD cotado em USD; USD/JPY converte P&L de JPY para USD.",
        "- Futuros são simulados com quantidades FRACIONÁRIAS equivalentes a US$ 1.000,",
        "  mesmo quando o contrato real não permite essa exposição; logo NÃO são resultados",
        "  de negociação executável nem projeção de lucro de corretora.",
        "- Custos round-trip de referência, apenas hipóteses: EUR/USD 1,5 pip; USD/JPY 1,5 pip;",
        "  GC=F $0,80 por onça; ES=F 1 ponto; CL=F $0,08 por barril.",
        "- Sem look-ahead: fecha o M15, usa H1 completo, simula entrada na abertura seguinte;",
        "  testa stop antigo antes de mover o trailing para o candle seguinte.",
        "- Nenhuma estratégia foi otimizada separadamente por mercado nesta comparação.",
        "- Janela de 30 dias foi utilizada devido ao limite de acesso M15, não são 5 meses.",
        "- Mesmo que positivo, resultado é histórico e insuficiente para comprovar lucratividade.",
        "- Se indisponível, manter a condição 'sem dados'; não preencher com zeros.",
        "",
        "## Controle de equivalência USD/CAD",
        json.dumps(results.get("control_usdcad"),ensure_ascii=False),
        "",
    ])
    report.write_text("\n".join(lines),encoding="utf-8")
    print("FINAL_RESULTS=" + json.dumps({
        k:{item:v.get(item) for item in ("status","closed_n","wins","losses","win_rate_pct","realized_pnl_usd","pnl_including_open_usd","error")}
        for k,v in results["markets"].items()
    },ensure_ascii=False))
    print("REPORT=" + str(report))


def main():
    now=int(time.time())
    results={
        "created_utc":utcstamp(now),
        "requested_days":DAYS,
        "warmup_days":WARMUP_DAYS,
        "paper_only":True,
        "initial_bank_per_market_usd":BANK,
        "strategy_version":"bb20_m15_sma20_touch_h1_ema50_trend_v3",
        "trailing":"1R of best closed M15, no TP; same candle stop first",
        "markets":{},
        "caveats":["No verified FBS fills, spreads, or execution; costs estimated",
                   "Fractional continuous future equivalents are non-executable at this notional",
                   "This is a retrospective comparison, not proof of future edge"],
    }
    try:
        results["control_usdcad"]=verify_against_usdcad_frozen()
    except Exception as exc:
        raise RuntimeError("ABORT: USD/CAD golden control failed: "+str(exc)) from exc
    for key,config in MARKETS.items():
        try:
            bars,host=fetch_one(key,config,now)
            r=replay(bars,config,now)
            r["source"]="Yahoo Finance "+config["ticker"]+" via "+host
            r["ticker"]=config["ticker"]
            r["quoted_cost_roundtrip"]=config["cost_price"]
            r["quote_currency"]=config["quote_currency"]
            r["price_sha256"]=hashlib.sha256(
                json.dumps(bars,sort_keys=True,separators=(",",":")).encode("utf-8")
            ).hexdigest()
            results["markets"][key]=r
            print("MARKET_OK="+json.dumps({
                "market":key,"trades":r["closed_n"],
                "win_rate":r["win_rate_pct"],"net_usd":round(r["realized_pnl_usd"],4),
                "test_candles":r["m15_test"]},ensure_ascii=False))
        except Exception as exc:
            results["markets"][key]={"status":"unavailable","error":type(exc).__name__+": "+str(exc)[:380]}
            print("MARKET_UNAVAILABLE="+json.dumps({"market":key,"reason":str(exc)[:250]},ensure_ascii=False))
    save_report(results,now)
    available=sum(r["status"]=="ok" for r in results["markets"].values())
    print("COVERAGE=%s/5" % available)
    if available == 0:
        raise RuntimeError("Nenhum dos 5 mercados tinha dados verificáveis; relatório indica indisponibilidade")


if __name__=="__main__":
    main()
