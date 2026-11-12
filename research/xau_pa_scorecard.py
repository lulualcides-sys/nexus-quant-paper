"""Aggregate a frozen XAUUSD PA M1/M5 June 2026 historical experiment.

Does not optimize parameters or approve trading; reports both weeks separately.
Quarantine an entire invalid feed, not individual losing/troubled bars.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import random


DATES=("20260608","20260609","20260610","20260611","20260612",
       "20260615","20260616","20260617","20260618","20260619")


def _stats(rows, timeframe):
    trades=[t for row in rows for t in row["results"][timeframe]["trades"]]
    profit=sum(max(t["net_usd_per_oz"],0) for t in trades)
    loss=-sum(min(t["net_usd_per_oz"],0) for t in trades)
    net=profit-loss
    signals=sum(x["results"][timeframe]["signals"] for x in rows)
    pnl_days=[sum(t["net_usd_per_oz"] for t in x["results"][timeframe]["trades"]) for x in rows]
    profits=Counter(t["reason"] for t in trades)
    setup_groups={}
    for kind in ("break_retest","range_rejection"):
        x=[t for t in trades if t["setup"]==kind]
        setup_groups[kind]={
            "trades":len(x),"wins":sum(t["net_usd_per_oz"]>0 for t in x),
            "net_usd_per_oz":round(sum(t["net_usd_per_oz"] for t in x),6)
        }
    if pnl_days:
        rng=random.Random(20261110)
        boot=sorted(sum(rng.choices(pnl_days,k=len(pnl_days))) for _ in range(3000))
        ci=[round(boot[75],6),round(boot[2924],6)]
    else:ci=[None,None]
    equity=peak=dd=0.
    for t in trades:
        equity+=t["net_usd_per_oz"];peak=max(equity,peak);dd=max(dd,peak-equity)
    return {
        "source_days":len(rows),
        "signals":signals,"filled":len(trades),
        "wins":sum(t["net_usd_per_oz"]>0 for t in trades),
        "losses":sum(t["net_usd_per_oz"]<0 for t in trades),
        "net_usd_per_oz":round(net,6),
        "profit_factor":round(profit/loss,6) if loss>0 else None,
        "expectancy_usd_per_oz":round(net/len(trades),6) if trades else None,
        "bootstrap_day_net_95pct":ci,
        "max_realized_drawdown_usd_per_oz":round(dd,6),
        "exit_reasons":dict(sorted(profits.items())),
        "by_setup":setup_groups,
        "days_with_trades":sum(bool(x["results"][timeframe]["trades"]) for x in rows)
    }


def score(folder: str | Path):
    folder=Path(folder)
    clean=[];quarantine=[]
    for day in DATES:
        success=folder/f"xau_pa_{day}.json"
        failed=folder/f"quarantine_{day}.json"
        if success.is_file()==failed.is_file():
            raise ValueError(f"Missing/ambiguous whole-session evidence for {day}")
        if failed.is_file():
            q=json.loads(failed.read_text(encoding="utf-8"))
            if (q.get("day")!=day or q.get("whole_session_excluded") is not True or
                q.get("trades_included")!=0):
                raise ValueError("Quarantine must exclude all trades")
            quarantine.append(q);continue
        r=json.loads(success.read_text(encoding="utf-8"))
        if (r.get("day")!=day or r["source"].get("date_utc")!=day or
            len(r["source"].get("sha256",""))!=64 or
            r.get("spread_included_bid_ask") is not True or
            r.get("approval_for_live") is not False or
            r.get("is_actual_broker_backtest") is not False or
            set(r["results"])!={"M1","M5"}):
            raise ValueError("Unverifiable source or fabricated approval")
        for tf in ("M1","M5"):
            item=r["results"][tf]
            if item["filled"]!=len(item["trades"]) or item["filled"]>item["signals"]:
                raise ValueError("Fill/accounting mismatch")
            pnl=sum(t["net_usd_per_oz"] for t in item["trades"])
            if abs(pnl-item["net_usd_per_oz"])>.001:
                raise ValueError("Net PnL mismatch")
        clean.append(r)
    first=[x for x in clean if x["day"]<="20260612"]
    second=[x for x in clean if x["day"]>="20260615"]
    if len(clean)<8 or len(first)<4 or len(second)<4:
        raise ValueError("Too many low-quality/missing sessions")
    result={
        "experiment":"WIN Price Action logic adapted to XAUUSD spot M1/M5",
        "dates_planned":list(DATES),"clean_dates":[x["day"] for x in clean],
        "quarantined_sessions":quarantine,
        "tf":{},"not_a_mt5_broker_backtest":True,
        "strictly_historical_not_future_holdout":True,
        "approval_blocked":True,
        "one_ounce_USD_hypothetical":True,
        "notes":[
            "Market orders at first bid/ask quote after completed candle; no next-open ideal price",
            "Risk settings and costs are hypotheses, not WIN contract rules or MT5 broker settings",
            "No margin/swap/rejected orders/verified broker lot size; no auto trading"
        ]
    }
    for tf in ("M1","M5"):
        result["tf"][tf]={
            "all":_stats(clean,tf),
            "first_week":_stats(first,tf),
            "second_week":_stats(second,tf),
        }
    return result


def markdown(r):
    lines=[
        "# Ouro XAUUSD: robô Price Action M1/M5 (rompimento/reteste e lateralização)",
        "",
        f"Janelas fixas: {len(r['dates_planned'])} previstas, "
        f"{len(r['clean_dates'])} válidas, {len(r['quarantined_sessions'])} excluídas integralmente.",
        "",
        "| TF | Sinais | Operações | Vitórias/Derrotas | Líquido US$/oz | PF | Primeira semana | Segunda semana |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for tf,row in r["tf"].items():
        a,b,c=row["all"],row["first_week"],row["second_week"]
        pf="N/D" if a["profit_factor"] is None else f"{a['profit_factor']:.3f}"
        lines.append(f"| {tf} | {a['signals']} | {a['filled']} | "
                     f"{a['wins']}/{a['losses']} | {a['net_usd_per_oz']:+.3f} | "
                     f"{pf} | {b['net_usd_per_oz']:+.3f} | {c['net_usd_per_oz']:+.3f} |")
        for name,setup in a["by_setup"].items():
            lines.append(f"- {tf} {name}: {setup['trades']} trades; "
                         f"resultado {setup['net_usd_per_oz']:+.3f} US$/oz")
    lines.extend([
        "",
        "**Atenção:** resultados simulados por onça, NÃO R$/WIN, nem milhares de USD.",
        "Fonte Dukascopy quote spot; não um feed/conta de corretora MT5.",
        "Comissão hipotética de US$0,30 por onça por ida e volta, "
        "slippage adverso US$0,10 por lado de ordem a mercado, "
        "além de spreads bid/ask observados. Não inclui swap/impacto de liquidez.",
        "As regras adaptaram a geometria de price action de WIN para escala/ATR de ouro; "
        "não são cópia comprovadamente equivalente do robô WIN.",
        "**NÃO APROVADO para operação automática.**",
        "",
        "## Sessões invalidadas (sem escolher trades)",
    ])
    for row in r["quarantined_sessions"]:
        lines.append(f"- {row['day']}: {row['reason']}")
    if not r["quarantined_sessions"]:lines.append("- Nenhuma")
    return "\n".join(lines)+"\n"


def cli():
    p=argparse.ArgumentParser()
    p.add_argument("--folder",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    result=score(args.folder)
    target=Path(args.out);target.mkdir(parents=True,exist_ok=True)
    (target/"xau_pa_june_scorecard.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    report=markdown(result)
    (target/"xau_pa_june_scorecard.md").write_text(report,encoding="utf-8")
    print(report)


if __name__=="__main__":
    cli()
