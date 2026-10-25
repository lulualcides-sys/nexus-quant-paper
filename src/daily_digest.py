"""Compact audit-friendly Telegram recap of TEN separate virtual gold H4 books."""
from src.feed import MARKETS
from src.gold_forward import STUDY,DISPLAY,scorecard,day_of
from src.leveraged_gold import CONFIG as LEV_CONFIG,stats as lev_stats,CAPITAL as LEV_CAPITAL

def _daily(closed,date):
    trades=[t for t in closed if day_of(t["exit_ts"]+14400)==date]
    return len(trades),sum(t["net_usd"] for t in trades)

def digest(day,conventional,leveraged,datasets=None,unavailable=None):
    old_books=conventional["books"];new_books=leveraged["books"]
    if len(old_books)!=5 or len(new_books)!=5:
        raise ValueError("Daily ten-bot report needs 5+5 distinct virtual books")
    lines=[f"🏆 NEXUS QUANT — {day}","🔎 10 robôs • Ouro H4 • RESULTADOS VIRTUAIS",
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
    lines.append("")
    all_books=[(DISPLAY[k],scorecard(old_books[k])["pnl"]) for k in STUDY]
    all_books.extend((LEV_CONFIG[k][1],lev_stats(new_books[k])["pnl_usd"]) for k in LEV_CONFIG)
    leader=max(all_books,key=lambda item:item[1])
    lines.append(f"🏅 Melhor saldo acumulado: {leader[0]} (US$ {leader[1]:+.2f})")
    lines.append(f"💼 Capital de referência: US$ {5000*10:,.0f} em 10 bancas independentes.")
    lines.append("🌍 Outros mercados observados: EUR/USD, USD/JPY, US500, WTI.")
    if unavailable:
        lines.append("⚠️ Sem dados confirmados hoje: "+", ".join(unavailable))
    lines.append("⚠️ Risco maior pode ampliar perdas; financiamento alavancado estimado.")
    lines.append("⛔ Sem operações reais ou ganhos de corretora. Dados e custos aproximados.")
    text="\n".join(lines)
    if len(text)>4000:raise ValueError("Daily 10-bot Telegram report too long")
    return text
