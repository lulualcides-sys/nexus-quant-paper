"""A/B M30 and original M1/M5/M15 paper bots on one identical XAU quote tape.

Reuses the previously verified 24 gold sessions, generates M30 strictly
from adjacent pairs of recorded M15 bars. DOES NOT download new quotes,
fabricate fills or change existing original entry rules. A second controlled
M1/M5 experiment tests ONLY bar-clock-equivalent maximum TIME exits, not
signal selection or stop/ATR multiples. No broker orders.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from research import xau_all_original_3tf as xau

SOURCE_REPORT_SHA256="3c5871014a7abf2c2abc68d1d28f3ea92bd289523f9b472d8aeb01031f6db6c7"
SOURCE_REPORT_REL="xau-score/27-originals-plus-atlas-xau-M1-M5-M15.json"
M30_SECONDS=1800
ORIGINAL_KEYS=28


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _from_m15(rows):
    """Build genuine consecutive M30 OHLC only. Reject gaps and duplicates."""
    groups=defaultdict(list)
    previous=None
    for bar in rows:
        stamp=bar["time"]
        if stamp%900 or (previous is not None and stamp<=previous):
            raise ValueError("M15 is unaligned, duplicate or out of order")
        previous=stamp
        groups[stamp//1800*1800].append(bar)
    out=[]
    for start,items in sorted(groups.items()):
        if len(items)!=2 or [b["time"] for b in items]!=[start,start+900]:
            raise ValueError(f"Incomplete real M30 bar: {start}; do not invent OHLC")
        out.append({
            "time":start,
            "open":items[0]["open"],
            "high":max(b["high"] for b in items),
            "low":min(b["low"] for b in items),
            "close":items[-1]["close"],
            # quote update counts only, never claimed trade/market volume
            "volume":sum(b["volume"] for b in items),
            "max_spread":max(b["max_spread"] for b in items),
        })
    if len(out)<xau.INITIAL_WARMUP+100:
        raise ValueError("M30 lacks original engine warmup plus 100 real candles")
    return out


def _load_frozen(root):
    root=Path(root)
    raw_path=root/SOURCE_REPORT_REL
    if _sha(raw_path)!=SOURCE_REPORT_SHA256:
        raise ValueError("Frozen 27+ATLAS original report SHA-256 mismatch")
    original=json.loads(raw_path.read_text(encoding="utf-8"))
    if len(original["predeclared_dates"])!=25 or len(original["valid_dates"])!=24:
        raise ValueError("Historical source sessions have changed")
    if set(original["valid_dates"])!=set(original["source_fingerprints"]):
        raise ValueError("Missing real quote fingerprints")
    observed={tf:[] for tf in ("M1","M5","M15")}
    for day in original["valid_dates"]:
        path=root/"xau-candles"/(day+".json")
        source=json.loads(path.read_text(encoding="utf-8"))
        if source.get("quarantined") or source["day"]!=day:
            raise ValueError(f"Invalid frozen source day {day}")
        if source["source_sha256"]!=original["source_fingerprints"][day]:
            raise ValueError(f"Unexpected quote fingerprint for {day}")
        for tf in observed:
            observed[tf].extend(source["bars"][tf])
    for tf,bars in observed.items():
        if len(bars)!=original["timeframes"][tf]["source_bars"]:
            raise ValueError(f"{tf} source candle count differs from original replay")
        if any(bars[i]["time"]<=bars[i-1]["time"] for i in range(1,len(bars))):
            raise ValueError("Duplicate or out-of-order M1/M5/M15 bar")
    observed["M30"]=_from_m15(observed["M15"])
    return original,observed


def _one(rows,tf,start_ts,clock_factor=1):
    a=xau.replay(rows,tf,stress=1.,start_ts=start_ts,
                 exit_horizon_multiplier=clock_factor)
    b=xau.replay(rows,tf,stress=2.,start_ts=start_ts,
                 exit_horizon_multiplier=clock_factor)
    if (set(a["books"])!=set(b["books"]) or
        len(a["books"])!=ORIGINAL_KEYS):
        raise RuntimeError("Missing original bot during price replay")
    return {key:{
        **val,
        "double_cost_net_usd":b["books"][key]["net_usd"],
        "double_cost_closed":b["books"][key]["closed"],
    } for key,val in a["books"].items()}


def _count(rows):
    values=list(rows.values())
    # Count original robot slots and unique rule families separately.
    unique=[(key,val) for key,val in rows.items() if (
        not key.startswith("experimental_h1:")
        or key.startswith("experimental_h1:XAUUSD:"))]
    return {
        "slots":len(values),"unique_families":len(unique),
        "positive_slots":sum(r["net_usd"]>0 for r in values),
        "positive_unique_families":sum(r["net_usd"]>0 for _,r in unique),
        "positive_unique_families_double_cost":sum(
            r["double_cost_net_usd"]>0 for _,r in unique),
        "total_close_events_slots_with_H1_duplicates":sum(r["closed"] for r in values),
        "total_close_events_unique":sum(r["closed"] for _,r in unique),
        "net_sum_unique_independent_paper_books_usd_NOT_portfolio":
            round(sum(r["net_usd"] for _,r in unique),2),
    }


def run(root,output):
    initial,all_bars=_load_frozen(root)
    m30=all_bars["M30"]
    start_ts=m30[xau.INITIAL_WARMUP]["time"]
    # Compare ALL four TFs after same exact UTC time. They still have
    # different candle sample lengths and different original time-exit clocks.
    scenarios={}
    with patch.dict(xau.TIMEFRAMES,{"M30":M30_SECONDS}):
        for tf,bars in all_bars.items():
            scenarios[tf]={
                "number_of_original_bars":len(bars),
                "matched_start_utc":datetime.fromtimestamp(start_ts,timezone.utc).isoformat(),
                "original_time_exits":_one(bars,tf,start_ts),
            }
            scenarios[tf]["original_summary"]=_count(
                scenarios[tf]["original_time_exits"])
            if tf in ("M1","M5"):
                # Precommitted, *NOT* optimized after seeing this P&L:
                # hold exits last the same wall-clock minutes as 15m setup.
                factor=900//xau.TIMEFRAMES[tf]
                scenarios[tf]["experimental_same_clock_time_exits"]=_one(
                    bars,tf,start_ts,clock_factor=factor)
                scenarios[tf]["same_clock_summary"]=_count(
                    scenarios[tf]["experimental_same_clock_time_exits"])
                scenarios[tf]["time_exit_multiplier_only"]=factor
    output_data={
        "study":"XAUUSD all original 27 books plus ATLAS: M1 M5 M15 M30",
        "paper_only":True,"broker_verified":False,"live_trade_authorized":False,
        "original_signal_rules_not_changed":True,
        "date_window_matched":True,
        "original_h4_paper_config_retargeted_to_intraday":True,
        "source_original_run":"https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42847239203",
        "source_original_json_sha256":SOURCE_REPORT_SHA256,
        "predeclared_dates":initial["predeclared_dates"],
        "valid_dates":initial["valid_dates"],
        "quarantined_dates":initial["quarantined_dates"],
        "new_m30_source":"Adjacent real M15 midpoint quotes: complete M30 pairs only",
        "observed_bid_ask_not_broker_fills":True,
        "calendar_matched_start_utc":
            datetime.fromtimestamp(start_ts,timezone.utc).isoformat(),
        "M15_positive_candidate_snapshot_is_separate_unchanged":True,
        "M1_M5_clock_experiment_only_changes_MAX_HOLD_not_entry_signals":
            True,
        "historical_period_already_seen_not_OOS":True,
        "sample_period_shorter_than_previous_all_dates_baseline":True,
        "timeframes":scenarios,
    }
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(output_data,ensure_ascii=False,indent=2)+"\n",
                      encoding="utf-8")
    summaries={tf:{
        "original":d["original_summary"],
        **({"clock_15m":d["same_clock_summary"],
            "clock_factor":d["time_exit_multiplier_only"]}
           if tf in ("M1","M5") else {})
        } for tf,d in scenarios.items()}
    names=list(scenarios["M30"]["original_time_exits"])
    lines=[
        "# XAUUSD — 27 ROBÔS ORIGINAIS + ATLAS EM M1 / M5 / M15 / M30",
        "",
        "Mesmos 24 pregões de 2026, dados OHLC MID derivados do BID/ASK "
        "Dukascopy previamente congelado e verificado por SHA-256. "
        "**Nenhuma estratégia nova; cada um dos 28 nomes preservado.**",
        "",
        "**Comparação corrigida:** todos os timeframes começam a negociar em "
        f"{output_data['calendar_matched_start_utc']}; candles anteriores "
        "são usados apenas para indicadores e aquecimento, sem trades.",
        "",
        "As 15 instâncias H1 são só 3 regras repetidas 5 vezes no XAUUSD; "
        "não somar resultados como se fossem independente. "
        "Os 20 positivos M15 do snapshot anterior permanecem salvos "
        "e não são sobrescritos por esta janela pareada.",
        "",
        "Cotações MID em barras, custos originais estimados com stress 2x, "
        "sem execução real BID/ASK da corretora nem resultados prospectivos.",
        "",
        "## Totais por timeframe (não são carteira)",
        "",
        "| TF | 28 slots positivos | 16 regras distintas positivas | "
        "Regras positivas sob custo 2x | Fechamentos únicos |",
        "|---|---:|---:|---:|---:|",
    ]
    for tf in ("M1","M5","M15","M30"):
        s=scenarios[tf]["original_summary"]
        lines.append(f"| {tf} | {s['positive_slots']}/28 | "
                     f"{s['positive_unique_families']}/16 | "
                     f"{s['positive_unique_families_double_cost']}/16 | "
                     f"{s['total_close_events_unique']} |")
    lines.extend(["","## 28 robôs (resultados virtuais, janela UTC pareada)","",
        "| Robô | M1 US$ / ops | M5 US$ / ops | M15 US$ / ops | M30 US$ / ops |",
        "|---|---:|---:|---:|---:|---:|"])
    for key in names:
        vals=[]
        for tf in ("M1","M5","M15","M30"):
            s=scenarios[tf]["original_time_exits"][key]
            vals.append(f"{s['net_usd']:+.2f} / {s['closed']}")
        lines.append("| "+key+" | "+" | ".join(vals)+" |")
    lines.extend(["","## Estresse: custo dobrado (US$ por banca simulada)","",
         "| Robô | M1 ×2 | M5 ×2 | M15 ×2 | M30 ×2 |",
         "|---|---:|---:|---:|---:|"])
    for key in names:
        lines.append("| "+key+" | "+" | ".join(
            f"{scenarios[tf]['original_time_exits'][key]['double_cost_net_usd']:+.2f}"
            for tf in ("M1","M5","M15","M30"))+" |")
    lines.extend(["",
         "## Experimento CONTROLADO de saída em M1 / M5",
         "",
         "Mantém sinais, indicadores e stops originais. M1 ×15 e M5 ×3 "
         "multiplicam **somente MAX_HOLD / TIME exit**, para fazer os "
         "90 candles da estratégia corresponderem ao mesmo tempo de 90 "
         "candles M15 (quando houver esse parâmetro). "
         "Não prometer ganho: tamanho de amostra, entradas e duração mudam.",
         "",
         "| Robô | M1 original → tempo M15 | M5 original → tempo M15 |",
         "|---|---:|---:|"])
    for key in names:
        m1=scenarios["M1"];m5=scenarios["M5"]
        lines.append(f"| {key} | "
         f"{m1['original_time_exits'][key]['net_usd']:+.2f} → "
         f"{m1['experimental_same_clock_time_exits'][key]['net_usd']:+.2f} | "
         f"{m5['original_time_exits'][key]['net_usd']:+.2f} → "
         f"{m5['experimental_same_clock_time_exits'][key]['net_usd']:+.2f} |")
    lines.extend(["","## Restrições e decisão","",
        "- Não é robô novo nem código aprovado. O experimento de tempo é "
        "apenas cenário contrafactual em pesquisa, sem alterar main.",
        "- O preço MID de OHLC não substitui fills por BID/ASK nem custos reais MT5.",
        "- As amostras já foram estudadas; **não são independentes** nem "
        "predizem lucro futuro. Comparações de retornos misturam bancas "
        "iniciais distintas e nunca devem ser somadas.",
        "- M15 preservado no arquivo principal de pesquisa não é modificado.",
        ""])
    output.with_suffix(".md").write_text("\n".join(lines),encoding="utf-8")
    print("XAU_MATCHED_M30_RESULTS",json.dumps(summaries,ensure_ascii=False),flush=True)
    return output_data


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-artifact",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    run(args.frozen_artifact,args.output)


if __name__=="__main__":
    main()
