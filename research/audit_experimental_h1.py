"""Retrospective audit for 15 experimental H1 bots. No broker fills."""
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import json

from src.feed import MARKETS
from src.experimental_h1 import CAPITAL, STRATEGIES, WARMUP, book, step, scorecard, _close
from src.strategies import make_indicators
from research.backtest_year import get_history, COST_BPS

DEST = Path("research/results")
def ts(y,m,d):
    return int(datetime(y,m,d,tzinfo=timezone.utc).timestamp())
TRAIN_START, SPLIT, TEST_END = ts(2024,10,24), ts(2025,10,24), ts(2026,10,25)

def evaluate(market, strategy, bars, indicators, start, end, cost_factor=1):
    indices = [i for i in range(WARMUP+1,len(bars)) if start <= bars[i]["time"] < end]
    if len(indices) < 300:
        raise ValueError(f"{market}: only {len(indices)} bars for study interval")
    b=book()
    peak=CAPITAL
    max_dd=0
    for i in indices:
        step(b,market,strategy,bars,indicators,i)
        p=b["position"]
        value=b["equity"]
        if p is not None:
            last=bars[i]["close"]
            convert=last if market=="USDJPY" else 1.0
            gross=(last-p["entry"])*p["side"]*p["qty"]
            fees=COST_BPS[market]/10000*p["qty"]*(p["entry"]+last)/2
            value+=(gross-fees)/convert
        peak=max(peak,value)
        if peak>0:max_dd=max(max_dd,100*(peak-value)/peak)
    if b["position"]:
        last=bars[indices[-1]]
        _close(b,market,last,last["close"],"EVAL_END")
    stat=scorecard(b)
    stat.update({
        "cost_factor":cost_factor,
        "actual_first_timestamp":bars[indices[0]]["time"],
        "actual_last_timestamp":bars[indices[-1]]["time"],
        "h1_candles_scanned":len(indices),
        "max_mtm_drawdown_pct":round(max_dd,3),
        "forced_end_closes":sum(t["exit_type"]=="EVAL_END" for t in b["closed"]),
        "diagnostics":b["diagnostics"],
        "trade_ledger":b["closed"]
    })
    return stat

def main():
    market_bars={}
    for market,asset in MARKETS.items():
        print("BACKTEST_FETCH",market,asset.ticker,flush=True)
        rows=[b for b in get_history(asset) if b["time"]<TEST_END]
        if rows[0]["time"]>SPLIT-240*86400:
            raise RuntimeError(f"{market}: insufficient historic H1 coverage")
        if sum(SPLIT<=b["time"]<TEST_END for b in rows)<1500:
            raise RuntimeError(f"{market}: short later window")
        market_bars[market]=rows
        print("BACKTEST_CANDLES",market,len(rows),flush=True)
    results=[]
    for market,bars in market_bars.items():
        indicators=make_indicators(bars)
        base_cost=COST_BPS[market]
        for key in STRATEGIES:
            train=evaluate(market,key,bars,indicators,TRAIN_START,SPLIT)
            later=evaluate(market,key,bars,indicators,SPLIT,TEST_END)
            with patch.dict(COST_BPS,{market:base_cost*2}):
                stress=evaluate(market,key,bars,indicators,SPLIT,TEST_END,cost_factor=2)
            results.append({"market":market,"strategy":key,
                            "train":train,"later":later,"later_cost_x2":stress})
            print("BACKTEST_RESULT",market,key,
                  "train",train["net_usd"],"n",train["closed"],
                  "later",later["net_usd"],"n",later["closed"],
                  "stress",stress["net_usd"],flush=True)
    data={
        "schema":1, "created_at":datetime.now(timezone.utc).isoformat(),
        "strategy_parameters_frozen":True,"paper_only":True,"real_broker_orders":0,
        "markets":list(MARKETS),"strategies":list(STRATEGIES),
        "train_dates_utc":["2024-10-24","2025-10-24"],
        "later_dates_utc":["2025-10-24","2026-10-25"],
        "later_is_genuinely_untouched":False,
        "source":"Yahoo H1 public indicative FX/futures proxies; not executable FBS prices",
        "notional":"Fractional derivatives are not executable futures contracts; simulation only",
        "entry_rules":"exact frozen src.experimental_h1 book/step sizing, stops, trailing, 36-bar limit",
        "capital_per_bot_usd":CAPITAL,"cost_bps":COST_BPS,
        "note":"Historical 2025-26 period inspected in other Nexus studies; not independent holdout. "
               "Yahoo retention may truncate early historical data. End-of-evaluation positions "
               "are forcibly closed at the last completed bar. Intrabar paths unknown. "
               "No slippage/commission specific to FBS and no real broker fills.",
        "results":results,
    }
    DEST.mkdir(parents=True,exist_ok=True)
    (DEST/"experimental_h1_backtest_2026-10-30.json").write_text(
        json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    lines=[
        "# Auditoria dos 15 robôs H1 — regras congeladas",
        "",
        "Simulações com preços públicos Yahoo, não ordens da corretora FBS.",
        "Treino: 24/10/2024 a 23/10/2025 UTC. Período posterior: 24/10/2025 a 24/10/2026 UTC.",
        "Período posterior já analisado em outras pesquisas: NÃO é amostra intocada.",
        "Banca US$ 1.000/bot, risco-stop planejado 0,25%/op., exposição máxima 1x.",
        "Stop 1,5 ATR, trailing após 1R, saída até 36 candles H1.",
        "Inclui custos de giro estimados e cenário com custos dobrados.",
        "Gaps e stops estimados, resultados USD; USDJPY convertido de ienes.",
        "Operações em aberto ao fim de cada janela foram forçadas a fechar no último candle.",
        "",
        "| Mercado | Estratégia | Op. treino | Treino US$ | Op. posteriores | Acerto | Posterior US$ | DD MTM | Custo 2x US$ |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        a,b,c=r["train"],r["later"],r["later_cost_x2"]
        lines.append(f"| {r['market']} | {r['strategy']} | {a['closed']} | {a['net_usd']:+.2f} | "
                     f"{b['closed']} | {b['win_rate_pct']:.1f}% | {b['net_usd']:+.2f} | "
                     f"{b['max_mtm_drawdown_pct']:.2f}% | {c['net_usd']:+.2f} |")
    positive_later=sum(r["later"]["net_usd"]>0 for r in results)
    positive_stress=sum(r["later_cost_x2"]["net_usd"]>0 for r in results)
    lines.extend(["",f"**Positivos no período posterior: {positive_later}/15.**",
                  f"**Positivos com custos 2x: {positive_stress}/15.**","",
                  "Nenhuma estratégia aprovada para dinheiro real por este teste.",
                  "Validação prospectiva, dados executáveis e custos da corretora são necessários.",
                  "Não escolher o melhor retrospectivamente como se fosse lucro futuro garantido."])
    (DEST/"experimental_h1_backtest_2026-10-30.md").write_text(
        "\n".join(lines)+"\n",encoding="utf-8")
    print("BACKTEST_COMPLETE",positive_later,positive_stress,flush=True)

if __name__=="__main__":
    main()
