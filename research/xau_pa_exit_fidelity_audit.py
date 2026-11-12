"""Audit fidelity of exits to user's Stop Red / Stop Win request.

No new signals, indicators, filters, directions or parameter optimization.
Compare (a) EXISTING v6 simulator that closes after 20 M1 candles, versus
(b) same STOP and TARGET levels only, with a mandatory end-of-session close.
An automatic exit after 20 candles is a development ASSUMPTION and was not
specified by the user. We must test its effect, not silently change policy.

Both arms execute identical BID/ASK historical quotes and identical signal
sequence; fills can differ naturally because one position may remain open
longer, blocking subsequent signals. Cost assumptions remain the same.
No claim this backtest reproduces user drawings or a real MT5 broker.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path

from research.xau_price_action_m1m5 import (
    Settings,SourceQualityError,parse_quotes,simulate_ticks,
)
from research.xau_pa_stop_geometry_audit import replay_signals
from research.xau_pa_m5_context_m1_v6 import DAYS,utc_ms,evaluate_day

ARMS=("existing_20_bar_time_exit","stop_win_red_until_session_end")
COSTS=("standard","double")


def quote_gaps(quotes,begin,end):
    """Integrity diagnostics, not cherry-picking of trades or days."""
    tape=[q[0] for q in quotes if begin<=q[0]<end]
    if len(tape)<1500:
        raise SourceQualityError("Too few quotes in execution period")
    gaps=[(a,b) for a,b in zip(tape,tape[1:]) if b-a>60000]
    return {
        "gaps_over_one_minute":len(gaps),
        "largest_gap_seconds":round(max(
            (b-a)/1000 for a,b in zip(tape,tape[1:])
        ),3) if len(tape)>1 else None,
        "top_gaps_utc_ms":[
            {"start":a,"end":b,"gap_seconds":round((b-a)/1000,3)}
            for a,b in sorted(gaps,key=lambda x:x[1]-x[0],reverse=True)[:5]
        ],
        "total_execution_quotes":len(tape),
    }


def day_audit(filepath,day):
    if day not in DAYS:
        raise ValueError("Only the original v6 preregistered source dates")
    quotes,source=parse_quotes(filepath,day)
    trade_start=utc_ms(day,12);trade_end=utc_ms(day,21)
    if (quotes[0][0]>utc_ms(day,9)+60000 or
        quotes[-1][0]<trade_end-120000 or
        quotes[-1][0]>trade_end+59999):
        raise SourceQualityError("Incomplete same 09-21 UTC historical session")
    tape=[q for q in quotes if trade_start<=q[0]<trade_end]
    if not tape or tape[0][0]>trade_start+60000:
        raise SourceQualityError("Trading tape starts too late")
    prior=evaluate_day(filepath,day)
    signals=replay_signals(quotes,day)
    cfg=Settings()
    stressed=replace(cfg,commission_roundtrip_usd_per_oz=.60,
                     slippage_usd_each_market_side=.20)
    outcomes={}
    for name,enable_time in (
        ("existing_20_bar_time_exit",True),
        ("stop_win_red_until_session_end",False)
    ):
        record={"signals":len(signals),"costs":{}}
        for label,settings in (("standard",cfg),("double",stressed)):
            simulation=simulate_ticks(tape,signals,60,settings,
                                      time_stop_enabled=enable_time)
            record["costs"][label]=simulation
        outcomes[name]=record
    # Critical reproducibility invariant: changed parameter cannot
    # corrupt historical reports or previously recorded original v6.
    for cost in COSTS:
        old=prior["results"]["v6_M5_context_M1_entry"]["costs"][cost]
        replay=outcomes["existing_20_bar_time_exit"]["costs"][cost]
        for field in ("signals","filled","wins","losses","net_usd_per_oz"):
            if old[field]!=replay[field]:
                raise ValueError(f"Original v6 output differs in {field}")
        if [(t["entry_ms"],t["exit_ms"],t["reason"]) for t in old["trades"]]!=[
            (t["entry_ms"],t["exit_ms"],t["reason"]) for t in replay["trades"]
        ]:
            raise ValueError("Original time-exit trade order differs")
    return {
        "day":day,"source":source,"quote_gaps":quote_gaps(tape,trade_start,trade_end),
        "same_signal_list_in_both_arms":True,
        "original_v6_reproduced_exactly":True,
        "time_exit_not_user_confirmed":True,
        "original_stop_target_prices_unchanged":True,
        "no_manual_user_drawings":True,
        "not_real_mt5_broker_executions":True,
        "live_approved":False,
        "session_start_utc":"12:00","session_end_utc":"21:00",
        "units":"USD per theoretical one ounce",
        "results":outcomes,
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--ticks",required=True)
    parser.add_argument("--day",required=True)
    parser.add_argument("--out",required=True)
    parser.add_argument("--quarantine",required=True)
    args=parser.parse_args()
    try:
        record=day_audit(args.ticks,args.day)
    except SourceQualityError as err:
        q={"day":args.day,"excluded_entire_day":True,"reason":str(err),
           "trades_counted":0}
        out=Path(args.quarantine);out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(q,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        print("QUARANTINED WHOLE DATE",args.day,str(err))
        return
    path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(record,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    for arm,book in record["results"].items():
        sim=book["costs"]["double"]
        print("EXECUTION_FIDELITY",args.day,arm,"signals",book["signals"],
              "fills",sim["filled"],"wins",sim["wins"],"losses",sim["losses"],
              "net_USDperOz",sim["net_usd_per_oz"],
              "timeouts",sum(t["reason"]=="TIME" for t in sim["trades"]))
    print("QUOTE_GAP_DIAGNOSTIC",record["quote_gaps"])


if __name__=="__main__":
    main()
