"""Daily Telegram recap of paper books; no live brokerage results."""
from html import escape
from src.feed import MARKETS
from src.gold_forward import STUDY,DISPLAY,scorecard,day_of
from src.leveraged_gold import CONFIG as LEV_CONFIG,stats as lev_stats,CAPITAL as LEV_CAPITAL
from src.bb_rebound_mtf import digest as bb_digest, CAPITAL as BB_CAPITAL
from src.experimental_h1 import digest as experimental_digest, STRATEGIES as H1_STRATEGIES
from src.momentum60_shadow import daily_line as momentum60_daily_line, CAPITAL as MOMENTUM_CAPITAL

def _daily(closed,date):
    trades=[t for t in closed if day_of(t["exit_ts"])==date]
    return len(trades),sum(t["net_usd"] for t in trades)

def _entry_info(book, date):
    """Count all observed virtual entries, including positions still open."""
    starts = {int(t["entry_ts"]) for t in book["closed"]}
    p = book.get("position")
    if p is not None:
        starts.add(int(p.get("start", p.get("entry_ts"))))
    return sum(day_of(ts) == date for ts in starts)

def _position_info(book):
    p = book.get("position")
    if p is None:
        return "sem posição"
    start = int(p.get("start", p.get("entry_ts")))
    direction = "COMPRA" if p["side"] > 0 else "VENDA"
    return f"aberta {direction} {day_of(start)} @ {p['entry']:.2f}"

def digest(day, conventional, leveraged, datasets=None, unavailable=None,
           mtf=None, mtf_error=None, shadow=None, momentum60=None, planned_robots=None):
    """Readable HTML Telegram digest; presentation only, no trading-state changes."""
    old_books = conventional["books"]
    new_books = leveraged["books"]
    if len(old_books) != 5 or len(new_books) != 5:
        raise ValueError("Daily ten-bot report needs 5+5 distinct virtual books")
    if planned_robots not in (None, 27):
        raise ValueError("Only the explicit 27-bot plan is supported")

    extra = mtf is not None or mtf_error is not None
    count = 10 + (1 if extra else 0) + (15 if shadow is not None else 0)
    books = list(old_books.values()) + list(new_books.values())
    entries_today = sum(_entry_info(b, day) for b in books)
    closes_today = sum(_daily(b["closed"], day)[0] for b in books)
    pnl_today = sum(_daily(b["closed"], day)[1] for b in books)
    total_pnl = (sum(scorecard(b)["pnl"] for b in old_books.values())
                 + sum(lev_stats(b)["pnl_usd"] for b in new_books.values()))
    open_count = sum(b.get("position") is not None for b in books)

    scope = ("27 robôs previstos: 10 Ouro H4 + 15 H1 + 1 USD/CAD + 1 Momentum60"
             if planned_robots == 27 else
             f"{count} robôs: 10 Ouro H4"
             + (" + 1 USD/CAD" if extra else "")
             + (" + 15 H1 experimentais" if shadow is not None else ""))
    lines = [
        f"<b>📊 NEXUS QUANT — {escape(str(day))}</b>",
        f"🧪 {scope}",
        "<i>RESULTADOS VIRTUAIS • sem ordens reais na FBS</i>",
        "",
        "<b>📌 RESUMO DO DIA • OURO H4</b>",
        f"📥 Entradas: <b>{entries_today}</b>  •  Saídas: <b>{closes_today}</b>",
        f"💵 Hoje: <b>US$ {pnl_today:+.2f}</b>",
        f"📈 Acumulado: <b>US$ {total_pnl:+.2f}</b>",
        f"📍 Posições abertas: {open_count}/10",
        "",
        "<b>🟦 5 CONVENCIONAIS</b>",
        "<i>0,75% risco-stop • até 1× nocional</i>",
    ]

    for key in sorted(STUDY, key=lambda k: scorecard(old_books[k])["pnl"], reverse=True):
        book = old_books[key]
        closed, today = _daily(book["closed"], day)
        stats = scorecard(book)
        entries = _entry_info(book, day)
        lines.append(f"• <b>{escape(str(DISPLAY[key]))}</b>  |  hoje <b>US$ {today:+.2f}</b>")
        detail = (f"  E/S {entries}/{closed} · acum. US$ {stats['pnl']:+.2f}"
                  f" · V/D {stats['wins']}/{stats['losses']}")
        if book.get("position") is None:
            lines.append(detail + " · ⚪ livre")
        else:
            lines.extend([detail, f"  ↳ {'🔵' if book['position']['side'] > 0 else '🔴'} {escape(_position_info(book))}"])

    lines.extend([
        "",
        "<b>🟥 5 ALAVANCADOS</b>",
        "<i>1,50% risco-stop • limite 3× nocional</i>",
        "🟢 Stop móvel GREEN: após +1R; sem TP fixo (novas posições).",
    ])
    for key in sorted(LEV_CONFIG, key=lambda k: lev_stats(new_books[k])["pnl_usd"], reverse=True):
        book = new_books[key]
        stats = lev_stats(book)
        closed, today = _daily(book["closed"], day)
        entries = _entry_info(book, day)
        lines.append(f"• <b>{escape(str(LEV_CONFIG[key][1]))}</b>  |  hoje <b>US$ {today:+.2f}</b>")
        detail = (f"  E/S {entries}/{closed} · acum. US$ {stats['pnl_usd']:+.2f}"
                  f" · V/D {stats['wins']}/{stats['losses']}")
        if stats["frozen"]:
            lines.append(detail + " · ⏸ PAUSADO")
        elif book.get("position") is None:
            lines.append(detail + " · ⚪ livre")
        else:
            position = book["position"]
            lev = f"{stats['effective_leverage']:.2f}×"
            green = ("green protegido" if position.get("green_protected")
                     else "aguardando +1R") if position.get("mode") == "green_runner" else "stop fixo"
            lines.extend([detail, f"  ↳ {escape(_position_info(book))} · {lev} · {green}"])

    lines.extend([
        "",
        f"📥 Entradas virtuais abertas hoje: <b>{entries_today}</b> nos dez robôs de ouro.",
    ])
    if extra:
        lines.append("")
        if mtf is not None:
            bb_lines = bb_digest(mtf, day)
            lines.extend("<b>" + escape(str(line)) + "</b>"
                         if line.startswith("🟨 11º ROBÔ") else escape(str(line))
                         for line in bb_lines)
        else:
            lines.extend([
                "<b>🟨 11º ROBÔ — BB20 Pullback H1/M15 | USD/CAD</b>",
                "⚠️ Dados indisponíveis: " + escape(str(mtf_error)[:130])
                + ". Não atribuir P&L zero.",
            ])

    if shadow is not None:
        for line in experimental_digest(shadow, day):
            lines.append("<b>" + escape(line) + "</b>"
                         if line.startswith("🧪 15 EXPERIMENTAIS") else escape(line))
    elif planned_robots == 27:
        lines.append("🧪 15 H1 experimentais: dados indisponíveis; não presumir P&L zero")
    if momentum60 is not None:
        lines.append(escape(momentum60_daily_line(momentum60, day)))
    elif planned_robots == 27:
        lines.append("🧪 Momentum60 H4: estado indisponível; sem lucro/perda presumidos")

    all_books = [(DISPLAY[k], scorecard(old_books[k])["pnl"]) for k in STUDY]
    all_books.extend((LEV_CONFIG[k][1], lev_stats(new_books[k])["pnl_usd"])
                     for k in LEV_CONFIG)
    leader = max(all_books, key=lambda item: item[1])
    lines.extend(["", "<b>🏁 FECHAMENTO</b>"])
    if any(abs(pnl) > 1e-9 for _, pnl in all_books):
        lines.append(f"🏅 Melhor saldo acumulado (grupo ouro): {escape(str(leader[0]))}"
                     f" · US$ {leader[1]:+.2f}")
    else:
        lines.append("🏅 Ouro H4: todos empatados, sem resultado realizado.")
    if planned_robots == 27:
        capital = 5000 * 10 + 15 * 1000 + BB_CAPITAL + MOMENTUM_CAPITAL
        lines.append(f"💼 Capital VIRTUAL: US$ {capital:,.0f} em 27 bancas previstas.")
    else:
        capital = 5000 * 10 + (BB_CAPITAL if extra else 0) + (15000 if shadow is not None else 0)
        lines.append(f"💼 Capital VIRTUAL: US$ {capital:,.0f} em {count} bancas.")
    lines.append("🌍 Mercados observados: EUR/USD, USD/JPY, US500, WTI.")
    if unavailable:
        lines.append("⚠️ Sem dados confirmados hoje: " + escape(", ".join(map(str, unavailable))))
    lines.extend([
        "⚠️ Risco maior pode ampliar perdas; financiamento estimado.",
        "⛔ Dados/custos aproximados; sem ganhos reais de corretora.",
    ])
    message = "\n".join(lines)
    if len(message) > 4000:
        raise ValueError("Daily multi-bot Telegram report too long")
    return message
