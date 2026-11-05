"""Run a small fixed V4 study on a pinned, independently sourced WINQ26 M1.

May = development diagnostic, June/July = later retrospective checks (but
previous V1/V3 June/July results have been inspected in prior investigations).
Do NOT claim pristine forward validation or select a 1-month winning variant.

The study fixes signal rules and exit execution before viewing V4 results.
Uses the unchanged WIN futures engine, R$5000 and 0.75% risk, costs and tick
stress. A monthly candidate signal is only emitted on candles in that month.
"""
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from research.atlas_winq26_public import fetch, canonicalize, SYMBOL
from research.win_price_data import read_win_csv, local_day, win_session
from research.atlas_v4_filters import CANDIDATES, candidate
from research import atlas_win_backtest as win

PERIODS=(
    ("development_2026_05","2026-05-01","2026-06-01"),
    ("audit_2026_06","2026-06-01","2026-07-01"),
    ("audit_2026_07","2026-07-01","2026-08-01"),
)
COST_TICKS=(0,1,2)
FEE_BRL=4.0

def selected_month(bars,start,end):
    indices=[i for i,b in enumerate(bars) if start<=local_day(b["time"])<end]
    if not indices:
        return None,0
    first,last=indices[0],indices[-1]
    # 160 historical bars for warmup, but no signals/trades inside seed interval.
    if first < 160:
        return None,0
    sample=bars[first-160:last+1]
    return sample, first-(first-160)

def coverage(bars,start,end):
    days=defaultdict(int)
    for bar in bars:
        d=local_day(bar["time"])
        if start<=d<end and win_session(bar["time"]):
            days[d]+=1
    vals=sorted(days.values())
    return {"session_days":len(days),
            "minutes_in_session":sum(vals),
            "days_with_300_min":sum(x>=300 for x in vals),
            "median_minutes_per_day":vals[len(vals)//2] if vals else None,
            "min_minutes_per_day":min(vals) if vals else None}

def examine(imported,provenance):
    if imported["symbol"]!=SYMBOL or imported["timeframe_seconds"]!=60:
        raise ValueError("WINQ26 real M1 source required")
    bars=imported["bars"]
    out={
        "market":"WINQ26", "model":"independent filters, not Tracker source",
        "source":provenance,
        "pre_registered_variants":list(CANDIDATES),
        "training_month":"2026-05",
        "audit_months":["2026-06","2026-07"],
        "audits_are_not_pristine":"Earlier V1/V3 results were already observed on June/July",
        "execution":"same untouched research.atlas_win_backtest engine, prior closed candle, next bar 50% limit, -100% stop, 200% target, 1:1 nominal",
        "costs":{"fee_brl_per_contract_roundtrip":FEE_BRL,
                 "ticks_slippage_per_side":list(COST_TICKS)},
        "capital_brl":win.CAPITAL_BRL,"planned_risk_fraction":win.RISK,
        "approved_for_live":False,"forward_validated":False,
        "periods":{},
    }
    for name,start,end in PERIODS:
        sample,_=selected_month(bars,start,end)
        quality=coverage(bars,start,end)
        p={"data_quality":quality,"variants":{},"diagnostics":{},"status":"not_run"}
        out["periods"][name]=p
        if not sample or quality["days_with_300_min"]<8:
            p["status"]="INSUFFICIENT_LIQUID_M1_MONTH";continue
        p["status"]="BACKTESTED"
        day_markers=[start<=local_day(bar["time"])<end for bar in sample]
        # Each candidate is computed once, using bars up to the signal candle only.
        # The same cached signal is used at every transaction cost level.
        for var in CANDIDATES:
            signals=[candidate(sample,j,var) if j>=100 and day_markers[j] else 0
                     for j in range(len(sample))]
            with patch.object(win,"candidate",
                              side_effect=lambda ignored_b,i,ignored_variant,s=signals:s[i]):
                simulations={
                    str(k):win.simulate(sample,timeframe="M1",variant="original",
                                        fee_brl=FEE_BRL,slip_ticks=k)
                    for k in COST_TICKS
                }
            p["variants"][var]=simulations
            baseline=simulations["1"]
            p["diagnostics"][var]={
                "signal_buys":sum(s==1 for s in signals),
                "signal_sells":sum(s==-1 for s in signals),
                "entry_orders_filled":baseline.get("entries"),
                "orders_cancelled_or_unfilled":baseline.get("unfilled_or_cancelled"),
                "open_at_month_end":baseline.get("open_at_end"),
                "same_bar_ambiguous_exits":baseline.get("uncertain_same_bar_exits"),
            }
    out["approval_gate"]=approval_gate(out)
    return out

def approval_gate(out):
    """Conservative study gate: no automatic deployment or strategy selection."""
    result={}
    for model in CANDIDATES:
        reasons=[]
        for name,_,_ in PERIODS:
            period=out["periods"][name]
            if period["status"]!="BACKTESTED":
                reasons.append(name+"_unavailable");continue
            sims=period["variants"][model]
            base,stress=sims["1"],sims["2"]
            if (base.get("closed") or 0)<30:
                reasons.append(name+"_under_30_trades")
            if (base.get("net_brl") or 0)<=0 or (stress.get("net_brl") or 0)<=0:
                reasons.append(name+"_net_negative_or_flat_under_costs")
            if (base.get("profit_factor") or 0)<1.2:
                reasons.append(name+"_pf_below_1.2")
            if base.get("open_at_end") or base.get("pending_at_end"):
                reasons.append(name+"_unresolved_position_or_order")
        result[model]={"passes":not reasons,"reasons":reasons}
    return {
        "passed":sum(z["passes"] for z in result.values()),
        "total":len(result),"auto_promote":False,"models":result,
        "note":"Even a retrospective gate pass requires new-contract prospective validation",
    }

def tabulate(out):
    lines=[
        "# ATLAS V4 — estudo de filtros sem otimização por lucro histórico",
        "",
        "**NÃO é Tracker, não é robô aprovado e não representa operações reais.**",
        "Modelos e thresholds foram declarados antes do teste; não ajustados para 2026-06/07.",
        "As séries de junho/julho já foram examinadas para modelos anteriores, portanto NÃO são forward nem holdout absolutamente virgem.",
        "Fonte WINQ26 terceira (Profit) com hash de Git fixado, não auditada pela B3.",
        "Risco nominal 0,75%/operação, banca R$5.000, até 3 contratos inteiros.",
        "Taxa estimada R$4 por contrato roundtrip mais slippage de 0, 1, 2 ticks por lado.",
        "",
        "## Cobertura e resultados M1 com 1 tick por lado",
        "",
        "| Período | Dias com >=300 M1 | Modelo | Trades fechados | Acerto | P&L R$ | PF | DD% |",
        "|---|---:|---|---:|---:|---:|---:|---:|",
    ]
    for period,p in out["periods"].items():
        quality=p["data_quality"]
        if p["status"]!="BACKTESTED":
            lines.append(f"| {period} | {quality['days_with_300_min']} | INDISPONÍVEL | — | — | — | — | — |")
            continue
        for model,sc in p["variants"].items():
            x=sc["1"]
            def fmt(n):
                return "N/D" if n is None else str(n)
            lines.append("| "+" | ".join([
                period,str(quality["days_with_300_min"]),model,
                fmt(x.get("closed")),fmt(x.get("winrate_pct")),
                fmt(x.get("net_brl")),fmt(x.get("profit_factor")),
                fmt(x.get("max_realized_drawdown_pct"))])+" |")
    lines+=["","## Sensibilidade ao custo (P&L R$)",
            "| Período | Modelo | 0 tick | 1 tick | 2 ticks |",
            "|---|---|---:|---:|---:|"]
    for period,p in out["periods"].items():
        for model,sc in p["variants"].items():
            lines.append("| "+" | ".join([period,model]+[str(sc[str(k)]["net_brl"]) for k in COST_TICKS])+" |")
    lines+=["","## Diagnóstico — sinais emitidos vs entradas executadas", "",
            "| Período | Modelo | Sinais compra | Sinais venda | Entradas | Ordens canceladas |",
            "|---|---|---:|---:|---:|---:|"]
    for period,p in out["periods"].items():
        for model,d in p["diagnostics"].items():
            lines.append("| "+" | ".join([
                period,model,str(d["signal_buys"]),str(d["signal_sells"]),
                str(d["entry_orders_filled"]),str(d["orders_cancelled_or_unfilled"])])+" |")
    gate=out["approval_gate"]
    lines+=["",f"## Gate quantitativo: {gate['passed']}/{gate['total']} modelos aprovados","",
            "Nenhuma aprovação causa promoção automática.",
            "A ausência de trades não é evidência de lucro.", "", "## Aprovação",
        "Nenhuma estratégia será promovida sem lucro líquido sob 2 ticks por lado em mais de um período e vencimento, amostra adequada e teste prospectivo.",
        "Não premiar 0 trades (sinalizar nada não é edge). V4 é pesquisa; nenhum código operacional foi alterado.",
        "Se o estudo permanecer negativo, registrar o insucesso e priorizar dados novos em vez de procurar 100 filtros no mesmo mês.",
        ""]
    return "\n".join(lines)

def main():
    with TemporaryDirectory() as work:
        raw=Path(work)/"WINQ26_source.csv"
        canon=Path(work)/"WINQ26_M1.csv"
        source=fetch(raw)
        details=canonicalize(raw,canon)
        imported=read_win_csv(canon,expected_symbol=SYMBOL)
        out=examine(imported,{**source,"quality":details})
    doc=tabulate(out)
    print("ATLAS_V4_RESULTS_BEGIN",flush=True)
    print(doc,flush=True)
    print("ATLAS_V4_RESULTS_END",flush=True)
    folder=Path("research/results");folder.mkdir(parents=True,exist_ok=True)
    (folder/"atlas_v4_study_latest.json").write_text(
        json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (folder/"atlas_v4_study_latest.md").write_text(doc+"\n",encoding="utf-8")

if __name__=="__main__":
    main()
