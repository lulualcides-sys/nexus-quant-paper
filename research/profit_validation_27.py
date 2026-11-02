"""Strict 3-segment chronology and double-cost profit validation for all 27.

Research ONLY: no trading state, secrets, Telegram, API orders, live broker or
strategy promotion. Replays the actual paper engines independently on disjoint
time segments with prior-only indicator warmup. ALL series have been inspected
by prior research: these are retrospective stability diagnostics, NOT untouched
out-of-sample evidence. The official news calendar was first observed in Nov
2026, so applying it to these earlier segments is forbidden look-ahead.
"""
from __future__ import annotations

from collections import Counter
from contextlib import ExitStack
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from unittest.mock import patch
import json
import os

from research import backtest_27 as bt
from research import cost_repair_lab as lab
from research.screen_v2 import aggregate_hourly_to_h4
from src import experimental_h1 as h1

OUT=Path("research/results/profit_validation_27_2026-11-02")
FOLDS=3
# Predefined statistical warning thresholds; tests do not optimize these.
MIN_TRADES_H1=60
MIN_TRADES_H4=20
MIN_TRADES_M15=60
MAX_CLOSED_DD_PCT=10.


def fold_windows(bars, *, interval, warmup, earliest, latest,
                 folds=FOLDS, minimum_selected=90):
    """Three disjoint, chronological segments, OHLC provided by same source.

    All candles before a segment may be used ONLY for causal indicator warmup.
    Trade states always start afresh at each window boundary, so no cross-fold
    position is continued or closed after a segmentation boundary.
    """
    if folds<2 or minimum_selected<1 or warmup<0:
        raise ValueError("Invalid fold request")
    times=[b["time"] for b in bars]
    if not all(isinstance(t,(int,float)) and isfinite(t) for t in times):
        raise ValueError("Invalid candle timestamp")
    if times!=sorted(set(times)):
        raise ValueError("Candles unordered or duplicated")
    eligible=[i for i,t in enumerate(times) if i>=warmup and earliest<=t<latest]
    if len(eligible)<folds*minimum_selected:
        raise ValueError(f"Not enough complete observed candles for {folds} folds")
    sizes=[len(eligible)//folds + int(i<len(eligible)%folds) for i in range(folds)]
    output=[]
    offset=0
    for fold,size in enumerate(sizes):
        segment=eligible[offset:offset+size]
        start=times[segment[0]]
        end=(times[eligible[offset+size]] if offset+size<len(eligible)
             else times[segment[-1]]+interval)
        if start>=end:
            raise ValueError("Empty fold")
        output.append({"fold":fold+1,"start":start,"end_exclusive":end,
                       "selected_bars":size})
        offset+=size
    if any(a["end_exclusive"]>b["start"] for a,b in zip(output,output[1:])):
        raise AssertionError("Overlapping folds")
    return output


def _date(t):
    return datetime.fromtimestamp(t,timezone.utc).strftime("%Y-%m-%d")


def _row(original, variant, old_stress, variant_stress, status):
    if original["status"]!="historical_replay_not_validated":
        raise ValueError("Only observed historical replays are comparable")
    assert original["group"]==variant["group"]
    return {
        "group":original["group"],"name":original["strategy"],
        "fold":status["fold"],
        "start_utc":_date(status["start"]),
        "end_utc_exclusive":_date(status["end_exclusive"]),
        "selected_bars":status["selected_bars"],
        "baseline_closed":original["closed_trades"],
        "candidate_closed":variant["closed_trades"],
        "baseline_net_usd":original["net_realized_usd"],
        "baseline_2x_cost_net_usd":old_stress["net_realized_usd"],
        "candidate_net_usd":variant["net_realized_usd"],
        "candidate_2x_cost_net_usd":variant_stress["net_realized_usd"],
        "candidate_closed_drawdown_pct":variant["closed_only_drawdown_pct"],
        "candidate_wins":variant["wins"],"candidate_losses":variant["losses"],
        "candidate_costs_usd":variant["costs_and_funding_usd"],
        "candidate_has_open_position_at_cutoff":variant["open_at_end"],
    }


def _run_with_window(start,end,work):
    with patch.object(bt,"HIST_START",start),patch.object(bt,"HIST_END",end):
        return work()


def _h4_batch(hourly, window):
    def baseline(stress):
        return _run_with_window(window["start"],window["end_exclusive"],
             lambda:bt._h4_replay(hourly,stress=stress,min_selected_bars=45))
    def variant(stress):
        return _run_with_window(window["start"],window["end_exclusive"],
             lambda:lab.h4_deleveraged_candidate(hourly,stress=stress,min_selected_bars=45))
    base,bs,candidate,cs=baseline(1.),baseline(2.),variant(1.),variant(2.)
    return {key:_row(base[key],candidate[key],bs[key],cs[key],window) for key in base}


def _h1_batch(market, hourly, window):
    def baseline(stress):
        return _run_with_window(window["start"],window["end_exclusive"],
             lambda:bt._h1_replay(market,hourly,stress=stress))
    def variant(stress):
        return _run_with_window(window["start"],window["end_exclusive"],
             lambda:lab.h1_candidate(market,hourly,stress=stress))
    base,bs,candidate,cs=baseline(1.),baseline(2.),variant(1.),variant(2.)
    return {key:_row(base[key],candidate[key],bs[key],cs[key],window) for key in base}


def _m15_batch(bars, window):
    def baseline(stress):
        return _run_with_window(window["start"],window["end_exclusive"],
             lambda:bt._m15_replay(bars,stress=stress))
    base,bs=baseline(1.),baseline(2.)
    return {key:_row(base[key],base[key],bs[key],bs[key],window) for key in base}


def summarize(folds):
    if len(folds)!=FOLDS:
        raise ValueError("Require three complete chronological folds")
    if [x["fold"] for x in folds]!=[1,2,3]:
        raise ValueError("Out-of-order folds")
    if any(a["end_utc_exclusive"]>b["start_utc"] for a,b in zip(folds,folds[1:])):
        raise ValueError("Overlapping segments")
    count=sum(x["candidate_closed"] for x in folds)
    group=folds[0]["group"]
    min_closed=MIN_TRADES_H1 if group=="experimental_h1" else (
        MIN_TRADES_M15 if group=="usdcad_m15" else MIN_TRADES_H4)
    first_key=folds[0]["name"]
    if any(x["name"]!=first_key or x["group"]!=group for x in folds):
        raise ValueError("Mismatched robot segments")
    profitable=sum(x["candidate_net_usd"]>0 for x in folds)
    profitable_stress=sum(x["candidate_2x_cost_net_usd"]>0 for x in folds)
    base_net=round(sum(x["baseline_net_usd"] for x in folds),2)
    base_stress=round(sum(x["baseline_2x_cost_net_usd"] for x in folds),2)
    new_net=round(sum(x["candidate_net_usd"] for x in folds),2)
    stress_net=round(sum(x["candidate_2x_cost_net_usd"] for x in folds),2)
    pass_all=(count>=min_closed and profitable==3 and profitable_stress==3
              and new_net>0 and stress_net>0
              and all(x["candidate_closed_drawdown_pct"]<=MAX_CLOSED_DD_PCT
                      for x in folds))
    reasons=[]
    if count<min_closed: reasons.append("too_few_closed_trades")
    if profitable<3: reasons.append("not_profitable_each_period")
    if profitable_stress<3: reasons.append("double_cost_failed_in_period")
    if new_net<=0 or stress_net<=0: reasons.append("total_net_not_positive_after_stress")
    if any(x["candidate_closed_drawdown_pct"]>MAX_CLOSED_DD_PCT for x in folds):
        reasons.append("realized_drawdown_over_10pct")
    # Even if retrospective consistency is positive, never classify proven.
    return {
        "group":group,"strategy":first_key,
        "closed_total":count,"baseline_net_usd":base_net,
        "baseline_2x_cost_net_usd":base_stress,
        "candidate_net_usd":new_net,"candidate_2x_cost_net_usd":stress_net,
        "improvement_vs_original_usd":round(new_net-base_net,2),
        "periods_positive":profitable,"periods_positive_2x_cost":profitable_stress,
        "max_closed_drawdown_pct":max(x["candidate_closed_drawdown_pct"] for x in folds),
        "minimum_closed_for_review":min_closed,
        "retrospective_consistency_pass":pass_all,
        "rejection_reasons":reasons,
        "safe_to_trade_real_money":False,
        "segment_reset_warning":"All segments reset virtual capital; totals are not compounded account results",
    }


def run(feeds,m15rows):
    expected=bt.all_ids()
    if set(feeds)!=set(bt.MARKETS) or m15rows is None:
        raise ValueError("Missing one of the six required original price streams")
    # Official Nov news was unknown in most of history: prevent any accidental
    # calendar leakage regardless of operator environment.
    with patch.dict(os.environ,{"NEXUS_NEWS_GUARD_ENABLED":"0"}):
        records={key:[] for key in expected}
        h4=aggregate_hourly_to_h4(feeds["XAUUSD"])
        gold_windows=fold_windows(h4,interval=14400,warmup=242,
                                  earliest=bt.HIST_START,latest=bt.HIST_END,
                                  minimum_selected=75)
        for window in gold_windows:
            result=_h4_batch(feeds["XAUUSD"],window)
            for key,row in result.items(): records[key].append(row)
        h1windows={}
        for market,rows in feeds.items():
            windows=fold_windows(rows,interval=3600,warmup=h1.WARMUP+1,
                                 earliest=bt.HIST_START,latest=bt.HIST_END,
                                 minimum_selected=200)
            h1windows[market]=windows
            for window in windows:
                for key,row in _h1_batch(market,rows,window).items():
                    records[key].append(row)
        m15windows=fold_windows(m15rows,interval=900,warmup=240,
                               earliest=bt.HIST_START,latest=bt.HIST_END,
                               minimum_selected=100)
        for window in m15windows:
            for key,row in _m15_batch(m15rows,window).items():
                records[key].append(row)
    if any(len(rows)!=3 for rows in records.values()):
        raise AssertionError("Incomplete 3-period / 27-engine evaluation")
    summary={key:summarize(rows) for key,rows in records.items()}
    qualified=[key for key,entry in summary.items() if entry["retrospective_consistency_pass"]]
    return {
        "study":"27 robot profitability consistency: 3 disjoint historical period resets",
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "paper_only":True,"has_real_broker_execution":False,
        "bots":27,"folds_per_bot":3,"fold_results":81,
        "news_filter_backtested":False,
        "news_filter_exclusion_reason":"Official calendar snapshot was not known before 2026-11-02; no retrospective look-ahead",
        "historical_windows_previously_inspected":True,
        "independent_untouched_holdout":False,
        "fee_multiplier_stress":2.,
        "candidate_policy_by_group":{
            "gold_h4":"unchanged gold control",
            "leveraged_h4":"1x notional, 0.75pct planned stop-risk experiment",
            "experimental_h1":"causal base-fee ATR coverage and EMA trend filter experiment",
            "usdcad_m15":"unchanged M15 control (short data window)",
            "momentum60_h4":"unchanged Momentum60 control",
        },
        "coverage_sha256":{
            market:bt._fingerprint(bars) for market,bars in
            list(feeds.items())+[("USDCAD_M15",m15rows)]
        },
        "windows_by_market":{"XAUUSD_H4":gold_windows,"USDCAD_M15":m15windows,
                             **{m+"_H1":windows for m,windows in h1windows.items()}},
        "status_counts":dict(Counter(
            "retrospective_consistency_only" if x["retrospective_consistency_pass"]
            else "not_robust" for x in summary.values())),
        "retrospective_candidates_only":qualified,
        "robots":summary,
        "segments":records,
        "all_approved_real_money":False,
        "conclusion":"Past profitability not a guarantee; need NEW timestamped forward fills, broker spreads and fees; no automatic promotion.",
    }


def markdown(data):
    out=[
      "# Nexus Quant — lucro líquido em 3 períodos para 27 robôs",
      "",
      "**Pesquisa virtual. Nada foi operado na FBS.** Três janelas cronológicas "
      "disjuntas por mercado, bancos reinicializados a cada segmento; nenhum "
      "resultado é lucro futuro garantido ou conta real composta.",
      "",
      "Os períodos históricos já foram examinados em pesquisas anteriores. "
      "**Isto NÃO é out-of-sample independente.**",
      "Custos normais vs custos ×2, regras atuais dos 27 robôs e duas variantes "
      "experimentais (H1 filtrado / alavancados 1×).",
      "Notícias NÃO retroaplicadas, pois o calendário não estava disponível nas "
      "datas antigas e usar dados posteriores geraria look-ahead.",
      "",
      "| Robô | Fech. | P&L original soma | P&L candidato soma | Custo×2 soma | Períodos + | Períodos + custo×2 | Revisão |",
      "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for key,entry in data["robots"].items():
        s="consistência histórica, NÃO validado" if entry["retrospective_consistency_pass"] else "rejeitado/amostra insuficiente"
        out.append(f"| {key} | {entry['closed_total']} | {entry['baseline_net_usd']:+.2f} | "
                   f"{entry['candidate_net_usd']:+.2f} | {entry['candidate_2x_cost_net_usd']:+.2f} | "
                   f"{entry['periods_positive']}/3 | {entry['periods_positive_2x_cost']}/3 | {s} |")
    out.extend(["","## Janelas por mercado (UTC, finais exclusivos)"])
    for market,rows in data["windows_by_market"].items():
        s=", ".join(_date(row["start"])+" a "+_date(row["end_exclusive"])+
                    f" ({row['selected_bars']} candles)" for row in rows)
        out.append(f"- {market}: {s}")
    out.extend(["","## Principais salvaguardas",
      "- 27 robôs, 3 janelas por robô = 81 linhas auditáveis; nenhum período sobreposto.",
      "- Sinais no candle anterior completo; próxima abertura para entradas; stops conservadores.",
      "- Fonte: Yahoo indicativo GC=F, ES=F, CL=F e FX, não bid/ask executável da FBS.",
      "- Encerramentos já registrados; operações em aberto não incluem marcação a mercado; DD apenas de fechamento.",
      "- Mínimos de revisão: 60 operações H1/M15 e 20 H4, resultado positivo "
      "em todos os 3 períodos nos custos normal e ×2, drawdown fechado ≤10%.",
      "- Os critérios acima são triagem histórica, não licença para capital real.",
      "- Se uma estratégia não tem vantagem positiva, é correto ficar sem operar; nunca forçar 27 robôs a lucrar.",
      "- Vários testes/candidatos geram risco de seleção retrospectiva e multiplicidade. "
      "Somente observações prospectivas novas podem confirmar vantagem.",
    ])
    return "\n".join(out)+"\n"


def main():
    feeds={}
    for market in bt.MARKETS:
        feeds[market]=bt.fetch_hourly(market)
        print("PROFIT_FEED",market,len(feeds[market]),flush=True)
    m15=bt.fetch_m15()
    print("PROFIT_FEED","USDCAD_M15",len(m15),flush=True)
    result=run(feeds,m15)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.with_suffix(".json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    OUT.with_suffix(".md").write_text(markdown(result),encoding="utf-8")
    concise={key:{
        "closed":value["closed_total"],"baseline":value["baseline_net_usd"],
        "net":value["candidate_net_usd"],"stress":value["candidate_2x_cost_net_usd"],
        "positive_folds":value["periods_positive"],
        "stress_folds":value["periods_positive_2x_cost"],
        "robust":value["retrospective_consistency_pass"]
    } for key,value in result["robots"].items()}
    print("PROFIT_VALIDATION_27",json.dumps({
        "qualified":result["retrospective_candidates_only"],
        "status_counts":result["status_counts"],"robots":concise},sort_keys=True),flush=True)


if __name__=="__main__":
    main()
