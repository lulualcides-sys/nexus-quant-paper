"""Read-only audit of two predeclared XAUUSD PA periods and a frozen quality gate.

Do not select a winning strategy from the holdouts. This compares control and
one quality hypothesis. Data are previously sampled Dukascopy quotes; neither
window is broker MT5 forward-testing and no profits are verified.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import random

from research.xau_pa_quality_experiment import FIRST,SECOND,DAYS,MODES,COSTS


def _stats(reports,tf,mode,cost):
    signal_count=0
    executed=[]
    per_day=[]
    rejected=Counter()
    active_days=0
    for record in reports:
        item=record["modes"][tf][mode]
        history=item["costs"][cost]
        if history["signals"]!=item["signals"]:
            raise ValueError("Unverifiable signal count")
        if history["filled"]!=len(history["trades"]) or history["filled"]>history["signals"]:
            raise ValueError("Unverifiable fill accounting")
        if abs(sum(t["net_usd_per_oz"] for t in history["trades"])-
               history["net_usd_per_oz"])>.001:
            raise ValueError("Unverifiable PnL ledger")
        signal_count+=history["signals"]
        per_day.append(sum(t["net_usd_per_oz"] for t in history["trades"]))
        active_days+=bool(history["trades"])
        executed.extend(history["trades"])
        rejected.update(history["rejected"])
    wins=sum(t["net_usd_per_oz"]>0 for t in executed)
    losses=sum(t["net_usd_per_oz"]<0 for t in executed)
    gross_gain=sum(max(0,t["net_usd_per_oz"]) for t in executed)
    gross_loss=-sum(min(0,t["net_usd_per_oz"]) for t in executed)
    net=gross_gain-gross_loss
    rng=random.Random(20261110)
    if per_day:
        bootstrap=sorted(sum(rng.choices(per_day,k=len(per_day))) for _ in range(3000))
        interval=[round(bootstrap[75],6),round(bootstrap[2924],6)]
    else:
        interval=[None,None]
    by_setup={}
    for label in ("break_retest","range_rejection"):
        trades=[t for t in executed if t["setup"]==label]
        by_setup[label]={
            "filled":len(trades),
            "net_usd_per_oz":round(sum(t["net_usd_per_oz"] for t in trades),6),
            "wins":sum(t["net_usd_per_oz"]>0 for t in trades),
        }
    return {
        "source_days":len(reports),
        "signal_count":signal_count,
        "filled":len(executed),"wins":wins,"losses":losses,
        "net_usd_per_oz":round(net,6),
        "profit_factor":round(gross_gain/gross_loss,6) if gross_loss else None,
        "expectancy_per_fill":round(net/len(executed),6) if executed else None,
        "days_with_trades":active_days,
        "positive_days":sum(v>0 for v in per_day),
        "bootstrap_day_net_p025_p975":interval,
        "exit_reasons":dict(sorted(Counter(t["reason"] for t in executed).items())),
        "rejected":dict(sorted(rejected.items())),
        "by_setup":by_setup,
    }


def aggregate(directory: str|Path):
    root=Path(directory)
    groups={"july":[],"september":[]}
    quarantines=[]
    for day in DAYS:
        report=root/f"xau_pa_quality_{day}.json"
        failed=root/f"quarantine_{day}.json"
        if report.is_file()==failed.is_file():
            raise ValueError(f"Missing or ambiguous research date {day}")
        if failed.is_file():
            q=json.loads(failed.read_text(encoding="utf-8"))
            if (q.get("day")!=day or q.get("whole_day_quarantined") is not True
                or q.get("trades_included")!=0):
                raise ValueError("Invalid quarantine")
            quarantines.append(q)
            continue
        row=json.loads(report.read_text(encoding="utf-8"))
        if (row.get("day")!=day or row["source"].get("date_utc")!=day or
            len(row["source"].get("sha256",""))!=64 or
            row["source"].get("raw_quote_rows",0)<1500 or
            row.get("approved_for_live") is not False or
            row.get("broker_mt5_account_verification") is not False or
            row.get("auto_order_execution") is not False or
            set(row.get("modes",{}))!={"M1","M5"}):
            raise ValueError("Source cannot support a trading claim")
        for tf in ("M1","M5"):
            if set(row["modes"][tf])!=set(MODES):
                raise ValueError("Missing control or quality gate")
            baseline=row["modes"][tf]["control"]["signals"]
            quality=row["modes"][tf]["quality_v1"]["signals"]
            if quality>baseline:
                raise ValueError("Quality veto invented a signal")
            for mode in MODES:
                if set(row["modes"][tf][mode]["costs"])!=set(COSTS):
                    raise ValueError("Missing a cost scenario")
        groups["july" if day in FIRST else "september"].append(row)
    if len(groups["july"])<8 or len(groups["september"])<8:
        raise ValueError("Insufficient unchanged independent session coverage")
    by_tf={}
    for tf in ("M1","M5"):
        by_tf[tf]={}
        for mode in MODES:
            by_tf[tf][mode]={}
            for scenario in COSTS:
                by_tf[tf][mode][scenario]={
                    name:_stats(rows,tf,mode,scenario)
                    for name,rows in groups.items()
                }
    return {
        "periods":{"july":list(FIRST),"september":list(SECOND)},
        "valid_dates":{name:[x["day"] for x in group] for name,group in groups.items()},
        "quarantined":quarantines,
        "rules":"unchanged reference vs one precommitted quality_v1 veto",
        "double_costs":"US$0.60/oz roundtrip commission + US$0.20/oz adverse market slippage each side; historical BID/ASK spread",
        "cost_sensitive_eligibility":"An increased cost may veto a marginal entry, changing fills; all ledgers independent",
        "units":"hypothetical USD per 1 oz, not broker equity",
        "no_connected_mt5_validation":True,
        "not_a_prospective_future_holdout":True,
        "approval_blocked":True,
        "results":by_tf,
    }


def markdown(result):
    lines=[
      "# Ouro XAUUSD — qualidade Price Action (M1/M5), comparação congelada",
      "",
      f"Julho: {len(result['valid_dates']['july'])}/10 sessões válidas; "
      f"setembro: {len(result['valid_dates']['september'])}/10.",
      "Os dois períodos são **históricos**, não resultados forward de uma conta MT5.",
      "",
      "| TF | Política | Julho sinais/trades | Julho líquido US$/oz | Setembro sinais/trades | Setembro líquido US$/oz |",
      "|---|---|---:|---:|---:|---:|",
    ]
    for tf in ("M1","M5"):
        for mode in MODES:
            v=result["results"][tf][mode]["double"]
            j=v["july"];s=v["september"]
            lines.append(f"| {tf} | {mode} | {j['signal_count']}/{j['filled']} | "
                         f"{j['net_usd_per_oz']:+.3f} | "
                         f"{s['signal_count']}/{s['filled']} | "
                         f"{s['net_usd_per_oz']:+.3f} |")
    lines.extend([
        "",
        "Os números usam **custos hipotéticos dobrados**, além do spread bid/ask observado. "
        "Os custos mais altos podem vetar entradas por razão econômica; conferir número "
        "de trades, não apenas comparar lucros como se a amostra fosse idêntica.",
        "",
        "## Diagnóstico separado por setup (double costs)",
    ])
    for tf in ("M1","M5"):
        for mode in MODES:
            for period,part in result["results"][tf][mode]["double"].items():
                lines.append(f"- {tf} {mode} {period}: "
                             f"{part['by_setup']['break_retest']['filled']} rompimento/reteste, "
                             f"{part['by_setup']['range_rejection']['filled']} lateralização; "
                             f"IC bootstrap por dia {part['bootstrap_day_net_p025_p975']}")
    lines.extend([
        "",
        "## Conclusão de segurança",
        "O filtro é uma HIPÓTESE estudada depois de as perdas de maio terem sido vistas. "
        "Não declarar uma configuração lucrativa só pela melhora relativa histórica.",
        "**NÃO aprovar** contas reais, ordens automatizadas ou alteração da main.",
        "Falta período futuro genuinamente não visto e dados de corretora MT5.",
        "",
        "## Dias inteiramente excluídos por validação de origem",
    ])
    lines.extend(f"- {q['day']}: {q['reason']}" for q in result["quarantined"])
    if not result["quarantined"]:lines.append("- Nenhum")
    return "\n".join(lines)+"\n"


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    report=aggregate(a.source)
    target=Path(a.out);target.mkdir(parents=True,exist_ok=True)
    (target/"xau_pa_quality_comparison.json").write_text(
        json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    md=markdown(report)
    (target/"xau_pa_quality_comparison.md").write_text(md,encoding="utf-8")
    print(md)
