"""Predeclared independent scorecard for XAUUSD Price Action frequency v2.

Never optimize thresholds or choose a winner using this report. Show all
hypotheses (baseline, structural, pullback, combined), both M1/M5, standard
and stress-cost simulations, all valid dates and full-day quarantines.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import random
from pathlib import Path

from research.xau_pa_frequency_v2 import APRIL,AUGUST,DAYS,ARMS,COSTS


def metrics(records,tf,arm,cost):
    all_trades=[];signals=0;per_day=[];rejection=Counter();raw_setups=Counter()
    for record in records:
        item=record["arms"][tf][arm]
        r=item["costs"][cost]
        if (r["signals"]!=item["signals"] or
            r["filled"]!=len(r["trades"]) or
            r["filled"]>r["signals"] or
            abs(r["net_usd_per_oz"]-
                sum(t["net_usd_per_oz"] for t in r["trades"]))>.001):
            raise ValueError("Mismatch between quote-based ledger and report")
        if sum(item["setups"].values())!=item["signals"]:
            raise ValueError("Setup signal tally differs from total")
        raw_setups.update(item["setups"])
        signals+=item["signals"];all_trades+=r["trades"]
        per_day.append(sum(t["net_usd_per_oz"] for t in r["trades"]))
        rejection.update(r["rejected"])
    gains=sum(max(0,t["net_usd_per_oz"]) for t in all_trades)
    losses=-sum(min(0,t["net_usd_per_oz"]) for t in all_trades)
    net=round(gains-losses,6)
    rng=random.Random(20261110)
    bootstrap=sorted(sum(rng.choices(per_day,k=len(per_day))) for _ in range(3000))
    setup_names=sorted(set(t["setup"] for t in all_trades)|set(raw_setups))
    by_setup={}
    for name in setup_names:
        trades=[t for t in all_trades if t["setup"]==name]
        by_setup[name]={
            "signals":raw_setups.get(name,0),
            "filled":len(trades),
            "wins":sum(t["net_usd_per_oz"]>0 for t in trades),
            "net_usd_per_oz":round(sum(t["net_usd_per_oz"] for t in trades),6),
        }
    equity=peak=dd=0.
    for t in all_trades:
        equity+=t["net_usd_per_oz"];peak=max(peak,equity)
        dd=max(dd,peak-equity)
    return {
        "valid_days":len(records),"signals":signals,
        "filled":len(all_trades),
        "wins":sum(t["net_usd_per_oz"]>0 for t in all_trades),
        "losses":sum(t["net_usd_per_oz"]<0 for t in all_trades),
        "net_usd_per_oz":net,
        "profit_factor":round(gains/losses,6) if losses else None,
        "expectancy_usd_per_oz":round(net/len(all_trades),6) if all_trades else None,
        "max_closed_drawdown_usd_per_oz":round(dd,6),
        "positive_days":sum(v>0 for v in per_day),
        "negative_days":sum(v<0 for v in per_day),
        "bootstrap_day_95pct": [round(bootstrap[75],5),round(bootstrap[2924],5)],
        "rejected":dict(sorted(rejection.items())),
        "by_setup":by_setup,
    }


def consolidate(root: str|Path):
    root=Path(root)
    valid={"april":[],"august":[]};excluded=[]
    for day in DAYS:
        ok=root/f"xau_v2_{day}.json"
        fail=root/f"quarantine_{day}.json"
        if ok.is_file()==fail.is_file():
            raise ValueError(f"Missing or duplicate results for {day}")
        if fail.is_file():
            q=json.loads(fail.read_text(encoding="utf-8"))
            if (q.get("day")!=day or q.get("whole_day_excluded") is not True
                or q.get("included_trades")!=0 or not q.get("reason")):
                raise ValueError("Quarantine failed whole-day exclusion")
            excluded.append(q);continue
        d=json.loads(ok.read_text(encoding="utf-8"))
        if (d.get("day")!=day or d.get("live_approval") is not False or
            d.get("connected_broker_validated") is not False or
            d.get("USD_per_one_theoretical_ounce") is not True or
            d.get("historical_not_forward_trading") is not True or
            d.get("identical_execution_bid_ask_tape") is not True or
            d.get("trade_window_utc")!="12:00-21:00" or
            d.get("train_history_utc")!="09:00-12:00" or
            len(d.get("source",{}).get("sha256",""))!=64 or
            d["source"].get("raw_quote_rows",0)<1500 or
            set(d.get("arms",{}))!={"M1","M5"}):
            raise ValueError("Invalid source and model integrity for "+day)
        for tf in ("M1","M5"):
            if set(d["arms"][tf])!=set(ARMS):
                raise ValueError("Missing predeclared mode")
            for arm in ARMS:
                if set(d["arms"][tf][arm]["costs"])!=set(COSTS):
                    raise ValueError("Missing cost stress case")
            if (d["arms"][tf]["combined"]["signals"] >
                d["arms"][tf]["structural"]["signals"]+
                d["arms"][tf]["pullback"]["signals"]):
                raise ValueError("Combined mode fabricated signal")
        valid["april" if day in APRIL else "august"].append(d)
    if min(map(len,valid.values()))<8:
        raise ValueError("Fail closed: less than 8 valid days per block")
    data={}
    for tf in ("M1","M5"):
        data[tf]={}
        for arm in ARMS:
            data[tf][arm]={}
            for cost in COSTS:
                data[tf][arm][cost]={
                    month:metrics(records,tf,arm,cost)
                    for month,records in valid.items()
                }
    return {
        "predeclared_dates":{"april":list(APRIL),"august":list(AUGUST)},
        "clean_dates":{month:[r["day"] for r in rows]
                       for month,rows in valid.items()},
        "quarantined_full_days":excluded,
        "approach":"fixed price action structural retest and EMA pullback vs old baseline",
        "hours":"09-12 warmup only; 12-21 BTC/ASK quote execution, all arms same prices",
        "not_future_forward_trading":True,
        "no_broker_mt5_validation":True,
        "trading_approved":False,
        "profits_usd_per_single_theoretical_ounce":True,
        "result":data,
    }


def to_markdown(result):
    lines=[
        "# XAUUSD M1/M5 Price Action v2 — mais sinais sob custos realistas",
        "",
        "Quatro braços *pré-declarados*: controle anterior, reteste de nível, "
        "pullback de tendência EMA e combinação (cooldown de 3 candles).",
        "Janela de observação 09–12 UTC, só negociar 12–21 UTC. Execução "
        "tick-a-tick BID/ASK com gap stop e uma única posição.",
        f"Abril: **{len(result['clean_dates']['april'])}/10** dias válidos; "
        f"agosto: **{len(result['clean_dates']['august'])}/10** dias válidos.",
        "",
        "### Cenário de custos DOBRADOS, não operação real",
        "",
        "| TF | Modelo | Abr sinais / trades | Abr US$/oz | Ago sinais / trades | Ago US$/oz |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for tf in ("M1","M5"):
        for arm in ARMS:
            data=result["result"][tf][arm]["double"]
            apr=data["april"];aug=data["august"]
            lines.append(f"| {tf} | {arm} | {apr['signals']}/{apr['filled']} | "
                         f"{apr['net_usd_per_oz']:+.3f} | "
                         f"{aug['signals']}/{aug['filled']} | "
                         f"{aug['net_usd_per_oz']:+.3f} |")
    lines.extend([
        "",
        "Custos hipotéticos por 1 onça: comissão ida/volta US$0,60, "
        "deslizamento adverso US$0,20 por ordem a mercado e preço BID/ASK "
        "da fonte. Outra corretora terá spreads e contratos diferentes.",
        "",
        "### Causas de exclusão, detalhamento por setup e robustez",
    ])
    for tf in ("M1","M5"):
        for arm in ARMS:
            for month,p in result["result"][tf][arm]["double"].items():
                parts=", ".join(f"{k}={v['signals']} sinais/{v['filled']} operações"
                                for k,v in p["by_setup"].items()) or "sem sinais"
                lines.append(
                    f"- {tf} {arm} {month}: {parts}; "
                    f"não executadas {p['rejected']}; "
                    f"bootstrap 95% por dia: {p['bootstrap_day_95pct']}"
                )
    lines.extend([
        "",
        "**Não equiparar aumento da frequência com vantagem financeira.** "
        "Os dias já são históricos, não forward na corretora. "
        "Todos os braços e perdas foram mantidos. "
        "Não selecionar a hipótese vencedora no mesmo mês para declará-la validada.",
        "**NÃO aprovar nem enviar ordens; PR permanece rascunho.**",
        "",
        "### Sessões completamente excluídas por feed inválido",
    ])
    lines.extend(f"- {q['day']}: {q['reason']}"
                 for q in result["quarantined_full_days"])
    if not result["quarantined_full_days"]:lines.append("- Nenhuma")
    return "\n".join(lines)+"\n"


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--evidence",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    result=consolidate(a.evidence)
    dest=Path(a.out);dest.mkdir(parents=True,exist_ok=True)
    (dest/"xau_pa_frequency_v2.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    md=to_markdown(result)
    (dest/"xau_pa_frequency_v2.md").write_text(md,encoding="utf-8")
    print(md)


if __name__=="__main__":
    main()
