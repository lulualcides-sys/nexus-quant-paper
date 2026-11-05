"""ATLAS research on fixed public WINQ26 M1; NO real execution or cherry-picking.

Use a single genuine contract, never synthetic continuous WINFUT or GC=F.
Freeze models BEFORE inspecting results; evaluate June (development) and
July (chronologically later holdout) with 0/1/2 ticks slippage each way.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import json
import tempfile

from research.atlas_winq26_public import canonicalize, fetch, SYMBOL, SOURCE_URL
from research.atlas_confluence_v3 import VARIANTS, v3_signal
from research.win_price_data import read_win_csv, resample, TZ, win_session, local_day
from research import atlas_win_backtest as win

PERIODS={"train_2026_06": ("2026-06-01", "2026-07-01"),
         "holdout_2026_07": ("2026-07-01", "2026-08-01")}
TF={"M1":60,"M5":300,"M15":900,"M30":1800,"H1":3600}
SLIPPAGE_TICKS=(0,1,2)


def _period(candles, start, end):
    indices = [i for i,b in enumerate(candles) if start<=local_day(b["time"])<end]
    if not indices:
        return []
    # 80-bar warmup from past, but no entries are considered during first 60.
    # Use exactly 60 past candles at start, not future data.
    first=indices[0]
    if first < 60:
        return []
    return candles[first-60:indices[-1]+1]


def _daily_coverage(bars, year_month):
    grouped=defaultdict(list)
    for b in bars:
        d=local_day(b["time"])
        if d.startswith(year_month) and win_session(b["time"]):
            grouped[d].append(b)
    return {"trading_days":len(grouped),"days_with_300_candles":sum(len(x)>=300 for x in grouped.values()),
            "minimum_session_candles":min(map(len,grouped.values())) if grouped else None,
            "median_session_candles": sorted(map(len,grouped.values()))[len(grouped)//2] if grouped else None,
            "total_session_candles":sum(map(len,grouped.values()))}


def compare(imported, provenance=None):
    if imported["symbol"]!=SYMBOL or imported["timeframe_seconds"] !=60:
        raise ValueError("Only WINQ26 M1 is valid for this comparison")
    src=imported["bars"]
    result={
        "study":"ATLAS: frozen v1/v2/v3 on WINQ26 real-contract M1",
        "source":provenance or {"source":SOURCE_URL, "unverified":True},
        "symbol":SYMBOL,"instrument_type":"B3 WINQ26 dated contract, NOT continuous adjusted WINFUT",
        "start_local":datetime.fromtimestamp(src[0]["time"],timezone.utc).astimezone(TZ).isoformat(),
        "end_local":datetime.fromtimestamp(src[-1]["time"],timezone.utc).astimezone(TZ).isoformat(),
        "raw_candles":len(src),
        "source_market_data_caveat":"Third-party Profit export, not independently audited with B3",
        "train_fixed":"2026-06", "holdout_fixed":"2026-07",
        "paper_only":True,"validated":False,
        "point_value_brl_per_contract":0.20,"min_tick_points":5,
        "risk_cap_fraction":0.0075,"max_contracts":3,
        "outcome_claim":"No guaranteed replication of Tracker or 22 wins/5 stops",
        "scope":"No human model tuning on observed holdout results",
        "quality":{
            "2026-06":_daily_coverage(src,"2026-06"),
            "2026-07":_daily_coverage(src,"2026-07")},
        "parameters":{
            "models":list(VARIANTS), "cost_brl_roundtrip_per_contract":4,
            "slippage_ticks_each_side":list(SLIPPAGE_TICKS),
            "signal_rule":"after confirmed candle; limit at 50%, stop -100%, target 200%; 1:1 nominal",
            "v3":"sweep+volume+close confirmation+prior ATR+prior 48-bar Fibonacci-inspired zone (0.382/0.618)",
            "v3_obstacle":"additional confirmed clustered pivots between entry and target veto",
            "warning":"These are explicitly independent proxies, not the closed Tracker formula"
        },
        "results":{}
    }
    for tf, seconds in TF.items():
        rows=resample(src,seconds,base_seconds=60)
        result["results"][tf]={}
        for pname,(start,end) in PERIODS.items():
            period=_period(rows,start,end)
            result["results"][tf][pname]={
                "source_bars":len(period),"calendar_start":start,"calendar_end_exclusive":end,
                "variants":{}
            }
            for var in VARIANTS:
                score={}
                with patch.object(win,"candidate",side_effect=lambda b,i,ignored,v=var: v3_signal(b,i,v)):
                    for slip in SLIPPAGE_TICKS:
                        if period:
                            outcome=win.simulate(period,timeframe=tf,variant="original",
                                                 fee_brl=4.0,slip_ticks=slip)
                        else:
                            outcome={"status":"insufficient_bars","closed":None,
                                     "winrate_pct":None,"net_brl":None}
                        score[str(slip)]=outcome
                result["results"][tf][pname]["variants"][var]=score
    return result


def summarize(data):
    lines=[
      "# ATLAS — WINQ26 contrato real: validação em junho e julho/2026",
      "",
      "**NÃO é a fórmula do Tracker.** Estudo retrospectivo exploratório.",
      "O modelo, o contrato e as datas foram fixados antes da inspeção de resultados.",
      "Dados terceirizados exportados de Profit, não fills auditados da B3.",
      "Preço WIN: 5 pontos/tick; R$0,20 por ponto e por minicontrato.",
      "Banca virtual R$5.000; risco máximo nominal 0,75%, até 3 contratos.",
      "Custo: R$4/contrato ida+volta + slippage variável (0–2 ticks por lado).",
      "",
      "## Cobertura da fonte",
    ]
    for k,v in data["quality"].items():
        if not k.startswith("2026-"):
            continue  # source-wide metadata is not a calendar-month coverage row
        lines.append(f"- {k}: {v['trading_days']} pregões; {v['total_session_candles']} candles M1 "
                     f"na janela de estudo; mediana {v['median_session_candles']} por pregão; "
                     f"{v['days_with_300_candles']} pregões com >=300 candles.")
    lines+=["","## Resultados com 1 tick de slippage por lado","",
            "| TF | Período | Modelo | Trades | Winrate | P&L R$ | PF | DD fechado |",
            "|---|---|---|---:|---:|---:|---:|---:|"]
    for tf,periods in data["results"].items():
        for pname,p in periods.items():
            for var,scenarios in p["variants"].items():
                x=scenarios["1"]
                def fmt(v, suffix=""):
                    return "N/D" if v is None else str(v)+suffix
                lines.append(
                    f"| {tf} | {pname} | {var} | {fmt(x.get('closed'))} | "
                    f"{fmt(x.get('winrate_pct'),'%')} | {fmt(x.get('net_brl'))} | "
                    f"{fmt(x.get('profit_factor'))} | "
                    f"{fmt(x.get('max_realized_drawdown_pct'),'%')} |")
    lines+=["","## Controle de custos (líquido em R$)",
            "| TF | Período | Modelo | 0 ticks | 1 tick | 2 ticks |",
            "|---|---|---|---:|---:|---:|"]
    for tf,periods in data["results"].items():
        for pname,p in periods.items():
            for var,scenarios in p["variants"].items():
                numbers=["N/D" if scenarios[str(k)].get("net_brl") is None
                         else str(scenarios[str(k)]["net_brl"]) for k in SLIPPAGE_TICKS]
                lines.append("| "+ " | ".join([tf,pname,var]+numbers)+" |")
    lines+=["","## Critérios para avançar","",
      "- Não premiar winrate elevado sem amostra suficiente; operações em julho são validação retrospectiva, não forward.",
      "- Só considerar estratégias que mantêm expectativa líquida positiva após taxas/slippage, PF sustentado e drawdown aceitável em vários períodos e contratos, inclusive meses posteriores.",
      "- OHLC M1 desconhece sequência exata do toque de entrada/stop/alvo dentro do minuto; saída pessimista em ambiguidade.",
      "- Não se pode inferir delta de agressor, absorção institucional, manipulação, ou o indicador comercial Tracker somente com OHLCV.",
      "- Dataset terceiro é limitado a WINQ26 até julho/2026: o pregão anunciado de 13/10/2026 usa outro vencimento e não pode ser replicado aqui.",
      "- Dados contínuos WINFUT ajustados com preços fora do tick NÃO são aceitos como preços negociáveis.",
      "- Nunca converter taxa promocional 22/27 de um pregão em promessa de winrate futuro.",
      ""]
    return "\n".join(lines)


def main():
    with tempfile.TemporaryDirectory() as d:
        raw=Path(d)/"WINQ26_profit_raw_1min.csv"
        normalized=Path(d)/"WINQ26_M1.csv"
        provenance=fetch(raw)
        quality=canonicalize(raw,normalized)
        imported=read_win_csv(normalized,expected_symbol=SYMBOL)
        report=compare(imported,provenance)
        report["quality"]["raw"]=quality
    text=summarize(report)
    print("ATLAS_WINQ26_REPORT_START")
    print(text,flush=True)
    print("ATLAS_WINQ26_REPORT_END")
    out=Path("research/results")
    out.mkdir(parents=True,exist_ok=True)
    (out/"atlas_winq26_v3_latest.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (out/"atlas_winq26_v3_latest.md").write_text(text,encoding="utf-8")


if __name__=="__main__":
    main()
