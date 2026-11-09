"""Independent closed-candle sweep/volume detector and public vector geometry.

NOT the Greenhouse Tracker source, no claim of same proprietary signals.
This Python reference mirrors indicators/mt5/NQ_Vector_Exhaustion_Research.mq5.
Candles are chronological, genuine M1 bars with no lookahead:
each decision at i reads bars [i-lookback:i] and the just-CLOSED bar i.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean
from zoneinfo import ZoneInfo

TZ=ZoneInfo("America/Sao_Paulo")
VALUE_PER_WIN_POINT_BRL=0.20

@dataclass(frozen=True)
class Rules:
    lookback: int=20
    volume_factor: float=1.30
    min_wick_fraction: float=0.35
    min_sweep_points: float=5.0
    min_range_points: float=30.0
    max_range_points: float=450.0
    require_real_volume: bool=True
    # Trading sandbox constraints, NOT Greenhouse parameters:
    bankroll_brl: float=2000
    risk_fraction: float=.01
    fee_roundtrip_brl: float=4.
    slippage_ticks_each_side: int=1
    pending_bars: int=12
    max_hold_bars: int=40

def _day(ts):
    return datetime.fromtimestamp(ts,timezone.utc).astimezone(TZ).date().isoformat()

def vector(high,low,side):
    """Candle 0,50,100,200,-100 as publicly described."""
    if side not in (-1,1) or not low<high:
        raise ValueError("valid side and nonzero candle required")
    r=high-low
    origin=low if side==1 else high
    return {
        "0":origin, "50":origin+side*.5*r,
        "100":origin+side*r, "200":origin+side*2*r,
        "-100":origin-side*r
    }

def detect(bars,i,rule=Rules()):
    if i<rule.lookback or i>=len(bars):
        return None
    bar=bars[i]
    history=bars[i-rule.lookback:i]
    # Previous bars must all be from same local date: no blend across sessions.
    if any(_day(b["time"])!=_day(bar["time"]) for b in history):
        return None
    r=bar["high"]-bar["low"]
    if r<rule.min_range_points or r>rule.max_range_points:
        return None
    volumes=[float(b["volume"]) for b in history]
    current_volume=float(bar["volume"])
    if not all(v>0 for v in volumes) or current_volume<=0:
        return None
    if current_volume<rule.volume_factor*mean(volumes):
        return None
    prior_high=max(b["high"] for b in history)
    prior_low=min(b["low"] for b in history)
    lower_wick=min(bar["open"],bar["close"])-bar["low"]
    upper_wick=bar["high"]-max(bar["open"],bar["close"])
    buy=(bar["low"]<=prior_low-rule.min_sweep_points
         and bar["close"]>prior_low
         and bar["close"]>bar["open"]
         and lower_wick/r>=rule.min_wick_fraction)
    sell=(bar["high"]>=prior_high+rule.min_sweep_points
          and bar["close"]<prior_high
          and bar["close"]<bar["open"]
          and upper_wick/r>=rule.min_wick_fraction)
    if buy==sell:
        return None
    side=1 if buy else -1
    return {"index":i,"time":bar["time"],"side":side,
            "high":bar["high"],"low":bar["low"],
            "levels":vector(bar["high"],bar["low"],side)}

def planned_economics(signal,rule=Rules()):
    """Equal gross profit/risk, positive execution cost, size fixed at one WIN."""
    entry=signal["levels"]["50"]
    stop=signal["levels"]["-100"]
    target=signal["levels"]["200"]
    cost=rule.fee_roundtrip_brl+2*rule.slippage_ticks_each_side*1.0
    reward=abs(target-entry)*VALUE_PER_WIN_POINT_BRL-cost
    risk=abs(entry-stop)*VALUE_PER_WIN_POINT_BRL+cost
    max_risk=rule.bankroll_brl*rule.risk_fraction
    return {
        "entry":entry,"target":target,"stop":stop,
        "gross_reward_brl":abs(target-entry)*VALUE_PER_WIN_POINT_BRL,
        "gross_risk_brl":abs(entry-stop)*VALUE_PER_WIN_POINT_BRL,
        "reward_net_brl":round(reward,2),
        "risk_net_brl":round(risk,2),
        "break_even_hit_rate":risk/(risk+reward) if risk+reward>0 else 1.,
        "exceeds_budget":risk>max_risk+1e-9,
        "net_rr":round(reward/risk,4),
        "cost_roundtrip_brl":cost,
    }

def replay(bars,rule=Rules()):
    """Pessimistic OHLC-only paper replay, never real brokerage fills.

    Stop wins on intrabar ambiguities; missing bars invalidate an open trade.
    Pending entry is cancelled if a target can be reached before the limit.
    No partial fills, spread/depth, order routing or promised expectancy.
    """
    signals=0
    rejected_budget=0
    no_fill=0
    gaps_during_position=0
    ambiguous_fills=0
    ledger=[]
    pending=None
    trade=None
    last=None
    for i,bar in enumerate(bars):
        ts=bar["time"]
        day=_day(ts)
        if last is not None and ts-last!=60:
            if trade is not None:
                gaps_during_position+=1
                # Do not count as verified execution/profit:
                ledger.append({"entry_time":trade["time"],"exit_time":ts,
                               "outcome":"UNVERIFIABLE_GAP","net_brl":None})
                trade=None
            if pending is not None:
                no_fill+=1
                pending=None
        last=ts
        if pending is not None and (day!=pending["day"] or
                                    i-pending["signal_index"]>rule.pending_bars):
            no_fill+=1
            pending=None
        if trade is not None and day!=trade["day"]:
            gaps_during_position+=1
            ledger.append({"entry_time":trade["time"],"exit_time":ts,
                           "outcome":"UNVERIFIABLE_SESSION_BOUNDARY","net_brl":None})
            trade=None
        if trade is not None:
            x=trade
            stop_hit=(bar["low"]<=x["stop"] if x["side"]==1 else bar["high"]>=x["stop"])
            target_hit=(bar["high"]>=x["target"] if x["side"]==1 else bar["low"]<=x["target"])
            if stop_hit or target_hit or i-x["entry_index"]>=rule.max_hold_bars:
                why="STOP" if stop_hit else "TARGET" if target_hit else "TIME"
                exit_px=x["stop"] if stop_hit else x["target"] if target_hit else bar["close"]
                pnl=round((exit_px-x["entry"])*x["side"]*VALUE_PER_WIN_POINT_BRL-x["cost"],2)
                ledger.append({"entry_time":x["time"],"exit_time":ts,"outcome":why,"net_brl":pnl})
                trade=None
        # Process pending only if no open trade; no same-bar reentry.
        if pending is not None and trade is None:
            p=pending
            target_reached=(bar["high"]>=p["target"] if p["side"]==1 else bar["low"]<=p["target"])
            touched_entry=(bar["low"]<=p["entry"]<=bar["high"])
            # If target and limit both possible inside M1, sequence unobservable.
            if target_reached and touched_entry:
                ambiguous_fills+=1
                no_fill+=1
                pending=None
            elif target_reached:
                no_fill+=1
                pending=None
            elif touched_entry:
                trade={"time":ts,"day":day,"entry_index":i,"side":p["side"],
                       "entry":p["entry"],"stop":p["stop"],"target":p["target"],
                       "cost":p["cost"]}
                pending=None
                stop_hit=(bar["low"]<=trade["stop"] if trade["side"]==1 else bar["high"]>=trade["stop"])
                if stop_hit:
                    ambiguous_fills+=1
                    pnl=round(-abs(trade["entry"]-trade["stop"])*VALUE_PER_WIN_POINT_BRL-trade["cost"],2)
                    ledger.append({"entry_time":trade["time"],"exit_time":ts,
                                   "outcome":"AMBIGUOUS_ENTRY_STOP_ASSUMED_STOP","net_brl":pnl})
                    trade=None
        # Confirmation of current candle can only be acted on from next bar.
        if pending is None and trade is None:
            setup=detect(bars,i,rule)
            if setup is not None:
                signals+=1
                economy=planned_economics(setup,rule)
                if economy["exceeds_budget"]:
                    rejected_budget+=1
                else:
                    pending={"day":day,"signal_index":i,"side":setup["side"],
                             "entry":economy["entry"],"stop":economy["stop"],
                             "target":economy["target"],"cost":economy["cost_roundtrip_brl"]}
    closed=[t for t in ledger if t["net_brl"] is not None]
    net=round(sum(t["net_brl"] for t in closed),2)
    wins=[x for x in closed if x["net_brl"]>0]
    losses=[x for x in closed if x["net_brl"]<0]
    pf=(round(sum(x["net_brl"] for x in wins)/-sum(x["net_brl"] for x in losses),3)
        if losses else None)
    return {
        "status":"RESEARCH_NOT_LIVE_TRADING",
        "signals":signals,
        "rejected_for_1pct_budget":rejected_budget,
        "closed_paper_trades":len(closed),
        "winning_closed":len(wins),
        "winning_rate_pct":round(len(wins)*100/len(closed),2) if closed else None,
        "net_closed_brl":net,
        "profit_factor":pf,
        "not_filled_or_expired":no_fill,
        "ambiguous_within_M1":ambiguous_fills,
        "unverifiable_gap_or_session_exits":gaps_during_position,
        "unclosed_at_end":bool(trade),
        "pending_at_end":bool(pending),
        "approved_for_live":False,
        "ledger":ledger
    }
