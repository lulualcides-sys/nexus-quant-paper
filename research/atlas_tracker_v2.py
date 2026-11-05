"""ATLAS v2 research-only signal hypotheses — NOT a decoded Tracker algorithm.

Evidence: official Tracker marketing explicitly says signal after candle close
and describes volume/exhaustion/reversal. It does not publish the actual detector.
We test frozen price-action proxies, never train thresholds on the test period.

No direct modification of existing ATLAS #28 forward paper state.
"""
from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from unittest.mock import patch

from research.atlas_mtf_comparison import (
    COST_SCENARIOS_BPS, TIMEFRAMES, download_m5, resample_m5,
    simulate as gold_simulate, utc,
)
from src import atlas_vector as atlas

ORIGINAL_SIGNAL = atlas.signal
VARIANTS = ("original", "exhaustion_v2", "exhaustion_direction_v2")


def _ema(values, period):
    alpha = 2.0 / (period + 1)
    result = values[0]
    for value in values[1:]:
        result = alpha * value + (1 - alpha) * result
    return result


def candidate(bars, i, variant):
    """Returns 1/-1/0 using only bars <=i; all thresholds are predeclared."""
    if variant not in VARIANTS:
        raise ValueError("Unknown ATLAS hypothesis")
    direction = ORIGINAL_SIGNAL(bars, i)
    if not direction or variant == "original":
        return direction
    if i < 60:
        return 0
    b = bars[i]
    span = b["high"] - b["low"]
    if span <= 0:
        return 0

    # Confirmation: candle actually closes in the rejection direction.
    close_position = (b["close"] - b["low"]) / span
    if direction == 1 and (b["close"] <= b["open"] or close_position < 0.65):
        return 0
    if direction == -1 and (b["close"] >= b["open"] or close_position > 0.35):
        return 0

    # Context: reject candles whose size is small noise or unusual news shocks.
    previous = bars[i-14:i]
    true_ranges = []
    for j, old in enumerate(previous):
        close_before = bars[i-15+j]["close"]
        true_ranges.append(max(old["high"]-old["low"],
                               abs(old["high"]-close_before),
                               abs(old["low"]-close_before)))
    atr = mean(true_ranges)
    if atr <= 0 or not (0.65 * atr <= span <= 2.0 * atr):
        return 0

    if variant == "exhaustion_direction_v2":
        # Direction before the signal, not retroactive confirmation. Aims to
        # accept pullback sweeps only in prevailing local trend.
        previous_closes = [row["close"] for row in bars[i-60:i]]
        fast = _ema(previous_closes, 20)
        slow = _ema(previous_closes, 50)
        if direction == 1 and fast <= slow:
            return 0
        if direction == -1 and fast >= slow:
            return 0
    return direction


def compare_gold(m5):
    """Same GC=F bars, cost scenarios and simulator as ATLAS v1.
    
    All variants are frozen before inspecting outputs; do not choose the
    highest in-sample profit and call it independently validated.
    """
    result = {
        "name": "ATLAS v2 research, frozen candidate comparison",
        "market": "GC=F (gold future, NOT Brazilian WIN)",
        "source": "Yahoo Finance 5m OHLCV",
        "first_utc": utc(m5[0]["time"]),
        "last_utc": utc(m5[-1]["time"]),
        "settings": {
            "base": "sweep 20, wick>=30%, relative volume>=1.5",
            "exhaustion_v2": "base + directional green/red close, close location>=65% or <=35%, range 0.65-2.0 prior ATR14",
            "exhaustion_direction_v2": "exhaustion + prior EMA20/EMA50 directional alignment",
            "costs_bps_roundtrip": list(COST_SCENARIOS_BPS),
            "split": "chronological last 30% diagnostic, not independent forward validation",
        },
        "model_not_original_tracker": True,
        "paper_only": True, "validated": False, "results": {},
    }
    for tf, duration in TIMEFRAMES.items():
        candles = resample_m5(m5, duration)
        result["results"][tf] = {}
        for name in VARIANTS:
            with patch.object(atlas, "signal", side_effect=lambda bars, i, v=name: candidate(bars, i, v)):
                result["results"][tf][name] = {
                    str(cost): gold_simulate(candles, timeframe=tf, cost_bps=cost)
                    for cost in COST_SCENARIOS_BPS
                }
    return result


def report_gold(data):
    lines = [
        "# ATLAS v2 — Estudo de filtros por exaustão e contexto",
        "",
        "**ATENÇÃO:** hipóteses próprias; NÃO reconstituição do código do Tracker. "
        "Dados históricos retrospectivos GC=F, não WIN. Sem ordens reais.",
        f"**Fonte/período UTC:** {data['source']}, {data['first_utc']} – {data['last_utc']}",
        "",
        "## Comparação com custo estimado de 7 bps (ida e volta)",
        "",
        "| TF | Modelo | N trades | Winrate | Líquido USD | PF | DD fechado | Últimos 30% trades | Últimos 30% líquido |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    def v(value, suffix=""):
        return "N/D" if value is None else f"{value}{suffix}"
    for tf, variants in data["results"].items():
        for name, scenarios in variants.items():
            d = scenarios["7"]
            last = d.get("tail_30pct") or {}
            lines.append(
                f"| {tf} | {name} | {v(d.get('closed'))} | {v(d.get('winrate_pct'), '%')} | "
                f"{v(d.get('net_usd'))} | {v(d.get('profit_factor'))} | "
                f"{v(d.get('max_closed_drawdown_pct'), '%')} | {v(last.get('closed'))} | "
                f"{v(last.get('net_usd'))} |"
            )
    lines += ["", "## Sensibilidade aos custos (P&L líquido USD)", "",
              "| TF | Modelo | 7 bps | 14 bps | 28 bps |",
              "|---|---|---:|---:|---:|"]
    for tf, variants in data["results"].items():
        for name, scenarios in variants.items():
            line = [tf, name] + [v(scenarios[str(cost)].get("net_usd")) for cost in COST_SCENARIOS_BPS]
            lines.append("| " + " | ".join(line) + " |")
    lines += ["", "## Regras de qualidade", "",
              "- Manter thresholds fixos; não retreinar utilizando o mesmo mês.",
              "- 30 fechamentos é amostra mínima para revisão, NÃO evidência suficiente de vantagem futura.",
              "- Dados do WIN requerem outra fonte e motor de custos/tick; não usar GC=F como substituto.",
              "- Vários experimentos aumentam risco de seleção retrospectiva; qualquer escolha precisa de forward validation.",
              "- OHLC não comprova ordem intrabar, delta agressor, absorção real ou fills da corretora.",
              "- Não aplicar novo detector ao robô prospectivo sem prova independente.",
              ""]
    return "\n".join(lines)


def main():
    data = compare_gold(download_m5())
    print("ATLAS_V2_RESULT_START", flush=True)
    print(report_gold(data), flush=True)
    print("ATLAS_V2_RESULT_END", flush=True)
    folder = Path("research/results")
    folder.mkdir(parents=True, exist_ok=True)
    (folder/"atlas_tracker_v2_gold_latest.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    (folder/"atlas_tracker_v2_gold_latest.md").write_text(report_gold(data), encoding="utf-8")


if __name__ == "__main__":
    main()
