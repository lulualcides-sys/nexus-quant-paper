"""2025-10-24 .. 2026-10-24 one-year backtest with NO FBS fills.

Public 60m bars, next-bar-open execution, intrabar stops, after-cost P&L.
Per robot: USD 5,000 initial virtual balance across five proxy markets.
Run by GitHub Actions to access the market data, never silently fabricate bars.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from urllib.parse import quote
import json
import statistics
import time
import urllib.request

from src.feed import MARKETS, parse_yahoo
from src.strategies import WARMUP, CONFIGS, make_indicators, signal

START=int(datetime(2025,10,24,tzinfo=timezone.utc).timestamp())
END=int(datetime(2026,10,25,tzinfo=timezone.utc).timestamp())
INITIAL=5000.0
RISK=0.0075
MAX_OPEN=3
MAX_ASSET_LEVERAGE=3.0
MAX_PORTFOLIO_LEVERAGE=5.0
STOP_ATR=1.0
TARGET_ATR=1.75
MAX_HOLD_BARS=48
# Round-trip total approximation in basis points of notional (spread+commission+slippage).
# Not broker quotes; FBS costs may differ substantially.
COST_BPS={"EURUSD":3,"USDJPY":3,"XAUUSD":7,"US500":5,"XTIUSD":10}

def get_history(asset, retries=2):
    errors=[]
    for domain in ("query1.finance.yahoo.com","query2.finance.yahoo.com"):
        url=("https://"+domain+"/v8/finance/chart/"+quote(asset.ticker,safe="")+
            "?interval=60m&range=2y")
        for attempt in range(retries):
            try:
                req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0",
                                                        "Accept":"application/json"})
                with urllib.request.urlopen(req,timeout=30) as resp:
                    payload=json.load(resp)
                rows=parse_yahoo(payload,int(time.time()))
                if rows[0]["time"]>START-22*86400:
                    raise ValueError("Sem antecedência suficiente para 240 candles")
                in_test=[b for b in rows if START<=b["time"]<END]
                if len(in_test)<1200:
                    raise ValueError(f"Poucos candles anuais: {len(in_test)}")
                return [b for b in rows if b["time"]<END]
            except Exception as err:
                errors.append(type(err).__name__+":"+str(err)[:100])
                time.sleep(.8)
    raise RuntimeError(f"{asset.name}: dados de 1h indisponíveis ({'; '.join(errors)})")

def bps_cost(asset,qty,entry,exit):
    return (COST_BPS[asset]/10000)*qty*(abs(entry)+abs(exit))/2

def prepare(bars):
    ind=make_indicators(bars)
    if len(ind)!=len(bars):raise ValueError("Indicadores inconsistentes")
    return ind

def simulate(strategy, dataset, inds):
    cash=INITIAL
    peak=INITIAL
    max_dd=0.0
    positions={}
    last_price={}
    closed=[]
    observations=[]
    skipped=Counter()
    # The same robot sees each market at the end of its hourly bar;
    # positions enter only at a later bar open, never at signal close.
    events=sorted((b["time"],asset,i)
                  for asset,bars in dataset.items()
                  for i,b in enumerate(bars)
                  if START<=b["time"]<END)
    for ts,asset,i in events:
        bars=dataset[asset]
        bar=bars[i]
        price=bar["open"]
        last_price[asset]=bar["close"]
        p=positions.get(asset)
        if p is not None:
            low,high=bar["low"],bar["high"]
            stop=p["stop"];target=p["target"]
            if p["side"]==1:
                stop_hit=low<=stop
                target_hit=high>=target
                stop_fill=min(stop,price)  # opening gap through stop
                target_fill=target
            else:
                stop_hit=high>=stop
                target_hit=low<=target
                stop_fill=max(stop,price)
                target_fill=target
            age=i-p["entry_index"]
            reason=None
            if stop_hit:exit_price=stop_fill;reason="STOP (pessimista se TP e SL tocam juntos)"
            elif target_hit:exit_price=target_fill;reason="TAKE PROFIT"
            elif age>=MAX_HOLD_BARS:exit_price=bar["close"];reason="TIME EXIT"
            if reason:
                gross=(exit_price-p["entry"])*p["side"]*p["qty"]
                fee=bps_cost(asset,p["qty"],p["entry"],exit_price)
                pnl=gross-fee
                cash+=pnl
                closed.append({"market":asset,"entry_ts":p["entry_ts"],"exit_ts":ts,
                    "strategy":strategy,"side":p["side"],"entry":round(p["entry"],6),
                    "exit":round(exit_price,6),"size":round(p["qty"],6),
                    "pnl_usd":round(pnl,5),"gross_usd":round(gross,5),
                    "cost_usd":round(fee,5),"reason":reason,"bars_held":age})
                del positions[asset]
        # The previous bar's signal is known only when the new one starts.
        if i>WARMUP and asset not in positions:
            sg=signal(strategy,bars,inds[asset],i-1)
            prev=signal(strategy,bars,inds[asset],i-2)
            if sg!=0 and sg!=prev:
                if len(positions)>=MAX_OPEN:
                    skipped["max_concurrent"]+=1
                else:
                    atr=inds[asset][i-1]["atr"]
                    if atr>0 and isfinite(atr):
                        qty=(max(0,cash)*RISK)/(atr*STOP_ATR)
                        qty=min(qty,max(0,cash)*MAX_ASSET_LEVERAGE/price)
                        exposure=sum(abs(pos["qty"]*last_price.get(k,pos["entry"]))
                                     for k,pos in positions.items())
                        qty=min(qty,max(0,max(0,cash)*MAX_PORTFOLIO_LEVERAGE-exposure)/price)
                        if qty>0 and cash>0:
                            positions[asset]={
                                "entry":price,"side":sg,"qty":qty,
                                "entry_ts":ts,"entry_index":i,
                                "stop":price-sg*STOP_ATR*atr,
                                "target":price+sg*TARGET_ATR*atr
                            }
                        else:
                            skipped["leverage_or_equity"]+=1
        # MTM including assumed round-trip fees for currently open positions.
        mtm=cash+sum((last_price.get(k,p["entry"])-p["entry"])*p["side"]*p["qty"] -
                      bps_cost(k,p["qty"],p["entry"],last_price.get(k,p["entry"]))
                      for k,p in positions.items())
        peak=max(peak,mtm)
        max_dd=max(max_dd,100*(peak-mtm)/peak if peak else 0)
        observations.append((ts,mtm))
    for asset,p in list(positions.items()):
        last=[b for b in dataset[asset] if START<=b["time"]<END][-1]
        exit_price=last["close"]
        gross=(exit_price-p["entry"])*p["side"]*p["qty"]
        fee=bps_cost(asset,p["qty"],p["entry"],exit_price)
        pnl=gross-fee
        cash+=pnl
        closed.append({"market":asset,"entry_ts":p["entry_ts"],"exit_ts":last["time"],
                       "strategy":strategy,"side":p["side"],"entry":round(p["entry"],6),
                       "exit":round(exit_price,6),"size":round(p["qty"],6),
                       "pnl_usd":round(pnl,5),"gross_usd":round(gross,5),
                       "cost_usd":round(fee,5),"reason":"END OF TEST","bars_held":None})
    bymarket=defaultdict(lambda:{"trades":0,"pnl":0,"wins":0,"cost":0})
    for t in closed:
        m=bymarket[t["market"]]
        m["trades"]+=1;m["pnl"]+=t["pnl_usd"];m["cost"]+=t["cost_usd"]
        if t["pnl_usd"]>0:m["wins"]+=1
    sum_pnl=sum(x["pnl_usd"] for x in closed)
    if abs(cash-INITIAL-sum_pnl)>0.03:raise AssertionError("P&L ledger does not reconcile")
    wins=sum(t["pnl_usd"]>0 for t in closed)
    losses=sum(t["pnl_usd"]<0 for t in closed)
    positives=sum(t["pnl_usd"] for t in closed if t["pnl_usd"]>0)
    negatives=-sum(t["pnl_usd"] for t in closed if t["pnl_usd"]<0)
    # Monthly contributions from trades actually closed, not phantom account orders.
    monthly=defaultdict(float)
    for t in closed:
        month=datetime.fromtimestamp(t["exit_ts"],timezone.utc).strftime("%Y-%m")
        monthly[month]+=t["pnl_usd"]
    return {"name":CONFIGS[strategy],"strategy":strategy,"capital":INITIAL,
        "final_usd":round(cash,2),"pnl_usd":round(cash-INITIAL,2),
        "return_pct":round((cash/INITIAL-1)*100,2),
        "max_drawdown_pct":round(max_dd,2),
        "trades":len(closed),"wins":wins,"losses":losses,
        "win_rate_pct":round(wins/len(closed)*100,2) if closed else 0,
        "profit_factor":round(positives/negatives,3) if negatives else None,
        "total_cost_usd":round(sum(t["cost_usd"] for t in closed),2),
        "markets":{key:{"trades":v["trades"],"pnl_usd":round(v["pnl"],2),
                        "wins":v["wins"],"cost_usd":round(v["cost"],2)} for key,v in bymarket.items()},
        "monthly":{k:round(v,2) for k,v in sorted(monthly.items())},
        "skipped":dict(skipped),
        "trades_ledger":sorted(closed,key=lambda t:t["exit_ts"])}

def money(x):
    return f"{x:+,.2f}"
def make_report(result):
    runs=result["robots"]
    lines=[
        "# Nexus Quant | Backtest retrospectivo de 1 ano",
        "",
        "**PERÍODO:** 24/10/2025 a 24/10/2026 (UTC).",
        "**ATENÇÃO:** simulação retrospectiva com preços públicos de referência; "
        "**NÃO são operações da FBS, não há lucro real, nem garantia futura.**",
        "",
        "**Banca por robô:** US$ 5.000 (cada robô pode negociar os cinco mercados). "
        "Risco planejado por entrada: 0,75% do saldo; máximo de 3 posições abertas; "
        "leverage nocional de até 3x por ativo e 5x agregado. "
        "Semposição financiada, sem impostos. Stops sujeitos a saltos de preço.",
        "",
        "**Regras:** candle H1 fechado → entrada na abertura seguinte. "
        "Stop 1 ATR, objetivo 1,75 ATR, tempo máximo 48 candles. "
        "Ambiguidade entre stop/alvo no mesmo candle resolvida a favor do stop. "
        "Custos totais estimados por transação 3–10 pontos-base do valor nocional "
        "(inclui spread/slippage/comissões fictícias; taxas FBS podem divergir).",
        "",
        "| Robô | Operações | Vitórias | Taxa de acerto | Lucro/Prejuízo | Retorno | Maior drawdown | Custos |",
        "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for d in sorted(runs.values(),key=lambda v:v["return_pct"],reverse=True):
        lines.append(f'| {d["name"]} | {d["trades"]} | {d["wins"]} | '
          f'{d["win_rate_pct"]:.1f}% | US$ {money(d["pnl_usd"])} | '
          f'{d["return_pct"]:+.2f}% | {d["max_drawdown_pct"]:.2f}% | '
          f'US$ {d["total_cost_usd"]:,.2f} |')
    lines+=["","## Lucro/prejuízo atribuído a cada mercado",
        "",
        "US$, contribuição ao saldo compartilhado de cada robô; não retorno isolado do ativo.",
        "",
        "| Robô | EUR/USD | USD/JPY | Ouro (GC) | US500 (ES) | WTI (CL) |",
        "|---|---:|---:|---:|---:|---:|"]
    for d in runs.values():
        vals=[d["markets"].get(m,{}).get("pnl_usd",0) for m in MARKETS]
        lines.append("| "+d["name"]+" | "+" | ".join(f"{v:+,.2f}" for v in vals)+" |")
    lines+=["","## Amostra de dados", "", "| Mercado | Ticker de referência | Candles totais | Candles no período | Primeiro candle | Último candle |",
       "|---|---|---:|---:|---|---|"]
    for k,a in result["assets"].items():
        lines.append(f'| {k} | {a["ticker"]} | {a["candles_total"]} | {a["candles_test"]} | {a["first"]} | {a["last"]} |')
    lines+=["", "## Limitações", "",
        "- Ouro (GC=F), S&P500 (ES=F) e WTI (CL=F) são futuros contínuos usados como referência, não CFDs da FBS; rolagem do contrato pode criar saltos.",
        "- EURUSD=X e JPY=X são cotações indicativas; não têm spread e execução reais da FBS.",
        "- Resultado calculado depois de conhecer o ano completo, mas as decisões usam apenas candles anteriores.",
        "- Sem ajuste por swap, tributos, financiamento de margem, microestrutura intrabar, falhas de rede ou restrições específicas da FBS.",
        "- Um único ano pode incluir condições favoráveis demais; não prova persistência de lucro nem equivale a validação fora da amostra.",
        "- O algoritmo não foi calibrado nos dados desse ano e não assume dinheiro depositado em corretora.",
        "",
        "Fonte de candles: endpoints públicos Yahoo Finance Chart (sem SLA; podem mudar).",
        "Mecânica e livros de negociação constam em `research/backtest_year.py` e `research/results/backtest_1y.json`.",
        "",
    ]
    return "\n".join(lines)

def main():
    dataset={}
    assets={}
    for key,a in MARKETS.items():
        bars=get_history(a)
        dataset[key]=bars
        test=[b for b in bars if START<=b["time"]<END]
        assets[key]={"ticker":a.ticker,"candles_total":len(bars),"candles_test":len(test),
             "first":datetime.fromtimestamp(test[0]["time"],timezone.utc).isoformat(),
             "last":datetime.fromtimestamp(test[-1]["time"],timezone.utc).isoformat()}
        print(f"{key}: {len(test)} candles no ano; fonte={a.ticker}",flush=True)
    inds={k:prepare(v) for k,v in dataset.items()}
    robots={}
    for key in CONFIGS:
        d=simulate(key,dataset,inds)
        robots[key]=d
        print(f'{d["name"]}: {d["trades"]} trades / {d["pnl_usd"]:+.2f} USD / DD {d["max_drawdown_pct"]:.2f}%',flush=True)
    result={"scope":"historical retrospective, not FBS fills",
        "start_utc":"2025-10-24","end_exclusive_utc":"2026-10-25",
        "market_data_source":"Yahoo Finance 60m chart API; futures as CFDs proxies",
        "initial_usd_per_robot":INITIAL,"risk_fraction_per_trade":RISK,
        "max_concurrent":MAX_OPEN,"max_asset_leverage":MAX_ASSET_LEVERAGE,
        "max_portfolio_leverage":MAX_PORTFOLIO_LEVERAGE,
        "stop_atr":STOP_ATR,"target_atr":TARGET_ATR,
        "max_hold_bars":MAX_HOLD_BARS,"roundtrip_cost_bps":COST_BPS,
        "assets":assets,"robots":robots}
    dest=Path("research/results")
    dest.mkdir(parents=True,exist_ok=True)
    (dest/"backtest_1y.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    (dest/"backtest_1y.md").write_text(make_report(result),encoding="utf-8")
    print("RESULT_FILE_READY",flush=True)

if __name__=="__main__":
    main()
