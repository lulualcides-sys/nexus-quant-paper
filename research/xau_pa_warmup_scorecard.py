"""Chronological comparison of truncated vs 3h-warmed XAU M1/M5 signals.

Conservative historical diagnostics, no trading approval or model optimization.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
import random

from research.xau_pa_warmup_study import MARCH,OCTOBER,DAYS,ARMS,COSTS


def _stats(records,tf,arm,cost):
    trades=[];totals=[];n_signals=0
    for rec in records:
        row=rec["results"][tf][arm]
        b=row["costs"][cost]
        if (b["signals"]!=row["signals"] or
            b["filled"]!=len(b["trades"]) or
            b["filled"]>b["signals"] or
            abs(b["net_usd_per_oz"]-
                sum(t["net_usd_per_oz"] for t in b["trades"]))>.001):
            raise ValueError("Ledger invalid")
        n_signals+=row["signals"];trades.extend(b["trades"])
        totals.append(b["net_usd_per_oz"])
    gross=sum(max(t["net_usd_per_oz"],0) for t in trades)
    loss=-sum(min(t["net_usd_per_oz"],0) for t in trades)
    net=gross-loss
    rng=random.Random(20261110)
    resampled=sorted(sum(rng.choices(totals,k=len(totals))) for _ in range(2000))
    setups={}
    for name in ("break_retest","range_rejection"):
        sub=[t for t in trades if t["setup"]==name]
        setups[name]={"trades":len(sub),
                      "net_usd_per_oz":round(sum(t["net_usd_per_oz"] for t in sub),6)}
    return {
        "days":len(records),
        "signals":n_signals,"filled":len(trades),
        "wins":sum(t["net_usd_per_oz"]>0 for t in trades),
        "losses":sum(t["net_usd_per_oz"]<0 for t in trades),
        "net_usd_per_oz":round(net,6),
        "profit_factor":round(gross/loss,6) if loss else None,
        "active_days":sum(v!=0 for v in totals),
        "bootstrap_day_95pct":[round(resampled[49],5),round(resampled[1949],5)],
        "exit_reasons":dict(sorted(Counter(t["reason"] for t in trades).items())),
        "setups":setups,
    }


def compare(folder: str | Path):
    root=Path(folder)
    all_valid={"march":[],"october":[]}
    bad=[]
    for day in DAYS:
        target=root/f"warm_{day}.json"
        quarantine=root/f"quarantine_{day}.json"
        if target.is_file()==quarantine.is_file():
            raise ValueError("Missing/mixed source date "+day)
        if quarantine.is_file():
            row=json.loads(quarantine.read_text(encoding="utf-8"))
            if (row.get("day")!=day or row.get("fully_excluded") is not True or
                row.get("counted_operations")!=0):
                raise ValueError("Bad quarantine or exclusion")
            bad.append(row)
            continue
        r=json.loads(target.read_text(encoding="utf-8"))
        if (r.get("day")!=day or r.get("price_action_parameters_unchanged") is not True
            or r.get("same_execution_tape_for_all_arms") is not True or
            r.get("approved_for_live") is not False or
            r.get("broker_verified") is not False or
            r.get("warmup_start_utc")!="09:00" or
            r.get("execution_start_utc")!="12:00" or
            len(r.get("source",{}).get("sha256",""))!=64 or
            set(r.get("results",{}))!={"M1","M5"}):
            raise ValueError("Untrusted backtest or data provenance")
        for tf in ("M1","M5"):
            if set(r["results"][tf])!=set(ARMS):
                raise ValueError("Missing comparison arm")
            for arm in ARMS:
                if set(r["results"][tf][arm]["costs"])!=set(COSTS):
                    raise ValueError("Missing cost scenario")
            if r["results"][tf]["warm_quality"]["signals"]>r["results"][tf]["warm_control"]["signals"]:
                raise ValueError("Quality filter created fictitious signal")
        all_valid["march" if day in MARCH else "october"].append(r)
    if min(len(all_valid["march"]),len(all_valid["october"]))<8:
        raise ValueError("Insufficient full-session data, no optimistic subset")
    results={}
    for tf in ("M1","M5"):
        results[tf]={}
        for arm in ARMS:
            results[tf][arm]={}
            for period,records in all_valid.items():
                results[tf][arm][period]={
                    scenario:_stats(records,tf,arm,scenario)
                    for scenario in COSTS
                }
    return {
        "hypothesis":"Historical first 3h warms M1/M5, but trades allowed only 12-17 UTC",
        "planned_dates":{"march":list(MARCH),"october":list(OCTOBER)},
        "clean_dates":{k:[d["day"] for d in v] for k,v in all_valid.items()},
        "quarantined_whole_days":bad,
        "execution_prices":"identical BID/ASK tape 12-17 UTC for all three arms",
        "costs":"standard 0.30+0.10 USD/oz; doubled 0.60+0.20 adverse market slippage plus actual spread",
        "no_live_broker_mt5_data":True,
        "historical_experiment_not_forward_trading":True,
        "approved_for_live":False,
        "results":results,
    }


def report_markdown(r):
    lines=[
        "# XAU Price Action — warmup M1/M5, dados 09–17 UTC; trades só 12–17",
        "",
        f"Março: **{len(r['clean_dates']['march'])}/10** pregões válidos; "
        f"Outubro: **{len(r['clean_dates']['october'])}/10**.",
        "Mesmos sinais e custos ex ante, mesmos ticks para executar cada braço; "
        "somente o histórico permitido antes do sinal difere.",
        "",
        "| TF | Variante | Março sinais / fills | Março US$/oz | Outubro sinais / fills | Outubro US$/oz |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for tf in ("M1","M5"):
        for arm in ARMS:
            j=r["results"][tf][arm]["march"]["double"]
            o=r["results"][tf][arm]["october"]["double"]
            lines.append(f"| {tf} | {arm} | {j['signals']}/{j['filled']} | "
                         f"{j['net_usd_per_oz']:+.3f} | "
                         f"{o['signals']}/{o['filled']} | "
                         f"{o['net_usd_per_oz']:+.3f} |")
    lines.extend([
        "",
        "Aquecimento inicial usa candles anteriores a 12:00 UTC SOMENTE "
        "para cálculo de ATR, pivôs e regime. Não opera antes das 12h.",
        "Uma posição aberta às 17h é zerada no último quote observado. "
        "Operações contadas somente com sinal fechado após início do período.",
        "Custos hipotéticos dobrados e spread bid/ask de cotações Dukascopy; "
        "resultados por **UMA onça**, nunca em conta MT5 nem em milhares de USD.",
        "",
        "## Controle de aprovação",
        "Este estudo mede viés metodológico da inicialização, não valida "
        "rentabilidade de corretora nem estratégia Greenhouse.",
        "Não selecionar o período ou variante por PnL após olhar os resultados; "
        "**todos os braços estão aqui, inclusive negativos ou zero operações**.",
        "PR permanece isolada e nenhuma ordem automática pode ser enviada.",
        "",
        "## Sessões inteiras excluídas por falha de feed",
    ])
    lines.extend(f"- {x['day']}: {x['reason']}" for x in r["quarantined_whole_days"])
    if not r["quarantined_whole_days"]:lines.append("- Nenhuma")
    return "\n".join(lines)+"\n"


def cli():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True)
    p.add_argument("--output",required=True)
    args=p.parse_args()
    d=compare(args.input)
    root=Path(args.output);root.mkdir(parents=True,exist_ok=True)
    (root/"warmup_scorecard.json").write_text(json.dumps(d,indent=2,ensure_ascii=False)+"\n")
    md=report_markdown(d)
    (root/"warmup_scorecard.md").write_text(md,encoding="utf-8")
    print(md)


if __name__=="__main__":
    cli()
