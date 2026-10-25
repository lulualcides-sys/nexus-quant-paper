"""Reproducible one-year Group B backtest using EXACT src.leveraged_gold rules.

Does NOT change production books or send Telegram messages. Prices are public
Yahoo GC=F continuous futures proxy candles, not FBS CFD prices. The annual
period was inspected in earlier research and is NOT fresh out-of-sample data.
Public price series can change, so archived reports should record their candle fingerprint.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

from research.backtest_year import get_history, START, END
from research.screen_v2 import aggregate_hourly_to_h4
from src.feed import MARKETS
from src.strategies import make_indicators
from src import leveraged_gold as bot

def _date(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

def liquidate_at_end(book, candle):
    """Mark positions to market at last test close, with transaction and borrow costs."""
    p=book["position"]
    if p is None:
        return None
    t=candle["time"]
    fill=candle["close"]
    gross=(fill-p["entry"])*p["side"]*p["qty"]
    fee=bot.COST_BPS_ROUNDTRIP/10000*p["qty"]*((p["entry"]+fill)/2)
    funding=p["borrowed"]*bot.ANNUAL_BORROW_APR*max(0,(t-p["start"])/3600)/8760
    net=gross-fee-funding
    book["equity"]+=net
    book["peak_equity"]=max(book["peak_equity"],book["equity"])
    trade={"entry_ts":p["start"],"exit_ts":t,"side":p["side"],
           "entry":round(p["entry"],6),"exit":round(fill,6),
           "net_usd":round(net,5),"gross_usd":round(gross,5),
           "transaction_cost":round(fee,5),"funding_cost":round(funding,5),
           "notional_leverage":round(p["notional_leverage"],4),
           "exit_type":"BACKTEST END (mark-to-market)"}
    book["closed"].append(trade)
    book["position"]=None
    return trade

def execute():
    bars=get_history(MARKETS["XAUUSD"])
    h4=aggregate_hourly_to_h4(bars)
    before=[b for b in h4 if b["time"]<START]
    tests=[(i,b) for i,b in enumerate(h4) if START<=b["time"]<END]
    if len(before)<240 or len(tests)<1100:
        raise RuntimeError(f"Insufficient sample: warmup {len(before)}, annual H4 {len(tests)}")
    ind=make_indicators(h4)
    bookstate=bot.fresh(before)
    # Entry decisions only use information from bars BEFORE trade bar.
    for i,b in tests:
        if i<241:
            raise RuntimeError("Indicator warmup not ready")
        for key in bot.CONFIG:
            bot.one_bar(bookstate["books"][key],key,h4,ind,i)

    last=tests[-1][1]
    results={}
    for key,(strategy,label) in bot.CONFIG.items():
        book=bookstate["books"][key]
        liquidate_at_end(book,last)
        all_trades=book["closed"]
        wins=sum(x["net_usd"]>0 for x in all_trades)
        losses=sum(x["net_usd"]<0 for x in all_trades)
        revenues=sum(x["net_usd"] for x in all_trades if x["net_usd"]>0)
        loss_usd=-sum(x["net_usd"] for x in all_trades if x["net_usd"]<0)
        fees=sum(x["transaction_cost"] for x in all_trades)
        financing=sum(x["funding_cost"] for x in all_trades)
        pnl=book["equity"]-bot.CAPITAL
        if abs(pnl-sum(x["net_usd"] for x in all_trades))>.05:
            raise AssertionError("Ledger and book total do not reconcile")
        metric=bot.stats(book)
        month={}
        for x in all_trades:
            m=datetime.fromtimestamp(x["exit_ts"], timezone.utc).strftime("%Y-%m")
            month[m]=month.get(m,0)+x["net_usd"]
        max_trade_loss=min((x["net_usd"] for x in all_trades),default=0)
        results[key]={"strategy":strategy,"name":label,"initial_usd":bot.CAPITAL,
            "final_usd":round(book["equity"],2),"net_usd":round(pnl,2),
            "return_pct":round(pnl/bot.CAPITAL*100,2),
            "trades":len(all_trades),"wins":wins,"losses":losses,
            "win_rate_pct":round(100*wins/len(all_trades),2) if all_trades else 0,
            "profit_factor":round(revenues/loss_usd,3) if loss_usd>0 else None,
            "max_closed_drawdown_pct":round(metric["drawdown_closed_pct"],2),
            "transaction_cost_usd":round(fees,2),
            "funding_cost_usd":round(financing,2),
            "worst_trade_usd":round(max_trade_loss,2),
            "frozen":book["frozen"],"monthly_net":{k:round(v,2) for k,v in sorted(month.items())},
            "trades_ledger":all_trades}
        print(f'{label}: {len(all_trades)} positions, P&L US$ {pnl:+.2f}, '
             f'return {100*pnl/bot.CAPITAL:+.2f}%, fees {fees:.2f}, finance {financing:.2f}',flush=True)
    result={
       "status":"RETROSPECTIVE simulated historical fills, NEVER FBS broker P&L",
       "reference_asset":"Yahoo GC=F futures proxy; 4h bars aggregated from 1h, not spot CFD",
       "start":"2025-10-24 UTC","end_exclusive":"2026-10-25 UTC",
       "first_observed_bar":_date(tests[0][1]["time"]),
       "last_observed_bar":_date(last["time"]),
       "warmup_candles":len(before),"backtest_candles":len(tests),
       "annual_borrow_apr":bot.ANNUAL_BORROW_APR,
       "roundtrip_transaction_cost_bps":bot.COST_BPS_ROUNDTRIP,
       "nominal_exposure_multiple":bot.TARGET_NOTIONAL_LEVERAGE,
       "max_exposure_multiple":bot.MAX_NOTIONAL_LEVERAGE,
       "risk_limit_per_trade":bot.RISK_FRACTION,
       "daily_entry_loss_limit":bot.DAILY_ENTRY_LOSS_LIMIT,
       "peak_drawdown_entry_freeze":bot.ACCOUNT_ENTRY_DRAWDOWN_LIMIT,
       "closing_note":"Any still-open trade at final H4 close marked to market with assumed trading/borrow fees",
       "caveats":["Retrospective data previously inspected; not fresh out-of-sample",
        "Futures proxy can roll, cannot match FBS CFD fills",
        "Fractional fictitious ounces, not futures contract lot sizes",
        "No real margin call, swap, liquidity, true bid/ask or tick-level stops",
        "Max drawdown recorded on trade closes; intratrade losses may be larger",
        "Borrow fee approximated as 8 percent APR on notional above equity",
        "No guaranteed annual profit or loss; all five strategies trade same asset"],
       "robots":results
    }
    dest=Path("research/results")
    dest.mkdir(parents=True,exist_ok=True)
    (dest/"group_b_leverage_1y.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    rows=[
      "# Nexus Quant — Grupo B, simulação alavancada de 12 meses",
      "",
      "**Todos os valores são SIMULADOS; nenhuma operação foi executada na FBS.**",
      "",
      "Período: 24/10/2025 a 24/10/2026, histórico de futuros GC=F. "
      "O grupo B tem 5 bancas separadas de US$ 5.000, exposição virtual 2× por entrada, "
      "risco-stop planejado 1,5% e trava de entradas após perdas. "
      "Taxa de ida e volta 14 pontos-base e financiamento estimado 8% a.a. "
      "sobre valor emprestado.",
      "",
      "| Robô | Operações | Win rate | Lucro/prejuízo líquido | Saldo final | Retorno 12m | DD fechado | Transação | Financiamento |",
      "|---|---:|---:|---:|---:|---:|---:|---:|---:|"
    ]
    for x in sorted(results.values(),key=lambda r:r["net_usd"],reverse=True):
        rows.append(f'| {x["name"]} | {x["trades"]} | {x["win_rate_pct"]:.1f}% | '
          f'US$ {x["net_usd"]:+,.2f} | US$ {x["final_usd"]:,.2f} | '
          f'{x["return_pct"]:+.2f}% | {x["max_closed_drawdown_pct"]:.2f}% | '
          f'US$ {x["transaction_cost_usd"]:,.2f} | US$ {x["funding_cost_usd"]:,.2f} |')
    combined=sum(v["net_usd"] for v in results.values())
    endtotal=sum(v["final_usd"] for v in results.values())
    rows+=["",f"**Soma hipotética das 5 contas:** US$ {combined:+,.2f} de resultado; "
           f"US$ {endtotal:,.2f} de saldo final sobre US$ 25.000 iniciais. "
           "Não é uma carteira real nem prova de diversificação; as 5 estratégias usam o mesmo ouro.",
           "",
           "## Limitações importantes",
           "",
           "- O intervalo já foi consultado em análises anteriores; há risco de seleção retrospectiva.",
           "- Dados do futuro GC=F não são preços de CFD negociáveis na FBS.",
           "- A estratégia usa stops e alvos analisados por OHLC H4; não há simulação tick-a-tick.",
           "- Não contempla liquidações compulsórias de margem nem os custos exatos de qualquer corretora.",
           "- Uma posição aberta ao final do teste é liquidada virtualmente no último fechamento observado.",
           "- O drawdown informado é realizado em fechamentos; o risco intrabar pode ser maior.",
           "- Resultados dos 5 robôs estão correlacionados; alavancagem amplia resultados positivos e negativos.",
           "",
           "Código executável em `research/backtest_group_b.py` e registro completo no JSON correspondente.",
           ""]
    (dest/"group_b_leverage_1y.md").write_text("\n".join(rows),encoding="utf-8")
    print("GROUP_B_HISTORICAL_RUN_OK",flush=True)

if __name__=="__main__":
    execute()
