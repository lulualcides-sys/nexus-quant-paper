"""Independent WIN volume bars, classified delta, CVD and absorption candidates.

Public, clean-room implementation inspired by volume-based microstructure
research. NOT the Greenhouse Tracker algorithm, and not a copy of Quantick.

Source: trade-by-trade stream ONLY from licensed CSV loaded locally through
research.win_licensed_tape_csv.safe_trade_rows. Cannot manufacture aggression,
execute orders, validate historical fills or claim positive expectancy.

Research data and any resulting signals remain in private_mt5/, never GitHub.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from research.win_licensed_tape_csv import (
    safe_trade_rows, detect_csv_session, private_output, source_hash
)

@dataclass(frozen=True)
class Policy:
    target_contracts: int = 500
    min_classified_fraction: float = 0.80
    min_trade_prints: int = 25
    reference_bars: int = 8
    close_position: float = 0.60
    min_contra_fraction: float = 0.55
    require_sweep: bool = True

def check_policy(p: Policy):
    if p.target_contracts<1 or p.min_trade_prints<1 or p.reference_bars<2:
        raise ValueError("Positive bar size/print count and at least 2 reference bars needed")
    if not 0<p.min_classified_fraction<=1:
        raise ValueError("Bad classified fraction")
    if not .5<p.min_contra_fraction<=1:
        raise ValueError("Contra side threshold must be >50%")
    if not .5<=p.close_position<1:
        raise ValueError("Close position must be in [0.5,1)")

def build_closed_volume_bars(trades: Iterable[dict], policy: Policy=Policy()):
    """Emit one *complete* bar when executed contracts reach threshold.

    Large prints are NOT split into invented transactions; a bar's total volume
    can exceed its target. The last incomplete volume bar is discarded, not
    labelled or treated as a closed signal. A single trade can only belong to
    ONE bar. Timestamps must be monotonic.
    """
    check_policy(policy)
    closed=[]
    current=None
    last_stamp=-1
    total_trade_prints=0
    for trade in trades:
        stamp=int(trade["time_msc"])
        px=float(trade["price"])
        quantity=int(trade["quantity"])
        side=int(trade["aggressor"])
        if side not in (-1,0,1):
            raise ValueError("Unknown side must be coded as 0, not imputed")
        if stamp<last_stamp:
            raise ValueError("Out-of-order prints cannot form deterministic bars")
        if px<=0 or not math.isfinite(px) or abs(px/5-round(px/5))>1e-8:
            raise ValueError("Invalid WIN tick price")
        if quantity<=0:
            raise ValueError("Invalid executed quantity")
        last_stamp=stamp
        total_trade_prints+=1
        if current is None:
            current={"begin_time_msc":stamp,"end_time_msc":stamp,
                     "open":px,"high":px,"low":px,"close":px,
                     "volume_contracts":0,"buy_volume":0,"sell_volume":0,
                     "unknown_volume":0,"trade_prints":0,"classified_prints":0}
        bar=current
        bar["end_time_msc"]=stamp
        bar["high"]=max(bar["high"],px)
        bar["low"]=min(bar["low"],px)
        bar["close"]=px
        bar["volume_contracts"]+=quantity
        bar["trade_prints"]+=1
        if side==1:
            bar["buy_volume"]+=quantity
            bar["classified_prints"]+=1
        elif side==-1:
            bar["sell_volume"]+=quantity
            bar["classified_prints"]+=1
        else:
            bar["unknown_volume"]+=quantity
        if bar["volume_contracts"]>=policy.target_contracts:
            bar["closed"]=True
            bar["first_available_after_last_print_msc"]=stamp
            classified=bar["buy_volume"]+bar["sell_volume"]
            bar["classified_fraction"]=round(
                classified/bar["volume_contracts"],6)
            bar["delta"]=bar["buy_volume"]-bar["sell_volume"]
            bar["delta_fraction"]=round(
                bar["delta"]/classified,6) if classified else None
            bar["quality_ok"]=(
                bar["classified_fraction"]>=policy.min_classified_fraction
                and bar["trade_prints"]>=policy.min_trade_prints
                and bar["classified_prints"]>=policy.min_trade_prints
            )
            closed.append(bar)
            current=None
    cvd=0
    for b in closed:
        # CVD does not pretend unknown volume has a directional sign.
        cvd+=b["delta"]
        b["cvd"]=cvd
    return closed,{
        "source":"independent licensed trade tape research",
        "total_trade_prints_processed":total_trade_prints,
        "completed_volume_bars":len(closed),
        "incomplete_tail_dropped":current is not None,
        "incomplete_tail_contracts":current["volume_contracts"] if current else 0,
        "quality_passed_bars":sum(b["quality_ok"] for b in closed),
        "no_trade_splitting_or_direction_inference":True,
        "not_greenhouse_tracker":True,
    }

def detect_absorption(bars: list[dict], policy: Policy=Policy()):
    """Frozen, causal rule. Signals only on volume bars already CLOSED."""
    check_policy(policy)
    signals=[]
    for i in range(policy.reference_bars,len(bars)):
        b=bars[i]
        history=bars[i-policy.reference_bars:i]
        if not b["quality_ok"] or not all(h["quality_ok"] for h in history):
            continue
        if b["high"]<=b["low"]:
            continue
        classified=b["buy_volume"]+b["sell_volume"]
        if classified<=0:
            continue
        previous_low=min(x["low"] for x in history)
        previous_high=max(x["high"] for x in history)
        low_anchor=min(history,key=lambda x:(x["low"],x["end_time_msc"]))
        high_anchor=max(history,key=lambda x:(x["high"],-x["end_time_msc"]))
        close_pos=(b["close"]-b["low"])/(b["high"]-b["low"])
        sell_share=b["sell_volume"]/classified
        buy_share=b["buy_volume"]/classified
        # Absorption: aggressive SELL orders predominate, but price
        # rejects new low and candle closes strongly higher; mirrored SELL.
        bullish=(b["close"]>b["open"] and
                 close_pos>=policy.close_position and
                 sell_share>=policy.min_contra_fraction and
                 (not policy.require_sweep or
                  (b["low"]<previous_low and b["close"]>previous_low)))
        bearish=(b["close"]<b["open"] and
                 close_pos<=1-policy.close_position and
                 buy_share>=policy.min_contra_fraction and
                 (not policy.require_sweep or
                  (b["high"]>previous_high and b["close"]<previous_high)))
        # CVD/price divergence: price makes a fresh extreme while CVD
        # does not confirm relative to the OLDER prior-extreme bar.
        bullish_cvd_div=(b["low"]<previous_low and
                         b["cvd"]>low_anchor["cvd"])
        bearish_cvd_div=(b["high"]>previous_high and
                         b["cvd"]<high_anchor["cvd"])
        if bullish==bearish: # neither or both -> no signal
            continue
        side=1 if bullish else -1
        signals.append({
            "direction":"buy" if side==1 else "sell",
            "end_time_msc":b["end_time_msc"],
            "first_available_after_last_print_msc":b[
                "first_available_after_last_print_msc"],
            "source_bar_index":i,
            "close":b["close"],"high":b["high"],"low":b["low"],
            "delta":b["delta"],"delta_fraction":b["delta_fraction"],
            "cvd":b["cvd"],
            "cvd_divergence_at_closure":bullish_cvd_div if bullish
                                        else bearish_cvd_div,
            "signal_type":"INDEPENDENT_VOLUME_BAR_ABSORPTION",
            "not_original_tracker":True,
            "not_authorized_for_live_orders":True,
        })
    return signals

def main():
    ap=argparse.ArgumentParser(description="WIN licensed tick CSV -> deterministic volume bars / CVD / absorption research")
    ap.add_argument("--csv",required=True)
    ap.add_argument("--target-contracts",type=int,default=500)
    ap.add_argument("--out",default="private_mt5/nq_win_volume_bars.json")
    args=ap.parse_args()
    src=Path(args.csv)
    if not src.is_file():
        ap.error("Licensed local CSV not found")
    symbol,day=detect_csv_session(src)
    policy=Policy(target_contracts=args.target_contracts)
    bars,diagnostics=build_closed_volume_bars(
        safe_trade_rows(src,symbol,day),policy)
    signals=detect_absorption(bars,policy)
    report={"status":"LICENSED_DATA_INDEPENDENT_FLOW_RESEARCH",
            "source_symbol":symbol,"source_day":day,
            "source_sha256":source_hash(src),
            "policy":policy.__dict__,
            "diagnostics":diagnostics,"bars":bars,"signals":signals,
            "real_trades_confirmed_by_system":False,
            "profitability_demonstrated":False,
            "source_is_greenhouse_proprietary_indicator":False,
            "broker_orders_sent":0}
    digest=private_output(report,args.out)
    print(json.dumps({
        "symbol":symbol,"day":day,
        "closed_volume_bars":len(bars),
        "absorption_candidates":len(signals),
        "quality_passed_bars":diagnostics["quality_passed_bars"],
        "tail_dropped":diagnostics["incomplete_tail_dropped"],
        "private_output":str(Path(args.out).resolve()),
        "private_output_sha256":digest,
        "no_live_trades":True},indent=2))

if __name__=="__main__":
    main()
