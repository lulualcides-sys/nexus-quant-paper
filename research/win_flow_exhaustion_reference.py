"""Deterministic independent research reference for classified WIN trade ticks.

NOT Greenhouse Tracker code or its verified thresholds. Mirrors the conceptual
closed-M1-bar / CopyTicksRange processing in NQ_Win_Exaustao_Fluxo_Research.mq5.
Only genuine positive executed volume, and buy/sell flags classify aggressors.
No inference from tick-volume / candle direction. No orders, no live claims.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

SP = ZoneInfo("America/Sao_Paulo")
BUY_FLAG=32
SELL_FLAG=64
VOLUME_FLAG=16
TICK_MILLISECOND=1000

@dataclass(frozen=True)
class ResearchPolicy:
    lookback: int=20
    bar_volume_multiplier: float=1.15
    min_classified_events: int=25
    min_classified_share: float=0.60
    contra_aggressor_share: float=0.56
    min_wick_fraction: float=0.15
    close_location: float=0.60
    min_candle_points: float=30.0
    max_candle_points: float=400.0
    sweep_by_points: float=5.0
    near_extreme_points: float=50.0
    signal_method: int=2  # 0 sweep, 1 near extreme absorption, 2 either
    verify_tick_coverage: bool=True

def local_day(ts: int) -> str:
    return datetime.fromtimestamp(ts,tz=timezone.utc).astimezone(SP).date().isoformat()

def price_candidate(bars: list[dict], i: int, policy: ResearchPolicy=ResearchPolicy()):
    """Decision only uses the just-closed bar i and earlier bars, never later."""
    if i<policy.lookback or i>=len(bars):
        return None
    candle=bars[i]
    hist=bars[i-policy.lookback:i]
    if any(local_day(x["time"])!=local_day(candle["time"]) for x in hist):
        return None
    ran=candle["high"]-candle["low"]
    if not policy.min_candle_points<=ran<=policy.max_candle_points:
        return None
    if any(x.get("real_volume",0)<=0 for x in hist) or candle.get("real_volume",0)<=0:
        return None
    if candle["real_volume"]<policy.bar_volume_multiplier*sum(x["real_volume"] for x in hist)/len(hist):
        return None
    ph=max(x["high"] for x in hist)
    pl=min(x["low"] for x in hist)
    pos=(candle["close"]-candle["low"])/ran
    lower_wick=(min(candle["open"],candle["close"])-candle["low"])/ran
    upper_wick=(candle["high"]-max(candle["open"],candle["close"]))/ran
    buy_sweep=candle["low"]<=pl-policy.sweep_by_points and candle["close"]>pl
    sell_sweep=candle["high"]>=ph+policy.sweep_by_points and candle["close"]<ph
    buy_near=candle["low"]<=pl+policy.near_extreme_points
    sell_near=candle["high"]>=ph-policy.near_extreme_points
    if policy.signal_method==0:
        buy_method,sell_method=buy_sweep,sell_sweep
    elif policy.signal_method==1:
        buy_method,sell_method=buy_near,sell_near
    else:
        buy_method,sell_method=(buy_sweep or buy_near),(sell_sweep or sell_near)
    buy=(buy_method and candle["close"]>candle["open"]
         and pos>=policy.close_location and lower_wick>=policy.min_wick_fraction)
    sell=(sell_method and candle["close"]<candle["open"]
          and pos<=1-policy.close_location and upper_wick>=policy.min_wick_fraction)
    return 1 if buy and not sell else (-1 if sell and not buy else None)

def classified_flow(ticks: list[dict], candle_open_seconds: int,
                    policy: ResearchPolicy=ResearchPolicy()):
    """Classified executions only. Missing metadata means no signal."""
    from_ms=candle_open_seconds*1000
    to_ms=from_ms+59999
    buy=sell=unknown=0.
    classified_events=0
    first=last=None
    for t in ticks:
        stamp=t["time_msc"]
        if not from_ms<=stamp<=to_ms:
            continue
        flags=int(t.get("flags",0))
        is_buy=bool(flags & BUY_FLAG)
        is_sell=bool(flags & SELL_FLAG)
        vol=float(t.get("volume_real",0))
        if is_buy == is_sell:  # both or neither
            if not is_buy and flags & VOLUME_FLAG and vol>0:
                unknown+=vol
            continue
        if vol<=0:
            continue
        if is_buy:buy+=vol
        else:sell+=vol
        classified_events+=1
        first=stamp if first is None else min(first,stamp)
        last=stamp if last is None else max(last,stamp)
    classified=buy+sell
    if classified_events<policy.min_classified_events or classified<=0:
        return None
    share=classified/(classified+unknown)
    if share<policy.min_classified_share:
        return None
    if policy.verify_tick_coverage and (first>from_ms+15000 or last<to_ms-15000):
        return None
    dominance=max(buy,sell)/classified
    if dominance<policy.contra_aggressor_share:
        return None
    return {"side":1 if sell>buy else -1, "buy_volume":buy,
            "sell_volume":sell,"unknown_volume":unknown,
            "contra_share":dominance, "coverage":share,
            "classified_events":classified_events}

def fibonacci_levels(bar: dict, direction: int, tick_size: float=5.0):
    if direction not in (-1,1):
        raise ValueError("direction must be -1 or +1")
    high,low=bar["high"],bar["low"]
    if high<=low or tick_size<=0:
        raise ValueError("invalid candle/tick")
    ran=high-low
    origin=low if direction==1 else high
    def rounded(price):
        # MQL5 MathRound equivalent for positive index prices
        return int(price/tick_size+0.5)*tick_size
    return {name:rounded(origin+direction*f*ran)
            for name,f in {"0":0,"50":0.5,"100":1,"200":2,"-100":-1}.items()}

def classify_closed_bar(bars: list[dict], i: int, ticks: list[dict],
                        policy: ResearchPolicy=ResearchPolicy()):
    """Signal i is only available AFTER bars[i] closes; never bar in formation."""
    side=price_candidate(bars,i,policy)
    if side is None:return None
    flow=classified_flow(ticks,bars[i]["time"],policy)
    if flow is None or flow["side"]!=side:
        return None
    return {"time":bars[i]["time"],"side":side,
            "flow":flow,"levels":fibonacci_levels(bars[i],side),
            "status":"INDEPENDENT_RESEARCH_SIGNAL_NOT_BROKER_ORDER"}

def economic_note(signal, *, cost_roundtrip_brl=6.0, value_per_point=.20,
                  bankroll_brl=2000,risk_fraction=.01):
    level=signal["levels"]
    gross=abs(level["200"]-level["50"])*value_per_point
    gross_loss=abs(level["50"]-level["-100"])*value_per_point
    reward=gross-cost_roundtrip_brl
    risk=gross_loss+cost_roundtrip_brl
    return {"net_reward_brl":round(reward,2),"planned_net_loss_brl":round(risk,2),
            "break_even_win_rate":round(risk/(risk+reward),4) if reward+risk>0 else None,
            "exceeds_one_win_risk_budget":risk>bankroll_brl*risk_fraction,
            "broker_fee_confirmed":False,"approved_for_live":False}
