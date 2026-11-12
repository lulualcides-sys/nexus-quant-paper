"""Conservative long-only spot H1/M5-M1 research fills, no broker access.

A signal on bar i-1 closes before any fill at i.open. A stop triggered within
the bar fills at stop unless bar.open gaps below it. Stop wins same-bar collision.
An H1 trend/time exit is requested at confirmed bar close and fills next open.
"""
from research.alpha.engine import (check_candles,iso,stats,START_USDT,
                                   RISK_FRACTION,TAKER_FEE_BPS,HALF_SPREAD_BPS)
from research.alpha_v4.strategy import (
 TARGET_H1_ATR,STOP_H1_ATR,MAX_HOLD_HOURS,COOLDOWN_HOURS,H1_WARMUP)

def backtest(model,slippage_bps=5.0):
    bars=model.bars
    minutes=model.minutes
    check_candles(bars,minutes)
    fee=TAKER_FEE_BPS/10000
    friction=(HALF_SPREAD_BPS+slippage_bps)/10000
    equity=peak=START_USDT
    max_dd=0.
    trade=None
    rows=[]
    fills=signals=0
    cooldown_until=0
    exit_pending=False
    reasons={}
    def finish(price,ts,why):
        nonlocal equity,trade,cooldown_until
        p=trade
        sell=price*(1-friction)
        net=p["qty"]*(sell-p["entry"])-fee*p["qty"]*(sell+p["entry"])
        gross=p["qty"]*(price-p["raw"])
        equity+=net
        rows.append(dict(signal_ts_utc=iso(p["signal_ts"]),
             entry_ts_utc=iso(p["entry_ts"]),exit_ts_utc=iso(ts),
             side="LONG",entry_raw=round(p["raw"],6),entry=round(p["entry"],6),
             exit_raw=round(price,6),exit=round(sell,6),qty=round(p["qty"],9),
             gross_usdt=round(gross,6),costs_usdt=round(gross-net,6),
             net_usdt=round(net,6),reason=why,
             slippage_bps_per_side=slippage_bps))
        cooldown_until=ts+COOLDOWN_HOURS*3600
        trade=None

    # H1 requires 210 completed H1 bars. Start after that, avoiding indicators
    # that use pre-period information or source-month boundary fabrication.
    start=(H1_WARMUP+1)*(60//minutes)
    for i in range(start,len(bars)):
        b=bars[i]
        just_closed=False
        if trade is not None and exit_pending:
            finish(b["open"],b["time"],"time_or_h1_exit_next_open")
            exit_pending=False
            just_closed=True
        if trade is None and not just_closed and b["time"]>=cooldown_until:
            if model.signal(i-1):
                signals+=1
                h=model.last_closed_h1(i-1)
                atr=model.hf["atr"][h]
                if atr>0:
                    raw=b["open"]
                    entry=raw*(1+friction)
                    risk_dist=max(STOP_H1_ATR*atr,raw*.002)
                    stop=entry-risk_dist
                    target=entry+TARGET_H1_ATR*atr
                    stop_filled=stop*(1-friction)
                    risk_per_unit=(entry-stop_filled)+fee*(entry+stop_filled)
                    qty=min(equity*RISK_FRACTION/risk_per_unit,
                            equity*.98/(entry*(1+fee))) if risk_per_unit>0 else 0
                    if qty>0 and stop>0 and target>entry:
                        fills+=1
                        trade=dict(signal_ts=bars[i-1]["time"]+minutes*60,
                                   entry_ts=b["time"],raw=raw,entry=entry,
                                   qty=qty,stop=stop,target=target,
                                   start_time=b["time"])
        if trade is not None:
            p=trade
            if b["low"]<=p["stop"]:
                stop_raw=min(b["open"],p["stop"]) if i>start and b["time"]>p["entry_ts"] else p["stop"]
                why="ambiguous_stop_first" if b["high"]>=p["target"] else "stop"
                finish(stop_raw,b["time"]+minutes*60,why)
            elif b["high"]>=p["target"]:
                finish(p["target"],b["time"]+minutes*60,"target")
            elif (b["time"]+minutes*60-p["start_time"]>=MAX_HOLD_HOURS*3600
                  or model.h1_exiting(i)):
                exit_pending=True
        # Open position is marked conservatively but NOT counted as realized.
        mark=equity if trade is None else equity+(b["close"]-trade["entry"])*trade["qty"]
        peak=max(peak,mark)
        max_dd=max(max_dd,(peak-mark)/peak if peak>0 else 1)
    run=dict(ledger=rows,equity=equity,orders_filled=fills,signals_seen=signals,
             max_drawdown_pct=round(100*max_dd,5),
             open_end=trade is not None,
             marked_open_net_usdt=None if trade is None else round(
                (bars[-1]["close"]*(1-friction)-trade["entry"])*trade["qty"]
                -fee*trade["qty"]*(bars[-1]["close"]*(1-friction)+trade["entry"]),4))
    if abs(sum(x["net_usdt"] for x in rows)-(equity-START_USDT))>.05:
        raise AssertionError("ledger and equity disagree")
    return run
