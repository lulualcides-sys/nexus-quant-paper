"""Forward-only independent gold paper books for five pre-selected H4 rules.

All entry signals are evaluated on the previous COMPLETED 4h bar.
No historic trades are generated upon bootstrapping. This is NOT an FBS account.
"""
import json
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from src.strategies import make_indicators
from research.screen_v2 import aggregate_hourly_to_h4,sign,CAPITAL,MAX_LEVERAGE,ATR_STOP,ATR_TARGET,MAX_HOLD
from research.backtest_year import COST_BPS

FILE=Path("state/selected_gold_v2.json")
STUDY=("rsi_trend","channel20","pullback20","momentum100","channel55")
# Prospective paper-only risk. Does not modify prior historic backtests.
RISK=0.0075
DISPLAY={
  "rsi_trend":"RSI Trend",
  "channel20":"Channel 20",
  "pullback20":"Pullback 20",
  "momentum100":"Momentum 100",
  "channel55":"Channel 55",
}

def initial(bars):
    if len(bars)<245:raise ValueError("Gold H4 warmup below 245 bars")
    return {"schema":1,"market":"XAUUSD","h4_watermark":bars[-1]["time"],
        "paper_only":True,"books":{s:{"equity":CAPITAL,"position":None,"closed":[]} for s in STUDY}}

def evaluate_bar(book,key,bars,ind,i):
    row=bars[i];t=row["time"];open_price=row["open"]
    p=book["position"]
    if p:
        side=p["side"];stop=p["stop"];target=p["target"]
        if side==1:
            stopped=row["low"]<=stop;taken=row["high"]>=target
            stop_fill=min(open_price,stop)
        else:
            stopped=row["high"]>=stop;taken=row["low"]<=target
            stop_fill=max(open_price,stop)
        fill=None
        if stopped:fill=stop_fill;reason="STOP"
        elif taken:fill=target;reason="TARGET"
        elif i-p["i"]>=MAX_HOLD:fill=row["close"];reason="TIME"
        if fill is not None:
            gross=side*(fill-p["entry"])*p["qty"]
            fee=COST_BPS["XAUUSD"]/10000*p["qty"]*((fill+p["entry"])/2)
            pnl=gross-fee
            book["equity"]+=pnl
            book["closed"].append({"entry_ts":p["start"],"exit_ts":t,
                "side":side,"entry":round(p["entry"],6),"exit":round(fill,6),
                "net_usd":round(pnl,5),"cost_usd":round(fee,5),
                "exit_type":reason})
            book["position"]=None
    # Position may exit and new entry occur next bar, but never same bar
    # that just touched the stop or target.
    if p is not None:return
    signal_now=sign(key,bars,ind,i-1)
    signal_prev=sign(key,bars,ind,i-2)
    if signal_now and signal_now!=signal_prev:
        atr=ind[i-1]["atr"]
        if atr>0 and book["equity"]>0 and open_price>0:
            qty=min(book["equity"]*RISK/(ATR_STOP*atr),
                    MAX_LEVERAGE*book["equity"]/open_price)
            if qty>0:
                book["position"]={"side":signal_now,"entry":open_price,
                    "start":t,"i":i,"qty":qty,
                    "stop":open_price-signal_now*ATR_STOP*atr,
                    "target":open_price+signal_now*ATR_TARGET*atr}

def update(state,bars):
    h4=aggregate_hourly_to_h4(bars)
    if len(h4)<245:raise ValueError("History too short for five approved H4 research strategies")
    if state is None:return initial(h4)
    if state.get("schema")!=1 or not state.get("paper_only"):raise ValueError("Invalid paper state")
    watermark=state["h4_watermark"]
    times={b["time"] for b in h4}
    if watermark not in times:raise ValueError("H4 audit gap; no silent backfill")
    ind=make_indicators(h4)
    for i in range(241,len(h4)):
        if h4[i]["time"]<=watermark:continue
        for key in STUDY:
            evaluate_bar(state["books"][key],key,h4,ind,i)
        state["h4_watermark"]=h4[i]["time"]
    return state

def day_of(ts):
    return datetime.fromtimestamp(ts,timezone.utc).astimezone(ZoneInfo("America/Sao_Paulo")).date().isoformat()

def scorecard(book):
    equity=CAPITAL
    peak=CAPITAL
    max_drawdown=0
    wins=0
    losses=0
    for trade in book["closed"]:
        net=trade["net_usd"]
        equity+=net
        wins+=int(net>0)
        losses+=int(net<0)
        peak=max(peak,equity)
        max_drawdown=max(max_drawdown,100*(peak-equity)/peak)
    return {"pnl":book["equity"]-CAPITAL,"pnl_pct":100*(book["equity"]/CAPITAL-1),
            "wins":wins,"losses":losses,"count":len(book["closed"]),
            "max_realized_drawdown_pct":max_drawdown}

def summary(state,day):
    lines=["","🏆 NEXUS QUANT | COPA 5 ROBÔS — OURO H4",
           "📌 Transações VIRTUAIS, não FBS; preços de referência.",
           "📊 Risco planejado: 0,75%/operação, mesma regra para todos."]
    ranking=sorted(STUDY,key=lambda k:scorecard(state["books"][k])["pnl"],reverse=True)
    for place,key in enumerate(ranking,1):
        book=state["books"][key]
        score=scorecard(book)
        todays=[t for t in book["closed"] if day_of(t["exit_ts"]+14400)==day]
        daily=sum(t["net_usd"] for t in todays)
        lines.append(f"{place}º {DISPLAY[key]}: hoje {len(todays)} fechamentos, US$ {daily:+.2f};"
           f" total US$ {score['pnl']:+.2f} ({score['pnl_pct']:+.2f}%),"
           f" V/D {score['wins']}/{score['losses']},"
           f" drawdown realizado {score['max_realized_drawdown_pct']:.1f}%,"
           f" {'posição virtual aberta' if book['position'] else 'sem posição'}")
    lines.append("🌍 EUR/USD, USD/JPY, US500, WTI: monitorados, não aprovados para a copa de posições.")
    lines.append("⚠️ Retornos não incluem swap FBS; lucro/prejuízo virtual e perdas são possíveis.")
    return "\n".join(lines)

def process(bars,path=FILE):
    s=json.loads(path.read_text(encoding="utf8")) if path.exists() else None
    s=update(s,bars)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(s,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    return s
