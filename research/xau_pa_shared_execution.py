"""One-symbol M1/M5 quote executor for XAUUSD PA v3 research.

Unlike two separately reported backtests, this enforces the user's constraint
of ONE position on XAUUSD across both timeframes. It does not call an order API.
This reproduces the established quote execution mechanics while making holding
time depend on each actual originating timeframe, not an arbitrary global tf.

If M1 and M5 produce a signal at the same eligible timestamp, neither is
executed: trade priority was NOT specified by the user, and we may not invent
one to improve the backtest. The collision is counted.
"""
from __future__ import annotations

from collections import Counter

from research.xau_price_action_m1m5 import Settings


def simulate_shared_quotes(quotes,signals,settings=Settings()):
    settings.validate()
    ordered=sorted(signals,key=lambda s:(s["eligible_ms"],s["timeframe_seconds"]))
    for s in ordered:
        if s.get("timeframe_seconds") not in (60,300):
            raise ValueError("M1/M5 timeframe required")
        if s.get("side") not in (-1,1):
            raise ValueError("Invalid signal side")
    collision=Counter(s["eligible_ms"] for s in ordered)
    ambiguous={t for t,n in collision.items() if n>1}
    rejects=Counter()
    trades=[]
    index=0
    position=None;last=None
    for ms,bid,ask in quotes:
        if last is not None and ms<last[0]:
            raise ValueError("Nonchronological BID/ASK")
        if not 0<bid<ask:
            raise ValueError("Invalid BID/ASK")
        last=(ms,bid,ask)
        just_closed=False
        if position is not None:
            p=position;direction=p["side"]
            stop=(bid<=p["stop"] if direction==1 else ask>=p["stop"])
            target=(bid>=p["target"] if direction==1 else ask<=p["target"])
            expired=(ms>=p["entry_ms"]+
                     p["timeframe_seconds"]*settings.max_hold_bars*1000)
            reason=None
            if stop:
                reason="STOP"
                price=min(bid,p["stop"]) if direction==1 else max(ask,p["stop"])
                price-=direction*settings.slippage_usd_each_market_side
            elif target:
                reason="TARGET";price=p["target"]
            elif expired:
                reason="TIME"
                price=(bid if direction==1 else ask)
                price-=direction*settings.slippage_usd_each_market_side
            if reason:
                pnl=round(direction*(price-p["entry"])-
                          settings.commission_roundtrip_usd_per_oz,6)
                trades.append({**p,"exit_ms":ms,"exit":round(price,6),
                               "reason":reason,"net_usd_per_oz":pnl})
                position=None;just_closed=True

        while index<len(ordered) and ordered[index]["eligible_ms"]<=ms:
            s=ordered[index];index+=1
            if s["eligible_ms"] in ambiguous:
                rejects["simultaneous_m1_m5_ambiguous"]+=1
                continue
            if position is not None or just_closed:
                rejects["already_in_position"]+=1
                continue
            if ms-s["eligible_ms"]>settings.max_entry_delay_seconds*1000:
                rejects["delayed"]+=1
                continue
            if ask-bid>settings.max_entry_spread_usd:
                rejects["wide_spread"]+=1
                continue
            side=s["side"]
            entry=(ask if side==1 else bid)+side*settings.slippage_usd_each_market_side
            stop_level=round(s["stop"],3)
            dist=side*(entry-stop_level)
            if (not settings.min_stop_atr*s["atr"]<=dist<=settings.max_stop_atr*s["atr"]
                or dist<=0):
                rejects["stop_geometry"]+=1
                continue
            target_level=entry+side*settings.reward_risk*dist
            if s["setup"]=="range_rejection":
                room=side*(s["room_limit"]-entry)
                if room<1.5*dist:
                    rejects["stop_geometry"]+=1
                    continue
                target_level=entry+side*min(settings.reward_risk*dist,room)
            expected_net_goal=side*(target_level-entry)-settings.commission_roundtrip_usd_per_oz
            expected_net_stop=dist+settings.commission_roundtrip_usd_per_oz+settings.slippage_usd_each_market_side
            if expected_net_goal<settings.min_net_rr*expected_net_stop:
                rejects["uneconomic"]+=1
                continue
            position={**s,"entry_ms":ms,"entry":round(entry,6),
                      "stop":stop_level,"target":round(target_level,6)}
    if position is not None and last is not None:
        ms,bid,ask=last;side=position["side"]
        exit_at=(bid if side==1 else ask)-side*settings.slippage_usd_each_market_side
        pnl=round(side*(exit_at-position["entry"])-
                  settings.commission_roundtrip_usd_per_oz,6)
        trades.append({**position,"exit_ms":ms,
                       "exit":round(exit_at,6),
                       "reason":"SESSION_END","net_usd_per_oz":pnl})
    rejects["not_seen_before_end"]=len(ordered)-index
    gain=sum(t["net_usd_per_oz"] for t in trades if t["net_usd_per_oz"]>0)
    loss=-sum(t["net_usd_per_oz"] for t in trades if t["net_usd_per_oz"]<0)
    result={
        "signals":len(ordered),"filled":len(trades),
        "wins":sum(t["net_usd_per_oz"]>0 for t in trades),
        "losses":sum(t["net_usd_per_oz"]<0 for t in trades),
        "net_usd_per_oz":round(gain-loss,6),
        "profit_factor":round(gain/loss,5) if loss else None,
        "expectancy_usd_per_oz":round((gain-loss)/len(trades),5) if trades else None,
        "rejected":dict(sorted(rejects.items())),
        "by_setup":{
            name:{"trades":sum(t["setup"]==name for t in trades),
                  "net_usd_per_oz":round(sum(t["net_usd_per_oz"]
                                            for t in trades if t["setup"]==name),6)}
            for name in ("break_retest","range_rejection")
        },
        "one_global_position_per_symbol":True,
        "m1_m5_same_timestamp_skipped":True,
        "trades":trades,
    }
    ordered_fills=sorted(trades,key=lambda t:t["entry_ms"])
    for old,new in zip(ordered_fills,ordered_fills[1:]):
        if new["entry_ms"]<=old["exit_ms"]:
            raise ValueError("Simultaneous position detected")
    return result
