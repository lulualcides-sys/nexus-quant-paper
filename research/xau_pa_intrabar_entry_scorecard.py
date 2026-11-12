"""XAUUSD faithful-structure price-action entry timing audit.

Only breakout/retest order timing changes: original end-of-M1-candle market
entry vs live chronological quote touch + observed reaction, next-quote fill.
Preserve lateral-range signal set, stop/target/costs, symbol and M1 timeframe.

No synthetic profits, dates included even if unprofitable, no user-drawn
trendlines or manual broker execution claimed.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import random
from statistics import median

from research.xau_pa_intrabar_retest_execution import MAY,OCT,DAYS,ARMS,COSTS


def ledger(rows,arm,cost):
    all_trades=[];days=[];signals=0;rejections=Counter()
    for r in rows:
        x=r["results"][arm]
        sim=x["costs"][cost]
        if (sim["signals"]!=x["signals"] or
            sim["filled"]!=len(sim["trades"]) or
            sim["filled"]>sim["signals"] or
            sum(x["signal_setups"].values())!=sim["signals"] or
            abs(sim["net_usd_per_oz"]-sum(t["net_usd_per_oz"]
                                          for t in sim["trades"]))>.001):
            raise ValueError("Source trade ledger cannot reproduce financial result")
        signals+=sim["signals"]
        all_trades.extend(sim["trades"])
        days.append(sim["net_usd_per_oz"])
        rejections.update(sim["rejected"])
    win=sum(max(t["net_usd_per_oz"],0) for t in all_trades)
    loss=-sum(min(t["net_usd_per_oz"],0) for t in all_trades)
    rng=random.Random(20261110)
    ci=sorted(sum(rng.choices(days,k=len(days))) for _ in range(2000))
    distances=[]
    completed_bounces=0
    for t in all_trades:
        if t["setup"]!="break_retest":continue
        distance=abs(t["entry"]-t["stop"])
        if distance<=0:
            raise ValueError("Trade has non-positive initial stop distance")
        distances.append(abs(t["entry"]-t["line_retest_level"])/distance)
        if t.get("execution_assumption")=="next quote after observed reaction":
            if not (t["touch_ms"]<=t["signal_ms"]<t["entry_ms"]
                    and t["breakout_ms"]<t["touch_ms"]):
                raise ValueError("Intrabar signal non-causal")
            completed_bounces+=1
    return {
        "days":len(rows),"signals":signals,"filled":len(all_trades),
        "wins":sum(t["net_usd_per_oz"]>0 for t in all_trades),
        "losses":sum(t["net_usd_per_oz"]<0 for t in all_trades),
        "net_usd_per_oz":round(win-loss,6),
        "profit_factor":round(win/loss,6) if loss else None,
        "expectancy_usd_per_oz":round((win-loss)/len(all_trades),6)
            if all_trades else None,
        "stop_exits":sum(t["reason"]=="STOP" for t in all_trades),
        "target_exits":sum(t["reason"]=="TARGET" for t in all_trades),
        "time_exits":sum(t["reason"]=="TIME" for t in all_trades),
        "by_setup":{
            n:{"fills":sum(t["setup"]==n for t in all_trades),
               "net_usd_per_oz":round(sum(t["net_usd_per_oz"] for t in all_trades
                                            if t["setup"]==n),6)}
            for n in ("break_retest","range_rejection")
        },
        "entry_distance_to_retested_line_median_R":
            round(median(distances),6) if distances else None,
        "entries_farther_than_one_R_from_line":sum(d>1 for d in distances),
        "reactions_executed_at_next_quote":completed_bounces,
        "daily_bootstrap_net_95pct":[round(ci[49],5),round(ci[1949],5)],
        "execution_rejections":dict(sorted(rejections.items())),
    }


def audit(folder):
    folder=Path(folder)
    valid={"may":[],"sep_oct":[]}
    exclusions=[]
    for day in DAYS:
        p=folder/f"intrabar_{day}.json"
        q=folder/f"quarantine_{day}.json"
        if p.is_file()==q.is_file():
            raise ValueError("Missing or contradictory full date "+day)
        if q.is_file():
            z=json.loads(q.read_text())
            if z.get("day")!=day or z.get("full_day_quarantine") is not True or z.get("trades_counted")!=0:
                raise ValueError("Session quarantine not properly excluded")
            exclusions.append(z);continue
        x=json.loads(p.read_text())
        if (x.get("day")!=day or
            x.get("same_BID_ASK_execution_quotes") is not True or
            x.get("same_stop_target_cost_rules") is not True or
            x.get("causal_intrabar_reaction_only") is not True or
            x.get("user_manual_levels_verified") is not False or
            x.get("exact_manual_entry_timing_verified") is not False or
            x.get("not_MT5_broker_execution") is not True or
            x.get("approved_for_live") is not False or
            x.get("trading_utc")!="12:00-21:00" or
            x.get("warmup_utc")!="09:00-12:00" or
            x.get("source",{}).get("date_utc")!=day or
            len(x.get("source",{}).get("sha256",""))!=64 or
            set(x.get("results",{}))!=set(ARMS)):
            raise ValueError("Evidence makes unverified execution or profitability claims")
        for arm in ARMS:
            if set(x["results"][arm]["costs"])!=set(COSTS):
                raise ValueError("Missing a cost scenario")
        old=x["results"][ARMS[0]]["signal_setups"].get("range_rejection",0)
        new=x["results"][ARMS[1]]["signal_setups"].get("range_rejection",0)
        if old!=new:
            raise ValueError("Range signals changed in unrelated execution study")
        valid["may" if day in MAY else "sep_oct"].append(x)
    if min(len(arr) for arr in valid.values())<4:
        raise ValueError("Not enough complete dates, no subset optimization")
    result={
        mode:{
            cost:{period:ledger(rows,mode,cost)
                  for period,rows in valid.items()}
            for cost in COSTS
        } for mode in ARMS
    }
    events=Counter()
    for rows in valid.values():
        for row in rows:
            events.update(row["retest_event_counters"])
    return {
        "question":"Does causal price reaction at retested LTA/LTD improve entry price versus waiting full retest M1 candle?",
        "predeclared_dates":{"may":list(MAY),"sep_oct":list(OCT)},
        "clean_days":{key:[r["day"] for r in rows] for key,rows in valid.items()},
        "whole_days_quarantined":exclusions,
        "causal_events":dict(sorted(events.items())),
        "unchanged_range_setup":True,
        "same_costs_stop_target":True,
        "manual_trader_markings_verified":False,
        "real_broker_execution":False,
        "historical_not_true_forward_OOS":True,
        "live_approved":False,
        "units":"USD per one theoretical troy oz, never account equity",
        "stress_costs":"$0.60/oz commission round-trip + $0.20/oz adverse slippage per market fill plus BID/ASK spread",
        "result":result,
    }


def markdown(r):
    lines=[
        "# Price Action XAUUSD — entrada no reteste sem perseguir preço",
        "",
        "Causa observada em revisão de 21 negócios anteriores: distância "
        "mediana entre entrada e linha retestada ≈ **0,95R**; nove entradas "
        "mais afastadas que 1R, com stops frequentemente em poucos minutos.",
        "A experiência NÃO muda a estratégia: continua aguardando rompimento "
        "confirmado de LTA/LTD e reteste; mas testa entrada quando preço "
        "TOCA a linha e REAGE em quotes sucessivos (ordem no próximo quote) "
        "versus aguardar o fechamento do candle inteiro de rejeição.",
        "Sinais de lateralização da v6 preservados sem alteração. "
        "**0,08 ATR de reação intrabar ainda é HIPÓTESE técnica e não "
        "um parâmetro confirmado pelo usuário.**",
        "",
        f"Maio: {len(r['clean_days']['may'])}/5 pregões válidos; "
        f"setembro/outubro: {len(r['clean_days']['sep_oct'])}/5.",
        "",
        "## Cenário de custos DOBRADOS",
        "",
        "| Modelo | Mai sinais/fills | Mai USD/oz | Set/Out sinais/fills | Set/Out USD/oz |",
        "|---|---:|---:|---:|---:|",
    ]
    for name in ARMS:
        m=r["result"][name]["double"]["may"]
        o=r["result"][name]["double"]["sep_oct"]
        lines.append(f"| {name} | {m['signals']}/{m['filled']} | "
                     f"{m['net_usd_per_oz']:+.3f} | "
                     f"{o['signals']}/{o['filled']} | "
                     f"{o['net_usd_per_oz']:+.3f} |")
    lines+=["","## Diagnóstico da distância à linha e execução"]
    for name in ARMS:
        for period,row in r["result"][name]["double"].items():
            lines.append(
                f"- {name}, {period}: fills={row['filled']}, "
                f"acertos={row['wins']}, stops={row['stop_exits']}, "
                f"mediana distância/risco={row['entry_distance_to_retested_line_median_R']}, "
                f"mais distante 1R={row['entries_farther_than_one_R_from_line']}, "
                f"setup={row['by_setup']}, "
                f"bootstrap por dia={row['daily_bootstrap_net_95pct']}"
            )
    lines +=[
        "",
        f"Eventos intrabar auditados: {r['causal_events']}.",
        "O novo sinal só é criado no momento em que um tick CONFIRMADO "
        "se afasta da linha após toque; a ordem simula execução em tick "
        "SEGUINTE, jamais na melhor cotação anterior nem após ver o stop.",
        "Não há dados da corretora do trader, nem suas linhas manuais ou "
        "horários reais de execução. Nenhum período passado é verdadeiro "
        "forward prospectivo. NÃO usar rentabilidade eventual para aprovar.",
        "",
        "## Sessões inteiras excluídas por dados inválidos",
    ]
    lines += [f"- {q['day']}: {q['reason']}" for q in r["whole_days_quarantined"]]
    if not r["whole_days_quarantined"]:lines.append("- Nenhuma")
    return "\n".join(lines)+"\n"


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--evidence",required=True)
    parser.add_argument("--out",required=True)
    args=parser.parse_args()
    r=audit(args.evidence)
    path=Path(args.out);path.mkdir(parents=True,exist_ok=True)
    (path/"xau_intrabar_entry_scorecard.json").write_text(
        json.dumps(r,indent=2,ensure_ascii=False)+"\n")
    doc=markdown(r)
    (path/"xau_intrabar_entry_scorecard.md").write_text(doc)
    print(doc)


if __name__=="__main__":
    main()
