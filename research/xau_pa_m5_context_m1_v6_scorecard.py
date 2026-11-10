"""Paired historical comparison: M1 v4 vs M1-with-confirmed-M5-context.

Results include every predeclared source day, even if profitable or negative.
No parameter fitting or hiding negative setups. No account/MT5 equity claims.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import random
from research.xau_pa_m5_context_m1_v6 import JUNE,JULY,DAYS,POLICIES,COSTS


def _summarize(days,policy,cost):
    n_signals=0;trades=[];daily=[];signal_mix=Counter();rejections=Counter()
    for d in days:
        row=d["results"][policy];book=row["costs"][cost]
        if (book["signals"]!=row["signals"] or
            book["filled"]!=len(book["trades"]) or
            book["filled"]>book["signals"] or
            sum(row["setup_signals"].values())!=row["signals"] or
            abs(sum(x["net_usd_per_oz"] for x in book["trades"])
                -book["net_usd_per_oz"])>.001):
            raise ValueError("Signal ledger and simulated executions disagree")
        n_signals+=book["signals"]
        signal_mix.update(row["setup_signals"])
        trades+=book["trades"]
        daily.append(book["net_usd_per_oz"])
        rejections.update(book["rejected"])
    profit=sum(t["net_usd_per_oz"] for t in trades if t["net_usd_per_oz"]>0)
    loss=-sum(t["net_usd_per_oz"] for t in trades if t["net_usd_per_oz"]<0)
    equity=peak=dd=0.
    for t in trades:
        equity+=t["net_usd_per_oz"]
        peak=max(peak,equity)
        dd=max(dd,peak-equity)
    rng=random.Random(20261110)
    bootstrap=sorted(sum(rng.choices(daily,k=len(daily))) for _ in range(3000))
    setup_metrics={}
    for name in ("break_retest","range_rejection"):
        ss=[x for x in trades if x["setup"]==name]
        setup_metrics[name]={
            "signals":signal_mix[name],"fills":len(ss),
            "wins":sum(t["net_usd_per_oz"]>0 for t in ss),
            "net_usd_per_oz":round(sum(t["net_usd_per_oz"] for t in ss),6)
        }
    return {
        "days":len(days),"signals":n_signals,
        "filled":len(trades),
        "wins":sum(x["net_usd_per_oz"]>0 for x in trades),
        "losses":sum(x["net_usd_per_oz"]<0 for x in trades),
        "net_usd_per_oz":round(profit-loss,6),
        "profit_factor":round(profit/loss,6) if loss>0 else None,
        "expectancy_usd_per_oz":round((profit-loss)/len(trades),6) if trades else None,
        "max_realized_drawdown_usd_per_oz":round(dd,6),
        "daily_bootstrap_95pct":[round(bootstrap[75],6),round(bootstrap[2924],6)],
        "positive_days":sum(v>0 for v in daily),
        "negative_days":sum(v<0 for v in daily),
        "setup_metrics":setup_metrics,
        "exits":dict(sorted(Counter(t["reason"] for t in trades).items())),
        "entry_rejections":dict(sorted(rejections.items())),
    }


def audit(folder):
    folder=Path(folder)
    buckets={"june":[],"july":[]};excluded=[]
    for date in DAYS:
        good=folder/f"m5_m1_{date}.json"
        bad=folder/f"quarantine_{date}.json"
        if good.is_file()==bad.is_file():
            raise ValueError("Missing or ambiguous full-day historical record "+date)
        if bad.is_file():
            q=json.loads(bad.read_text(encoding="utf-8"))
            if (q.get("day")!=date or
                q.get("whole_source_quarantined") is not True or
                q.get("trades_included")!=0 or not q.get("reason")):
                raise ValueError("Whole-day quarantine not verifiable")
            excluded.append(q)
            continue
        rec=json.loads(good.read_text(encoding="utf-8"))
        if (rec.get("day")!=date or
            rec.get("auto_trading_approved") is not False or
            rec.get("M5_context_M1_entries_only") is not True or
            rec.get("no_independent_M5_orders") is not True or
            rec.get("single_XAU_position") is not True or
            rec.get("source_is_not_MT5_broker") is not True or
            rec.get("manual_user_marks_present") is not False or
            rec.get("strategy_fidelity_verified") is not False or
            rec.get("warmup_utc")!="09:00-12:00" or
            rec.get("trading_utc")!="12:00-21:00" or
            rec.get("source",{}).get("date_utc")!=date or
            len(rec.get("source",{}).get("sha256",""))!=64 or
            set(rec.get("results",{}))!=set(POLICIES)):
            raise ValueError("Data source or live-trading approval claim unverified")
        for policy in POLICIES:
            if set(rec["results"][policy]["costs"])!=set(COSTS):
                raise ValueError("Missing one of the cost scenarios")
        if rec["results"][POLICIES[1]]["signals"]>rec["results"][POLICIES[0]]["signals"]:
            raise ValueError("M5 context added a fabricated M1 signal")
        buckets["june" if date in JUNE else "july"].append(rec)
    if min(len(bucket) for bucket in buckets.values())<4:
        raise ValueError("At least four valid dates required in each predeclared window")
    result={
        policy:{
            cost:{
                month:_summarize(days,policy,cost)
                for month,days in buckets.items()
            } for cost in COSTS
        } for policy in POLICIES
    }
    reasons=Counter()
    touches=Counter()
    for days in buckets.values():
        for rec in days:
            reasons.update(rec["M5_context_rejections"])
            touches.update(rec["M1_M5_zone_touch_rejections"])
    return {
        "study":"XAUUSD M5 context with M1 execution only: PA trend-break retest unchanged; M5 range confirmation",
        "predeclared_dates":{"june":list(JUNE),"july":list(JULY)},
        "clean_dates":{k:[r["day"] for r in v] for k,v in buckets.items()},
        "quarantined":excluded,
        "M5_veto_reasons":dict(sorted(reasons.items())),
        "M5_zone_contact":dict(sorted(touches.items())),
        "user_marks_verified":False,
        "source":"Dukascopy XAUUSD historical BID/ASK, not MT5 broker",
        "hypothetical_costs":"standard $0.30/oz roundtrip and $0.10/oz per side; double $0.60 and $0.20, plus spread",
        "trade_unit":"US dollars per one theoretical ounce; not MT5 lots",
        "not_prospective_forward":True,
        "no_live_trades":True,
        "trading_approved":False,
        "results":result,
    }


def report_text(r):
    lines=[
        "# Price Action XAUUSD — M5 contexto, M1 entrada (v6)",
        "",
        "**Hipótese congelada antes dos dados:** não liberar toque em suporte ou "
        "resistência no M1 sem lateralização comprovada no M5 fechado, "
        "zona M5 com dois pivôs anteriores confirmados e contato do candle M1. "
        "Os sinais de LTA/LTD rompimento + reteste permanecem INALTERADOS. "
        "M5 nunca abre posição isolada. Todas as operações usam o simulador "
        "M1 BID/ASK com trava de uma posição.",
        "",
        f"Junho: {len(r['clean_dates']['june'])}/5 datas válidas; "
        f"julho: {len(r['clean_dates']['july'])}/5 datas válidas.",
        "",
        "## Comparação, custos hipotéticos DOBRADOS",
        "",
        "| Política | Jun sinais/fills | Jun US$/oz | Jul sinais/fills | Jul US$/oz |",
        "|---|---:|---:|---:|---:|",
    ]
    for policy in POLICIES:
        a=r["results"][policy]["double"]
        x=a["june"];y=a["july"]
        lines.append(f"| {policy} | {x['signals']}/{x['filled']} | "
                     f"{x['net_usd_per_oz']:+.3f} | "
                     f"{y['signals']}/{y['filled']} | "
                     f"{y['net_usd_per_oz']:+.3f} |")
    lines.extend([
        "",
        "## Causas que impedem entradas e distribuição das saídas",
        f"- Regime e zonas M5: {r['M5_veto_reasons']}",
        f"- Contato do candle M1 na zona M5: {r['M5_zone_contact']}",
    ])
    for policy in POLICIES:
        for month,row in r["results"][policy]["double"].items():
            lines.append(
                f"- {policy}, {month}: {row['setup_metrics']}; "
                f"saídas={row['exits']}; PF={row['profit_factor']}; "
                f"expectativa/oper={row['expectancy_usd_per_oz']}; "
                f"bootstrap por sessão={row['daily_bootstrap_95pct']}"
            )
    lines.extend([
        "",
        "**Nenhum dado de marcação real do usuário foi fornecido.** "
        "Todas as LTA/LTD/zonas são aproximações causais automáticas, "
        "não sua análise discricionária. Os valores são USD/1 onça teórica "
        "após custos simulados, não lucros ou perdas de conta. "
        "Períodos históricos não são forward na corretora. "
        "**Não aprovado para operação automática.**",
        "",
        "## Exclusões por validade do feed (dia inteiro)",
    ])
    lines.extend(f"- {x['day']}: {x['reason']}" for x in r["quarantined"])
    if not r["quarantined"]:lines.append("- Nenhuma")
    return "\n".join(lines)+"\n"


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--evidence",required=True)
    p.add_argument("--output",required=True)
    args=p.parse_args()
    result=audit(args.evidence)
    root=Path(args.output);root.mkdir(parents=True,exist_ok=True)
    (root/"m5_context_m1_v6.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    md=report_text(result)
    (root/"m5_context_m1_v6.md").write_text(md,encoding="utf-8")
    print(md)
