"""Fixed two-block audit: v4 preopen S/R vs v5 causal rolling S/R.

No post-hoc optimization or best-variant designation. All data are historical
quotes not MT5 broker orders, priced USD per *one theoretical ounce*.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import random

from research.xau_pa_rolling_zones_v5 import FEBRUARY,JULY,DAYS,ARMS,COSTS


def summary(rows,tf,mode,cost):
    signals=0;fills=[];daily=[];setups=Counter();veto=Counter();rejects=Counter()
    for d in rows:
        item=d["results"][tf][mode]
        sim=item["costs"][cost]
        if (sim["signals"]!=item["signals"] or sim["filled"]!=len(sim["trades"]) or
            sim["filled"]>sim["signals"] or
            sum(item["setups"].values())!=item["signals"] or
            abs(sum(t["net_usd_per_oz"] for t in sim["trades"])
                -sim["net_usd_per_oz"])>.001):
            raise ValueError("Broken chronological quote execution ledger")
        if tf=="SHARED" and sim.get("one_global_position_per_symbol") is not True:
            raise ValueError("No single-position XAU lock")
        signals+=sim["signals"];fills.extend(sim["trades"])
        daily.append(sim["net_usd_per_oz"]);setups.update(item["setups"])
        rejects.update(sim["rejected"])
        if tf!="SHARED":
            veto.update(item["reasons"].get("quality_veto_counts",{}))
    profit=sum(max(0,t["net_usd_per_oz"]) for t in fills)
    loss=-sum(min(0,t["net_usd_per_oz"]) for t in fills)
    rng=random.Random(20261110)
    boot=sorted(sum(rng.choices(daily,k=len(daily))) for _ in range(2000))
    by_setup={}
    for setup in ("break_retest","range_rejection"):
        sub=[t for t in fills if t["setup"]==setup]
        by_setup[setup]={
            "signals":setups[setup],
            "fills":len(sub),
            "wins":sum(t["net_usd_per_oz"]>0 for t in sub),
            "net_usd_per_oz":round(sum(t["net_usd_per_oz"] for t in sub),6)
        }
    return {
        "source_days":len(rows),
        "signals":signals,"filled":len(fills),
        "wins":sum(t["net_usd_per_oz"]>0 for t in fills),
        "losses":sum(t["net_usd_per_oz"]<0 for t in fills),
        "net_usd_per_oz":round(profit-loss,6),
        "profit_factor":round(profit/loss,5) if loss else None,
        "expectancy_per_trade":round((profit-loss)/len(fills),5) if fills else None,
        "positive_days":sum(v>0 for v in daily),
        "negative_days":sum(v<0 for v in daily),
        "day_bootstrap_95pct":[round(boot[49],5),round(boot[1949],5)],
        "by_setup":by_setup,
        "executed_exit_reasons":dict(sorted(Counter(t["reason"] for t in fills).items())),
        "execution_rejections":dict(sorted(rejects.items())),
        "signal_quality_reasons":dict(sorted(veto.items())),
        "daily_net_usd_per_oz":[round(x,6) for x in daily],
    }


def audit(folder):
    folder=Path(folder)
    groups={"february":[],"july":[]};quarantined=[];source_mode=None
    for day in DAYS:
        ok=folder/f"xau_pa_v5_{day}.json"
        failed=folder/f"quarantine_{day}.json"
        if ok.is_file()==failed.is_file():
            raise ValueError("Missing or conflicting whole-day evidence "+day)
        if failed.exists():
            q=json.loads(failed.read_text(encoding="utf-8"))
            if (q.get("day")!=day or q.get("whole_source_quarantined") is not True
                or q.get("included_fills")!=0 or not q.get("reason")):
                raise ValueError("Quarantine did not discard entire source day")
            quarantined.append(q)
            continue
        d=json.loads(ok.read_text(encoding="utf-8"))
        if (d.get("day")!=day or
            d.get("approved_for_real_trades") is not False or
            d.get("manual_drawings_reproduced") is not False or
            d.get("same_quotes_and_exec_for_both_arms") is not True or
            d.get("one_shared_XAUUSD_position") is not True or
            d.get("not_a_mt5_broker_feed") is not True or
            d.get("warming_period_utc")!="09:00-12:00" or
            d.get("trading_period_utc")!="12:00-21:00" or
            d.get("source",{}).get("date_utc")!=day or
            len(d.get("source",{}).get("sha256",""))!=64 or
            d.get("source",{}).get("raw_quote_rows",0)<1500 or
            set(d.get("results",{}))!={"M1","M5","SHARED"}):
            raise ValueError("Unverifiable historical result and provenance "+day)
        mode=d.get("source_mark_mode")
        if mode not in ("proxy","manual"):
            raise ValueError("Source of drawing not declared")
        if source_mode is None:source_mode=mode
        if source_mode!=mode:raise ValueError("Mixed user and proxy mark evidence")
        for tf in ("M1","M5","SHARED"):
            if set(d["results"][tf])!=set(ARMS):
                raise ValueError("Missing unchanged comparator")
            for arm in ARMS:
                if set(d["results"][tf][arm]["costs"])!=set(COSTS):
                    raise ValueError("Missing cost scenario")
        groups["february" if day in FEBRUARY else "july"].append(d)
    if min(len(x) for x in groups.values())<4:
        raise ValueError("Insufficient clean dates in a precommitted block")
    results={
        tf:{
            arm:{
                cost:{
                    month:summary(arr,tf,arm,cost)
                    for month,arr in groups.items()
                } for cost in COSTS
            } for arm in ARMS
        } for tf in ("M1","M5","SHARED")
    }
    return {
        "hypothesis":"v4 same old LTA/LTD and S/R drawn before 12; v5 updates S/R causal confirmed swings strictly prior to signal candle",
        "predeclared_dates":{"february":list(FEBRUARY),"july":list(JULY)},
        "clean_days":{month:[r["day"] for r in rows] for month,rows in groups.items()},
        "quarantined_whole_sessions":quarantined,
        "source_mode":source_mode,
        "no_real_user_drawings_supplied":source_mode=="proxy",
        "historical_not_prospective":True,
        "verified_mt5_broker_execution":False,
        "approved_for_live":False,
        "one_global_symbol_lock":True,
        "costs":"double: 0.60 USD/oz roundtrip commission + 0.20 USD/oz adverse each market side; real BID/ASK spread",
        "pnl_units":"USD per one theoretical troy ounce (not broker lot or dollars of equity)",
        "results":results,
    }


def as_markdown(r):
    lines=[
      "# Price Action ouro v5: zonas recalculadas sem futuro — mesma estratégia, M1/M5",
      "",
      "Uma mudança isolada: v4 usa suporte/resistência confirmados no início das "
      "operações; v5 considera a região dos swing-pairs confirmados antes de "
      "CADA candle de sinal. Rompimento LTA/LTD, reteste, stop, alvo, "
      "custos e posição global permanecem idênticos.",
      "",
      f"Fevereiro: {len(r['clean_days']['february'])}/5 dias válidos; "
      f"julho: {len(r['clean_days']['july'])}/5. "
      "**Sem desenhos manuais reais; zonas e linhas são proxies automáticos.**",
      "",
      "| TF | Política | Fev sinais / trades | Fev P&L USD/oz | Jul sinais / trades | Jul P&L USD/oz |",
      "|---|---|---:|---:|---:|---:|",
    ]
    for tf in ("M1","M5","SHARED"):
        for arm in ARMS:
            a=r["results"][tf][arm]["double"]
            f=a["february"];j=a["july"]
            lines.append(f"| {tf} | {arm} | {f['signals']}/{f['filled']} | "
                         f"{f['net_usd_per_oz']:+.3f} | "
                         f"{j['signals']}/{j['filled']} | "
                         f"{j['net_usd_per_oz']:+.3f} |")
    lines.extend([
      "",
      "## Decomposição em setups e motivo de saída (cenário de custo dobrado)",
    ])
    for tf in ("M1","M5","SHARED"):
        for month,s in r["results"][tf]["v5_rolling"]["double"].items():
            lines.append(
              f"- {tf} {month}: {s['by_setup']}, "
              f"stops/alvos/tempo={s['executed_exit_reasons']}; "
              f"bloqueios={s['execution_rejections']}; "
              f"veto por qualidade={s['signal_quality_reasons']}; "
              f"bootstrap por dia={s['day_bootstrap_95pct']}"
            )
    lines.extend([
      "",
      "**Sem dados de conta MT5, sem troca de parâmetros após ver este backtest, "
      "sem seleção de meses vencedores e sem operação autorizada.** "
      "A unidade é USD por uma onça hipotética, não saldo de conta ou lote.",
      "",
      "## Excluídos inteiramente por dados históricos inválidos",
    ])
    lines.extend(f"- {x['day']}: {x['reason']}" for x in r["quarantined_whole_sessions"])
    if not r["quarantined_whole_sessions"]:lines.append("- Nenhum")
    return "\n".join(lines)+"\n"


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--evidence",required=True)
    ap.add_argument("--out",required=True)
    args=ap.parse_args()
    report=audit(args.evidence)
    root=Path(args.out);root.mkdir(parents=True,exist_ok=True)
    (root/"xau_pa_v5_rolling_scorecard.json").write_text(
        json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    md=as_markdown(report)
    (root/"xau_pa_v5_rolling_scorecard.md").write_text(md,encoding="utf-8")
    print(md)


if __name__=="__main__":
    main()
