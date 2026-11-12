"""Independent period audit for XAU PA v4 without retroactive selection.

Control is the fixed v3 mark-based logic. Treatment is predeclared strict
break/retest & prior multi-touch levels; BOTH use same XAU bid/ask stream,
M1/M5 separately AND shared global symbol lock, standard/doubled costs.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
import random

from research.xau_pa_fidelity_v4 import DAYS,SEPTEMBER,OCTOBER,ARMS,COSTS


def _metric(rows,tf,arm,cost):
    trade_list=[];signal_count=0;veto=Counter();per_day=[]
    for day in rows:
        record=day["results"][tf][arm]
        engine=record["costs"][cost]
        if (record["signals"]!=engine["signals"] or
            engine["filled"]!=len(engine["trades"]) or
            engine["filled"]>engine["signals"] or
            sum(record["setup_signals"].values())!=engine["signals"] or
            abs(engine["net_usd_per_oz"]-
                sum(t["net_usd_per_oz"] for t in engine["trades"]))>.001):
            raise ValueError("Signal or trade ledger audit mismatch")
        if tf=="SHARED" and not engine.get("one_global_position_per_symbol"):
            raise ValueError("Shared executor failed to report a global lock")
        signal_count+=engine["signals"]
        trade_list.extend(engine["trades"])
        per_day.append(sum(x["net_usd_per_oz"] for x in engine["trades"]))
        why=record.get("diagnostics",{})
        if tf!="SHARED":
            nested=why.get("quality_veto_counts",{})
            if not isinstance(nested,dict):
                raise ValueError("Malformed quality diagnostics")
            veto.update(nested)
    wins=[t for t in trade_list if t["net_usd_per_oz"]>0]
    losses=[t for t in trade_list if t["net_usd_per_oz"]<0]
    gain=sum(x["net_usd_per_oz"] for x in wins)
    loss=-sum(x["net_usd_per_oz"] for x in losses)
    net=round(gain-loss,6)
    rng=random.Random(20261110)
    boots=sorted(sum(rng.choices(per_day,k=len(per_day))) for _ in range(3000))
    by_setup={}
    for key in ("break_retest","range_rejection"):
        filtered=[t for t in trade_list if t["setup"]==key]
        by_setup[key]={
            "fills":len(filtered),
            "net_usd_per_oz":round(sum(t["net_usd_per_oz"] for t in filtered),6),
            "wins":sum(t["net_usd_per_oz"]>0 for t in filtered),
        }
    return {
        "days":len(rows),"signals":signal_count,"filled":len(trade_list),
        "wins":len(wins),"losses":len(losses),
        "net_usd_per_oz":net,
        "profit_factor":round(gain/loss,6) if loss else None,
        "expectancy_usd_oz":round(net/len(trade_list),6) if trade_list else None,
        "positive_days":sum(x>0 for x in per_day),
        "negative_days":sum(x<0 for x in per_day),
        "day_bootstrap_95pct":[round(boots[75],6),round(boots[2924],6)],
        "rejects_by_reason":dict(sorted(veto.items())),
        "by_setup":by_setup,
        "exit_reasons":dict(sorted(Counter(x["reason"] for x in trade_list).items())),
    }


def evaluate(root):
    root=Path(root)
    groups={"september":[],"october":[]};quarantined=[];mode=None
    for day in DAYS:
        good=root/f"xau_pa_v4_{day}.json"
        bad=root/f"quarantine_{day}.json"
        if good.is_file()==bad.is_file():
            raise ValueError(f"Missing/ambiguous historical evidence {day}")
        if bad.exists():
            row=json.loads(bad.read_text(encoding="utf-8"))
            if (row.get("day")!=day or row.get("whole_source_excluded") is not True
                or row.get("trades_included")!=0 or not row.get("reason")):
                raise ValueError("Corrupt session must be excluded entirely")
            quarantined.append(row);continue
        r=json.loads(good.read_text(encoding="utf-8"))
        if (r.get("day")!=day or
            r.get("live_trading_approved") is not False or
            r.get("same_quoted_bid_ask_execution") is not True or
            r.get("one_position_globally") is not True or
            r.get("market_feed_not_mt5_broker") is not True or
            r.get("profits_usd_per_theoretical_ounce") is not True or
            r.get("warmup_utc")!="09:00-12:00" or
            r.get("execution_utc")!="12:00-21:00" or
            r["source"].get("date_utc")!=day or
            len(r["source"].get("sha256",""))!=64 or
            r["source"].get("raw_quote_rows",0)<1500 or
            set(r.get("results",{}))!={"M1","M5","SHARED"}):
            raise ValueError("Unverified source, broker or wrong time window")
        if r.get("marking_mode") not in ("proxy","manual"):
            raise ValueError("Incorrect mark provenance")
        if mode is None:mode=r["marking_mode"]
        if mode!=r["marking_mode"]:raise ValueError("Cannot mix user and proxy marks")
        for tf in ("M1","M5","SHARED"):
            if set(r["results"][tf])!=set(ARMS):
                raise ValueError("Incomplete paired comparison")
            for arm in ARMS:
                if set(r["results"][tf][arm]["costs"])!=set(COSTS):
                    raise ValueError("Incomplete costs")
        groups["september" if day in SEPTEMBER else "october"].append(r)
    if min(map(len,groups.values()))<4:
        raise ValueError("Too few validated dates, fail closed")
    result={}
    for tf in ("M1","M5","SHARED"):
        result[tf]={}
        for arm in ARMS:
            result[tf][arm]={
                cost:{
                    name:_metric(rows,tf,arm,cost)
                    for name,rows in groups.items()
                } for cost in COSTS
            }
    return {
        "precommitted_dates":{"september":list(SEPTEMBER),"october":list(OCTOBER)},
        "clean_dates":{m:[x["day"] for x in rows] for m,rows in groups.items()},
        "quarantined_days":quarantined,
        "mark_mode":mode,
        "fidelity_to_user_manual_lines_verified":False,
        "one_shared_position_across_timeframes":True,
        "no_broker_mt5_live_or_demo_fills_verified":True,
        "not_prospective_forward":True,
        "approved_to_trade":False,
        "costs":"double 0.60/oz roundtrip commission +0.20/oz slippage per market side + actual BID/ASK spread",
        "units":"Hypothetical USD per 1 troy oz. Never account return nor 1 lot.",
        "result":result,
    }


def markdown(r):
    lines=[
        "# Price Action XAUUSD v4 — fidelidade causal e entradas de qualidade",
        "",
        "**Controles congelados:** v3 (antes) e v4 (novo), 1 posição global "
        "em XAUUSD, entrada só após candle fechado e reteste real. "
        "V4 exige confirmações de rompimento/rejeição mais fortes, "
        "suportes/resistências com dois pivôs CONFIRMADOS antes da abertura.",
        "",
        f"Setembro {len(r['clean_dates']['september'])}/5 datas válidas; "
        f"outubro {len(r['clean_dates']['october'])}/5 datas válidas.",
        "Marcações: **proxy automático, NÃO as linhas reais do usuário**."
        if r["mark_mode"]=="proxy" else "Marcações: arquivo manual datado; fidelidade ainda não revisada visualmente.",
        "",
        "## Custos DOBRADOS, resultados USD por uma onça hipotética",
        "",
        "| Timeframe | Política | Set sinais / exec | Set líquido US$/oz | Out sinais / exec | Out líquido US$/oz |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for tf in ("M1","M5","SHARED"):
        for arm in ARMS:
            a=r["result"][tf][arm]["double"]
            s=a["september"];o=a["october"]
            lines.append(
                f"| {tf} | {arm} | {s['signals']}/{s['filled']} | "
                f"{s['net_usd_per_oz']:+.3f} | "
                f"{o['signals']}/{o['filled']} | {o['net_usd_per_oz']:+.3f} |"
            )
    lines.extend([
        "",
        "## Motivos de veto e distribuição dos stops e alvos",
    ])
    for tf in ("M1","M5","SHARED"):
        for month,row in r["result"][tf]["v4_confirmed"]["double"].items():
            lines.append(
                f"- {tf} {month}: {row['by_setup']}; "
                f"motivos veto={row['rejects_by_reason']}; "
                f"saídas={row['exit_reasons']}; "
                f"bootstrap por dia={row['day_bootstrap_95pct']}"
            )
    lines.extend([
        "",
        "Sem seleção do vencedor por resultados retrospectivos. "
        "A hipótese v4 foi documentada antes da consulta dessas cotações, "
        "mas os dados são históricos, não teste forward nem corretora MT5. "
        "Custos broker, swap, taxa efetiva, lote real, execução/slippage "
        "e níveis desenhados pelo usuário não foram verificados.",
        "",
        "**Não habilitar ordens automáticas nem aprovar lucro real.**",
        "",
        "## Quarentenas por integridade do feed (sessão inteira)",
    ])
    lines.extend(f"- {q['day']}: {q['reason']}" for q in r["quarantined_days"])
    if not r["quarantined_days"]:lines.append("- Nenhuma")
    return "\n".join(lines)+"\n"


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--folder",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    result=evaluate(args.folder)
    folder=Path(args.out);folder.mkdir(parents=True,exist_ok=True)
    (folder/"xau_pa_fidelity_v4_scorecard.json").write_text(
        json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    md=markdown(result)
    (folder/"xau_pa_fidelity_v4_scorecard.md").write_text(md,encoding="utf-8")
    print(md)


if __name__=="__main__":
    main()
