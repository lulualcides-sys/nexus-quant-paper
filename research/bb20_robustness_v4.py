"""Nexus Quant: controlled BB20 H1/M15 five-market robustness sweep.

Exploratory historic PAPER research. Keeps all deployed accounts unchanged.
Uses past-only EMA/ADX/RSI and M15 middle-band touch. Compares trailing
1R, 1.5R and 2R with identical sizing (0.75% planned stop-risk, <=1x
notional), broker-unverified roundtrip costs and gap-aware stop fills.

First 20 evaluation days: development and selection ONLY. Last 20 days:
retrospective validation of preselected rules. Earlier 30-day research
was already inspected; this is NOT an untouched external holdout.
"""
from __future__ import annotations
import bisect
import gzip
import hashlib
import json
import math
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlencode
from src import bb_rebound_mtf as bb
from src.strategies import make_indicators
from research.bb20_five_markets import MARKETS, BANK, RISK, MAX_NOTIONAL, convert_to_usd, position_units

OUT = Path("research/results")
FETCH_DAYS = 59
EVAL_DAYS = 40
DEV_DAYS = 20
FAMILIES = (
    "baseline", "adx18", "adx23", "ema_separation", "strong_trend",
    "wick_rejection", "session_liquid", "adx_session", "volatility",
    "rsi_follow", "adx_wick", "slope20",
)
TRAIL_MULTIPLIERS = (1.0, 1.5, 2.0)
PROFILES = [(f, trail) for f in FAMILIES for trail in TRAIL_MULTIPLIERS]
assert len(PROFILES) == 36


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def fetch(name, config, now):
    path = "/v8/finance/chart/" + quote(config["ticker"], safe="") + "?" + urlencode({
        "interval": "15m", "period1": now-FETCH_DAYS*86400, "period2": now+900,
    })
    errors = []
    for host in ("query1.finance.yahoo.com", "query2.finance.yahoo.com"):
        req = urllib.request.Request("https://"+host+path,headers={
            "User-Agent": "Mozilla/5.0", "Accept": "application/json",
        })
        try:
            with urllib.request.urlopen(req,timeout=28) as response:
                bars=bb.parse_15m(json.load(response),now=now)
            return bars,host
        except Exception as e:
            errors.append(host+": "+type(e).__name__+" "+str(e)[:110])
    raise RuntimeError(" / ".join(errors))


def h1_adx(h1):
    """Wilder ADX and +DI/-DI; index i only uses H1 OHLC through i."""
    strength=[]
    atr=plus=minus=adx=0.
    prev=None
    for idx,b in enumerate(h1):
        if prev is None:
            strength.append((0.,0.,0.))
            prev=b
            continue
        up=b["high"]-prev["high"]
        down=prev["low"]-b["low"]
        p_dm=up if up>down and up>0 else 0.
        m_dm=down if down>up and down>0 else 0.
        true_range=max(b["high"]-b["low"],
                       abs(b["high"]-prev["close"]),abs(b["low"]-prev["close"]))
        alpha=1.0/14
        atr=(1-alpha)*atr+alpha*true_range
        plus=(1-alpha)*plus+alpha*p_dm
        minus=(1-alpha)*minus+alpha*m_dm
        di_plus=100*plus/atr if atr>0 else 0.
        di_minus=100*minus/atr if atr>0 else 0.
        dx=100*abs(di_plus-di_minus)/(di_plus+di_minus) if di_plus+di_minus>0 else 0.
        adx=(1-alpha)*adx+alpha*dx
        strength.append((adx,di_plus,di_minus))
        prev=b
    return strength


def context_filters(family, h1, h1_feats, dmi, j, bars, m15_feats, i, side):
    h=h1[j];ind=h1_feats[j]; candle=bars[i-1]
    atr=ind["atr"]; price=candle["close"]
    trend_gap=abs(ind["e50"]-ind["e200"])/atr if atr>0 else 0.
    adx,up,down=dmi[j]
    directional=(up>down if side>0 else down>up)
    wick_width=candle["high"]-candle["low"]
    body=abs(candle["close"]-candle["open"])
    if side>0:
        rejection=(min(candle["open"],candle["close"])-candle["low"]>=0.35*body
                   and wick_width>0 and (candle["close"]-candle["low"])/wick_width>=.65)
    else:
        rejection=(candle["high"]-max(candle["open"],candle["close"])>=.35*body
                   and wick_width>0 and (candle["high"]-candle["close"])/wick_width>=.65)
    if family=="baseline":
        return True
    if family=="adx18":
        return adx>=18 and directional
    if family=="adx23":
        return adx>=23 and directional
    if family=="ema_separation":
        return trend_gap>=0.5
    if family=="strong_trend":
        return adx>=20 and directional and trend_gap>=0.5
    if family=="wick_rejection":
        return rejection
    if family=="session_liquid":
        return 7 <= datetime.fromtimestamp(candle["time"],timezone.utc).hour < 20
    if family=="adx_session":
        return adx>=18 and directional and 7<=datetime.fromtimestamp(candle["time"],timezone.utc).hour<20
    if family=="volatility":
        return atr >= .95*ind["avg_atr"] and trend_gap>=.25
    if family=="rsi_follow":
        r=m15_feats[i-1]["rsi"]
        return 52<=r<=70 if side>0 else 30<=r<=48
    if family=="adx_wick":
        return adx>=18 and directional and rejection
    if family=="slope20":
        if j<25:return False
        mean_now=sum(b["close"] for b in h1[j-19:j+1])/20
        mean_old=sum(b["close"] for b in h1[j-24:j-4])/20
        return side*(mean_now-mean_old) > .18*atr
    raise ValueError("Unknown profile "+family)


def prepare(bars, now):
    start=now-EVAL_DAYS*86400
    index=bisect.bisect_left([b["time"] for b in bars],start)
    h1=bb.to_h1(bars)
    if index<900 or len(bb.to_h1(bars[:index]))<200:
        raise ValueError("Not enough warmup: %s M15, %s H1" % (index,len(h1)))
    if len(bars)-index<2400 or bars[index]["time"]>start+4*86400:
        raise ValueError("Not enough 40d M15 coverage")
    if bars[-1]["time"]<now-3*86400:
        raise ValueError("Price feed stale")
    if any(bars[k]["time"]<=bars[k-1]["time"] for k in range(1,len(bars))):
        raise ValueError("Timestamps not increasing")
    hfeat=make_indicators(h1)
    mfeat=make_indicators(bars)
    return {
        "bars":bars,"h1":h1,"hfeat":hfeat,"mfeat":mfeat,
        "dmi":h1_adx(h1),
        "h1ends":[b["time"]+3600 for b in h1],
        "eval_start":start,"first":bars[index]["time"],
        "last":bars[-1]["time"],
    }


def simulate(data,config,start,end,family,trail,cost_factor=1.):
    bars=data["bars"];h1=data["h1"]; hfeat=data["hfeat"];mfeat=data["mfeat"]
    start_i=bisect.bisect_left([b["time"] for b in bars],start)
    end_i=bisect.bisect_left([b["time"] for b in bars],end)
    equity=BANK;position=None;closed=[];last_h1=None
    spread=config["cost_price"]*cost_factor
    for i in range(max(2,start_i),end_i):
        b=bars[i];prior=bars[i-1]
        if position is not None:
            side=position["side"]
            hit=(b["low"]<=position["stop"] if side>0 else b["high"]>=position["stop"])
            if hit:
                fill=min(b["open"],position["stop"]) if side>0 else max(b["open"],position["stop"])
                delta=((fill-position["entry"])*side-spread)*position["qty"]
                pnl=convert_to_usd(config,delta,fill)
                equity+=pnl
                closed.append({"entry_ts":position["entry_ts"],"exit_ts":b["time"],
                               "side":side,"net_usd":round(pnl,7),"entry":position["entry"],
                               "exit":fill,"kind":"TRAIL" if position["updates"] else "STOP",
                               "cost_usd":round(convert_to_usd(config,spread*position["qty"],fill),7)})
                position=None
                continue
            # Stop only changes at this completed M15 close, effective next bar.
            if side>0:
                position["best"]=max(position["best"],b["close"])
                proposal=position["best"]-trail*position["initial_r"]
                tightened=max(position["stop"],proposal)
                if tightened>position["stop"]:
                    position["stop"]=tightened;position["updates"]+=1
            else:
                position["best"]=min(position["best"],b["close"])
                proposal=position["best"]+trail*position["initial_r"]
                tightened=min(position["stop"],proposal)
                if tightened<position["stop"]:
                    position["stop"]=tightened;position["updates"]+=1
            continue
        if equity<=0:continue
        if b["time"]-prior["time"]!=900 or prior["time"]-bars[i-2]["time"]!=900:continue
        j=bisect.bisect_right(data["h1ends"],prior["time"])-1
        if j<200 or prior["time"] >= data["h1ends"][j]+3600:continue
        if last_h1 == h1[j]["time"]:continue
        side=bb.h1_trend_confirmation(h1,hfeat,j)
        if not side or not bb.m15_sma20_pullback(bars,mfeat,i,side):continue
        if not context_filters(family,h1,hfeat,data["dmi"],j,bars,mfeat,i,side):continue
        entry=b["open"]
        risk_dist=max(bb.STOP_ATR*hfeat[j]["atr"],6*config["min_tick"])
        if risk_dist<=0 or entry<=0:continue
        qty=position_units(config,equity,entry,risk_dist)
        if not math.isfinite(qty) or qty<=0:continue
        position={"side":side,"entry":entry,"entry_ts":b["time"],
                  "initial_r":risk_dist,"stop":entry-side*risk_dist,
                  "best":entry,"qty":qty,"updates":0}
        last_h1=h1[j]["time"]
        # Fill at current M15 open; intrabar stop tests follow.
        if (b["low"]<=position["stop"] if side>0 else b["high"]>=position["stop"]):
            fill=min(b["open"],position["stop"]) if side>0 else max(b["open"],position["stop"])
            pnl=convert_to_usd(config,((fill-entry)*side-spread)*qty,fill)
            equity+=pnl
            closed.append({"entry_ts":position["entry_ts"],"exit_ts":b["time"],
                           "side":side,"net_usd":round(pnl,7),"entry":entry,
                           "exit":fill,"kind":"STOP","cost_usd":round(convert_to_usd(config,spread*qty,fill),7)})
            position=None
        else:
            if side>0:
                tightened=max(position["stop"],b["close"]-trail*risk_dist)
            else:
                tightened=min(position["stop"],b["close"]+trail*risk_dist)
            if tightened!=position["stop"]:
                position["stop"]=tightened;position["updates"]+=1
            position["best"]=max(entry,b["close"]) if side>0 else min(entry,b["close"])
    wins=[x for x in closed if x["net_usd"]>0];losses=[x for x in closed if x["net_usd"]<0]
    gross_wins=sum(x["net_usd"] for x in wins)
    gross_losses=sum(x["net_usd"] for x in losses)
    running=peak=BANK;max_dd=0.
    for x in closed:
        running+=x["net_usd"]
        peak=max(peak,running)
        max_dd=max(max_dd,100*(peak-running)/peak)
    mark=None
    if position and end_i>0:
        last_close=bars[end_i-1]["close"]
        theoretical=((last_close-position["entry"])*position["side"]-spread)*position["qty"]
        mark=convert_to_usd(config,theoretical,last_close)
    return {
        "trades":len(closed),"greens":len(wins),"reds":len(losses),
        "accuracy_pct":round(100*len(wins)/len(closed),2) if closed else None,
        "net_usd":round(equity-BANK,5),
        "net_pct":round(100*(equity-BANK)/BANK,4),
        "mark_usd":round(mark,5) if mark is not None else None,
        "mtm_usd":round(equity-BANK+(mark or 0),5),
        "profit_factor":round(gross_wins/-gross_losses,4) if gross_losses<0 else None,
        "max_realized_dd_pct":round(max_dd,4),
        "estimated_cost_usd":round(sum(x["cost_usd"] for x in closed),4),
        "best_trade_usd":max((x["net_usd"] for x in closed),default=None),
        "worst_trade_usd":min((x["net_usd"] for x in closed),default=None),
        "open_position":bool(position),
    }


def aggregate(per_market):
    ok=[v for v in per_market.values() if v.get("status")!="unavailable"]
    wins=sum(x["greens"] for x in ok)
    reds=sum(x["reds"] for x in ok)
    trades=sum(x["trades"] for x in ok)
    profit=sum(x["net_usd"] for x in ok)
    positive=sum(x["net_usd"]>0 for x in ok)
    # This is net of per-market costs, not a single executable basket.
    return {"covered":len(ok),"trades":trades,"greens":wins,"reds":reds,
            "accuracy_pct":round(100*wins/trades,2) if trades else None,
            "net_usd":round(profit,5),
            "mtm_usd":round(sum(x["mtm_usd"] for x in ok),5),
            "positive_markets":positive,
            "worst_market_net_usd":min((x["net_usd"] for x in ok),default=None),
            "worst_market_dd_pct":max((x["max_realized_dd_pct"] for x in ok),default=None)}


def run():
    now=int(time.time())
    start=now-EVAL_DAYS*86400
    midpoint=start+DEV_DAYS*86400
    stamp=datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sources={}; missing={}
    for name,config in MARKETS.items():
        try:
            bars,host=fetch(name,config,now)
            sources[name]={"host":host,"bars":bars,"data":prepare(bars,now),
                           "sha256":hashlib.sha256(json.dumps(bars,sort_keys=True,separators=(",",":")).encode()).hexdigest()}
            print("OBSERVED="+json.dumps({"market":name,"bars":len(bars),
                  "first":iso(bars[0]["time"]),"last":iso(bars[-1]["time"])}))
        except Exception as e:
            missing[name]=type(e).__name__+": "+str(e)[:240]
            print("MISSING="+json.dumps({"market":name,"reason":missing[name]}))
    if len(sources)<5:
        # No cherry-picking available markets. Save explicit status and fail.
        OUT.mkdir(parents=True,exist_ok=True)
        p=OUT/("bb20_robustness_"+stamp+".json")
        p.write_text(json.dumps({"status":"incomplete","missing":missing,
            "available":list(sources),"require_all_five":True},indent=2)+"\n")
        raise RuntimeError("5/5 original markets required; research incomplete")
    analyses={}
    for family,trail in PROFILES:
        label=family+"__trail_"+str(trail).replace(".","p")+"R"
        halves={}
        for part,lo,hi in (("train",start,midpoint),("validation",midpoint,now+60),("full",start,now+60)):
            per={name:simulate(obj["data"],MARKETS[name],lo,hi,family,trail) for name,obj in sources.items()}
            halves[part]={"aggregate":aggregate(per),"markets":per}
        analyses[label]={"family":family,"trail_R":trail,**halves}
        tr=halves["train"]["aggregate"];val=halves["validation"]["aggregate"]
        print("CANDIDATE="+json.dumps({"id":label,"train_n":tr["trades"],
            "train_pnl":tr["net_usd"],"train_positive_markets":tr["positive_markets"],
            "validation_n":val["trades"],"validation_pnl":val["net_usd"]}))
    # Freeze selection purely from FIRST 20 days; do not use validation scores.
    eligible=[]
    for name,d in analyses.items():
        tr=d["train"]["aggregate"]
        if tr["covered"]!=5 or tr["trades"]<45 or tr["positive_markets"]<3 or tr["net_usd"]<=0:
            continue
        if tr["worst_market_dd_pct"]>5:
            continue
        eligible.append((tr["net_usd"] - max(0,tr["worst_market_dd_pct"]-2)*3,name))
    eligible.sort(reverse=True)
    winner=eligible[0][1] if eligible else None
    chosen=analyses[winner] if winner else None
    baseline=analyses["baseline__trail_1p0R"]
    validation=chosen["validation"]["aggregate"] if chosen else None
    approved=bool(validation and validation["covered"]==5
        and validation["trades"]>=45
        and validation["positive_markets"]>=3
        and validation["net_usd"]>0
        and validation["worst_market_dd_pct"]<=5)
    # A positive validation does not prove return, as same era was inspected.
    result={
        "status":"complete","generated_utc":iso(now),
        "dates":{"start":iso(start),"split":iso(midpoint),"end":iso(now)},
        "markets":list(MARKETS),
        "per_market_initial_virtual_usd":BANK,
        "source":{"kind":"Yahoo 15m indicative, not FBS, fractional future notional"},
        "market_data":{name:{"ticker":MARKETS[name]["ticker"],
            "observations":len(obj["bars"]),"first":iso(obj["bars"][0]["time"]),
            "last":iso(obj["bars"][-1]["time"]),"sha256":obj["sha256"],
            "roundtrip_cost_price_units":MARKETS[name]["cost_price"]}
            for name,obj in sources.items()},
        "research":{"candidate_families":list(FAMILIES),"trailing_R":list(TRAIL_MULTIPLIERS),
            "candidates":len(PROFILES),
            "selection":"first 20d only: >=45 trades, >=3 positive markets, net >0, worst DD <=5%; highest net minus DD penalty",
            "validation":"last 20d: >=45 trades, >=3 positive markets, net>0, worst DD<=5%",
            "validation_caveat":"Previously observed calendar period; retrospective validation is not untouched OOS",
            "no_production_switch":True,
            "chosen_on_development":winner,"validation_criteria_passed":approved,
            "recommendation":"continue paper research; no claim of proven edge or guaranteed profit"},
        "baseline":baseline,
        "candidates":analyses,
    }
    # Cost stress only chosen and baseline, using doubled assumed roundtrip friction.
    for label in (winner,"baseline__trail_1p0R"):
        if label is None:continue
        d=analyses[label]; family=d["family"];trail=d["trail_R"]
        d["double_cost_validation"]={
            "aggregate":aggregate({name:simulate(obj["data"],MARKETS[name],
                midpoint,now+60,family,trail,cost_factor=2.) for name,obj in sources.items()})
        }
    OUT.mkdir(parents=True,exist_ok=True)
    prefix="bb20_robustness_"+stamp
    (OUT/(prefix+".json")).write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    for name,obj in sources.items():
        with gzip.open(OUT/(prefix+"_"+name+"_candles.json.gz"),"wt",encoding="utf-8") as stream:
            json.dump({"ticker":MARKETS[name]["ticker"],"download_utc":iso(now),
                "bars":obj["bars"]},stream,separators=(",",":"))
    lines=[
        "# BB20 — experimento robustez, cinco gráficos, 40 dias",
        "",
        "**Janela:** "+iso(start)+" a "+iso(now)+" (20 dias desenvolvimento, 20 validação retrospectiva).",
        "**Preços:** Yahoo Finance M15, custos estimados, nenhuma operação FBS.",
        "**Hipótese:** no H1 EMA50/200 confirmam lado, M15 toca e reage na SMA20, trailing sem alvo fixo.",
        "**O risco permanece 0,75% planejado e 1x nocional em cada banca independente de US$ 1.000.**",
        "",
        "## Comparação principal",
        "| Variante | Período | Fechadas | Positivas (mercados) | Lucro líquido virtual USD |",
        "|---|---|---:|---:|---:|",
    ]
    for label,d in (("Original",baseline),("Escolhida pelo desenvolvimento",chosen)):
        if not d:continue
        for stage in ("train","validation","full"):
            x=d[stage]["aggregate"]
            lines.append("| %s | %s | %s | %s/5 | %+.2f |" % (
                label if stage=="train" else "",stage,x["trades"],x["positive_markets"],x["net_usd"]))
    lines+=["","**Escolhida por treino:** "+(winner or "NENHUMA superou exigência mínima no desenvolvimento"),
        "**Aprovada pela validação:** "+("SIM apenas como pesquisa; não validar para execução real" if approved else "NÃO"),
        "",
        "## Baseline e candidata, por mercado (validação somente)",
        "| Mercado | Base n | Base % acerto | Base resultado | Selecionada n | Selecionada % acerto | Selecionada resultado |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name in MARKETS:
        b=baseline["validation"]["markets"][name]
        v=chosen["validation"]["markets"][name] if chosen else None
        lines.append("| %s | %s | %s | %+.2f | %s | %s | %s |" % (
            name,b["trades"],b["accuracy_pct"],b["net_usd"],
            v["trades"] if v else "—",
            v["accuracy_pct"] if v else "—",
            ("%+.2f" % v["net_usd"]) if v else "—"))
    lines+=["","## Todos os 36 testes - desenvolvimento e validação",
        "| Família | Trailing R | Dev operações | Dev saldo USD | Val operações | Val saldo USD | Val positivos |",
        "|---|---:|---:|---:|---:|---:|---:|"]
    for name,d in analyses.items():
        a=d["train"]["aggregate"];b=d["validation"]["aggregate"]
        lines.append("| %s | %.1f | %s | %+.2f | %s | %+.2f | %s/5 |" % (
            d["family"],d["trail_R"],a["trades"],a["net_usd"],
            b["trades"],b["net_usd"],b["positive_markets"]))
    lines+=["","## Advertências",
        "- Exploramos 36 combinações; selecionar a melhor no treino cria risco de overfitting.",
        "- Os dados de validação pertencem a um período parcialmente investigado anteriormente.",
        "- Mesmo um resultado positivo não valida operações reais nem rentabilidade recorrente.",
        "- Futuros GC=F, ES=F e CL=F usam exposição fracionária fictícia; não representam contratos executáveis com US$ 1.000.",
        "- Yahoo não fornece os bid/ask e a liquidez FBS; spreads e slippage reais podem ser maiores.",
        "- Todos os cinco gráficos foram exigidos; nenhuma falha foi substituída por lucro zero.",
        "- Stops simulados com gaps adversos e avanço pelo fechamento M15 posterior, sem olhar o futuro.",
        "- OHLC originais preservados em arquivos compactados por ticker para auditoria.",
        "- **Nenhuma configuração nova foi ativada automaticamente nos robôs de produção virtual.**",
        ""]
    (OUT/(prefix+".md")).write_text("\n".join(lines),encoding="utf-8")
    print("RESEARCH_SUMMARY="+json.dumps({
        "selected_train_only":winner,"validation_passed":approved,
        "baseline_development":baseline["train"]["aggregate"],
        "baseline_validation":baseline["validation"]["aggregate"],
        "chosen_development":chosen["train"]["aggregate"] if chosen else None,
        "chosen_validation":validation,
        "chosen_double_cost_validation":chosen.get("double_cost_validation") if chosen else None
    },ensure_ascii=False))


if __name__=="__main__":
    run()
