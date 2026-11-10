"""Unselected STOP geometry diagnostic for the EXISTING XAU M1 v6 signals.

No candidate generation/filter changes: exactly same filled entries when the
old STOP is used. "Fix" is only an explicitly unapproved STOP hypothesis.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import random

from research.xau_pa_m5_context_m1_v6 import JUNE,JULY,DAYS
MODELS=("unchanged_v6","line_stop_check")
COSTS=("standard","double")


def _aggregate(rows,model,cost):
    signals=0;filled=[];days=[];source_reject=Counter()
    for row in rows:
        item=row["models"][model]
        ledger=item["costs"][cost]
        if (item["signals"]!=ledger["signals"] or
            ledger["filled"]!=len(ledger["trades"]) or
            ledger["filled"]>ledger["signals"] or
            abs(ledger["net_usd_per_oz"]-
                sum(t["net_usd_per_oz"] for t in ledger["trades"]))>.001):
            raise ValueError("Ledger not reproducible")
        signals+=item["signals"]
        filled.extend(ledger["trades"])
        days.append(sum(t["net_usd_per_oz"] for t in ledger["trades"]))
        source_reject.update(ledger["rejected"])
    gains=sum(max(t["net_usd_per_oz"],0) for t in filled)
    losses=-sum(min(t["net_usd_per_oz"],0) for t in filled)
    net=gains-losses
    rng=random.Random(20261110)
    boot=sorted(sum(rng.choices(days,k=len(days))) for _ in range(2000))
    return {
        "days":len(rows),"signals":signals,
        "filled":len(filled),
        "wins":sum(t["net_usd_per_oz"]>0 for t in filled),
        "losses":sum(t["net_usd_per_oz"]<0 for t in filled),
        "net_usd_per_oz":round(net,6),
        "profit_factor":round(gains/losses,6) if losses else None,
        "stops":sum(t["reason"]=="STOP" for t in filled),
        "targets":sum(t["reason"]=="TARGET" for t in filled),
        "timeouts":sum(t["reason"]=="TIME" for t in filled),
        "bootstrap_daily_net_95pct":[round(boot[49],6),round(boot[1949],6)],
        "execution_rejections":dict(sorted(source_reject.items())),
    }


def summarize(root):
    root=Path(root)
    buckets={"june":[],"july":[]};quarantine=[]
    for date in DAYS:
        path=root/f"stop_geom_{date}.json"
        failed=root/f"quarantine_{date}.json"
        if path.is_file()==failed.is_file():
            raise ValueError("Missing or duplicate session "+date)
        if failed.is_file():
            r=json.loads(failed.read_text())
            if (r.get("day")!=date or r.get("whole_day_quarantined") is not True
                or r.get("trades_included")!=0 or not r.get("reason")):
                raise ValueError("Invalid quarantine record")
            quarantine.append(r);continue
        row=json.loads(path.read_text())
        if (row.get("day")!=date or
            row.get("original_v6_exactly_replayed") is not True or
            row.get("same_M1_signals_and_execution_ticks") is not True or
            row.get("only_stop_geometry_changed") is not True or
            row.get("correct_stop_distances_user_confirmed") is not False or
            row.get("is_not_mt5_broker") is not True or
            row.get("live_trading_approved") is not False or
            row["source"].get("date_utc")!=date or
            len(row["source"].get("sha256",""))!=64 or
            set(row["models"])!=set(MODELS)):
            raise ValueError("Unverified source, user stops or profitability")
        for model in MODELS:
            if set(row["models"][model]["costs"])!=set(COSTS):
                raise ValueError("Incomplete ledger scenarios")
        if row["models"][MODELS[0]]["signals"]!=row["models"][MODELS[1]]["signals"]:
            raise ValueError("Stop hypothesis may not invent signals")
        buckets["june" if date in JUNE else "july"].append(row)
    if min(len(x) for x in buckets.values())<4:
        raise ValueError("Incomplete independent historical block")
    results={
        model:{
            cost:{
                month:_aggregate(rows,model,cost)
                for month,rows in buckets.items()
            } for cost in COSTS
        } for model in MODELS
    }
    stops=Counter()
    for rows in buckets.values():
        for r in rows:
            stops.update(r["candidate_geometry"])
    return {
        "study":"Actual v6 stop placements vs retested LTA/LTD, unchanged entry and quote stream",
        "calendar":{"june":list(JUNE),"july":list(JULY)},
        "clean_dates":{x:[q["day"] for q in y] for x,y in buckets.items()},
        "quarantined":quarantine,
        "geometry":dict(sorted(stops.items())),
        "user_stop_red_win_still_undocumented":True,
        "actual_broker_mt5_test":False,
        "forward_out_of_sample":False,
        "profits_real":False,
        "auto_trade_approved":False,
        "units":"USD per one hypothetical troy oz, not account equity",
        "result":results,
    }


def markdown(r):
    g=r["geometry"]
    lines=[
        "# Price Action XAUUSD — por que os stops estão sendo atingidos?",
        "",
        "**Objetivo:** não criar robôs, indicadores nem filtros. Reexecutar os "
        "mesmos sinais da v6 e verificar se o stop ficou do lado errado da "
        "LTA/LTD rompida. Um segundo braço muda SOMENTE esse posicionamento "
        "para além da linha por 0,10 ATR. Isso é uma HIPÓTESE de stop, "
        "**não** a regra Stop Red real do usuário.",
        "",
        f"Junho {len(r['clean_dates']['june'])}/5 sessões válidas; "
        f"julho {len(r['clean_dates']['july'])}/5.",
        "",
        "## Causa: geometria do stop no nível de reteste",
        "",
        f"- Sinais rompimento/reteste inspecionados: {g['break_retest_candidates']}",
        f"- Stops do lado errado da linha ANTES de simular: {g['stop_wrong_side_candidates']}",
        f"- Operações executadas com stop do lado errado: {g['filled_stop_wrong_side']}",
        f"- Stops efetivamente reposicionados na hipótese: {g['actually_adjusted_candidate_stops']}",
        "",
        "## Contabilidade BID/ASK idêntica, custos DOBRADOS",
        "",
        "| Cenário de STOP | Junho trades | Junho US$/oz | Julho trades | Julho US$/oz |",
        "|---|---:|---:|---:|---:|",
    ]
    for model in MODELS:
        j=r["result"][model]["double"]["june"]
        u=r["result"][model]["double"]["july"]
        lines.append(f"| {model} | {j['filled']} | {j['net_usd_per_oz']:+.3f} | "
                     f"{u['filled']} | {u['net_usd_per_oz']:+.3f} |")
    lines.extend([
        "",
        "O cenário hipotético não muda o lado, símbolo, candle, horário, "
        "tendência, marcações, critério de rompimento/reteste ou custos. "
        "O novo stop pode aumentar o tamanho do risco e mudar alvos 2R e fills "
        "por limitação econômica: **nenhum benefício garantido**.",
        "",
        "O backtest ainda usa marcações PROXY, não as marcas manuais do trader. "
        "Stop Win, Stop Red e disposição real para reentradas não foram "
        "definidos pelo usuário em preços/horários. Não é corretora MT5, "
        "não é teste futuro e não justifica dinheiro real.",
        "",
        "**Decisão: não aprovar nenhuma variante sem confirmar geometria "
        "manual e expectativa líquida em dados intocados.**",
        "",
        "## Quarentenas de sessões inteiras",
    ])
    lines.extend(f"- {q['day']}: {q['reason']}" for q in r["quarantined"])
    if not r["quarantined"]:
        lines.append("- Nenhuma")
    return "\n".join(lines)+"\n"


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--folder",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    report=summarize(a.folder)
    dest=Path(a.out);dest.mkdir(parents=True,exist_ok=True)
    (dest/"xau_pa_stop_geometry.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    md=markdown(report)
    (dest/"xau_pa_stop_geometry.md").write_text(md,encoding="utf-8")
    print(md)


if __name__=="__main__":
    main()
