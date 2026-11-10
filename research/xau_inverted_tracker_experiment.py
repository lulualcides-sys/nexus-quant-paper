"""Counterfactual BUY↔SELL inversion at EXACTLY the original XAUUSD signal times.

Hypothesis fixed before the July historical replication: flip BUY→SELL and
SELL→BUY, mirror price-based Fibonacci entry/target/stop around the candle.
Quotes are genuine Dukascopy historical bid/ask; no equity-account or
Greenhouse Tracker claim. This is NOT profit-flipping the original ledger:
counterfactual quotes, fills, spread, expiries and exits are re-simulated.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path

from research.xau_frequency_lab import (
    VARIANTS, policies_for, levels_for, planned_for,
)
from research.xau_dukascopy_replay import aggregate_real_quotes
from research.xau_quote_execution_backtest import (
    ExecutionAssumptions, _ticks, simulate_quote_execution
)
from research.xau_quote_tracker_reference import scan_closed


# Original research presets; DO NOT select settings after seeing a result.
VARIANT_KEYS = tuple(f"{v.name}_{tf}" for tf in ("M1", "M5") for v in VARIANTS)
SIDES = ("original", "inverted")
# The original experiment already reported negative on all variants for August.
# All dates are historical, NOT a prospective out-of-sample production test.
AUGUST = (
 "20260803","20260804","20260805","20260806","20260807",
 "20260810","20260811","20260812","20260813","20260814",
 "20260817","20260818","20260819","20260820","20260821",
 "20260824","20260825","20260826","20260827","20260828",
)
# Precommitted, separately evaluated replication dates (not used in the
# original six-variant design). July is still a historical, not future, test.
JULY = (
 "20260706","20260707","20260708","20260709","20260710",
 "20260713","20260714","20260715","20260716","20260717",
)
DATES = JULY + AUGUST


def mirrored_plans(bars: list[dict], tf: int, variant, policy):
    """Same signal candle/time, opposite trade direction, mirrored geometry."""
    original=planned_for(bars,tf,variant,policy)
    candles={int(b["time"])*1000:b for b in bars}
    mirrored=[]
    for old in original:
        candle=candles[old["signal_ms"]]
        side=-old["side"]
        levels=levels_for(candle,side,variant,policy.tick_size)
        mirrored.append({
            "signal_ms":old["signal_ms"],
            "eligible_ms":old["eligible_ms"],
            "side":side, **levels
        })
    assert len(mirrored)==len(original)
    return original,mirrored


def run_one_day(path: str | Path, date: str, *, point: float=.001,
                commission: float=.60, slippage: float=.20) -> dict:
    if date not in DATES or point<=0 or commission<0 or slippage<0:
        raise ValueError("Invalid predeclared day or cost parameters")
    path=Path(path)
    quotes=list(_ticks(path))
    if len(quotes)<1000:
        raise ValueError("Insufficient source bid/ask quotes")
    results={}
    feed_sha=None
    bar_counts={}
    for tf in (60,300):
        candles, audit=aggregate_real_quotes(path,tf,point)
        if audit["first_candle_utc"][:10].replace("-","")!=date:
            raise ValueError("Wrong source date")
        if feed_sha is not None and feed_sha!=audit["source_sha256"]:
            raise ValueError("M1/M5 data source changed")
        feed_sha=audit["source_sha256"]
        bar_counts[f"M{tf//60}"]=len(candles)
        policies=policies_for(tf,point)
        for var in VARIANTS:
            orig,inv=mirrored_plans(candles,tf,var,policies[var.policy])
            key=f"{var.name}_{'M1' if tf==60 else 'M5'}"
            value={"signals":len(orig),"variant":asdict(var),
                   "timeframe_seconds":tf,"sides":{}}
            for name,planned in (("original",orig),("inverted",inv)):
                cfg=ExecutionAssumptions(
                    timeframe_seconds=tf,
                    commission_roundtrip_usd_per_oz=commission,
                    slippage_usd_per_side=slippage,
                )
                run=simulate_quote_execution(iter(quotes),planned,cfg)
                if run["filled"]!=run["closed"] or run["filled"]>len(orig):
                    raise ValueError("Invalid counterfactual accounting")
                value["sides"][name]={
                    "filled":run["filled"],"wins":run["wins"],"losses":run["losses"],
                    "expired":run["unfilled_expired"],
                    "skipped":run["skipped_busy_or_unseen"],
                    "net_usd_per_oz":run["net_usd_per_oz"],
                    "gross_profit_usd_per_oz":run["gross_profit_usd_per_oz"],
                    "gross_loss_usd_per_oz":run["gross_loss_usd_per_oz"],
                    "max_closed_drawdown_usd_per_oz":run["max_closed_drawdown_usd_per_oz"],
                    "ledger":run["ledger"],
                }
            results[key]=value
    return {
        "date":date,
        "source":"Dukascopy XAUUSD spot bid/ask quote updates",
        "source_sha256":feed_sha,"quote_rows":len(quotes),
        "m1_bars":bar_counts["M1"],"m5_bars":bar_counts["M5"],
        "assumptions":{"commission_roundtrip_usd_per_oz":commission,
                       "slippage_usd_per_side":slippage,
                       "triggers":"bid/ask, same signal times; mirrored Fibonacci"},
        "identical_original_greenhouse_signals_verified":False,
        "broker_real_execution_verified":False,
        "approved_for_live":False,
        "results":results,
    }


def summarize(folder: str | Path) -> dict:
    folder=Path(folder)
    rows={"july":[],"august":[]}
    quarantine=[]
    for date in DATES:
        data=folder/f"xau_{date}.json"
        qa=folder/f"quarantine_{date}.json"
        if data.exists()==qa.exists():
            raise ValueError(f"Missing or double evidence on {date}")
        if qa.exists():
            q=json.loads(qa.read_text(encoding="utf-8"))
            if (q.get("day_id")!=date or q.get("all_trades_excluded_before_scoring") is not True or
                not q.get("data_quality_error")):
                raise ValueError("Malformed quarantine")
            quarantine.append(q)
            continue
        r=json.loads(data.read_text(encoding="utf-8"))
        if (r["date"]!=date or len(r["source_sha256"])!=64 or
            r["quote_rows"]<1000 or
            r["identical_original_greenhouse_signals_verified"] is not False or
            r["broker_real_execution_verified"] is not False or
            r["approved_for_live"] is not False or
            set(r["results"])!=set(VARIANT_KEYS)):
            raise ValueError(f"Invalid evidence on {date}")
        for key,item in r["results"].items():
            if set(item["sides"])!=set(SIDES):
                raise ValueError("Missing paired inverse/original scenario")
            for side in SIDES:
                s=item["sides"][side]
                if s["filled"]!=len(s["ledger"]) or s["filled"]>item["signals"]:
                    raise ValueError("Invalid ledger")
        rows["july" if date in JULY else "august"].append(r)

    if len(rows["july"])<8 or len(rows["august"])<16:
        raise ValueError("Too few clean days for replication; fail closed")

    board={}
    for key in VARIANT_KEYS:
        row={}
        for label,group in rows.items():
            panel={}
            for direction in SIDES:
                day_nets=[]
                trades=[]
                signals=filled=wins=losses=0
                for day in group:
                    record=day["results"][key]
                    item=record["sides"][direction]
                    signals+=record["signals"]
                    filled+=item["filled"]
                    wins+=item["wins"];losses+=item["losses"]
                    if len(item["ledger"])!=item["filled"]:
                        raise ValueError("Missing trade ledger")
                    trades.extend(item["ledger"])
                    day_nets.append(item["net_usd_per_oz"])
                profit=sum(sum(max(0,float(t["net_usd_per_oz"])) for t in []) for _ in [])
                profit=sum(max(0,float(t["net_usd_per_oz"])) for t in trades)
                loss=-sum(min(0,float(t["net_usd_per_oz"])) for t in trades)
                net=profit-loss
                if abs(net-sum(day_nets))>.002:
                    raise ValueError("P&L mismatch")
                panel[direction]={
                    "signals":signals,"filled":filled,"wins":wins,"losses":losses,
                    "net_usd_per_oz":round(net,4),
                    "profit_factor":round(profit/loss,4) if loss else None,
                    "expectancy_usd_per_oz":round(net/filled,4) if filled else None,
                    "positive_days":sum(x>0 for x in day_nets),
                    "losing_days":sum(x<0 for x in day_nets),
                    "zero_days":sum(x==0 for x in day_nets),
                }
            if panel["original"]["signals"]!=panel["inverted"]["signals"]:
                raise ValueError("Different BUY/SELL signal timestamps")
            row[label]=panel
        board[key]=row
    return {
        "hypothesis":"Same signals, reverse BUY/SELL only; reprice entry/TP/SL in opposite direction",
        "dates_predeclared":{"july":list(JULY),"august":list(AUGUST)},
        "clean_days":{name:len(group) for name,group in rows.items()},
        "whole_day_quarantines":quarantine,
        "costs":"USD 0.60/oz commission roundtrip, USD 0.20/oz stop/time slippage, bid/ask spread",
        "units":"hypothetical USD per one troy ounce; no verified brokerage account",
        "not_a_prospective_future_holdout":True,
        "profitability_approved":False,
        "original_tracker_equivalence":False,
        "variants":board,
    }


def markdown_report(report: dict) -> str:
    lines=[
        "# Tracker XAUUSD: inverter Compra/Venda funciona?",
        "",
        "O oposto é re-simulado quote a quote. **Não** é o negativo matemático do P&L original.",
        "Sem algoritmo proprietário; sem execução em broker MT5; todos os cenários hipotéticos.",
        f"Julho: **{report['clean_days']['july']}** datas válidas / 10 planejadas. "
        f"Agosto: **{report['clean_days']['august']}** válidas / 20 planejadas.",
        "",
        "| Configuração | TF | Jul original | Jul invertido | Jul fills inv. | Ago original | Ago invertido | Ago fills inv. |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for key in VARIANT_KEYS:
        s=report["variants"][key]
        j=s["july"]; a=s["august"]
        origj=j["original"]; invj=j["inverted"]
        origa=a["original"]; inva=a["inverted"]
        tf=key.rsplit("_",1)[-1]
        name=key[:-(len(tf)+1)]
        lines.append(
            f"| {name} | {tf} | {origj['net_usd_per_oz']:+.3f} | "
            f"{invj['net_usd_per_oz']:+.3f} | {invj['filled']} | "
            f"{origa['net_usd_per_oz']:+.3f} | {inva['net_usd_per_oz']:+.3f} | {inva['filled']} |"
        )
    lines.extend([
        "",
        "Custos hipotéticos DOBRADOS: $0.60/oz por roundtrip + $0.20/oz de slippage de stop/mercado.",
        "Mesmo spread bid/ask histórico, mesmo timestamp de sinal, "
        "mas preço/side de limit entry, take profit, stop e fills recalculados.",
        "",
        "Julho é uma replicação em **dados históricos anteriores** à amostra original; "
        "não pode ser chamado de teste futuro. Agosto já havia sido observado com prejuízos.",
        "Nenhuma inversão deve ser selecionada só por ganhar numa das datas ou variantes.",
        "Não aprovar ordens sem número de trades, robustez independente, custos reais "
        "e confirmação em feed de corretora MT5.",
        "",
        "## Sessões excluídas integralmente antes de contar operações",
    ])
    for q in report["whole_day_quarantines"]:
        lines.append(f"- {q['day_id']}: {q['data_quality_error']}")
    if not report["whole_day_quarantines"]:lines.append("- Nenhuma")
    lines.append("")
    return "\n".join(lines)+"\n"


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--ticks")
    ap.add_argument("--day")
    ap.add_argument("--out",required=True)
    ap.add_argument("--quarantine-out")
    ap.add_argument("--summarize",action="store_true")
    args=ap.parse_args()
    target=Path(args.out)
    if args.summarize:
        summary=summarize(target)
        out=target/"inversion_scorecard.json"
        out.write_text(json.dumps(summary,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        md=markdown_report(summary)
        (target/"inversion_scorecard.md").write_text(md,encoding="utf-8")
        print(md)
        return
    if args.day not in DATES or not args.ticks:
        raise ValueError("Only predeclared source dates are accepted")
    try:
        report=run_one_day(args.ticks,args.day)
    except ValueError as exc:
        reason=str(exc)
        if (not args.quarantine_out or not reason.startswith((
            "Invalid or crossed XAUUSD bid/ask",
            "Nonchronological or crossed price stream",
            "Out-of-order Dukascopy source",
            "Quote time anomaly",
        ))):
            raise
        with Path(args.ticks).open("rb") as f:
            hashv=hashlib.file_digest(f,"sha256").hexdigest()
        q={"day_id":args.day,"data_quality_error":reason,
           "all_trades_excluded_before_scoring":True,
           "source_sha256":hashv}
        Path(args.quarantine_out).write_text(json.dumps(q,indent=2)+"\n",encoding="utf-8")
        print("ENTIRE DAY QUARANTINED",args.day,reason)
        return
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("DAY",args.day,"quotes",report["quote_rows"],"SHA",report["source_sha256"])
    for key,row in sorted(report["results"].items()):
        original=row["sides"]["original"]
        inverse=row["sides"]["inverted"]
        print(key,"signals",row["signals"],
              "original filled",original["filled"],"original net",original["net_usd_per_oz"],
              "inverted filled",inverse["filled"],"inverted net",inverse["net_usd_per_oz"])


if __name__=="__main__":
    main()
