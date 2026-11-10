"""Reproducible historical replay of all 27 *planned* Nexus Quant PAPER robots.

Unlike a strategy-screen surrogate this calls the actual research/paper
position engines. It never reads or writes state/, calls a broker, logs secrets,
sends Telegram, or promotes strategies. Market data are Yahoo proxies.
Historical samples already inspected; NOT independent OOS validation.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from contextlib import ExitStack
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

from src.feed import MARKETS, parse_yahoo
from src.market_quality import validate_bars
from src.strategies import make_indicators
from research.screen_v2 import aggregate_hourly_to_h4
from research.trade_attribution_27 import attribute_trades
from src import gold_forward as gold
from src import leveraged_gold as leveraged
from src import experimental_h1 as h1
from src import bb_rebound_mtf as m15
from src import momentum60_shadow as mom

OUT = Path("research/results/backtest_27_2026-11-01")
HIST_START = int(datetime(2025, 10, 24, tzinfo=timezone.utc).timestamp())
# End date is exclusive. No future candles.
HIST_END = int(datetime(2026, 11, 2, tzinfo=timezone.utc).timestamp())
GROUPS = {"gold_h4":5, "leveraged_h4":5, "experimental_h1":15,
          "usdcad_m15":1, "momentum60_h4":1}
EXPECTED = 27


def _date(ts):
    return datetime.fromtimestamp(ts,timezone.utc).strftime("%Y-%m-%d")


def _fingerprint(rows):
    return hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(",",":")).encode()).hexdigest()


def _validate(rows, seconds, minimum):
    if len(rows) < minimum:
        raise ValueError(f"Histórico insuficiente: {len(rows)} candles, mínimo {minimum}")
    # No constructed or corrected OHLC: reject questionable observations.
    now = int(time.time())
    validate_bars(rows,now=max(now,rows[-1]["time"]+seconds),
                  interval=seconds,min_bars=minimum,
                  max_age=365*86400, continuous=False)
    if rows[-1]["time"]+seconds > now:
        raise ValueError("Candle futuro/incompleto")
    return rows


def _fetch_json(url):
    request=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0",
                                                "Accept":"application/json"})
    with urllib.request.urlopen(request,timeout=30) as response:
        return json.load(response)


def fetch_hourly(market):
    """Yahoo two-year 60m observations, not FBS/CFD executable quotes."""
    ticker=MARKETS[market].ticker
    errors=[]
    # Yahoo may not support 2y H1 for some continuous futures. Falling
    # back to a shorter window is honest: the result records actual coverage,
    # never extrapolates missing bars or swaps underlying instruments.
    for window in ("2y","1y","6mo","3mo"):
        for host in ("query1.finance.yahoo.com","query2.finance.yahoo.com"):
            url=("https://"+host+"/v8/finance/chart/"+quote(ticker,safe="")+
                 "?interval=60m&range="+window)
            try:
                bars=parse_yahoo(_fetch_json(url),int(time.time()))
                checked=_validate(bars,3600,500)
                print("PRICE_WINDOW",market,window,host,flush=True)
                return checked
            except Exception as error:
                errors.append(window+":"+host+":"+type(error).__name__+":"+str(error)[:100])
    raise RuntimeError("; ".join(errors))


def fetch_m15():
    """Only about one month of M15 may be publicly available; do not extend it."""
    errors=[]
    for host in ("query1.finance.yahoo.com","query2.finance.yahoo.com"):
        url=("https://"+host+"/v8/finance/chart/CAD%3DX?interval=15m&range=1mo")
        try:
            rows=m15.parse_15m(_fetch_json(url),int(time.time()))
            return _validate(rows,900,240)
        except Exception as error:
            errors.append(host+":"+type(error).__name__+":"+str(error)[:80])
    raise RuntimeError("; ".join(errors))


def _ledger_result(group, name, book, capital, *, first, last, samples,
                   market, risk, cost_rule, entries=None, window="H1/H4"):
    closed=book["closed"]
    pnls=[float(x["net_usd"]) for x in closed]
    equity=capital
    peak=capital
    drawdown=0.
    wins=sum(p>0 for p in pnls)
    for val in pnls:
        equity+=val
        peak=max(peak,equity)
        if peak>0:
            drawdown=max(drawdown,100*(peak-equity)/peak)
    gains=sum(x for x in pnls if x>0)
    losses=-sum(x for x in pnls if x<0)
    realized=book["equity"]-capital
    # Book equity may have unrounded precision; use it, not summed rounded trades.
    if not isfinite(realized):
        raise ValueError("Saldo não finito")
    fees=0.
    for trade in closed:
        fees += float(trade.get("cost_usd",trade.get("transaction_cost",0.)))
        fees += float(trade.get("funding_cost",0.))
    count=entries if entries is not None else len(closed)+int(book.get("position") is not None)
    return {
        "group":group, "strategy":name, "market":market, "interval":window,
        "status":"historical_replay_not_validated", "paper_only":True,
        "initial_capital_usd":capital, "risk_plan":risk, "cost_assumption":cost_rule,
        "sample_bars":samples, "start_utc":_date(first), "end_utc":_date(last),
        "entries_observed":count, "closed_trades":len(closed),
        "open_at_end":book.get("position") is not None,
        "wins":wins, "losses":sum(p<0 for p in pnls),
        "loss_attribution":attribute_trades(closed),
        "win_rate_pct":round(100*wins/len(closed),2) if closed else None,
        "profit_factor":round(gains/losses,3) if losses else None,
        "net_realized_usd":round(realized,2),
        "net_realized_pct":round(100*realized/capital,3),
        "costs_and_funding_usd":round(fees,2),
        "closed_only_drawdown_pct":round(drawdown,3),
        "note":"P&L realizado de posições fechadas; posições abertas SEM marcação a mercado",
    }


def _h4_replay(hourly, *, stress=1., min_selected_bars=250):
    h4=aggregate_hourly_to_h4(hourly)
    ind=make_indicators(h4)
    selected=[i for i in range(242,len(h4)) if HIST_START<=h4[i]["time"]<HIST_END]
    if min_selected_bars<1:
        raise ValueError("Invalid minimum H4 bars")
    if len(selected)<min_selected_bars:
        raise ValueError("Poucos H4 completos na janela histórica")
    first,last=h4[selected[0]]["time"],h4[selected[-1]]["time"]
    out={}
    base_fee=gold.COST_BPS["XAUUSD"]
    # Temporarily adjust only module-level research cost assumptions, never
    # production source files or any persistent state.
    with ExitStack() as stack:
        stack.enter_context(patch.object(gold,"COST_BPS",{**gold.COST_BPS,"XAUUSD":base_fee*stress}))
        stack.enter_context(patch.object(leveraged,"COST_BPS_ROUNDTRIP",
                                         leveraged.COST_BPS_ROUNDTRIP*stress))
        stack.enter_context(patch.object(mom,"COST_BPS",{**mom.COST_BPS,"XAUUSD":base_fee*stress}))
        normal={k:{"equity":gold.CAPITAL,"position":None,"closed":[]} for k in gold.STUDY}
        leverbooks=leveraged.fresh(h4)["books"]
        candidate=mom.fresh(h4)
        for i in selected:
            for key in gold.STUDY:
                gold.evaluate_bar(normal[key],key,h4,ind,i)
            for key in leveraged.CONFIG:
                leveraged.one_bar(leverbooks[key],key,h4,ind,i,mode=leveraged.LIVE_POLICY)
            mom.step(candidate,h4,ind,i)
        for key in gold.STUDY:
            out["gold_h4:"+key]=_ledger_result(
                "gold_h4",gold.DISPLAY[key],normal[key],gold.CAPITAL,
                first=first,last=last,samples=len(selected),market="XAUUSD (GC=F)",
                risk="0.75% stop planejado, até 1x",cost_rule=f"{base_fee*stress:g} bps ida/volta",window="H4")
        for key,(rule,label) in leveraged.CONFIG.items():
            out["leveraged_h4:"+key]=_ledger_result(
                "leveraged_h4",label,leverbooks[key],leveraged.CAPITAL,
                first=first,last=last,samples=len(selected),market="XAUUSD (GC=F)",
                risk="1.5% stop planejado, 2x nocional",cost_rule=f"{leveraged.COST_BPS_ROUNDTRIP:g} bps base x{stress:g}; financiamento 8% a.a.",window="H4")
        out["momentum60_h4:momentum60"]=_ledger_result(
            "momentum60_h4","Momentum60 candidato",candidate,mom.CAPITAL,
            first=first,last=last,samples=len(selected),market="XAUUSD (GC=F)",
            risk="0.75% stop planejado, até 1x",cost_rule=f"{base_fee*stress:g} bps ida/volta",
            entries=len(candidate["entries"]),window="H4")
    return out


def _h1_replay(market, rows, *, stress=1.):
    inds=make_indicators(rows)
    selected=[i for i in range(h1.WARMUP+1,len(rows))
              if HIST_START<=rows[i]["time"]<HIST_END]
    if len(selected)<200:
        raise ValueError(f"{market}: menos de 200 candles H1 para simular")
    first,last=rows[selected[0]]["time"],rows[selected[-1]]["time"]
    costs=h1.COST_BPS[market]
    books={k:h1.book() for k in h1.STRATEGIES}
    with patch.object(h1,"COST_BPS",{**h1.COST_BPS,market:costs*stress}):
        for i in selected:
            for strategy in h1.STRATEGIES:
                h1.step(books[strategy],market,strategy,rows,inds,i)
    return {"experimental_h1:"+h1.bot_key(market,k):_ledger_result(
        "experimental_h1",f"{market} {title}",books[k],h1.CAPITAL,
        first=first,last=last,samples=len(selected),market=market,
        risk="0.25% stop planejado, até 1x",
        cost_rule=f"{costs*stress:g} bps ida/volta",
        entries=len(books[k]["entries"]),window="H1") for k,title in h1.STRATEGIES.items()}


def _m15_replay(rows, *, stress=1.):
    h1rows=m15.to_h1(rows)
    if len(h1rows)<53:
        raise ValueError("USD/CAD: faltam candles H1 completos")
    h1_ind=make_indicators(h1rows)
    m15_ind=make_indicators(rows)
    selected=[i for i in range(240,len(rows)) if HIST_START<=rows[i]["time"]<HIST_END]
    if len(selected)<80:
        raise ValueError("USD/CAD: faltam candles M15 após aquecimento")
    book=m15.initial(rows)
    # Starting a historical replay differs from production "bootstrap": the
    # state is private/in-memory and starts at the first selected candle.
    book["watermark_m15"]=rows[selected[0]-1]["time"]
    with patch.object(m15,"ROUNDTRIP_PIPS",m15.ROUNDTRIP_PIPS*stress), \
         patch.object(m15,"NET_GREEN_BUFFER_PIPS",m15.NET_GREEN_BUFFER_PIPS*stress):
        for i in selected:
            if rows[i]["time"]-rows[i-1]["time"]!=900 or rows[i-1]["time"]-rows[i-2]["time"]!=900:
                if book["position"] is not None:
                    if not m15.exit_position(book,rows[i]):
                        m15.advance_trailing_stop(book,rows[i])
                else:
                    book["last_reason"]="Intervalo M15 com lacuna; entrada ignorada"
            else:
                m15.step(book,rows,i,h1rows,h1_ind,m15_ind)
            book["watermark_m15"]=rows[i]["time"]
    result=_ledger_result(
        "usdcad_m15","BB20 Pullback H1/M15",book,m15.CAPITAL,
        first=rows[selected[0]]["time"],last=rows[selected[-1]]["time"],
        samples=len(selected),market="USD/CAD (CAD=X)",window="M15",
        risk="0.75% stop planejado, até 1x USD nocional",
        cost_rule=f"{m15.ROUNDTRIP_PIPS*stress:g} pips ida/volta")
    result["coverage_warning"]="Apenas aproximadamente 1 mês de M15; impossível equiparar horizonte ao H4/H1"
    result["entries_observed"]=len(book["closed"])+int(book["position"] is not None)
    result["entries_complete"]=False
    return {"usdcad_m15:bb20":result}


def _placeholder(group,key,market,why):
    return {
        "group":group, "strategy":key, "market":market,
        "status":"unavailable", "paper_only":True,
        "reason":str(why)[:240], "closed_trades":None,
        "entries_observed":None, "net_realized_usd":None,
        "net_realized_pct":None, "closed_only_drawdown_pct":None,
        "win_rate_pct":None, "profit_factor":None,
    }


def all_ids():
    ids={"gold_h4:"+k:("gold_h4","XAUUSD") for k in gold.STUDY}
    ids.update({"leveraged_h4:"+k:("leveraged_h4","XAUUSD") for k in leveraged.CONFIG})
    ids.update({"experimental_h1:"+h1.bot_key(m,k):("experimental_h1",m)
                for m in MARKETS for k in h1.STRATEGIES})
    ids["usdcad_m15:bb20"]=("usdcad_m15","USDCAD")
    ids["momentum60_h4:momentum60"]=("momentum60_h4","XAUUSD")
    if len(ids)!=EXPECTED:
        raise AssertionError(f"Expected {EXPECTED}, found {len(ids)}")
    return ids


def run(*, datasets=None, m15rows=None, obtain=True, stress=True):
    """No fabricated records; partial failures represented as unavailable."""
    expected=all_ids()
    feeds={}
    issues={}
    if datasets is None:
        datasets={}
    if obtain:
        for market in MARKETS:
            try:
                datasets[market]=fetch_hourly(market)
                print(f"PRICE_FEED {market} {len(datasets[market])}",flush=True)
            except Exception as error:
                issues[market]=str(error)[:210]
                print("PRICE_FEED_UNAVAILABLE",market,type(error).__name__,flush=True)
        try:
            m15rows=fetch_m15()
            print("PRICE_FEED USDCAD_M15",len(m15rows),flush=True)
        except Exception as error:
            issues["USDCAD_M15"]=str(error)[:210]
            print("PRICE_FEED_UNAVAILABLE USDCAD_M15",type(error).__name__,flush=True)
    else:
        if m15rows is None: issues["USDCAD_M15"]="M15 não fornecido"
        for m in MARKETS:
            if m not in datasets: issues[m]="H1 não fornecido"
    fingerprints={}
    for m,rows in datasets.items():
        fingerprints[m]={"sha256":_fingerprint(rows),"bars":len(rows),
                         "first":_date(rows[0]["time"]),"last":_date(rows[-1]["time"])}
    if m15rows:
        fingerprints["USDCAD_M15"]={"sha256":_fingerprint(m15rows),"bars":len(m15rows),
                          "first":_date(m15rows[0]["time"]),"last":_date(m15rows[-1]["time"])}

    def replay(multiplier):
        out={}
        if "XAUUSD" in datasets:
            try:
                out.update(_h4_replay(datasets["XAUUSD"],stress=multiplier))
            except Exception as error:
                issues["XAUUSD_H4"]=type(error).__name__+": "+str(error)[:180]
        for market,rows in datasets.items():
            try:
                out.update(_h1_replay(market,rows,stress=multiplier))
            except Exception as error:
                issues[market+"_H1"]=type(error).__name__+": "+str(error)[:180]
        if m15rows:
            try:
                out.update(_m15_replay(m15rows,stress=multiplier))
            except Exception as error:
                issues["USDCAD_M15"]=type(error).__name__+": "+str(error)[:180]
        return out
    base=replay(1.)
    doubled=replay(2.) if stress else {}
    robots={}
    for key,(group,market) in expected.items():
        if key not in base:
            reason=issues.get(market+"_H1" if group=="experimental_h1" else
                              "XAUUSD_H4" if group in ("gold_h4","leveraged_h4","momentum60_h4")
                              else "USDCAD_M15",issues.get(market,"Fonte sem dados válidos"))
            robots[key]=_placeholder(group,key,market,reason)
        else:
            robots[key]=base[key]
            if stress:
                robots[key]["double_cost_net_usd"]=(doubled[key]["net_realized_usd"]
                         if key in doubled else None)
    if len(robots)!=EXPECTED or sum(1 for x in robots.values() if x["group"]=="experimental_h1")!=15:
        raise AssertionError("Wrong research census")
    ready=[v for v in robots.values() if v["status"]!="unavailable"]
    return {
        "study":"Nexus Quant 27 fixed-paper-rule historical replay",
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "planned":EXPECTED,"analyzed":len(ready),"unavailable":EXPECTED-len(ready),
        "groups":GROUPS,"paper_only":True,"broker_orders":False,
        "historical_samples_are_not_independent_holdout":True,
        "window_h1_h4_requested":["2025-10-24","2026-11-02 exclusive"],
        "m15_window":"Actual Yahoo one-month coverage only; not comparable to H1/H4 duration",
        "closed_only_no_unrealized_pnl":True,
        "source":"Yahoo public proxy prices; no FBS fills, no verified execution costs",
        "price_data":fingerprints,"issues":issues,"robots":robots,
        "decision":"NO AUTO PROMOTION. Backtests cannot establish future returns.",
    }


def markdown(result):
    lines=[
        "# Nexus Quant — backtest dos 27 robôs (pesquisa virtual)",
        "",
        f"**{result['analyzed']}/27 avaliados com dados; {result['unavailable']} indisponíveis.**",
        "",
        "Não são trades da FBS; dados públicos de referência, custos estimados, "
        "períodos históricos já examinados. Nenhuma estratégia foi promovida.",
        "P&L apenas realizado em saídas; posições abertas e custos reais da corretora "
        "não aparecem na marcação a mercado.",
        "M15 usa janela diferente (histórico curto); não comparar diretamente valores absolutos.",
        "",
        "| Robô | Grupo | Período observado (UTC) | Entradas | Fechadas | V/D | P&L US$ | Custos ×2 US$ | DD realizado |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for key,value in result["robots"].items():
        if value["status"]=="unavailable":
            lines.append(f"| {key} | {value['group']} | SEM DADOS | — | — | — | — | — | — |")
            continue
        vd=f"{value['wins']}/{value['losses']}"
        stress=value.get("double_cost_net_usd")
        stressed = f"{stress:+.2f}" if stress is not None else "—"
        lines.append(f"| {value['strategy']} | {value['group']} | {value['start_utc']} a {value['end_utc']} | "
                     f"{value['entries_observed']} | {value['closed_trades']} | {vd} | "
                     f"{value['net_realized_usd']:+.2f} | {stressed} | "
                     f"{value['closed_only_drawdown_pct']:.2f}% |")
    lines += ["", "## Atribuição descritiva das perdas por robô", "",
              "O JSON registra saídas, horários UTC de entrada, meses de saída, "
              "custos e as cinco piores operações. Atribuição descritiva "
              "não estabelece causalidade nem justifica filtrar operações retrospectivamente.", "",
              "| Robô | Expectativa US$/fech. | Maior origem de perdas | Perda US$ |",
              "|---|---:|---|---:|"]
    for key, value in result["robots"].items():
        if value["status"] == "unavailable":
            lines.append(f"| {key} | — | SEM DADOS | — |")
            continue
        diag = value["loss_attribution"]
        losers = [(reason, row["total_losing_trades_abs_usd"])
                  for reason, row in diag["by_exit_reason"].items()
                  if row["total_losing_trades_abs_usd"] > 0]
        reason, loss = max(losers, key=lambda item: item[1]) if losers else ("Sem perdas", 0.)
        expectancy = diag["avg_net_usd"]
        exp_label = f"{expectancy:+.5f}" if expectancy is not None else "—"
        lines.append(f"| {key} | {exp_label} | {reason} | {loss:.2f} |")
    lines += ["","## Dados e limitações"]
    for market,meta in result["price_data"].items():
        lines.append(f"- {market}: {meta['bars']} candles; {meta['first']} a {meta['last']}; SHA-256 \x60{meta['sha256']}\x60")
    for market,error in result["issues"].items():
        lines.append(f"- INDISPONÍVEL {market}: {error}")
    lines+=["","A seleção retrospectiva, incluindo Momentum60, não é validação"
            " fora da amostra. É necessário acompanhamento prospectivo, cotações"
            " da corretora, custos reais e testes robustos antes de decisões reais."]
    return "\n".join(lines)+"\n"


def main():
    result=run()
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.with_suffix(".json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    OUT.with_suffix(".md").write_text(markdown(result),encoding="utf-8")
    print("BACKTEST_27_SUMMARY",json.dumps(
        {"analyzed":result["analyzed"],"unavailable":result["unavailable"],
         "robots":{k:{"n":v.get("closed_trades"),
                       "pnl":v.get("net_realized_usd"),
                       "double_cost":v.get("double_cost_net_usd"),
                       "status":v.get("status")} for k,v in result["robots"].items()}},
         ensure_ascii=False,sort_keys=True),flush=True)


if __name__=="__main__":
    main()
