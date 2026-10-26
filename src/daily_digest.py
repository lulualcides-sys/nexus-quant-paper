"""Compact Telegram recap: ten independent H4 gold books and optional 11th USD/CAD."""
from src.feed import MARKETS
from src.gold_forward import STUDY,DISPLAY,scorecard,day_of
from src.leveraged_gold import CONFIG as LEV_CONFIG,stats as lev_stats,CAPITAL as LEV_CAPITAL
from src.bb_rebound_mtf import digest as bb_digest, CAPITAL as BB_CAPITAL

def _daily(closed,date):
    trades=[t for t in closed if day_of(t["exit_ts"]+14400)==date]
    return len(trades),sum(t["net_usd"] for t in trades)

def digest(day,conventional,leveraged,datasets=None,unavailable=None,mtf=None,mtf_error=None):
    old_books=conventional["books"];new_books=leveraged["books"]
    if len(old_books)!=5 or len(new_books)!=5:
        raise ValueError("Daily ten-bot report needs 5+5 distinct virtual books")
    extra=mtf is not None or mtf_error is not None
    count=11 if extra else 10
    lines=[f"🏆 NEXUS QUANT — {day}",f"🔎 {count} robôs • 10 Ouro H4"+(" + 1 USD/CAD H1/M15" if extra else "")+" • RESULTADOS VIRTUAIS",
      "📌 Preços de futuros GC=F, não cotações nem execuções FBS.","",
      "🟦 5 CONVENCIONAIS | 0,75% risco-stop | até 1× nocional"]
    for key in sorted(STUDY,key=lambda k:scorecard(old_books[k])["pnl"],reverse=True):
        b=old_books[key];n,today=_daily(b["closed"],day);s=scorecard(b)
        lines.append(f"{DISPLAY[key]}: {n} fech. | dia US$ {today:+.2f}"
          f" | total US$ {s['pnl']:+.2f} | V/D {s['wins']}/{s['losses']}"
          f" | {'aberta' if b['position'] else 'sem posição'}")
    lines+=["","🟥 5 ALAVANCADOS | 1,50% risco-stop | limite 3× nocional",
            "🟢 Stop móvel GREEN: após +1R, acompanha o movimento; sem TP fixo."]
    for key in sorted(LEV_CONFIG,key=lambda k:lev_stats(new_books[k])["pnl_usd"],reverse=True):
        b=new_books[key];s=lev_stats(b)
        n,today=_daily(b["closed"],day)
        state="PAUSADO" if s["frozen"] else ("aberto" if b["position"] else "sem posição")
        lev=f"{s['effective_leverage']:.2f}×" if b["position"] else "0×"
        green=("green protegido" if b["position"].get("green_protected") else "esperando +1R") if b["position"] and b["position"].get("mode")=="green_runner" else "stop fixo/sem entrada"
        lines.append(f"{LEV_CONFIG[key][1]}: {n} fech. | dia US$ {today:+.2f}"
           f" | total US$ {s['pnl_usd']:+.2f} | V/D {s['wins']}/{s['losses']}"
           f" | {state}, exp. {lev}, {green}")
    if extra:
        lines.append("")
        if mtf is not None:
            lines.extend(bb_digest(mtf,day))
        else:
            lines.extend(["🟨 11º ROBÔ — BB20 Pullback H1/M15 | USD/CAD",
                          "⚠️ Dados indisponíveis: " + str(mtf_error)[:130] + ". Não atribuir P&L zero."])
    lines.append("")
    all_books=[(DISPLAY[k],scorecard(old_books[k])["pnl"]) for k in STUDY]
    all_books.extend((LEV_CONFIG[k][1],lev_stats(new_books[k])["pnl_usd"]) for k in LEV_CONFIG)
    leader=max(all_books,key=lambda item:item[1])
    if any(abs(pnl) > 1e-9 for _,pnl in all_books):
        lines.append(f"🏅 Melhor saldo acumulado (grupo ouro): {leader[0]} (US$ {leader[1]:+.2f})")
    else:
        lines.append("🏅 Ouro H4: todos empatados, sem resultado realizado.")
    lines.append(f"💼 Capital virtual: US$ {5000*10+(BB_CAPITAL if extra else 0):,.0f} em {count} bancas independentes.")
    lines.append("🌍 Outros mercados observados: EUR/USD, USD/JPY, US500, WTI.")
    if unavailable:
        lines.append("⚠️ Sem dados confirmados hoje: "+", ".join(unavailable))
    lines.append("⚠️ Risco maior pode ampliar perdas; financiamento alavancado estimado.")
    lines.append("⛔ Sem operações reais ou ganhos de corretora. Dados e custos aproximados.")
    text="\n".join(lines)
    if len(text)>4000:raise ValueError("Daily multi-bot Telegram report too long")
    return text
