"""V6 ALPHA02: 22-month uninterrupted V5 baseline vs causal protective stops.

All other parameters, original signal, H1/H4 gates, target, emergency stop,
fee/spread/slippage, cooldown, and sizing are identical in both arms. ONLY:
- old month-start reset removed in BOTH arms;
- candidate may tighten but NEVER widen a stop, after 2 ATR favorable CLOSE;
- updated stop applies ONLY FROM NEXT CANDLE, never retroactively same bar.

No order placement, leverage or real broker fills. Cost estimates are assumed.
"""
from __future__ import annotations
from datetime import datetime,timezone
from research.alpha.engine import START_USDT,RISK_FRACTION,TAKER_FEE_BPS,HALF_SPREAD_BPS,check_candles,iso
from research.alpha_v4.strategy import H1_WARMUP,TARGET_H1_ATR,STOP_H1_ATR,MAX_HOLD_HOURS,COOLDOWN_HOURS

PROTECT_ACTIVATE_ATR=2.0
TRAIL_FROM_CLOSE_ATR=2.0

def replay(model,slippage_bps=5.,protect=False):
    bars=model.bars
    minutes=model.minutes
    check_candles(bars,minutes)
    fee=TAKER_FEE_BPS/10000.
    half_and_slip=(HALF_SPREAD_BPS+slippage_bps)/10000.
    equity=peak=START_USDT
    max_dd=0.
    position=None
    pending_time=False
    cooldown_until=0
    ledger=[]
    open_count=signal_count=protect_activations=0
    # V5 requires 60 fully closed H4 as well as 210 H1. These bars are
    # consumed ONCE in the continuous sequence, not once every month.
    start=(H1_WARMUP+1)*(60//minutes)
    if len(bars)<=start+1:raise ValueError("not enough historical candles")

    def close_trade(price,when,reason):
        nonlocal position,equity,cooldown_until
        p=position
        sell=price*(1-half_and_slip)
        gross=(price-p["raw"])*p["qty"]
        net=(sell-p["entry"])*p["qty"]-fee*(sell+p["entry"])*p["qty"]
        equity+=net
        ledger.append(dict(signal_ts_utc=iso(p["signal_ts"]),
            entry_ts_utc=iso(p["entry_ts"]),exit_ts_utc=iso(when),
            side="LONG",entry_raw=round(p["raw"],8),entry=round(p["entry"],8),
            exit_raw=round(price,8),exit=round(sell,8),
            qty=round(p["qty"],9),gross_usdt=round(gross,6),
            costs_usdt=round(gross-net,6),net_usdt=round(net,6),
            reason=reason,stop_protect_activated=p["protected"],
            slippage_bps_per_side=slippage_bps))
        cooldown_until=when+COOLDOWN_HOURS*3600
        position=None

    for i in range(start,len(bars)):
        b=bars[i]
        closed_at_open=False
        if position is not None and pending_time:
            close_trade(b["open"],b["time"],"time_or_h1_next_open")
            pending_time=False
            closed_at_open=True
        if position is None and not closed_at_open and b["time"]>=cooldown_until:
            # Prior M5 bar is entirely closed at current M5 open.
            if model.signal(i-1):
                signal_count+=1
                h=model.last_closed_h1(i-1)
                atr=model.hf["atr"][h]  # H1 known before new entry
                if atr>0:
                    raw=b["open"]
                    entry=raw*(1+half_and_slip)
                    dist=max(STOP_H1_ATR*atr,raw*.002)
                    stop=entry-dist
                    target=entry+TARGET_H1_ATR*atr
                    stop_sell=stop*(1-half_and_slip)
                    risk_unit=entry-stop_sell+fee*(entry+stop_sell)
                    quantity=(min(equity*RISK_FRACTION/risk_unit,
                                 equity*.98/(entry*(1+fee)))
                              if risk_unit>0 and stop>0 and equity>0 else 0)
                    if quantity>0 and target>entry:
                        open_count+=1
                        position=dict(signal_ts=bars[i-1]["time"]+minutes*60,
                                      entry_ts=b["time"],raw=raw,entry=entry,
                                      stop=stop,original_stop=stop,target=target,
                                      atr=atr,qty=quantity,
                                      protected=False)
        if position is not None:
            p=position
            # Intrabar stop/target paths unknown: conservative stop precedence.
            if b["low"]<=p["stop"]:
                exit_raw=(min(b["open"],p["stop"])
                          if b["time"]>p["entry_ts"] else p["stop"])
                close_trade(exit_raw,b["time"]+minutes*60,
                       ("protected_stop" if p["protected"] else
                        ("ambiguous_stop_first" if b["high"]>=p["target"] else "stop")))
            elif b["high"]>=p["target"]:
                close_trade(p["target"],b["time"]+minutes*60,"target")
            else:
                if (b["time"]+minutes*60-p["entry_ts"]>=MAX_HOLD_HOURS*3600
                    or model.h1_exiting(i)):
                    pending_time=True
                # Only update after this candle's high/low exit processing;
                # newly raised stop becomes active in NEXT candle.
                if protect and b["close"]>=p["entry"]+PROTECT_ACTIVATE_ATR*p["atr"]:
                    # Exact cost-inclusive raw stop that would net ~zero,
                    # assuming exit at stop with modelled spread and slippage.
                    breakeven_raw=p["entry"]*(1+fee)/((1-half_and_slip)*(1-fee))
                    new_stop=max(p["stop"],breakeven_raw,
                                 b["close"]-TRAIL_FROM_CLOSE_ATR*p["atr"])
                    new_stop=min(new_stop,b["close"])
                    if new_stop>p["stop"]:
                        p["stop"]=new_stop
                        if not p["protected"]:protect_activations+=1
                        p["protected"]=True
        marked=equity
        if position is not None:
            assumed_close=b["close"]*(1-half_and_slip)
            marked+=((assumed_close-position["entry"])-
                     fee*(assumed_close+position["entry"]))*position["qty"]
        peak=max(peak,marked)
        max_dd=max(max_dd,(peak-marked)/peak if peak>0 else 1.)
        if equity < -1e-6:
            raise AssertionError("negative virtual book equity")

    # No fabricated market close: keep final open position marked separately.
    open_marked_net=None
    if position is not None:
        last=bars[-1]["close"]*(1-half_and_slip)
        open_marked_net=((last-position["entry"])-
                         fee*(last+position["entry"]))*position["qty"]
    result=dict(ledger=ledger,equity=equity,signals_seen=signal_count,
                orders_filled=open_count,protection_activations=protect_activations,
                protective_enabled=protect,
                max_drawdown_pct=round(max_dd*100,5),
                open_at_end=position is not None,
                marked_open_net_usdt=(round(open_marked_net,5)
                                      if open_marked_net is not None else None),
                marked_total_equity_usdt=round(equity+(open_marked_net or 0),5))
    if abs(sum(x["net_usdt"] for x in ledger)-(equity-START_USDT))>.05:
        raise AssertionError("ledger/equity mismatch")
    return result
