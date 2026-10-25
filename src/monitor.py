"""Forward-only real-price signal journal. No broker fills or claimed P&L."""
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from .strategies import CONFIGS,WARMUP,signal,make_indicators
from .feed import MARKETS
TZ=ZoneInfo("America/Sao_Paulo")
HORIZON=6

def date_local(ts):
    return datetime.fromtimestamp(ts,timezone.utc).astimezone(TZ).date().isoformat()
def hour_local(ts):
    return datetime.fromtimestamp(ts,timezone.utc).astimezone(TZ).strftime("%H:%M")
def empty_state():
    return {"schema":4,"markets":{},"last_report_day":None}

def scan_market(state,key,bars):
    if key not in MARKETS:raise KeyError(key)
    if len(bars)<WARMUP+2:raise ValueError("Histórico insuficiente")
    stamps=[b["time"] for b in bars]
    if stamps!=sorted(set(stamps)):raise ValueError("Candles fora da ordem")
    if state["schema"]!=4:raise ValueError("Estado incompatível")
    store=state["markets"].get(key)
    if store is None:
        state["markets"][key]={"watermark":stamps[-1],"signals":[],"source":MARKETS[key].ticker}
        return 0
    if store["watermark"]<stamps[0]:
        raise ValueError(f"{key}: intervalo sem histórico; auditoria interrompida")
    inds=make_indicators(bars)
    count=0
    for i in range(WARMUP,len(bars)):
        if bars[i]["time"]<=store["watermark"]:continue
        ts=bars[i]["time"]
        for strategy in CONFIGS:
            direction=signal(strategy,bars,inds,i)
            prior=signal(strategy,bars,inds,i-1)
            if direction and direction!=prior and inds[i]["atr"]>0:
                store["signals"].append({"id":f"{key}:{strategy}:{ts}","asset":key,
                    "strategy":strategy,"ts":ts,"side":direction,"close":bars[i]["close"],
                    "atr":inds[i]["atr"],"eval":None,"evaluated_at":None,"directional_move_atr":None})
                count+=1
        store["watermark"]=ts
    index={b["time"]:i for i,b in enumerate(bars)}
    for ev in store["signals"]:
        if ev["eval"] is not None:continue
        idx=index.get(ev["ts"])
        if idx is None or idx+HORIZON>=len(bars):continue
        j=idx+HORIZON
        move=ev["side"]*(bars[j]["close"]-ev["close"])/ev["atr"]
        ev["eval"]="favoravel" if move>=.3 else "contrario" if move<=-.3 else "neutro"
        ev["evaluated_at"]=bars[j]["time"]
        ev["directional_move_atr"]=round(move,5)
    return count

def day_change(bars,today):
    same=[b for b in bars if date_local(b["time"]+3600)==today]
    return None if not same else 100*(same[-1]["close"]/same[0]["open"]-1)

def report(state,datasets,day):
    lines=[f"📊 NEXUS QUANT — {day}",
        "5 mercados públicos · 5 robôs de sinais · sem ordens FBS",
        "⚠️ Não há lucro/RED de corretora sem operações executadas.",""]
    tally={k:[0,0,0] for k in CONFIGS}
    for key,asset in MARKETS.items():
        bars=datasets[key];latest=bars[-1];store=state["markets"][key]
        change=day_change(bars,day)
        price=f'{latest["close"]:.5f}' if latest["close"]<100 else f'{latest["close"]:.2f}'
        lines.append(f"🌍 {asset.name}: {price}")
        lines.append(f"  Dia: {change:+.2f}%" if change is not None else "  Mercado sem novo candle")
        lines.append(f"  Fonte: Yahoo {asset.ticker} · último candle {hour_local(latest['time']+3600)} BRT")
        signals=[e for e in store["signals"] if date_local(e["ts"]+3600)==day]
        if signals:
            for e in signals[-2:]:
                lines.append(f'  {CONFIGS[e["strategy"]]}: {"COMPRA" if e["side"]>0 else "VENDA"} · {hour_local(e["ts"]+3600)}')
            if len(signals)>2:lines.append(f"  +{len(signals)-2} sinais adicionais")
        else:lines.append("  Sem sinais novos registrados hoje")
        completed=[e for e in store["signals"] if e["evaluated_at"] and date_local(e["evaluated_at"]+3600)==day]
        if completed:
            lines.append("  Sinais avaliados hoje: "+" · ".join(f"{kind}: {sum(e['eval']==kind for e in completed)}" for kind in ("favoravel","contrario","neutro")))
        for e in store["signals"]:
            if e["eval"] is not None:
                tally[e["strategy"]][{"favoravel":0,"contrario":1,"neutro":2}[e["eval"]]]+=1
        lines.append("")
    lines.append("🏆 COMPARATIVO ACUMULADO — DIREÇÃO APÓS 6 CANDLES")
    for k,v in tally.items():
        lines.append(f"{CONFIGS[k]}: ✅{v[0]} ❌{v[1]} ➖{v[2]}")
    lines.extend(["","Dados de referência, não preços negociáveis da FBS.",
        "Ouro/US500/WTI usam futuros, não CFDs da FBS.",
        "Sem fills na FBS não há P&L comprovado."])
    msg="\n".join(lines)
    if len(msg)>3900:raise ValueError("Telegram: mensagem muito longa")
    return msg
