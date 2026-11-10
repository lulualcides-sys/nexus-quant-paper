"""Audit manual-strategy interpretation versus old XAU PA baseline.

Historical replay uses machine-generated CAUSAL PROXY markings if no real,
time-stamped user drawings exist. Proxy results do NOT validate manual fidelity.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import random

from research.xau_pa_manual_rules_v3 import OCTOBER,NOVEMBER,DAYS


def stats(dates,tf,policy,cost):
    signals=0
    trades=[]
    rejection=Counter()
    events=Counter()
    day_pnl=[]
    for d in dates:
        v=d["results"][tf][policy]
        e=v["costs"][cost]
        if (v["signals"]!=e["signals"] or
            e["filled"]!=len(e["trades"]) or
            e["filled"]>e["signals"] or
            sum(v["signal_setups"].values())!=v["signals"] or
            abs(sum(t["net_usd_per_oz"] for t in e["trades"])-e["net_usd_per_oz"])>.001):
            raise ValueError("Inconsistent filled ledger and signal counts")
        signals+=v["signals"]
        trades.extend(e["trades"])
        events.update(v["events"])
        rejection.update(e["rejected"])
        day_pnl.append(sum(t["net_usd_per_oz"] for t in e["trades"]))
    positive=sum(max(0,t["net_usd_per_oz"]) for t in trades)
    negative=-sum(min(0,t["net_usd_per_oz"]) for t in trades)
    net=positive-negative
    rng=random.Random(20261110)
    boot=sorted(sum(rng.choices(day_pnl,k=len(day_pnl)))
                for _ in range(2000))
    by_setup={}
    for key in sorted(set(x["setup"] for x in trades)):
        sub=[x for x in trades if x["setup"]==key]
        by_setup[key]={"filled":len(sub),
                       "wins":sum(x["net_usd_per_oz"]>0 for x in sub),
                       "net_usd_per_oz":round(sum(x["net_usd_per_oz"] for x in sub),6)}
    return {
        "days":len(dates),"signals":signals,
        "filled":len(trades),"wins":sum(t["net_usd_per_oz"]>0 for t in trades),
        "losses":sum(t["net_usd_per_oz"]<0 for t in trades),
        "net_usd_per_oz":round(net,6),
        "profit_factor":round(positive/negative,6) if negative else None,
        "expectancy_usd_per_oz":round(net/len(trades),6) if trades else None,
        "bootstrap_day_p025_p975":[round(boot[49],4),round(boot[1949],4)],
        "by_setup":by_setup,
        "rejection_reasons":dict(sorted(rejection.items())),
        "detector_events":dict(sorted(events.items())),
    }


def summarize(folder: str|Path):
    root=Path(folder)
    clean={"october":[],"november":[]};quarantined=[]
    mode=None
    for day in DAYS:
        success=root/f"xau_manual_v3_{day}.json"
        invalid=root/f"quarantine_{day}.json"
        if success.is_file()==invalid.is_file():
            raise ValueError("Missing or double complete day: "+day)
        if invalid.is_file():
            row=json.loads(invalid.read_text(encoding="utf-8"))
            if (row.get("day")!=day or row.get("whole_day_excluded") is not True
                or row.get("included_trades")!=0 or not row.get("reason")):
                raise ValueError("Quarantined day cannot include operations")
            quarantined.append(row)
            continue
        r=json.loads(success.read_text(encoding="utf-8"))
        if (r.get("day")!=day or
            r.get("symbol")!="XAUUSD" or
            r.get("live_approval") is not False or
            r.get("not_an_MT5_broker_backtest") is not True or
            r.get("user_drawn_marking_fidelity_verified") is not False or
            r.get("one_concurrent_position") is not True or
            r.get("trade_utc")!="12:00-21:00" or
            len(r.get("source",{}).get("sha256",""))!=64 or
            r["source"].get("date_utc")!=day or
            set(r.get("results",{}))!={"M1","M5"}):
            raise ValueError("Source/provenance cannot support this result")
        if r["marking_mode"] not in ("manual","proxy"):
            raise ValueError("Unrecognized mark source")
        if mode is None: mode=r["marking_mode"]
        if mode!=r["marking_mode"]:
            raise ValueError("Cannot mix manual and proxy source days")
        for tf in ("M1","M5"):
            if set(r["results"][tf])!={"legacy","marked_rules_v3"}:
                raise ValueError("Missing control/v3 paired replay")
            for policy in ("legacy","marked_rules_v3"):
                if set(r["results"][tf][policy]["costs"])!={"standard","double"}:
                    raise ValueError("Missing cost stress")
        clean["october" if day in OCTOBER else "november"].append(r)
    if min(len(x) for x in clean.values())<3:
        raise ValueError("Insufficient clean days in each predeclared panel")
    output={}
    for tf in ("M1","M5"):
        output[tf]={}
        for policy in ("legacy","marked_rules_v3"):
            output[tf][policy]={
                cost:{
                    period:stats(records,tf,policy,cost)
                    for period,records in clean.items()
                } for cost in ("standard","double")
            }
    return {
        "title":"Price Action marked LTA/LTD break-retest and range-only rejection",
        "predeclared_days":{"october":list(OCTOBER),"november":list(NOVEMBER)},
        "clean_days":{x:[r["day"] for r in arr] for x,arr in clean.items()},
        "whole_day_quarantines":quarantined,
        "marking_mode":mode,
        "actual_user_marks_provided":mode=="manual",
        "manual_fidelity_verified":False,
        "never_a_MT5_broker_backtest":True,
        "live_trading_approved":False,
        "costs_standard":"hypothetical USD0.30/oz roundtrip, USD0.10/oz adverse market slippage plus bid/ask spread",
        "costs_double":"hypothetical USD0.60/oz roundtrip, USD0.20/oz adverse market slippage plus bid/ask spread",
        "result":output,
    }


def markdown(r):
    lines=[
        "# Price Action do usuário no XAUUSD M1/M5 — auditoria de fidelidade v3",
        "",
        "A **lógica de decisão** usa somente marcação anterior, rompimento de "
        "LTD/LTA e **reteste posterior**, ou rejeição do suporte/resistência "
        "marcado **somente em lateralização**. SEM gatilho por EMA.",
        "A marcação é "
        +("fornecida por arquivo datado, sem prova de identidade com a análise manual."
          if r["marking_mode"]=="manual" else
          "**PROXY CAUSAL AUTOMÁTICO**. **Não é a marcação do usuário**.")
        + " O código nunca infere a marcação humana a partir dos resultados.",
        f"Outubro {len(r['clean_days']['october'])}/5 pregões válidos; "
        f"novembro {len(r['clean_days']['november'])}/5.",
        "",
        "## Comparação de custos DOBRADOS por uma onça teórica",
        "",
        "| TF | Braço | Out sinais / exec. | Out US$/oz | Nov sinais / exec. | Nov US$/oz |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for tf in ("M1","M5"):
        for arm in ("legacy","marked_rules_v3"):
            a=r["result"][tf][arm]["double"]
            x=a["october"];y=a["november"]
            lines.append(f"| {tf} | {arm} | {x['signals']}/{x['filled']} | "
                         f"{x['net_usd_per_oz']:+.3f} | "
                         f"{y['signals']}/{y['filled']} | "
                         f"{y['net_usd_per_oz']:+.3f} |")
    lines.extend([
        "",
        "## Motivos para NÃO entrar, e composição dos sinais",
    ])
    for tf in ("M1","M5"):
        for period,row in r["result"][tf]["marked_rules_v3"]["double"].items():
            lines.append(
                f"- {tf} {period}: {row['by_setup']}; "
                f"eventos={row['detector_events']}; "
                f"bloqueios de execução={row['rejection_reasons']}; "
                f"bootstrap diário={row['bootstrap_day_p025_p975']}")
    lines.extend([
        "",
        "Simulação em BID/ASK Dukascopy; custos de corretora hipotéticos; "
        "não é conta MT5, nem valida lotes reais, nem demonstra desempenho futuro.",
        "Os dois meses foram fixados antes de executar a pesquisa v3, "
        "mas são históricos e não devem ser chamados de forward prospectivo.",
        "**Nenhuma ordem automática e nenhuma aprovação para dinheiro real.**",
        "",
        "## Exclusões de sessões inteiras por falha de origem",
    ])
    lines.extend(f"- {q['day']}: {q['reason']}" for q in r["whole_day_quarantines"])
    if not r["whole_day_quarantines"]:lines.append("- Nenhuma")
    return "\n".join(lines)+"\n"


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--evidence",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    r=summarize(args.evidence)
    dest=Path(args.out);dest.mkdir(parents=True,exist_ok=True)
    (dest/"price_action_marked_v3.json").write_text(
        json.dumps(r,ensure_ascii=False,indent=2)+"\n")
    md=markdown(r)
    (dest/"price_action_marked_v3.md").write_text(md,encoding="utf-8")
    print(md)


if __name__=="__main__":
    main()
