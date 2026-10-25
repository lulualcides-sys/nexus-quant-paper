"""Research V3: multi-regime DAILY strategies on five market proxies.

Predefined candidate rules, walk-forward chronological train/validation/review.
This is retrospective research only, not FBS executions, and 2025-26 is NOT a
pristine holdout (previous research already inspected it).
"""
import json,math,statistics,time,urllib.request
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import quote
from src.feed import MARKETS

def epoch(day):return int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp())
PERIODS={"development":("2022-07-01","2024-01-01"),
         "validation":("2024-01-01","2025-01-01"),
         "review":("2025-01-01","2026-10-25")}
BANK=5000.
RISK=0.0075
MAX_LEVERAGE=2.
MAX_DAYS=80
FEES_BPS={"EURUSD":5,"USDJPY":5,"XAUUSD":12,"US500":8,"XTIUSD":15}
KEYS=("turtle20","turtle55","momentum60","momentum120",
      "ema_cross","ema_slope","pullback20","rsi_trend",
      "range_reversal","vol_expansion")

def load_daily(asset,now=None):
    # Read observed Yahoo daily candles, no random or fabricated bars.
    now=int(time.time()) if now is None else int(now)
    error=None
    for domain in ("query1.finance.yahoo.com","query2.finance.yahoo.com"):
        url=(f"https://{domain}/v8/finance/chart/{quote(asset.ticker,safe='')}"
             "?interval=1d&range=5y")
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
            with urllib.request.urlopen(req,timeout=25) as response:
                d=json.load(response)
            part=(d.get("chart") or {}).get("result") or []
            if not part:raise ValueError("No result")
            item=part[0];timestamps=item.get("timestamp") or []
            indicators=(item.get("indicators") or {}).get("quote") or []
            if not indicators:raise ValueError("No OHLC")
            q=indicators[0];out=[]
            for i,ts in enumerate(timestamps):
                if ts+86400>now:continue
                try:
                    row={"ts":int(ts),**{k:float(q[k][i]) for k in ("open","high","low","close")}}
                except (TypeError,ValueError,KeyError,IndexError):continue
                if not all(math.isfinite(row[k]) and row[k]>0 for k in ("open","high","low","close")):continue
                if row["low"]>min(row["open"],row["close"]) or row["high"]<max(row["open"],row["close"]):continue
                out.append(row)
            clean={row["ts"]:row for row in out}
            rows=[clean[k] for k in sorted(clean)]
            if len(rows)<900:raise ValueError(f"Insufficient daily bars: {len(rows)}")
            if rows[0]["ts"]>epoch("2022-01-01"):raise ValueError("Missing warmup for 2022")
            return rows
        except Exception as exc:error=type(exc).__name__+": "+str(exc)[:130]
    raise RuntimeError(f"Missing observable daily history for {asset.name}: {error}")

def ema(v,n):
    alpha=2/(n+1);out=[];last=v[0]
    for x in v:
        last=alpha*x+(1-alpha)*last
        out.append(last)
    return out

def build(b):
    closes=[x["close"] for x in b]
    lows=[x["low"] for x in b];highs=[x["high"] for x in b]
    atrs=[]
    tr=[max(b[i]["high"]-b[i]["low"],abs(b[i]["high"]-closes[max(i-1,0)]),
            abs(b[i]["low"]-closes[max(i-1,0)])) for i in range(len(b))]
    atrs=ema(tr,14)
    e20=ema(closes,20);e50=ema(closes,50);e200=ema(closes,200)
    gains=ema([max(0,closes[i]-closes[max(0,i-1)]) for i in range(len(b))],14)
    losses=ema([max(0,closes[max(0,i-1)]-closes[i]) for i in range(len(b))],14)
    result=[]
    for i in range(len(b)):
        # Efficiency ratio is in [0,1]: smaller means chop, higher trending.
        window=closes[max(0,i-20):i+1]
        denominator=sum(abs(window[j]-window[j-1]) for j in range(1,len(window)))
        efficiency=abs(window[-1]-window[0])/denominator if denominator else 0
        rsi=100* gains[i]/(gains[i]+losses[i]) if gains[i]+losses[i]>0 else 50
        recent_atr=atrs[max(0,i-59):i+1]
        result.append({"atr":atrs[i],"e20":e20[i],"e50":e50[i],"e200":e200[i],
          "rsi":rsi,"er":efficiency,
          "a60":statistics.median(recent_atr),
          "h20":max(highs[max(0,i-20):i] or [highs[i]]),
          "l20":min(lows[max(0,i-20):i] or [lows[i]]),
          "h55":max(highs[max(0,i-55):i] or [highs[i]]),
          "l55":min(lows[max(0,i-55):i] or [lows[i]])})
    return result

def decide(name,b,v,i):
    if i<210:return 0
    c=b[i]["close"];p=v[i];q=v[i-1];last=b[i-1]["close"]
    up=p["e50"]>p["e200"];down=p["e50"]<p["e200"]
    er=p["er"];r=p["rsi"]
    if name=="turtle20":
        return 1 if up and er>.25 and c>p["h20"] else (-1 if down and er>.25 and c<p["l20"] else 0)
    if name=="turtle55":
        return 1 if up and c>p["h55"] else (-1 if down and c<p["l55"] else 0)
    if name=="momentum60":
        d=(c/b[i-60]["close"]-1)
        return 1 if up and d>.045 else (-1 if down and d<-.045 else 0)
    if name=="momentum120":
        d=(c/b[i-120]["close"]-1)
        return 1 if up and d>.08 else (-1 if down and d<-.08 else 0)
    if name=="ema_cross":
        return 1 if q["e20"]<=q["e50"] and p["e20"]>p["e50"] and up else (-1 if q["e20"]>=q["e50"] and p["e20"]<p["e50"] and down else 0)
    if name=="ema_slope":
        slope=p["e50"]/v[i-20]["e50"]-1
        return 1 if up and slope>.02 and c>p["e20"] else (-1 if down and slope<-.02 and c<p["e20"] else 0)
    if name=="pullback20":
        return 1 if up and last<q["e20"] and c>p["e20"] and 48<r<67 else (-1 if down and last>q["e20"] and c<p["e20"] and 33<r<52 else 0)
    if name=="rsi_trend":
        return 1 if up and q["rsi"]<=52 and r>52 else (-1 if down and q["rsi"]>=48 and r<48 else 0)
    if name=="range_reversal":
        return 1 if er<.22 and q["rsi"]<=32 and r>32 else (-1 if er<.22 and q["rsi"]>=68 and r<68 else 0)
    if name=="vol_expansion":
        return 1 if up and p["atr"]>1.25*p["a60"] and c>p["h20"] else (-1 if down and p["atr"]>1.25*p["a60"] and c<p["l20"] else 0)
    raise KeyError(name)

def trade_math(market,side,entry,exit,qty,cost_multiplier=1.):
    """JPY pair quoted JPY per USD; convert quote-currency P&L to USD."""
    gross=side*(exit-entry)*qty
    if market=="USDJPY":gross/=exit
    notional=qty if market=="USDJPY" else qty*entry
    fee=(FEES_BPS[market]/10000)*notional*cost_multiplier
    return gross-fee,fee

def size_position(market,balance,entry,atr,stop_mult):
    # All outputs are USD-account value, even when USDJPY is JPY-quoted.
    per_unit=stop_mult*atr/(entry if market=="USDJPY" else 1)
    max_qty=(balance*MAX_LEVERAGE if market=="USDJPY" else balance*MAX_LEVERAGE/entry)
    return min(balance*RISK/per_unit,max_qty) if per_unit>0 else 0

def run(market,name,b,v,period,fees=1.):
    start,end=(epoch(x) for x in PERIODS[period])
    equity=BANK;max_eq=BANK;max_dd=0;pos=None;trades=[];equity_days={}
    for i in range(211,len(b)):
        x=b[i];ts=x["ts"]
        if ts<start:continue
        if ts>=end:break
        had_pos=pos is not None
        if pos:
            stop=pos["stop"];target=pos["target"];side=pos["side"];o=x["open"]
            if side==1:
                hitstop=x["low"]<=stop;hittarget=x["high"]>=target
                price=min(o,stop)
            else:
                hitstop=x["high"]>=stop;hittarget=x["low"]<=target
                price=max(o,stop)
            why=""
            if hitstop:why="stop"
            elif hittarget:price=target;why="target"
            elif i-pos["index"]>=MAX_DAYS:price=x["close"];why="time"
            if why:
                net,fee=trade_math(market,side,pos["entry"],price,pos["qty"],fees)
                equity+=net
                trades.append({"ts":ts,"opened":pos["time"],"net":round(net,4),"cost":round(fee,4),
                   "side":side,"reason":why})
                pos=None
        # never reenter in the same bar as a completed trade
        if pos is None and not had_pos and equity>0:
            current=decide(name,b,v,i-1)
            prev=decide(name,b,v,i-2)
            if current and current!=prev:
                atr=v[i-1]["atr"];mult=1.3 if name=="range_reversal" else 1.8
                if atr>0 and x["open"]>0:
                    qty=size_position(market,equity,x["open"],atr,mult)
                    if qty>0:
                        pos={"side":current,"qty":qty,"entry":x["open"],"index":i,"time":ts,
                            "stop":x["open"]-current*mult*atr,
                            "target":x["open"]+current*(2.2 if name=="range_reversal" else 3.6)*atr}
        mtm=0
        if pos:mtm=trade_math(market,pos["side"],pos["entry"],x["close"],pos["qty"],fees)[0]
        shown=equity+mtm
        max_eq=max(max_eq,shown)
        max_dd=max(max_dd,100*(max_eq-shown)/max_eq)
        equity_days[datetime.fromtimestamp(ts,timezone.utc).strftime("%Y-%m-%d")]=shown
    if pos:
        eligible=[x for x in b if start<=x["ts"]<end]
        if eligible:
            last=eligible[-1]
            net,fee=trade_math(market,pos["side"],pos["entry"],last["close"],pos["qty"],fees)
            equity+=net
            trades.append({"ts":last["ts"],"opened":pos["time"],"net":round(net,4),
                "cost":round(fee,4),"side":pos["side"],"reason":"period_cutoff"})
    positives=sum(x["net"] for x in trades if x["net"]>0)
    negatives=-sum(x["net"] for x in trades if x["net"]<0)
    bymonth=defaultdict(float)
    for tr in trades:
        bymonth[datetime.fromtimestamp(tr["ts"],timezone.utc).strftime("%Y-%m")]+=tr["net"]
    return {"n":len(trades),"return_pct":round(100*(equity/BANK-1),2),
        "pnl":round(equity-BANK,2),"fees":round(sum(x["cost"] for x in trades),2),
        "drawdown_pct":round(max_dd,2),
        "win_pct":round(100*sum(x["net"]>0 for x in trades)/len(trades),2) if trades else 0,
        "pf":round(positives/negatives,3) if negatives>0 else (999 if positives>0 else 0),
        "month_pnl":{k:round(val,2) for k,val in sorted(bymonth.items())},
        "ledger":trades}

def qualify_train(o):
    return o["n"]>=5 and o["return_pct"]>0 and o["pf"]>1.12 and o["drawdown_pct"]<=22

def qualify_valid(o,double):
    return o["n"]>=3 and o["return_pct"]>0 and double["pnl"]>0 and o["drawdown_pct"]<=18

def report(out):
    lines=["# Nexus Quant — V3, pesquisa ampliada com condições de mercado",
    "",
    "**Não há lucro garantido e nenhum resultado veio de uma conta FBS.**",
    "",
    "Dez regras pré-definidas x cinco mercados = 50 modelos em D1. Comparação com todos os resultados, inclusive perdedores.",
    "Janela 1 (desenvolvimento) 2022-07 a 2023-12; janela 2 (validação) 2024; janela 3 (revisão retrospectiva) 2025 a 2026-10-24.",
    "As janelas posteriores já foram consultadas em pesquisas anteriores, portanto **não são holdouts genuinamente inéditos**.",
    "Risco planejado 0,75% por entrada, exposição nocional máxima 2x, entrada somente na abertura seguinte, stop/alvo ATR, permanência máxima 80 candles D1.",
    "Custos por giro completo de 5–15 bp no nocional, com cenário alternativo de custos em dobro. Slippage real, swaps, impostos, variações de contrato e restrições de margem FBS não reproduzidos.",
    "",
    "## Pré-seleção apenas com desenvolvimento + validação",
    "",
    "| Mercado | Melhor estratégia elegível | Dev. | Validação | Revisão 2025–26 | Custos x2 na revisão | Drawdown rev. |",
    "|---|---|---:|---:|---:|---:|---:|"]
    for k,p in out["selected"].items():
        if p is None:lines.append(f"| {k} | Nenhuma passou nas exigências | — | — | — | — | — |")
        else:
            a=p["development"];v=p["validation"];r=p["review"];x=p["review_fees_x2"]
            lines.append(f'| {k} | {p["strategy"]} | {a["return_pct"]:+.2f}% | {v["return_pct"]:+.2f}% | {r["return_pct"]:+.2f}% | {x["return_pct"]:+.2f}% | {r["drawdown_pct"]:.2f}% |')
    lines+=["","## Distribuição de resultados (não ocultar as perdas)",
      "", "| Mercado | Positivos desenvolvimento | Positivos validação | Positivos revisão | Resistentes a custos em dobro na revisão |",
      "|---|---:|---:|---:|---:|"]
    for market in MARKETS:
        trials=[x for x in out["trials"] if x["market"]==market]
        lines.append(f"| {market} | {sum(x['development']['pnl']>0 for x in trials)}/10 | "
            f"{sum(x['validation']['pnl']>0 for x in trials)}/10 | "
            f"{sum(x['review']['pnl']>0 for x in trials)}/10 | "
            f"{sum(x['review_fees_x2']['pnl']>0 for x in trials)}/10 |")
    lines+=["","## Avaliação",
      "",
      "Retornos anuais altos em backtest **não são** prova de estabilidade. É permitido ter meses negativos. Os filtros exigem expectativa líquida positiva, perdas limitadas e resistência ao dobro dos custos na validação.",
      "Sem dados de ordens da corretora, a avaliação é *research only*. Nenhuma candidata será ativada em conta real ou promovida automaticamente para a carteira de sinais futuros.",
      "",
      "Fontes científicas: Moskowitz et al. (2012) — time series momentum; Moreira & Muir (2017) — volatility managed portfolios; Bailey & López de Prado (2014) — selection bias.",
      "",
      "Dados: Yahoo Finance diário, EURUSD=X / JPY=X (indicativos); GC=F / ES=F / CL=F (futuros, não equivalentes a CFDs da FBS).",
      ""]
    return "\n".join(lines)

def main():
    dataset={};features={};coverage={};trials=[]
    for market,asset in MARKETS.items():
        bars=load_daily(asset)
        dataset[market]=bars;features[market]=build(bars)
        coverage[market]={"ticker":asset.ticker,"total_daily":len(bars),
            "start":datetime.fromtimestamp(bars[0]["ts"],timezone.utc).date().isoformat(),
            "end":datetime.fromtimestamp(bars[-1]["ts"],timezone.utc).date().isoformat()}
        for period,(start,end) in PERIODS.items():
            n=sum(epoch(start)<=b["ts"]<epoch(end) for b in bars)
            if n<190:raise RuntimeError(f"{market}: {period} has only {n} daily bars")
        print(market,coverage[market],flush=True)
    for market in MARKETS:
        for name in KEYS:
            a={period:run(market,name,dataset[market],features[market],period)
               for period in PERIODS}
            a["validation_fees_x2"]=run(market,name,dataset[market],features[market],"validation",2)
            a["review_fees_x2"]=run(market,name,dataset[market],features[market],"review",2)
            trials.append({"market":market,"strategy":name,**a})
            print(market,name,*(f'{p}:{a[p]["return_pct"]:+.2f}%' for p in PERIODS),flush=True)
    selected={}
    for market in MARKETS:
        eligible=[x for x in trials if x["market"]==market and
                 qualify_train(x["development"]) and
                 qualify_valid(x["validation"],x["validation_fees_x2"])]
        # Validation used only for eligibility; rank by development risk-adjusted expectancy.
        chosen=sorted(eligible,key=lambda x:(x["development"]["pnl"]/(1+x["development"]["drawdown_pct"]),-x["development"]["drawdown_pct"]),reverse=True)
        selected[market]=chosen[0] if chosen else None
    out={"disclaimer":"historical synthetic execution; not FBS, no guarantee",
        "selection_not_pristine_holdout":True,"periods":PERIODS,
        "capital_usd_per_strategy":BANK,"risk_per_trade":RISK,
        "max_notional_leverage":MAX_LEVERAGE,"turn_cost_bps":FEES_BPS,
        "trials_count":len(trials),"markets":coverage,
        "selected":selected,"trials":trials}
    folder=Path("research/results");folder.mkdir(parents=True,exist_ok=True)
    (folder/"regime_research_v3.json").write_text(json.dumps(out,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    (folder/"regime_research_v3.md").write_text(report(out),encoding="utf8")
    print("V3_COMPLETE",flush=True)
if __name__=="__main__":main()
