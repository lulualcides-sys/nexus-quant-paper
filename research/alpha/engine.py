"""OHLC-only long-spot laboratory, next-open entries and conservative intrabar exits."""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
from math import isfinite
from research.alpha.indicators import History, build

# USDT book, NOT R$30,000 converted. No exchange access or orders.
START_USDT=5000.0
RISK_FRACTION=0.0075
TAKER_FEE_BPS=10.0              # per side; conservative illustrative retail assumption
HALF_SPREAD_BPS=1.0             # per side; not a measured live order book
SLIPPAGE_BPS=(0.,5.,10.)        # per side; no WIN tick conversion
WARMUP=220
MAX_HOLD={1:120,5:24}
MIN_TRADES=100

def check_candles(bars,minutes):
    if len(bars)<WARMUP+3:
        raise ValueError("insufficient real candles")
    interval=minutes*60
    previous=None
    for bar in bars:
        if set(("time","open","high","low","close","volume"))-set(bar):
            raise ValueError("missing OHLCV")
        o,h,l,c,v=(bar[k] for k in ("open","high","low","close","volume"))
        if not all(isfinite(x) for x in (o,h,l,c,v)) or min(o,l,c,h)<=0 or v<0:
            raise ValueError("nonfinite/negative/zero OHLCV")
        if h<max(o,c) or l>min(o,c) or l>h:
            raise ValueError("OHLC inconsistent")
        ts=bar["time"]
        if not isinstance(ts,int) or ts%interval:
            raise ValueError("misaligned timestamp")
        if previous is not None and ts-previous!=interval:
            raise ValueError("missing or duplicate bars: no interpolation")
        previous=ts
    return True

def iso(ts):
    return datetime.fromtimestamp(ts,timezone.utc).isoformat()

def backtest(bars,signals,minutes,start,end,slip_bps=5.,capital=START_USDT,features=None):
    """start/end are indices; each segment is a fresh independent virtual book.
    Uses only closed bar i-1 to decide an entry at i.open. Exit checks on bar i.
    No overlapping positions. Stops take precedence over targets inside one bar.
    """
    check_candles(bars,minutes)
    if not (WARMUP<start<end<=len(bars)):
        raise ValueError("bad chronological split or warmup")
    feat=features if features is not None else build(bars)
    equity=capital
    peak=capital
    max_drawdown=0.
    pending=None
    ledger=[]
    opens=0
    signals_count=0
    for i in range(start,end):
        bar=bars[i]
        if pending is None and i>start:
            # Only bars completed strictly inside this chronological segment.
            history=History(bars,i)
            decision=bool(signals.signal(history,feat,i-1))
            if decision:
                signals_count += 1
                prev=bars[i-1]
                dist=max(1.5*feat["atr"][i-1],prev["close"]*0.001)
                raw=bar["open"]
                entry=raw*(1+(HALF_SPREAD_BPS+slip_bps)/10000)
                stop=entry-dist
                target=entry+1.8*dist
                if stop>0 and dist>0 and equity>0:
                    # Size on STOP LOSS INCLUDING both modeled fills and both fees.
                    # 0.75% is the complete theoretical stop loss if no adverse gap.
                    exit_at_stop=stop*(1-(HALF_SPREAD_BPS+slip_bps)/10000)
                    fee_rate=TAKER_FEE_BPS/10000
                    risk_unit=(entry-exit_at_stop)+fee_rate*(entry+exit_at_stop)
                    qty=min(equity*RISK_FRACTION/risk_unit,
                            equity*0.98/(entry*(1+fee_rate)))
                    if qty>0:
                        opens+=1
                        pending=dict(entry_ts=bar["time"],signal_ts=prev["time"]+minutes*60,
                                     entry_raw=raw,entry=entry,stop=stop,target=target,
                                     qty=qty,held=0,risk=qty*dist,initial_equity=equity)
        if pending is not None:
            p=pending
            p["held"]+=1
            reason=None
            # Stop gap adverse at bar.open, no optimistic limit fills.
            if bar["low"]<=p["stop"]:
                exit_raw=min(bar["open"],p["stop"]) if i>start and p["held"]>1 else p["stop"]
                reason="stop" if bar["high"]<p["target"] else "ambiguous_stop_first"
            elif bar["high"]>=p["target"]:
                exit_raw=p["target"]
                reason="target"
            elif p["held"]>=MAX_HOLD[minutes]:
                exit_raw=bar["close"]
                reason="time"
            elif i==end-1:
                exit_raw=bar["close"]
                reason="segment_boundary"
            if reason is not None:
                exit_fill=exit_raw*(1-(HALF_SPREAD_BPS+slip_bps)/10000)
                gross=(exit_raw-p["entry_raw"])*p["qty"]
                pnl=(exit_fill-p["entry"])*p["qty"]-TAKER_FEE_BPS/10000*p["qty"]*(exit_fill+p["entry"])
                cost=gross-pnl
                equity+=pnl
                ledger.append(dict(signal_ts_utc=iso(p["signal_ts"]),entry_ts_utc=iso(p["entry_ts"]),
                                   exit_ts_utc=iso(bar["time"]+minutes*60),side="LONG",
                                   entry_raw=round(p["entry_raw"],6),entry=round(p["entry"],6),
                                   exit_raw=round(exit_raw,6),exit=round(exit_fill,6),
                                   qty=round(p["qty"],9),gross_usdt=round(gross,6),
                                   costs_usdt=round(cost,6),net_usdt=round(pnl,6),
                                   reason=reason,slippage_bps_per_side=slip_bps))
                pending=None
        mark=equity if pending is None else equity+(bar["close"]-pending["entry"])*pending["qty"]
        peak=max(peak,mark)
        max_drawdown=max(max_drawdown,(peak-mark)/peak if peak>0 else 1.)
    if pending is not None:
        raise AssertionError("end-of-segment position not closed")
    return dict(ledger=ledger,equity=equity,max_drawdown_pct=round(max_drawdown*100,5),
                orders_filled=opens,signals_seen=signals_count,signal_to_fill_gap=signals_count-opens)

def stats(run):
    ledger=run["ledger"]
    if not ledger:
        return dict(trades=0,winrate_pct=None,net_usdt=None,profit_factor=None,
                    expectancy_usdt=None,total_costs_usdt=None,max_drawdown_pct=None,
                    status="INCONCLUSIVE")
    wins=sum(x["net_usdt"]>0 for x in ledger)
    gross_pos=sum(x["net_usdt"] for x in ledger if x["net_usdt"]>0)
    gross_neg=-sum(x["net_usdt"] for x in ledger if x["net_usdt"]<0)
    pf=(gross_pos/gross_neg) if gross_neg>0 else None
    net=sum(x["net_usdt"] for x in ledger)
    # A positive historical period alone is not sufficient for approval.
    return dict(trades=len(ledger),winrate_pct=round(100*wins/len(ledger),3),
                net_usdt=round(net,4),profit_factor=round(pf,4) if pf is not None else None,
                expectancy_usdt=round(net/len(ledger),4),
                total_costs_usdt=round(sum(x["costs_usdt"] for x in ledger),4),
                max_drawdown_pct=run["max_drawdown_pct"],
                status="INCONCLUSIVE" if len(ledger)<MIN_TRADES else
                    ("REJECTED" if net<=0 or pf is None or pf<=1.2 else "RESEARCH_CANDIDATE_NOT_APPROVED"))

def split_months(bars):
    by_month=defaultdict(list)
    for i,bar in enumerate(bars):
        by_month[iso(bar["time"])[:7]].append(i)
    return {k:(v[0],v[-1]+1) for k,v in sorted(by_month.items())}
