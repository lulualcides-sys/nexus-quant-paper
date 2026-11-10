"""Untuned historical replication of XAUUSD PA M1/M5 in May 2026.

The June observation was already seen; this separate EARLIER calendar window
is informative for robustness but is NOT a prospective future holdout.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.xau_pa_scorecard import _stats


MAY_DATES=(
    "20260504","20260505","20260506","20260507","20260508",
    "20260511","20260512","20260513","20260514","20260515",
    "20260518","20260519","20260520","20260521","20260522",
    "20260525","20260526","20260527","20260528","20260529",
)


def evaluate(folder: str | Path):
    path=Path(folder);clean=[];excluded=[]
    for d in MAY_DATES:
        valid=path/f"xau_pa_{d}.json"
        bad=path/f"quarantine_{d}.json"
        if valid.exists()==bad.exists():
            raise ValueError(f"Missing or ambiguous date: {d}")
        if bad.exists():
            q=json.loads(bad.read_text(encoding="utf-8"))
            if (q.get("day")!=d or q.get("whole_session_excluded") is not True
                or q.get("trades_included")!=0):
                raise ValueError("Unverified full-day exclusion")
            excluded.append(q)
            continue
        r=json.loads(valid.read_text(encoding="utf-8"))
        if (r.get("day")!=d or r["source"].get("date_utc")!=d or
            r["source"].get("raw_quote_rows",0)<1500 or
            len(r["source"].get("sha256",""))!=64 or
            r.get("spread_included_bid_ask") is not True or
            r.get("approval_for_live") is not False or
            r.get("is_actual_broker_backtest") is not False or
            set(r["results"])!={"M1","M5"}):
            raise ValueError(f"Unverified result source/date {d}")
        for tf in ("M1","M5"):
            e=r["results"][tf]
            if e["signals"]<e["filled"] or len(e["trades"])!=e["filled"]:
                raise ValueError("Trade count mismatch")
            if abs(e["net_usd_per_oz"]-sum(t["net_usd_per_oz"] for t in e["trades"]))>.001:
                raise ValueError("Ledger result mismatch")
        clean.append(r)
    half_a=[r for r in clean if r["day"]<="20260515"]
    half_b=[r for r in clean if r["day"]>="20260518"]
    if len(clean)<16 or len(half_a)<8 or len(half_b)<8:
        raise ValueError("Insufficient unaffected days in fixed May experiment")
    return {
        "dates_precommitted":list(MAY_DATES),
        "valid_dates":[r["day"] for r in clean],
        "quarantined_full_days":excluded,
        "calendar_note":"May PRECEDES June discovery; historical replication, not future holdout",
        "parameters_untouched_since_june":True,
        "usd_per_theoretical_ounce_not_account_pnl":True,
        "no_verified_mt5_broker_execution":True,
        "approved_to_trade":False,
        "results":{
            tf:{
                "all":_stats(clean,tf),
                "may_04_to_15":_stats(half_a,tf),
                "may_18_to_29":_stats(half_b,tf),
            } for tf in ("M1","M5")
        }
    }


def as_markdown(r: dict):
    lines=[
        "# Price Action do WIN adaptado ao XAUUSD — replicação histórica Maio 2026",
        "",
        f"Janelas fixas: **{len(r['dates_precommitted'])}**, "
        f"válidas: **{len(r['valid_dates'])}**, "
        f"quarentenadas: **{len(r['quarantined_full_days'])}**.",
        "",
        "| Tempo | Sinais | Operações | Wins/Losses | Líquido US$/oz | PF | 04–15/05 | 18–29/05 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for tf in ("M1","M5"):
        v=r["results"][tf];a=v["all"]
        pf=f"{a['profit_factor']:.3f}" if a["profit_factor"] is not None else "N/D"
        lines.append(
            f"| {tf} | {a['signals']} | {a['filled']} | "
            f"{a['wins']}/{a['losses']} | {a['net_usd_per_oz']:+.3f} | {pf} | "
            f"{v['may_04_to_15']['net_usd_per_oz']:+.3f} | "
            f"{v['may_18_to_29']['net_usd_per_oz']:+.3f} |"
        )
        for kind,z in a["by_setup"].items():
            lines.append(f"- {tf} {kind}: {z['trades']} trades; {z['net_usd_per_oz']:+.3f} US$/oz")
    lines.extend([
        "",
        "As regras foram congeladas antes de esta amostra ser inspecionada. "
        "Como maio antecede junho, não é teste futuro prospectivo.",
        "Valor por 1 onça teórica de ouro, não lote broker nem saldo em reais.",
        "Custos hipotéticos: US$0,30/oz roundtrip e US$0,10/oz por lado market, "
        "spread histórico bid/ask incluso; swap, latência, rejeição e corretora não validados.",
        "Nenhuma ordem foi enviada, nem a estratégia aprovada.",
        "",
        "## Sessões eliminadas integralmente, sem escolha por P&L"
    ])
    lines.extend(f"- {q['day']}: {q['reason']}" for q in r["quarantined_full_days"])
    if not r["quarantined_full_days"]:lines.append("- Nenhuma")
    return "\n".join(lines)+"\n"


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--evidence",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    report=evaluate(args.evidence)
    target=Path(args.out);target.mkdir(parents=True,exist_ok=True)
    (target/"xau_pa_may_evaluation.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    md=as_markdown(report)
    (target/"xau_pa_may_evaluation.md").write_text(md,encoding="utf-8")
    print(md)


if __name__=="__main__":
    main()
