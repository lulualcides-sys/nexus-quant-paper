"""27-dimensional mathematical audit of the *recorded* paper backtest.

Reproducible from one fixed JSON artifact. It never fetches prices, places
orders, optimizes parameters, or extrapolates future performance.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from math import isfinite, sqrt
from pathlib import Path
import json

from research.backtest_27 import EXPECTED, GROUPS

SOURCE = Path("research/results/backtest_27_2026-11-01.json")
TARGET = Path("research/results/vector_math_27_2026-11-01")
Z = 1.959963984540054

def wilson(wins, n):
    """Wilson binomial 95% interval, descriptive only (not iid proof)."""
    if n <= 0:
        return [None, None]
    p = wins/n
    d = 1 + Z*Z/n
    center = (p+Z*Z/(2*n))/d
    radius = Z*sqrt((p*(1-p)+Z*Z/(4*n))/n)/d
    return [round(100*max(0,center-radius),2),
            round(100*min(1,center+radius),2)]

def _finite(value,name):
    if not isinstance(value,(int,float)) or not isfinite(value):
        raise ValueError(f"{name}: campo numérico inválido")
    return float(value)

def _close(a,b):
    return abs(a-b) <= max(.02, 0.00001*max(abs(a),abs(b)))

def row_vector(key, r):
    """Closed-trade outcome algebra, no fabricated win/loss payoff breakdown.

    Components: gross_usd = net_realized_usd + booked_costs_and_funding_usd.
    Stress net is an independent replay, not net - base fee (size changes).
    """
    group=r["group"]
    n = r.get("closed_trades")
    if not isinstance(n,int) or n<0:
        raise ValueError(f"{key}: número de operações inválido")
    wins = r.get("wins")
    losses = r.get("losses")
    if not all(isinstance(v,int) and v>=0 for v in (wins,losses)) or wins+losses>n:
        raise ValueError(f"{key}: V/D inconsistente")
    net = _finite(r.get("net_realized_usd"),key+":net")
    fees = _finite(r.get("costs_and_funding_usd"),key+":costs")
    stress_net = _finite(r.get("double_cost_net_usd"),key+":stress")
    original_capital = _finite(r.get("initial_capital_usd"),key+":capital")
    drawdown = _finite(r.get("closed_only_drawdown_pct"),key+":drawdown")
    if original_capital<=0 or fees<0 or drawdown<0:
        raise ValueError(f"{key}: capital/custos/drawdown inválidos")
    if not _close(net, original_capital*r["net_realized_pct"]/100):
        raise ValueError(f"{key}: P&L e retorno contraditórios")
    gross = net + fees
    closed_avg = net/n if n else None
    gross_avg = gross/n if n else None
    fees_avg = fees/n if n else None
    # If only a rounded profit factor was recorded, payoff can only be estimated.
    pf = r.get("profit_factor")
    payoff = None
    break_even_win_pct = None
    if wins and losses and isinstance(pf,(int,float)) and isfinite(pf) and pf>0:
        payoff = pf*losses/wins
        break_even_win_pct = 100/(1+payoff)
    win_rate = 100*wins/n if n else None
    # Confidence intervals assume independent Bernoulli trials, which trading
    # returns do NOT guarantee. Use only as a sampling-warning diagnostic.
    conf = wilson(wins,n)
    decision_reasons=[]
    if n<30:
        decision_reasons.append("fewer_than_30_closed_trades")
    if net<=0:
        decision_reasons.append("nonpositive_net")
    if stress_net<=0:
        decision_reasons.append("nonpositive_double_cost")
    if drawdown>=15:
        decision_reasons.append("realized_drawdown_ge_15pct")
    # No strategy is marked validated on already-inspected history.
    return {
        "id":key,"group":group,"strategy":r["strategy"],"n_closed":n,
        "start_utc":r["start_utc"],"end_utc":r["end_utc"],
        "paper_only":True,"validated_for_real_money":False,
        "math_steps":{
            "1_closed_trades":n,
            "2_wins":wins,
            "3_losses":losses,
            "4_win_rate_pct":round(win_rate,3) if win_rate is not None else None,
            "5_net_realized_usd":round(net,2),
            "6_booked_costs_usd":round(fees,2),
            "7_implied_gross_before_booked_costs_usd":round(gross,2),
            "8_gross_per_closed_trade_usd":round(gross_avg,5) if n else None,
            "9_cost_per_closed_trade_usd":round(fees_avg,5) if n else None,
            "10_expected_net_per_closed_trade_usd":round(closed_avg,5) if n else None,
            "11_double_cost_replay_net_usd":round(stress_net,2),
            "12_extra_stress_loss_usd":round(net-stress_net,2),
            "13_drawdown_closed_only_pct":round(drawdown,3),
            "14_profit_factor_reported":pf,
            "15_payoff_ratio_approx_if_pf_rounded":round(payoff,3) if payoff else None,
            "16_breakeven_win_rate_approx_pct":round(break_even_win_pct,2) if break_even_win_pct else None,
            "17_wilson_95pct_win_rate_interval_pct":conf,
            "18_win_rate_minus_breakeven_pct_points":round(win_rate-break_even_win_pct,2) if win_rate is not None and break_even_win_pct else None,
            "19_net_as_pct_initial_capital":round(100*net/original_capital,3),
        },
        "review_failures":decision_reasons,
        "paper_research_watchlist_only":not decision_reasons,
        "caveats":["intervals_not_independent_trades",
                   "PF/payoff_approx_rounded",
                   "no_open_position_MTM",
                   "stress_is_separate_simulation",
                   "historical_data_previously_examined"],
    }

def analyze(source):
    if source.get("planned")!=EXPECTED or source.get("analyzed")!=EXPECTED or source.get("unavailable")!=0:
        raise ValueError("Backtest must include 27 observed records; do not fill missing")
    if not source.get("paper_only") or source.get("broker_orders") is not False:
        raise ValueError("Only paper-only backtests may be audited")
    records=source.get("robots",{})
    if len(records)!=EXPECTED:
        raise ValueError("27 distinct robot records required")
    groups = Counter(x.get("group") for x in records.values())
    if dict(groups)!=GROUPS:
        raise ValueError("Group census does not match 5+5+15+1+1")
    vectors={key:row_vector(key,value) for key,value in records.items()}
    group_summary={}
    for group in GROUPS:
        v=[vectors[k] for k in vectors if vectors[k]["group"]==group]
        gross=sum(x["math_steps"]["7_implied_gross_before_booked_costs_usd"] for x in v)
        fees=sum(x["math_steps"]["6_booked_costs_usd"] for x in v)
        net=sum(x["math_steps"]["5_net_realized_usd"] for x in v)
        stress=sum(x["math_steps"]["11_double_cost_replay_net_usd"] for x in v)
        group_summary[group]={
            "bots":len(v),
            "closed_trades":sum(x["n_closed"] for x in v),
            "gross_usd":round(gross,2),"costs_usd":round(fees,2),
            "net_usd":round(net,2),"double_cost_net_usd":round(stress,2),
            "model_cost_exceeds_positive_gross":gross>0 and fees>gross,
            "robots_positive_net":sum(x["math_steps"]["5_net_realized_usd"]>0 for x in v),
            "robots_positive_double_cost":sum(x["math_steps"]["11_double_cost_replay_net_usd"]>0 for x in v),
        }
    sign_check=Counter("positive" if v["math_steps"]["5_net_realized_usd"]>0
                       else "negative" if v["math_steps"]["5_net_realized_usd"]<0
                       else "flat" for v in vectors.values())
    return {
        "study":"Step-by-step 27D mathematical paper-robot vector",
        "source_data_sha256":source["price_data"], # immutable per-market fingerprints
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "paper_only":True,"no_order_execution":True,
        "no_strategy_changes":True,"all_27_count":len(vectors),
        "sign_count":dict(sign_check),
        "groups":group_summary,"vectors":vectors,
        "group_comparison_warning":"Different dates and sample sizes; do not treat group sums as one synchronous portfolio",
        "no_automated_promotion":True,
    }

def markdown(result):
    lines=[
        "# Nexus Quant — auditoria do vetor matemático dos 27 robôs",
        "",
        "**Cálculos reproduzíveis dos 27 registros reais de backtest virtual; "
        "dados Yahoo proxy, custos estimados e períodos desiguais.**",
        "",
        "## Fórmulas de cada etapa",
        "",
        "1. N = número de operações **fechadas**; W = vitórias; D = derrotas.",
        "2. Taxa de acerto (%) = 100 × W / N (se N > 0).",
        "3. P&L líquido realizado = saldo virtual atual − capital inicial.",
        "4. Custo contabilizado = soma das taxas estimadas + financiamento registrado.",
        "5. Bruto implícito antes desses custos = líquido + custo contabilizado.",
        "6. Bruto médio por operação = bruto / N.",
        "7. Custo médio por operação = custo / N.",
        "8. Expectativa líquida histórica observada = líquido / N; **não é previsão futura**.",
        "9. Stress = resultado de uma **nova simulação** com custos dobrados, "
        "não uma subtração linear dos custos iniciais.",
        "10. Sensibilidade ao stress (US$) = líquido base − líquido no stress.",
        "11. Drawdown = pior recuo na sequência de **saldos realizados**; "
        "não inclui drawdown intrabar nem posições abertas.",
        "12. Payoff aproximado = PF × D / W; taxa de equilíbrio aproximada (%) = "
        "100 / (1 + payoff), **somente quando PF, W, D são válidos**.",
        "13. Incerteza amostral: intervalo de Wilson de 95% para taxa de vitória; "
        "pressupõe independência binomial, irrealista em muitos mercados.",
        "",
        "### Vetor 27D (uma linha por robô)",
        "",
        "| Robô | N | W/D | Bruto US$ | Custo US$ | Líquido US$ | US$/trade | Custos ×2 US$ | DD realiz. |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for key,row in result["vectors"].items():
        x=row["math_steps"]
        n=x["1_closed_trades"]
        expectation=x["10_expected_net_per_closed_trade_usd"]
        lines.append(
            f"| {key} | {n} | {x['2_wins']}/{x['3_losses']} | "
            f"{x['7_implied_gross_before_booked_costs_usd']:+.2f} | "
            f"{x['6_booked_costs_usd']:.2f} | {x['5_net_realized_usd']:+.2f} | "
            f"{expectation:+.3f}" if False else ""
        )
        lines[-1]=(f"| {key} | {n} | {x['2_wins']}/{x['3_losses']} | "
                   f"{x['7_implied_gross_before_booked_costs_usd']:+.2f} | "
                   f"{x['6_booked_costs_usd']:.2f} | {x['5_net_realized_usd']:+.2f} | "
                   f"{expectation:+.3f}" if expectation is not None else
                   f"| {key} | {n} | {x['2_wins']}/{x['3_losses']} | "
                   f"{x['7_implied_gross_before_booked_costs_usd']:+.2f} | "
                   f"{x['6_booked_costs_usd']:.2f} | {x['5_net_realized_usd']:+.2f} | —")
        lines[-1]+=f" | {x['11_double_cost_replay_net_usd']:+.2f} | {x['13_drawdown_closed_only_pct']:.2f}% |"
    lines += ["", "## Decomposição por grupo (não é carteira sincronizada)","",
              "| Grupo | Robôs | Fechadas | Bruto US$ | Custos US$ | Líquido US$ | Stress US$ |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for group,v in result["groups"].items():
        lines.append(f"| {group} | {v['bots']} | {v['closed_trades']} | "
                     f"{v['gross_usd']:+.2f} | {v['costs_usd']:.2f} | "
                     f"{v['net_usd']:+.2f} | {v['double_cost_net_usd']:+.2f} |")
    lines+=["", "**Não promover estratégias com base nesses resultados retrospectivos.**",
            "O relatório estruturado JSON registra as 19 etapas por robô, ressalvas",
            "e verificações de cobertura. O resultado bruto é **implícito**, derivado",
            "de saldos e custos registrados, não de fills reais da corretora."]
    return "\n".join(lines)+"\n"

def main():
    original=json.loads(SOURCE.read_text(encoding="utf-8"))
    result=analyze(original)
    TARGET.parent.mkdir(parents=True,exist_ok=True)
    TARGET.with_suffix(".json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    TARGET.with_suffix(".md").write_text(markdown(result),encoding="utf-8")
    print("VECTOR_27_FINISHED",json.dumps({"groups":result["groups"],"signs":result["sign_count"]},sort_keys=True),flush=True)

if __name__=="__main__":
    main()
