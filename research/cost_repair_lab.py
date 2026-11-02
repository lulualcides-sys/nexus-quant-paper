"""Causal profit-repair research for 27 Nexus Quant virtual paper engines.

Research experiment, NOT production parameters or broker orders. All candidates
use the exact same fetched candles as baseline. Only two predeclared changes:
  - H1 signal filter: estimated spread coverage and EMA trend separation
    computed on LAST CLOSED H1 candle (no future prices).
  - leveraged H4 scenario: 1x virtual notional and 0.75% planned risk,
    versus the current 2x and 1.5% planned stop-risk.

No training/holdout claims: all historical periods have been seen before.
Missing prices are unknown, not zero. No promotion without NEW forward results.
"""
from __future__ import annotations

from collections import Counter
from contextlib import ExitStack
from datetime import datetime, timezone
from json import dumps
from pathlib import Path
from unittest.mock import patch
import json

from research import backtest_27 as bt
from src import experimental_h1 as h1
from src import leveraged_gold as lev
from src.cost_aware_gate import allow_signal

OUTPUT = Path("research/results/profit_repair_27_2026-11-01")
COVERAGE_MULTIPLE = 4.0  # ATR in bps must cover round-trip fee ×4
TREND_SEPARATION_ATR = 1.5  # abs(EMA50-EMA200) / ATR on CLOSED H1
MIN_H1_CLOSED_TO_REVIEW = 30
MIN_H4_CLOSED_TO_REVIEW = 12
GROUPS_CHANGED = ("experimental_h1","leveraged_h4")


def h1_gate_signal(rule, bars, indicators, i, market, original=None, *, base_cost_bps=None):
    """Time-causal candidate; returns zero when estimated edge is too small.

    All indicator values and closing price are from i or earlier.
    Signal at H1 close i can lead to entry at next H1 opening i+1.
    """
    original = original or h1.setup
    raw = original(rule,bars,indicators,i)
    if raw not in (-1,0,1):
        raise ValueError("Unexpected direction")
    if not raw:
        return 0
    if i < h1.WARMUP:
        return 0
    fee_bps = h1.COST_BPS[market] if base_cost_bps is None else base_cost_bps
    return allow_signal(raw,bars,indicators,i,fee_bps=fee_bps)


def h1_candidate(market, bars, *, stress=1.):
    base_setup = h1.setup
    base_cost_bps = h1.COST_BPS[market]
    # Hold entry-filter inputs FIXED; _h1_replay doubles execution costs
    # internally under stress, never the filter threshold.
    def filtered(rule, candles, indicators, i):
        return h1_gate_signal(rule,candles,indicators,i,market,base_setup,
                              base_cost_bps=base_cost_bps)
    with patch.object(h1,"setup",filtered):
        return bt._h1_replay(market,bars,stress=stress)


def h4_deleveraged_candidate(bars, *, stress=1., min_selected_bars=250):
    """Research-only 1x notional scenario; all 11 H4 books replay, but only
    leveraged five differ from baseline. No existing positions altered."""
    with ExitStack() as stack:
        stack.enter_context(patch.object(lev,"TARGET_NOTIONAL_LEVERAGE",1.0))
        stack.enter_context(patch.object(lev,"RISK_FRACTION",0.0075))
        return bt._h4_replay(bars,stress=stress,min_selected_bars=min_selected_bars)


def assessment(baseline, candidate, stressed, group):
    if candidate is None or baseline is None:
        return {"decision":"unavailable","reason":"historical_data_unavailable"}
    n=candidate["closed_trades"]
    threshold=MIN_H1_CLOSED_TO_REVIEW if group=="experimental_h1" else MIN_H4_CLOSED_TO_REVIEW
    baseline_net=baseline["net_realized_usd"]
    new_net=candidate["net_realized_usd"]
    cost_stress=stressed["net_realized_usd"] if stressed is not None else None
    positive_strict=(new_net>0 and cost_stress is not None and cost_stress>0)
    better=(new_net>baseline_net and
            cost_stress is not None and cost_stress>baseline["double_cost_net_usd"])
    if n<threshold:
        decision="insufficient_sample"
    elif not positive_strict:
        decision="rejected_no_stress_profit"
    elif not better:
        decision="not_better_than_existing"
    else:
        # Historical selection alone never authorizes actual promotion.
        decision="forward_test_only"
    return {
        "decision":decision,"changed_engine":group in GROUPS_CHANGED,
        "closed_baseline":baseline["closed_trades"],
        "closed_candidate":n,
        "baseline_net_usd":baseline_net,
        "candidate_net_usd":new_net,
        "candidate_minus_baseline_usd":round(new_net-baseline_net,2),
        "baseline_stress_net_usd":baseline["double_cost_net_usd"],
        "candidate_stress_net_usd":cost_stress,
        "candidate_costs_usd":candidate["costs_and_funding_usd"],
        "candidate_closed_only_drawdown_pct":candidate["closed_only_drawdown_pct"],
        "no_auto_promotion":True,
    }


def compare(datasets, m15_rows):
    # Replay SAME historical bars at base and double cost.
    baseline = bt.run(datasets=datasets,m15rows=m15_rows,obtain=False,stress=True)
    if baseline["analyzed"] != 27:
        raise ValueError("Insufficient price history to compare all 27. No implied returns.")
    variants, stressed_variants = {}, {}
    h4 = datasets["XAUUSD"]
    variants.update(h4_deleveraged_candidate(h4,stress=1.))
    stressed_variants.update(h4_deleveraged_candidate(h4,stress=2.))
    for market in bt.MARKETS:
        variants.update(h1_candidate(market,datasets[market],stress=1.))
        stressed_variants.update(h1_candidate(market,datasets[market],stress=2.))
    # USD/CAD M15 remains unchanged; no rule is being claimed improved.
    variants["usdcad_m15:bb20"] = bt._m15_replay(m15_rows,stress=1.)["usdcad_m15:bb20"]
    stressed_variants["usdcad_m15:bb20"] = bt._m15_replay(m15_rows,stress=2.)["usdcad_m15:bb20"]
    comparisons={}
    for key, old in baseline["robots"].items():
        current=variants[key]
        stressed=stressed_variants[key]
        group=old["group"]
        comparisons[key]=assessment(old,current,stressed,group)
        comparisons[key]["market"]=old["market"]
        comparisons[key]["strategy"]=old["strategy"]
        comparisons[key]["group"]=group
        comparisons[key]["candidate_policy"]=(
            "h1_cost_coverage_and_trend" if group=="experimental_h1"
            else "1x_virtual_leverage_risk_075" if group=="leveraged_h4"
            else "unchanged_control"
        )
    if len(comparisons)!=27:
        raise AssertionError("Incorrect strategy census")
    summary = Counter(v["decision"] for v in comparisons.values())
    return {
        "title":"Nexus Quant profit-repair simulation: fixed controls vs two predeclared candidates",
        "generated_utc":datetime.now(timezone.utc).isoformat(),
        "paper_only":True,"never_real_orders":True,
        "no_strategy_code_changed":True,"no_auto_promotion":True,
        "historical_data_previously_inspected":True,
        "compare_same_exact_feeds":True,
        "policy":{
            "H1":"require ATR bps ≥ 4× base cost bps AND |EMA50−EMA200| / ATR ≥ 1.5 AND aligned EMA50/EMA200",
            "leveraged":"decrease target notional 2x → 1x and risk-stop planned 1.50% → 0.75%",
            "preserved":"5 H4 conventional, Momentum60, and USD/CAD M15; no live changes",
            "note":"H1 filter uses base costs even under doubled-fee stress; selection identical in both runs",
        },
        "feed_data":baseline["price_data"],
        "counts":dict(summary),"robots":comparisons,
        "conclusion":"No claim of profitability; need NEW chronological walk-forward paper results before promotion.",
    }


def markdown(report):
    s=[
        "# Nexus Quant — reparo econômico dos 27 robôs (somente laboratório)",
        "",
        "**Nenhuma ordem real e nenhuma estratégia de produção alterada.**",
        "",
        "A comparação usa os mesmos candles para o original e candidato, e "
        "também refaz o P&L com custos dobrados. H1 testa filtros "
        "decididos antes de ler o resultado da nova execução; "
        "os dados históricos já foram examinados.",
        "",
        "## Políticas testadas",
        "",
        "- 15 H1: ATR/preço em bps ≥ 4× custo estimado de ida/volta, "
        "além de separação EMA50/EMA200 ≥ 1,5 ATR e alinhamento da tendência.",
        "- 5 H4 alavancados: exposição nominal de 2× para 1× e "
        "risco-stop planejado de 1,5% para 0,75%.",
        "- 7 controles: sem modificações (5 H4, Momentum60, USD/CAD M15).",
        "",
        "| Robô | Política | Fech. original | Fech. candidato | Original US$ | Novo US$ | Custos×2 US$ | Status |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for key,row in report["robots"].items():
        s.append(f"| {key} | {row['candidate_policy']} | "
                 f"{row['closed_baseline']} | {row['closed_candidate']} | "
                 f"{row['baseline_net_usd']:+.2f} | {row['candidate_net_usd']:+.2f} | "
                 f"{row['candidate_stress_net_usd']:+.2f} | {row['decision']} |")
    s.extend(["","**Aprovação de dinheiro real: nenhuma.**",
              "Mesmo um candidato historicamente melhor só pode entrar em "
              "experimento prospectivo após validação específica, controle "
              "de custos reais e sem seleção retrospectiva favorável."])
    return "\n".join(s)+"\n"


def main():
    feeds={}
    for market in bt.MARKETS:
        feeds[market]=bt.fetch_hourly(market)
        print("FEED_OK",market,len(feeds[market]),flush=True)
    m15=bt.fetch_m15()
    report=compare(feeds,m15)
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.with_suffix(".json").write_text(dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    OUTPUT.with_suffix(".md").write_text(markdown(report),encoding="utf-8")
    print("PROFIT_REPAIR_REPLAY",dumps({"counts":report["counts"],
          "changed":{k:{"decision":v["decision"],
                         "base":v["baseline_net_usd"],
                         "candidate":v["candidate_net_usd"],
                         "stress":v["candidate_stress_net_usd"]}
                     for k,v in report["robots"].items() if v["changed_engine"]}},
                     ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
