"""Predeclared exploratory candidate screen on pinned WINQ26 M1 (no live orders).

Screens eight simple price-action hypotheses on Feb-May/June then reports July
separately. July is NOT pristine out-of-sample: earlier research used that month.
No parameter selection from July is permitted in the screen logic.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json

import research.win_price_action as pa
from research.win_price_action import Settings
from research.atlas_winq26_public import fetch, canonicalize, SYMBOL, SOURCE_BLOB
from research.win_price_data import read_win_csv, local_day, TZ

PERIODS = {
    "exploratory_feb_mar": ("2026-02-13", "2026-04-01"),
    "exploratory_apr_may": ("2026-04-01", "2026-06-01"),
    "review_jun": ("2026-06-01", "2026-07-01"),
    "later_jul": ("2026-07-01", "2026-08-01"),
}
VARIANTS = (
    "baseline",
    "break_only",
    "range_only",
    "break_rr1_5",
    "break_rr3",
    "break_strong_candle",
    "break_volume",
    "break_m5_momentum",
    "break_morning",
)


def candidate_variant(base_candidate, name):
    def fn(bars, i, cfg):
        out = base_candidate(bars, i, cfg)
        if not out:
            return None
        if name.startswith("break_") and out["setup"] != "break_retest":
            return None
        if name == "range_only" and out["setup"] != "range_rejection":
            return None
        b = bars[i]
        side = out["side"]
        if name == "break_strong_candle":
            rng = b["high"] - b["low"]
            if rng <= 0:
                return None
            strength = ((b["close"]-b["low"])/rng if side == 1
                        else (b["high"]-b["close"])/rng)
            if strength < 0.7:
                return None
        elif name == "break_volume":
            prev = [x["volume"] for x in bars[max(0,i-20):i]]
            if len(prev) < 20 or not all(v > 0 for v in prev) or b["volume"] < 1.2 * median(prev):
                return None
        elif name == "break_m5_momentum":
            m5 = pa._m5_closed(bars, i)
            if len(m5) < 3 or any(
                side * (m5[k]["close"]-m5[k-1]["close"]) <= 0
                for k in (-1,-2)
            ):
                return None
        elif name == "break_morning":
            local = datetime.fromtimestamp(b["time"],timezone.utc).astimezone(TZ)
            if not (9*60 + 30 <= local.hour*60+local.minute < 12*60):
                return None
        return out
    return fn


def _slice(bars, start, end):
    ids=[i for i,b in enumerate(bars) if start <= local_day(b["time"]) < end]
    if not ids:
        return []
    return bars[max(0,ids[0]-180):ids[-1]+1]


def _brief(result):
    return {
        "trades":result["closed"],
        "net_brl":result["net_brl"],
        "winrate_pct":result["win_rate_pct"],
        "pf":result["profit_factor"],
        "dd_pct":result["max_realized_drawdown_pct"],
        "open_at_end":result["open_at_end"],
        "setups":{
            key:sum(t["setup"] == key for t in result["trades"])
            for key in ("break_retest","range_rejection")
        },
    }


def run(bars):
    if len(bars) < 30000:
        raise ValueError("PINNED WINQ26 expected >=30,000 real M1")
    out = {
        "status":"EXPLORATORY_NO_EDGE_VALIDATION",
        "dataset":"WINQ26 third party Profit export, single contract",
        "source_blob_sha1":SOURCE_BLOB,
        "unmodified_pricing":True,
        "total_m1_candles":len(bars),
        "initial_capital_brl_per_run":2000,
        "one_contract_at_a_time":True,
        "no_daily_loss_limit":True,
        "cost_brl_per_roundtrip_at_base":6,
        "monthly_splits":PERIODS,
        "hypotheses_predeclared":list(VARIANTS),
        "variants":{},
        "warning":"Repeatedly studied June/July dataset, not independent holdout. All results exploratory.",
    }
    base=pa.candidate
    for name in VARIANTS:
        cfg=Settings(reward_risk=1.5 if name=="break_rr1_5" else
                     3.0 if name=="break_rr3" else 2.0)
        entry={}
        for pname,(start,end) in PERIODS.items():
            sliced=_slice(bars,start,end)
            with patch.object(pa,"candidate",side_effect=candidate_variant(base,name)):
                report=pa.simulate(sliced,cfg,start_local=start,end_local=end)
            entry[pname]=_brief(report)
        screen=["exploratory_feb_mar","exploratory_apr_may","review_jun"]
        entry["development_net_brl"]=round(sum(entry[p]["net_brl"] for p in screen),2)
        entry["development_trades"]=sum(entry[p]["trades"] for p in screen)
        entry["development_positive_periods"]=sum(entry[p]["net_brl"]>0 for p in screen)
        out["variants"][name]=entry
    out["candidates_development_only"]=sorted(
        list(VARIANTS),
        key=lambda n:(out["variants"][n]["development_positive_periods"],
                      out["variants"][n]["development_net_brl"]),
        reverse=True
    )
    out["recommendation"] = "REQUIRE_FRESH_OUT_OF_SAMPLE_AND_PROSPECTIVE_PAPER"
    return out


def summary(report):
    lines=["# WIN PA — 9 hipóteses pré-definidas com histórico PINNED do WINQ26",
           "","Somente pesquisa histórica. **Não comprova robô lucrativo nem autoriza operar em corretora.**",
           "",f"Total de candles M1: {report['total_m1_candles']}; 1 WIN; capital inicial por janela R$ 2.000; custo simulado R$ 6 por operação.",
           "","| Variante | Fev-Mar líquido | Abr-Mai líquido | Junho líquido | Julho líquido | Trades desenvolvimento |",
           "|---|---:|---:|---:|---:|---:|"]
    for name,d in report["variants"].items():
        lines.append(f"| {name} | {d['exploratory_feb_mar']['net_brl']:+.2f} | "
                     f"{d['exploratory_apr_may']['net_brl']:+.2f} | "
                     f"{d['review_jun']['net_brl']:+.2f} | "
                     f"{d['later_jul']['net_brl']:+.2f} | "
                     f"{d['development_trades']} |")
    lines+=["","## Ranking somente sobre desenvolvimento (julho não utilizado na escolha)",
            ", ".join(report["candidates_development_only"]),
            "","Importante: meses de treino e revisão não são OOS puro; julho já foi usado em projetos ATLAS.",
            "Resultados com amostras pequenas não permitem inferir vantagem matemática.",
            "A estratégia base e cada filtro usam os mesmos preços históricos e podem ter dependência estatística.",
            "Novos testes devem ser pré-registrados e executados com outro contrato/vencimento, custos reais e simulação prospectiva.",
            ""]
    return "\n".join(lines)


def main():
    with TemporaryDirectory() as d:
        raw=Path(d)/"WINQ26_profit_raw.csv"
        clean=Path(d)/"WINQ26_canonical.csv"
        provenance=fetch(raw)
        quality=canonicalize(raw,clean)
        data=read_win_csv(clean, expected_symbol=SYMBOL)
        report=run(data["bars"])
        report["provenance"]=provenance
        report["quality"]=quality
    out=Path("research/results")
    out.mkdir(parents=True,exist_ok=True)
    (out/"win_pa_variant_screen_2026.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    md=summary(report)
    (out/"win_pa_variant_screen_2026.md").write_text(md+"\n",encoding="utf-8")
    print("WIN_PA_VARIANT_SCREEN_START",flush=True)
    print(md,flush=True)
    print("WIN_PA_VARIANT_SCREEN_END",flush=True)


if __name__=="__main__":
    main()
