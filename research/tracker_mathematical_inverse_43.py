"""Tracker public-vector inverse mathematics, risk viability, identifiability.

Only GREENHOUSE PUBLIC MARKETING labels and reconstructed presentation data.
No original licensed indicator code, no exchange-authenticated fills or data.
No optimization to achieve matching trades; all equations are exact given
the *advertised* 50%, 200%, and -100% level construction, up to tick rounding.

For one WIN: gross P&L = points * 0.20 BRL; costs are hypotheses only.
"""
from __future__ import annotations

import hashlib
import json
import math
import urllib.request
from collections import Counter
from pathlib import Path
from statistics import median

from research.greenhouse_public_gallery_decode import PAGE,decode_literal,record_to_candles

WIN_REAL_PER_POINT=0.20
TICK_POINTS=5
PUBLIC_FEES_SCENARIOS={
    "rico_no_rlp_estimate_3_4":3.40,
    "two_tick_stress_estimate_5_4":5.40,
    "prior_conservative_estimate_6":6.0,
}
BANKROLL_BRL=2000.0
RISK_CAP_BRL=20.0
PUBLIC_SIDES={"c":1,"v":-1}

def reconstruct_levels(entry:int,target:int,stop:int,side:int):
    """Derive vector range/anchor from observed trade levels, not chart candles.

    Symmetric public formula E=midpoint, target/stop = E +/- 1.5R.
    As observed prices may each be rounded to nearest 5 points, the
    max error of 2E-A-S in an exactly symmetric construction is ≤ 10 pt.
    (2*2.5 + 2.5 + 2.5); 43 labels happen to be tighter, ≤5 pt.
    """
    if side not in (-1,1):raise ValueError("side must be +/-1")
    if any(not isinstance(n,int) or n%TICK_POINTS for n in (entry,target,stop)):
        raise ValueError("published levels must be integer 5-point WIN ticks")
    if not side*(target-entry)>0 or not side*(entry-stop)>0:
        raise ValueError("invalid direction")
    center=(target+stop)/2
    amplitude=side*(target-stop)/3
    if amplitude<=0:raise ValueError("negative vector size")
    return {
        "observed_entry":entry,
        "advertised_center_from_extremes":center,
        "center_discrepancy_points":entry-center,
        "midpoint_error_twice_points":2*entry-target-stop,
        "inferred_range_points":amplitude,
        "inferred_high":center+amplitude/2,
        "inferred_low":center-amplitude/2,
        "gross_reward_pts":abs(target-entry),
        "gross_loss_pts":abs(entry-stop),
        "gross_payoff_imbalance_pts":abs(abs(target-entry)-abs(entry-stop)),
        "symmetric_under_level_rounding":abs(2*entry-target-stop)<=10,
        "approx_equal_distance_5pt":abs(2*entry-target-stop)<=5,
    }

def one_contract_economics(entry:int,target:int,stop:int,side:int,
                           fees_brl:float, bankroll_brl:float=BANKROLL_BRL,
                           max_risk_fraction:float=.01):
    """Theoretical P&L if every published entry and exit executed as shown.
    Does NOT estimate intrabar entry order, broker fill, liquidity or margin.
    """
    v=reconstruct_levels(entry,target,stop,side)
    if not math.isfinite(fees_brl) or fees_brl<0:raise ValueError("nonnegative cost")
    if bankroll_brl<=0 or not 0<max_risk_fraction<=1:
        raise ValueError("capital and risk must be positive")
    reward=v["gross_reward_pts"]*WIN_REAL_PER_POINT
    loss=v["gross_loss_pts"]*WIN_REAL_PER_POINT
    net_reward=reward-fees_brl
    net_loss=loss+fees_brl
    return {
        "gross_win_brl":round(reward,2),
        "gross_loss_brl":round(loss,2),
        "net_win_brl":round(net_reward,2),
        "net_loss_brl":round(net_loss,2),
        "planned_loss_within_budget":net_loss<=bankroll_brl*max_risk_fraction+1e-8,
        "minimum_break_even_win_rate_for_this_vector":round(
            net_loss/(net_loss+net_reward),6) if net_reward>0 else None,
        "modelled_costs_roundtrip_brl":fees_brl,
        "available_contracts_under_1pct":int((bankroll_brl*max_risk_fraction)//net_loss),
        "actual_fill_and_historical_ownership_unverified":True,
    }

def wilson_interval(k,n,z=1.96):
    """95% binomial interval conditional on unselected iid Bernoulli draws.
    We explicitly DO NOT assign its inferential meaning to curated promo labels.
    """
    if not 0<=k<=n or n<=0:raise ValueError("invalid count")
    p=k/n
    den=1+z*z/n
    center=(p+z*z/(2*n))/den
    width=z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/den
    return round(center-width,5),round(center+width,5)

def mathematical_nonidentifiability(labels,market_minutes):
    """Build two mathematically different functions consistent with all
    PROMOTIONAL POSITIVE examples but disagreeing on one unmarked point.
    This is a constructive proof that positives cannot uniquely identify
    proprietary threshold(s), independent of search effort.
    """
    positives={(int(r[1]),int(r[2]),int(PUBLIC_SIDES[r[3]])) for r in labels}
    candidates={(day,int(t),side)
                for day,bars in enumerate(market_minutes)
                for t in bars for side in (-1,1)}
    test=next((x for x in sorted(candidates)
               if x not in positives and x[1]>min(market_minutes[x[0]])+25),None)
    if test is None:raise ValueError("no unmarked market point to demonstrate identifiability")
    # f_one(d,m,s): membership among positive marker timestamps
    # f_two(d,m,s): f_one or a second unmarked timestamp.
    assert positives <= (positives|{test})
    assert test not in positives
    return {
        "published_positive_labels":len(positives),
        "minute_direction_possibilities":len(candidates),
        "illustrative_non_labeled_tuple":{"day_index":test[0],"minute":test[1],"side":test[2]},
        "model_A_matches_all_published_positives":True,
        "model_B_matches_all_published_positives":True,
        "model_A_emits_extra_unlabeled_tuple":False,
        "model_B_emits_extra_unlabeled_tuple":True,
        "conclusion":"There are distinct mathematical signal rules consistent with all observed positive labels; proprietary trigger is not uniquely identifiable without verified negatives/flow or code.",
        "caveat":"These constructed rules are proof witnesses, not tradable strategies.",
    }

def audit_data(data):
    if set(data)!={"d","s"}:raise ValueError("public shape changed")
    if len(data["s"])!=43 or len(data["d"])!=2:
        raise ValueError("Expected 43 public entries across two days; reassess source")
    bars=[record_to_candles(x) for x in data["d"]]
    signals=[]
    for rec in data["s"]:
        ident,day,minute,side,e,a,s,outcome,*_ = rec
        if day not in (0,1) or side not in PUBLIC_SIDES or outcome not in ("w","l"):
            raise ValueError("Unexpected public marker format")
        metric=reconstruct_levels(int(e),int(a),int(s),PUBLIC_SIDES[side])
        costs={name:one_contract_economics(int(e),int(a),int(s),PUBLIC_SIDES[side],fee)
               for name,fee in PUBLIC_FEES_SCENARIOS.items()}
        signals.append({
            "id":int(ident),"day_index":int(day),"minute":int(minute),
            "direction":side,"public_outcome_label":outcome,
            "mathematical_vector":metric,"economics_scenarios":costs,
        })
    costs_summary={}
    for name in PUBLIC_FEES_SCENARIOS:
        eligible=[r for r in signals if r["economics_scenarios"][name]["planned_loss_within_budget"]]
        all_win=[r["economics_scenarios"][name]["net_win_brl"] for r in eligible if r["public_outcome_label"]=="w"]
        all_loss=[r["economics_scenarios"][name]["net_loss_brl"] for r in eligible if r["public_outcome_label"]=="l"]
        costs_summary[name]={
            "one_WIN_eligible_1percent_2000BRL":len(eligible),
            "ineligible_even_with_one_WIN":len(signals)-len(eligible),
            "eligible_public_win_labels":len(all_win),
            "eligible_public_loss_labels":len(all_loss),
            "illustrative_sum_if_all_selected_labels_filled_as_shown_BRL":
                round(sum(all_win)-sum(all_loss),2),
            "not_a_backtest_or_verified_profit":True,
        }
    n_win=sum(x["public_outcome_label"]=="w" for x in signals)
    values=[r["mathematical_vector"]["inferred_range_points"] for r in signals]
    return {
        "status":"MATHEMATICAL_INVERSE_OF_PUBLIC_VECTOR_NO_PROPRIETARY_SIGNAL_SOURCE",
        "published_signals":len(signals),
        "public_claimed_win_labels":n_win,
        "public_claimed_loss_labels":len(signals)-n_win,
        "claimed_label_fraction":round(n_win/len(signals),5),
        "conditional_iid_binomial_95pct_interval_DO_NOT_INTERPRET_AS_PERFORMANCE":
            wilson_interval(n_win,len(signals)),
        "round_trip_scenario_fees_BRL_not_broker_confirmed":PUBLIC_FEES_SCENARIOS,
        "max_one_trade_risk_BRL":RISK_CAP_BRL,
        "implied_range_median_points":round(median(values),4),
        "implied_range_min_points":round(min(values),4),
        "implied_range_max_points":round(max(values),4),
        "approx_1to1_within_5WIN_pts":sum(x["mathematical_vector"]["approx_equal_distance_5pt"] for x in signals),
        "all_symmetric_with_rounding_tolerance":all(x["mathematical_vector"]["symmetric_under_level_rounding"] for x in signals),
        "cost_scenarios":costs_summary,
        "identifiability_counterexample":mathematical_nonidentifiability(data["s"],bars),
        "records":signals,
        "limitations":[
            "Only two days of selected promotional labels, NOT the complete original signal record",
            "Greenhouse chart candles are presentation data, not broker-authenticated M1/ticks",
            "No reliable signal-level volume/aggressor/orderbook/book or real-time alert capture",
            "Modeled results condition on all displayed targets/stops filling at exact advertised prices, a strong unverified assumption",
            "Even a high fraction of advertised winning labels cannot prove edge or proprietary rule",
            "This file is not a Greenhouse Tracker copy and must not issue real orders",
        ],
        "approved_for_live":False,
        "original_greenhouse_signal_logic_obtained":False,
    }

def main():
    req=urllib.request.Request(PAGE,headers={"User-Agent":"NexusQuantPublicMathAudit/1.0"})
    with urllib.request.urlopen(req,timeout=30) as r:
        raw=r.read(1_000_000)
    data=decode_literal(raw.decode("utf-8-sig"))
    report=audit_data(data)
    report["public_html_sha256"]=hashlib.sha256(raw).hexdigest()
    path=Path("research/results/tracker_mathematical_inverse_43.json")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    short={k:v for k,v in report.items() if k not in ("records","limitations")}
    print("TRACKER_MATH_INVERSE_START")
    print(json.dumps(short,ensure_ascii=False,indent=2))
    print("TRACKER_MATH_INVERSE_END")

if __name__=="__main__":
    main()
