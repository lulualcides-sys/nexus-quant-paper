"""Historical 30-day USD/CAD BB20 M15 replay using the identical forward engine.

First 13 days are warmup; last 30 days are evaluated. Never use FBS fills.
"""
import gzip
import hashlib
import json
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from src.bb_rebound_mtf import CAPITAL, PIP, ROUNDTRIP_PIPS, parse_15m, to_h1, update

OUT = Path("research/results")
WINDOW_DAYS = 30
HISTORY_DAYS = 43


def stamp(n):
    return datetime.fromtimestamp(n, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def fetch_history(now):
    p1 = now - HISTORY_DAYS * 86400
    path = "/v8/finance/chart/CAD%3DX?" + urlencode({
        "period1": p1, "period2": now + 900, "interval": "15m"
    })
    problems = []
    for host in ("query1.finance.yahoo.com", "query2.finance.yahoo.com"):
        req = urllib.request.Request("https://" + host + path, headers={
            "User-Agent": "Mozilla/5.0", "Accept": "application/json"
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                rows = parse_15m(json.load(response), now=now)
            return rows, host
        except Exception as error:
            problems.append(host + ": " + type(error).__name__ + ": " + str(error)[:100])
    raise RuntimeError("Backtest indisponível, sem preços M15 verificados: " + " | ".join(problems))


def analyze(bars, now, source):
    start = now - WINDOW_DAYS * 86400
    warm = [b for b in bars if b["time"] < start]
    test = [b for b in bars if b["time"] >= start]
    if len(warm) < 240 or len(to_h1(warm)) < 53:
        raise ValueError("Aquecimento H1 incompleto, sem inventar série")
    if len(test) < 600 or test[0]["time"] > start + 4*86400:
        raise ValueError("Janela de 30 dias sem cobertura M15 suficiente")
    if test[-1]["time"] < now - 2*86400:
        raise ValueError("Dados do Yahoo estão atrasados mais de 48 horas")
    if any(bars[k]["time"] <= bars[k-1]["time"] for k in range(1, len(bars))):
        raise ValueError("Candles desordenados ou duplicados")
    # Initialize at the start boundary, then run only new finished candles.
    state = update(None, warm)
    state = update(state, bars)
    trades = state["closed"]
    profit = sum(t["net_usd"] for t in trades if t["net_usd"] > 0)
    losses = sum(t["net_usd"] for t in trades if t["net_usd"] < 0)
    wins_n = sum(t["net_usd"] > 0 for t in trades)
    losses_n = sum(t["net_usd"] < 0 for t in trades)
    pnl = state["equity"] - CAPITAL
    equity = CAPITAL
    peak = CAPITAL
    dd = 0.
    for t in trades:
        equity += t["net_usd"]
        peak = max(peak, equity)
        dd = max(dd, 100 * (peak - equity) / peak)
    pos = state["position"]
    floating = None
    if pos:
        close = bars[-1]["close"]
        floating = ((close - pos["entry"]) * pos["side"] - ROUNDTRIP_PIPS * PIP) * pos["qty_usd"] / close
    all_pnl = pnl + (floating or 0)
    return {
        "timestamp_utc": stamp(now),
        "requested_start_utc": stamp(start),
        "source": "Yahoo CAD=X 15m public reference via " + source + "; not FBS bid/ask",
        "warmup_candles_m15": len(warm),
        "warmup_candles_h1": len(to_h1(warm)),
        "test_candles_m15": len(test),
        "actual_test_first_utc": stamp(test[0]["time"]),
        "actual_test_last_utc": stamp(test[-1]["time"]),
        "source_sha256": hashlib.sha256(json.dumps(bars, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "initial_bank_usd": CAPITAL,
        "strategy": "BB20 pullback H1 touch/rejection, M15 reaction, trailing 1R on CLOSED M15 bars, no fixed TP",
        "assumed_cost_roundtrip_pips": ROUNDTRIP_PIPS,
        "max_notional_multiple": 1.,
        "closed_n": len(trades),
        "wins_n": wins_n,
        "losses_n": losses_n,
        "win_rate_pct": wins_n * 100 / len(trades) if trades else None,
        "realized_pnl_usd": pnl,
        "realized_return_pct": 100 * pnl / CAPITAL,
        "drawdown_realized_pct": dd,
        "profit_factor": profit / -losses if losses < 0 else None,
        "mean_closed_trade_usd": pnl / len(trades) if trades else None,
        "costs_total_estimated_usd": sum(t["cost_usd"] for t in trades),
        "floating_pnl_usd": floating,
        "pnl_including_open_usd": all_pnl,
        "return_including_open_pct": 100 * all_pnl / CAPITAL,
        "open_position": pos,
        "exit_reasons": dict(Counter(t["exit_type"] for t in trades)),
        "closed_trades": trades,
        "caveats": [
            "Historical simulation, NOT independent forward testing, executed FBS trades, or realized brokerage gains.",
            "Source OHLC is indicative; bid/ask, spreads and slippage estimated, not executed.",
            "Unknown intrabar path: old stops checked before trailing on each candle close.",
            "Gaps can lose more than planned stop risk; no profit guarantee.",
            "Yahoo 15m lookback does not cover five months, so 5-month results not extrapolated."
        ],
    }


def markdown(r):
    def usd(x):
        return "indisponível" if x is None else "US$ %+.2f" % x
    def pct(x):
        return "indisponível" if x is None else "%+.3f%%" % x
    lines = [
        "# Nexus Quant — Backtest de 30 dias — USD/CAD BB20 Pullback H1/M15",
        "",
        "**Data da execução (UTC):** " + r["timestamp_utc"],
        "**Janela solicitada:** " + r["requested_start_utc"] + " → " + r["timestamp_utc"],
        "**Candles da avaliação:** " + r["actual_test_first_utc"] + " → " + r["actual_test_last_utc"],
        "**Fonte:** " + r["source"],
        "",
        "## Resultado histórico virtual",
        "- Operações encerradas: **%s** (%s vitória(s); %s derrota(s))." % (r["closed_n"], r["wins_n"], r["losses_n"]),
        "- Taxa de acerto: **" + pct(r["win_rate_pct"]) + "**",
        "- P&L líquido realizado: **" + usd(r["realized_pnl_usd"]) + " (" + pct(r["realized_return_pct"]) + ")**",
        "- P&L em aberto: **" + usd(r["floating_pnl_usd"]) + "**",
        "- P&L com posição aberta marcada a mercado: **" + usd(r["pnl_including_open_usd"]) + " (" + pct(r["return_including_open_pct"]) + ")**",
        "- Drawdown realizado: **%.3f%%**" % r["drawdown_realized_pct"],
        "- Média por operação encerrada: **" + usd(r["mean_closed_trade_usd"]) + "**",
        "- Profit factor: **" + (("%.3f" % r["profit_factor"]) if r["profit_factor"] is not None else "não calculável") + "**",
        "- Custos estimados realizados: **" + usd(r["costs_total_estimated_usd"]) + "**",
        "- Posição virtual ao final: **" + ("aberta" if r["open_position"] else "nenhuma") + "**",
        "",
        "## Auditoria",
        "- Histórico de aquecimento: %s candles M15, %s candles H1 completos." % (r["warmup_candles_m15"], r["warmup_candles_h1"]),
        "- Candles M15 no intervalo testado: %s." % r["test_candles_m15"],
        "- Impressão digital SHA-256 da série: " + r["source_sha256"],
        "- Os dados brutos serão guardados como JSON gzip para verificação.",
        "- Os 10 robôs de ouro não foram modificados.",
        "",
        "## Operações",
        "| Entrada UTC | Saída UTC | Lado | Fechamento | P&L USD |",
        "|---|---|---|---|---:|",
    ]
    for t in r["closed_trades"]:
        lines.append("| %s | %s | %s | %s | %s |" % (
            stamp(t["entry_ts"]), stamp(t["exit_ts"]),
            "Compra" if t["side"] > 0 else "Venda", t["exit_type"], usd(t["net_usd"])
        ))
    if not r["closed_trades"]:
        lines.append("| — | — | — | Nenhuma operação encerrada | — |")
    lines += ["", "## Limitações"] + ["- " + item for item in r["caveats"]]
    lines += ["", "**Resultado positivo não prova lucratividade futura; sem operações não há amostra de desempenho.**", ""]
    return "\n".join(lines)


def main():
    now = int(datetime.now(timezone.utc).timestamp())
    bars, source = fetch_history(now)
    r = analyze(bars, now, source)
    OUT.mkdir(parents=True, exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    prefix = "bb20_usdcad_m15_1mo_" + day
    (OUT / (prefix + ".json")).write_text(json.dumps(r, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    (OUT / (prefix + ".md")).write_text(markdown(r), encoding="utf-8")
    with gzip.open(OUT / (prefix + "_bars.json.gz"), "wt", encoding="utf-8") as stream:
        json.dump({"metadata": r["source"], "candles": bars}, stream, ensure_ascii=False, separators=(",", ":"))
    print("BACKTEST_SUMMARY=" + json.dumps({
        "closed": r["closed_n"], "wins": r["wins_n"], "losses": r["losses_n"],
        "realized_usd": round(r["realized_pnl_usd"], 5),
        "including_open_usd": round(r["pnl_including_open_usd"], 5),
        "test_m15": r["test_candles_m15"], "warmup_m15": r["warmup_candles_m15"],
        "saved_report": str(OUT / (prefix + ".md")),
    }))


if __name__ == "__main__":
    main()
