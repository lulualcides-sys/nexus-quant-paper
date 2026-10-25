"""One-year A/B trial of fixed TP/SL against cost-aware GREEN trailing variants.

All alternatives use identical five Group B entry strategies, historical
period, margin size, simulated transactions and funding. Four modes pre-registered ahead of this historical comparison. Trailing updates
take effect ONLY on a later 4h bar. No silent profit guarantees.
"""
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from research.backtest_group_b import liquidate_at_end
from research.backtest_year import get_history, START, END
from research.screen_v2 import aggregate_hourly_to_h4
from src.feed import MARKETS
from src.strategies import make_indicators
from src import leveraged_gold as bot
from src.green_stop import MODES

def simulate(h4,inds,mode):
    first=[b for b in h4 if b["time"]<START]
    test=[(i,b) for i,b in enumerate(h4) if START<=b["time"]<END]
    if len(first)<240 or len(test)<1100:
        raise RuntimeError("H4 sample not sufficient")
    state=bot.fresh(first)
    # There are no open positions at the beginning; no past P&L imported.
    for i,b in test:
        for key in bot.CONFIG:
            bot.one_bar(state["books"][key],key,h4,inds,i,mode=mode)
    for key in bot.CONFIG:
        liquidate_at_end(state["books"][key],test[-1][1])
    summary={}
    for key,(strategy,label) in bot.CONFIG.items():
        b=state["books"][key]
        v=bot.stats(b)
        trades=b["closed"]
        actual_pnl=b["equity"]-bot.CAPITAL
        ledger=sum(t["net_usd"] for t in trades)
        if abs(actual_pnl-ledger)>.05:
            raise AssertionError("Unreconciled net PnL")
        summary[key]={
         "name":label,"strategy":strategy,"trades":len(trades),
         "net_usd":round(actual_pnl,2),
         "return_pct":round(v["return_pct"],2),
         "drawdown_closed_pct":round(v["drawdown_closed_pct"],2),
         "wins":v["wins"],"losses":v["losses"],
         "stop_exits":sum(t["exit_type"]=="STOP" for t in trades),
         "target_exits":sum(t["exit_type"]=="TARGET" for t in trades),
         "funding_usd":round(sum(t["funding_cost"] for t in trades),2),
         "transaction_cost_usd":round(sum(t["transaction_cost"] for t in trades),2),
         "ledger":trades}
    return {"total_pnl_usd":round(sum(x["net_usd"] for x in summary.values()),2),
       "average_return_pct":round(sum(x["return_pct"] for x in summary.values())/len(summary),2),
       "total_trades":sum(x["trades"] for x in summary.values()),
       "total_funding_usd":round(sum(x["funding_usd"] for x in summary.values()),2),
       "total_transaction_cost_usd":round(sum(x["transaction_cost_usd"] for x in summary.values()),2),
       "robots":summary}

def main():
    bars=get_history(MARKETS["XAUUSD"])
    h4=aggregate_hourly_to_h4(bars)
    ind=make_indicators(h4)
    # Historical futures charts may revise/roll between downloads.
    history_hash=hashlib.sha256(json.dumps(h4,sort_keys=True,separators=(",",":")).encode("utf-8")).hexdigest()
    output={}
    for mode in MODES:
        d=simulate(h4,ind,mode)
        output[mode]=d
        print(f'{mode}: 5 robôs US$ {d["total_pnl_usd"]:+.2f}, '
              f'{d["total_trades"]} operações, '
              f'custos US$ {d["total_transaction_cost_usd"]:.2f}',flush=True)
    base=output["fixed"]
    report={
      "type":"retrospective 12-month OHLC A/B research; NOT broker execution",
      "start":"2025-10-24 UTC","end_exclusive":"2026-10-25 UTC",
      "data":"Yahoo GC=F 1h futures proxy aggregated to H4",
      "selection_warning":"Period already consulted in prior Nexus research; not independent out-of-sample",
      "anti_lookahead":"Stops updated after a completed bar; current bar exits against previously active stop",
      "capital_usd_each":bot.CAPITAL,"notional_leverage_each_entry":2,
      "estimated_roundtrip_bps":bot.COST_BPS_ROUNDTRIP,
      "estimated_borrow_apr":bot.ANNUAL_BORROW_APR,
      "history_sha256":history_hash,
      "history_total_h4":len(h4),
      "history_first_utc":datetime.fromtimestamp(h4[0]["time"],timezone.utc).isoformat(),
      "history_last_utc":datetime.fromtimestamp(h4[-1]["time"],timezone.utc).isoformat(),
      "modes":output,
      "reference_fixed_total_usd":base["total_pnl_usd"]
    }
    path=Path("research/results")
    path.mkdir(parents=True,exist_ok=True)
    (path/"group_b_green_stop_ab.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    md=["# Nexus Quant: Grupo B — stop móvel de green versus stop fixo",
      "",
      "**SOMENTE SIMULAÇÃO RETROSPECTIVA. Sem operações reais, sem FBS.**",
      "Cinco robôs, cinco bancas de US$ 5.000, ouro GC=F, H4, exposição virtual 2× por entrada.",
      f"Identificação da série de preços usada neste teste (SHA-256): \\`{history_hash}\\`.".replace("\\\\`","`"),
      "Período 24/10/2025–24/10/2026, 14 bps por operação ida e volta e 8% a.a. de financiamento virtual sobre excedente do saldo.",
      "",
      "### Como funcionam os quatro modos",
      "- **fixed:** stop inicial fixo + take profit 1,75R.",
      "- **green_fixed:** mesmo alvo fixo; após atingir +1R favorável, só no candle seguinte começa a proteger lucro líquido estimado; a partir de +1,5R segue uma distância de 1R.",
      "- **green_runner:** começa a proteger após +1R, trailing após +1,5R, **sem take-profit fixo** (deixa possíveis tendências correrem).",
      "- **green_wide:** proteção após +1,25R, trailing após +2R com distância de 1,35R, **sem take-profit fixo**.",
      "A ativação e ajuste são sempre **após o candle H4 fechar**, não dentro do candle do gatilho. Gaps podem produzir perdas mesmo com stop no green.",
      "",
      "| Variante | P&L total 5 robôs | Diferença do fixo | Trades | Custos transacionais | Financiamento |",
      "|---|---:|---:|---:|---:|---:|"]
    for mode,v in output.items():
        md.append(f'| {mode} | US$ {v["total_pnl_usd"]:+,.2f} | '
           f'US$ {v["total_pnl_usd"]-base["total_pnl_usd"]:+,.2f} | '
           f'{v["total_trades"]} | US$ {v["total_transaction_cost_usd"]:,.2f} | '
           f'US$ {v["total_funding_usd"]:,.2f} |')
    md+=["","### Lucro/prejuízo por robô e modo","","| Robô | Fixo | Green + TP | Green runner | Green wide |",
      "|---|---:|---:|---:|---:|"]
    for key,v in base["robots"].items():
        vals=[output[m]["robots"][key]["net_usd"] for m in MODES]
        md.append("| "+v["name"]+" | "+" | ".join(f'US$ {x:+,.2f}' for x in vals)+" |")
    md+=["","### Limitações importantes","",
       "- Proteger green não garante saída positiva: slippage/gaps, custos ou distância ao preço podem prejudicar o resultado.",
       "- Os candles OHLC não mostram a sequência intrabar; os stops só são atualizados depois do fechamento e os stops ativos têm prioridade sobre alvos simultâneos.",
       "- Não usamos cotação real da FBS, margem real, ordem efetiva nem swap exato; os modelos simulam preços públicos de contratos futuros.",
       "- Amostra já estudada anteriormente: diferenças de retorno não comprovam vantagem futura.",
       "- As cinco estratégias operam ouro e têm risco concentrado e correlacionado.",
       "",
       "Fonte e algoritmo: `research/green_stop_ab.py`, `src/leveraged_gold.py` e `src/green_stop.py`."]
    (path/"group_b_green_stop_ab.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    print("GREEN_AB_READY",flush=True)

if __name__=="__main__":
    main()
