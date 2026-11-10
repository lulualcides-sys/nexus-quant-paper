"""Audit effect of unauthorized 20-candle automatic close on user Stop Win/Red.

Never optimize periods/stops with results; do not approve a profitable month
without new untouched evidence, broker source or confirmed user rules.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import random

from research.xau_pa_m5_context_m1_v6 import JUNE,JULY,DAYS
from research.xau_pa_exit_fidelity_audit import ARMS,COSTS


def ledger(days,arm,cost):
    signals=0;trades=[];per_day=[];rejected=Counter()
    for day in days:
        x=day["results"][arm]["costs"][cost]
        n=day["results"][arm]["signals"]
        if (x["signals"]!=n or x["filled"]!=len(x["trades"])
            or x["filled"]>n or
            abs(x["net_usd_per_oz"]-
                sum(t["net_usd_per_oz"] for t in x["trades"]))>.001):
            raise ValueError("Ledger cannot support reported PnL")
        signals+=n;trades.extend(x["trades"])
        per_day.append(x["net_usd_per_oz"])
        rejected.update(x["rejected"])
    gain=sum(max(t["net_usd_per_oz"],0) for t in trades)
    loss=-sum(min(t["net_usd_per_oz"],0) for t in trades)
    rng=random.Random(20261110)
    boots=sorted(sum(rng.choices(per_day,k=len(per_day))) for _ in range(2000))
    return {
        "days":len(days),"signals":signals,
        "filled":len(trades),"wins":sum(t["net_usd_per_oz"]>0 for t in trades),
        "losses":sum(t["net_usd_per_oz"]<0 for t in trades),
        "net_usd_per_oz":round(gain-loss,6),
        "profit_factor":round(gain/loss,6) if loss else None,
        "expectancy_per_trade":round((gain-loss)/len(trades),6) if trades else None,
        "stop_exits":sum(t["reason"]=="STOP" for t in trades),
        "target_exits":sum(t["reason"]=="TARGET" for t in trades),
        "time_exits":sum(t["reason"]=="TIME" for t in trades),
        "session_end_exits":sum(t["reason"]=="SESSION_END" for t in trades),
        "daily_net_bootstrap_95pct":[round(boots[49],5),round(boots[1949],5)],
        "execution_rejections":dict(sorted(rejected.items())),
        "pnl_by_setup":{
            name:{"fills":sum(t["setup"]==name for t in trades),
                  "net_usd_per_oz":round(
                      sum(t["net_usd_per_oz"] for t in trades if t["setup"]==name),6)}
            for name in ("break_retest","range_rejection")
        },
    }


def report(root):
    root=Path(root)
    valid={"june":[],"july":[]};missing=[]
    for d in DAYS:
        good=root/f"time_exit_{d}.json"
        bad=root/f"quarantine_{d}.json"
        if good.is_file()==bad.is_file():
            raise ValueError("Incomplete or contradictory complete source day "+d)
        if bad.is_file():
            row=json.loads(bad.read_text(encoding="utf-8"))
            if (row.get("day")!=d or row.get("excluded_entire_day") is not True
                or row.get("trades_counted")!=0 or not row.get("reason")):
                raise ValueError("Bad source quarantined incompletely")
            missing.append(row);continue
        record=json.loads(good.read_text(encoding="utf-8"))
        if (record.get("day")!=d or
            record.get("same_signal_list_in_both_arms") is not True or
            record.get("original_v6_reproduced_exactly") is not True or
            record.get("time_exit_not_user_confirmed") is not True or
            record.get("original_stop_target_prices_unchanged") is not True or
            record.get("no_manual_user_drawings") is not True or
            record.get("not_real_mt5_broker_executions") is not True or
            record.get("live_approved") is not False or
            record.get("session_start_utc")!="12:00" or
            record.get("session_end_utc")!="21:00" or
            len(record.get("source",{}).get("sha256",""))!=64 or
            record.get("source",{}).get("date_utc")!=d or
            set(record.get("results",{}))!=set(ARMS)):
            raise ValueError("Unverified execution assumptions or input file")
        if record.get("quote_gaps",{}).get("total_execution_quotes",0)<1500:
            raise ValueError("Insufficient execution quotes")
        for arm in ARMS:
            if set(record["results"][arm]["costs"])!=set(COSTS):
                raise ValueError("Missing standard/stress economic assumptions")
        if record["results"][ARMS[0]]["signals"]!=record["results"][ARMS[1]]["signals"]:
            raise ValueError("Signals fabricated or dropped")
        valid["june" if d in JUNE else "july"].append(record)
    if min(map(len,valid.values()))<4:
        raise ValueError("Insufficient whole-day evidence")
    count=Counter()
    max_gap=0.
    for rows in valid.values():
        for row in rows:
            count["large_quote_gaps"]+=row["quote_gaps"]["gaps_over_one_minute"]
            max_gap=max(max_gap,row["quote_gaps"]["largest_gap_seconds"] or 0)
    result={
        arm:{
            cost:{
                month:ledger(rows,arm,cost)
                for month,rows in valid.items()
            } for cost in COSTS
        } for arm in ARMS
    }
    if any(
        result[ARMS[1]][c][month]["time_exits"]!=0
        for c in COSTS for month in valid
    ):
        raise ValueError("Stop-only model still forcibly exits by timeout")
    return {
        "question":"Are 20-bar automatic exits (never confirmed by trader) the cause of losses?",
        "planned_days":{"june":list(JUNE),"july":list(JULY)},
        "clean_days":{k:[v["day"] for v in rows] for k,rows in valid.items()},
        "quarantined_days":missing,
        "quote_integrity":{"gaps_over_60_seconds":count["large_quote_gaps"],
                           "worst_gap_seconds":max_gap},
        "manual_stop_red_and_win_confirmed":False,
        "no_live_broker_execution":True,
        "not_future_OOS":True,
        "auto_trading_approved":False,
        "same_signals_and_prices_for_arms":True,
        "simulated_units":"USD per single theoretical troy ounce",
        "cost_stress":"commission $0.60/oz RT, slippage $0.20/oz each market order, observed BID ASK spread",
        "results":result,
    }


def markdown(r):
    lines=[
        "# Ouro Price Action — auditoria de saída por tempo não autorizada",
        "",
        "É o MESMO robô de rompimento/reteste v6, com as MESMAS entradas "
        "M1 e contexto M5, mesmo preço BID/ASK, Stop Red, Stop Win e "
        "custos. Uma única diferença: braço de controle encerra após "
        "**20 candles M1**; braço auditado mantém a posição até alcançar "
        "**stop ou alvo** ou finalizar a sessão. Não inventa entradas.",
        "",
        f"Junho {len(r['clean_days']['june'])}/5 pregões válidos; "
        f"julho {len(r['clean_days']['july'])}/5 pregões válidos.",
        "",
        "## Custos dobrados, US$/uma onça hipotética",
        "",
        "| Braço | Junho sinais / fills | Junho líquido | Julho sinais / fills | Julho líquido |",
        "|---|---:|---:|---:|---:|",
    ]
    for arm in ARMS:
        j=r["results"][arm]["double"]["june"]
        u=r["results"][arm]["double"]["july"]
        lines.append(f"| {arm} | {j['signals']}/{j['filled']} | "
                     f"{j['net_usd_per_oz']:+.3f} | "
                     f"{u['signals']}/{u['filled']} | "
                     f"{u['net_usd_per_oz']:+.3f} |")
    lines+=["", "## Saídas e risco por modalidade"]
    for arm in ARMS:
        for month,x in r["results"][arm]["double"].items():
            lines.append(
                f"- {arm} {month}: STOP={x['stop_exits']}; WIN/target={x['target_exits']}; "
                f"TIME={x['time_exits']}; SESSION_END={x['session_end_exits']}; "
                f"bloqueios={x['execution_rejections']}; "
                f"bootstrap dia={x['daily_net_bootstrap_95pct']}"
            )
    lines +=[
        "",
        f"Integridade do fluxo: {r['quote_integrity']}. "
        "Nenhum minuto faltante vira preço sintético.",
        "",
        "Stop Red e Stop Win ainda são hipóteses do código: "
        "2R, stop técnico ATR e encerramento na última cotação diária "
        "NÃO foram confirmados pelo usuário. Um resultado positivo ou menos "
        "negativo após retirar saídas por tempo não comprovaria lucro futuro.",
        "",
        "**Sem marcações reais, sem corretora MT5, sem aprovação para operar.**",
        "",
        "## Dias inteiros excluídos por integridade",
    ]
    lines += [f"- {x['day']}: {x['reason']}" for x in r["quarantined_days"]]
    if not r["quarantined_days"]:lines.append("- Nenhum")
    return "\n".join(lines)+"\n"


def cli():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True)
    p.add_argument("--output",required=True)
    args=p.parse_args()
    r=report(args.input)
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    (out/"xau_pa_time_exit_scorecard.json").write_text(
        json.dumps(r,ensure_ascii=False,indent=2)+"\n")
    doc=markdown(r)
    (out/"xau_pa_time_exit_scorecard.md").write_text(doc)
    print(doc)


if __name__=="__main__":
    cli()
