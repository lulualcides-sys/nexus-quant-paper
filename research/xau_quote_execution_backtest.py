"""Quote-by-quote execution diagnostic for NQ XAUUSD (research, not live).

Uses authentic historical bid/ask quotes and signal candles ONLY after they close.
Buy limits fill when ASK <= entry; sell limits fill when BID >= entry.
Long TP/SL use BID; short TP/SL use ASK. Targets fill at the stated level,
stops can slip through gaps, and the last tick forces liquidation. There is
no intrabar OHLC fill assumption. Broker commissions/swap, latency, rejected
orders and available liquidity are not known; this is NOT a broker backtest.
A limit order is never filled worse than its limit. Slippage applies only to
stop/market exits; target limits fill at target if touched.
PnL units are hypothetical USD per ONE ounce, not per broker lot/account.
"""
from __future__ import annotations
import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from research.xau_quote_tracker_reference import QuotePolicy, scan_closed
from research.xau_dukascopy_replay import aggregate_real_quotes


@dataclass(frozen=True)
class ExecutionAssumptions:
    timeframe_seconds: int = 60
    ttl_bars: int = 3
    max_hold_bars: int = 20
    commission_roundtrip_usd_per_oz: float = 0.0
    slippage_usd_per_side: float = 0.0

    def check(self):
        if (self.timeframe_seconds not in (60, 300) or self.ttl_bars < 1 or
            self.max_hold_bars < 1 or self.commission_roundtrip_usd_per_oz < 0 or
            self.slippage_usd_per_side < 0):
            raise ValueError("Invalid execution assumptions")


def _ticks(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not {"timestamp", "askPrice", "bidPrice"}.issubset(reader.fieldnames or []):
            raise ValueError("Missing Dukascopy bid/ask columns")
        last = -1
        for row in reader:
            try:
                ts = int(row["timestamp"])
                bid, ask = float(row["bidPrice"]), float(row["askPrice"])
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise ValueError("Malformed quote stream") from exc
            if ts < last or ts < 946684800000 or not (0 < bid < ask):
                raise ValueError("Nonchronological or crossed price stream")
            last = ts
            yield ts, bid, ask


def simulate_quote_execution(ticks, planned_signals: list[dict],
                             cfg: ExecutionAssumptions = ExecutionAssumptions()):
    """Deterministic execution on time-ordered quotes; testable without network."""
    cfg.check()
    for i, s in enumerate(planned_signals):
        if s["side"] not in (1, -1) or s["entry"] <= 0 or s["stop"] <= 0 or s["target"] <= 0:
            raise ValueError("Invalid planned signal")
        if not (s["stop"] < s["entry"] < s["target"] if s["side"]==1 else
                s["target"] < s["entry"] < s["stop"]):
            raise ValueError("Wrong-way Fibonacci geometry")
        if i and s["eligible_ms"] <= planned_signals[i-1]["eligible_ms"]:
            raise ValueError("Duplicate/out-of-order signal")
    ns=0
    pending=None
    position=None
    closed=[]
    skipped=0
    expired=0
    filled=0
    lastquote=None
    previous_stamp=-1
    first_stamp=None

    def close(ts, quote_exit, reason):
        nonlocal position
        p=position
        if p is None:
            raise AssertionError("No position to close")
        # Slip ALWAYS adverse, fees per one ounce are hypothetical assumptions.
        side=p["side"]
        raw_exit=quote_exit
        # TAKE PROFIT is treated as a LIMIT exit: never an adverse fill past
        # its own limit. Only stops and market/time exits can slip.
        exit_px=(raw_exit if reason=="TARGET" else
                 raw_exit-side*cfg.slippage_usd_per_side)
        pnl=side*(exit_px-p["fill"])-cfg.commission_roundtrip_usd_per_oz
        closed.append({
            "side":"BUY" if side==1 else "SELL",
            "signal_candle_utc": datetime.fromtimestamp(p["signal_ms"]/1000,timezone.utc).isoformat(),
            "entry_time_utc":datetime.fromtimestamp(p["opened_ms"]/1000,timezone.utc).isoformat(),
            "exit_time_utc":datetime.fromtimestamp(ts/1000,timezone.utc).isoformat(),
            "limit_entry":round(p["entry"],6),
            "executed_entry_assumed":round(p["fill"],6),
            "exit_price_assumed":round(exit_px,6),
            "target":round(p["target"],6),"stop":round(p["stop"],6),
            "reason":reason,"net_usd_per_oz":round(pnl,6),
            "fees_usd_per_oz":cfg.commission_roundtrip_usd_per_oz,
            "assumed_slippage_each_side":cfg.slippage_usd_per_side
        })
        position=None

    for ts,bid,ask in ticks:
        if ts < previous_stamp:
            raise ValueError("Reordered quote stream")
        previous_stamp=ts
        first_stamp=ts if first_stamp is None else first_stamp
        lastquote=(ts,bid,ask)
        # Stop/target time order follows the real bid/ask quote sequence.
        # On a long position, the broker sells at BID. Short closes at ASK.
        if position is not None:
            p=position
            if p["side"]==1:
                if bid<=p["stop"]:
                    close(ts,min(bid,p["stop"]),"STOP")
                elif bid>=p["target"]:
                    close(ts,p["target"],"TARGET")
            else:
                if ask>=p["stop"]:
                    close(ts,max(ask,p["stop"]),"STOP")
                elif ask<=p["target"]:
                    close(ts,p["target"],"TARGET")
            if position is not None and ts >= p["opened_ms"]+cfg.max_hold_bars*cfg.timeframe_seconds*1000:
                close(ts,bid if p["side"]==1 else ask,"TIME")

        if pending is not None and ts>=pending["expires_ms"]:
            expired+=1
            pending=None

        # Newly-closed signal is eligible only at/after its bar's CLOSE time.
        while ns<len(planned_signals) and planned_signals[ns]["eligible_ms"]<=ts:
            s=planned_signals[ns]
            ns+=1
            if s["eligible_ms"]+cfg.ttl_bars*cfg.timeframe_seconds*1000<=ts:
                expired+=1
                continue
            if pending is not None or position is not None:
                skipped+=1
                continue
            pending={**s,"expires_ms":s["eligible_ms"]+cfg.ttl_bars*cfg.timeframe_seconds*1000}

        # Limit entry: execute only when ASK/BID touches the limit and
        # pessimistically fill at limit rather than getting price improvement.
        if pending is not None and position is None:
            side=pending["side"]
            touch=(ask<=pending["entry"]) if side==1 else (bid>=pending["entry"])
            if touch:
                s=pending
                pending=None
                filled+=1
                position={**s,"opened_ms":ts,
                          "fill":s["entry"]  # LIMIT orders must not fill at a worse price}
                # Account for gap-through both entry and stop on the SAME tick.
                if side==1 and bid<=s["stop"]:
                    close(ts,min(bid,s["stop"]),"STOP_SAME_TICK")
                elif side==-1 and ask>=s["stop"]:
                    close(ts,max(ask,s["stop"]),"STOP_SAME_TICK")

    # Never fabricate a valid fill where the quote tape ended.
    if lastquote is not None:
        ts,bid,ask=lastquote
        if pending is not None:
            expired+=1
        if position is not None:
            close(ts,bid if position["side"]==1 else ask,"SESSION_END")
    skipped+=len(planned_signals)-ns
    gains=[row["net_usd_per_oz"] for row in closed if row["net_usd_per_oz"]>0]
    losses=[row["net_usd_per_oz"] for row in closed if row["net_usd_per_oz"]<0]
    gross_gains=sum(gains)
    gross_losses=-sum(losses)
    pnl=sum(t["net_usd_per_oz"] for t in closed)
    cumulative=peak=worst_dd=0.
    for trade in closed:
        cumulative+=trade["net_usd_per_oz"]
        peak=max(peak,cumulative)
        worst_dd=max(worst_dd,peak-cumulative)
    return {
        "planned_signals":len(planned_signals),
        "filled":filled,"closed":len(closed),
        "unfilled_expired":expired,"skipped_busy_or_unseen":skipped,
        "wins":len(gains),"losses":len(losses),
        "net_usd_per_oz":round(pnl,6),
        "expectancy_usd_per_oz":round(pnl/len(closed),6) if closed else None,
        "profit_factor":round(gross_gains/gross_losses,6) if gross_losses>0 else None,
        "max_closed_drawdown_usd_per_oz":round(worst_dd,6),
        "gross_profit_usd_per_oz":round(gross_gains,6),
        "gross_loss_usd_per_oz":round(gross_losses,6),
        "first_quote_ms":first_stamp,
        "last_quote_ms":previous_stamp if first_stamp is not None else None,
        "ledger":closed,
    }


def replay_with_costs(source: str|Path, timeframe_seconds: int=60,
                      commission_roundtrip_usd_per_oz: float=0.,
                      slippage_usd_per_side: float=0.,
                      point: float=0.001) -> dict:
    """Historical signal detector + chronological quote execution, no live calls."""
    cfg=ExecutionAssumptions(timeframe_seconds=timeframe_seconds,
        commission_roundtrip_usd_per_oz=commission_roundtrip_usd_per_oz,
        slippage_usd_per_side=slippage_usd_per_side)
    cfg.check()
    bars, provenance=aggregate_real_quotes(source,timeframe_seconds,point)
    policy=QuotePolicy(timeframe_seconds=timeframe_seconds,point=point,tick_size=point)
    signals=scan_closed(bars,len(bars)-2,policy)
    planned=[]
    for signal in signals:
        levels=signal["levels"]
        side=1 if signal["side"]=="BUY" else -1
        stamp=int(datetime.fromisoformat(signal["time_utc"]).timestamp()*1000)
        planned.append({
            "signal_ms":stamp,
            "eligible_ms":stamp+timeframe_seconds*1000,
            "side":side,
            "entry":levels["50"],
            "target":levels["200"],
            "stop":levels["-100"],
        })
    outcomes=simulate_quote_execution(_ticks(Path(source)),planned,cfg)
    return {
        "name":"XAUUSD Dukascopy bid/ask tick execution experiment",
        "source":provenance,"assumptions":cfg.__dict__,
        "periodic_candle_signal_count":len(signals),
        "execution":outcomes,
        "pnl_unit":"USD per one troy ounce of hypothetical notional",
        "spread_accounted_through_actual_bid_ask":True,
        "broker_lot_or_commission_verified":False,
        "swap_latency_market_impact_modelled":False,
        "independently_validated_with_original_greenhouse":False,
        "not_investment_advice":True,
        "not_live_or_broker_backtest":True
    }


def main():
    ap=argparse.ArgumentParser(description="Auditable historical quote execution for XAU research")
    ap.add_argument("--ticks",required=True)
    ap.add_argument("--output",required=True)
    ap.add_argument("--timeframe",choices=("M1","M5"),default="M1")
    ap.add_argument("--commission",type=float,default=0.)
    ap.add_argument("--slippage",type=float,default=0.)
    args=ap.parse_args()
    report=replay_with_costs(args.ticks,60 if args.timeframe=="M1" else 300,
                              args.commission,args.slippage)
    out=Path(args.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"timeframe":args.timeframe,
       "source_rows":report["source"]["source_rows"],
       "planned":report["execution"]["planned_signals"],
       "filled":report["execution"]["filled"],
       "expired":report["execution"]["unfilled_expired"],
       "closed":report["execution"]["closed"],
       "net_usd_per_oz":report["execution"]["net_usd_per_oz"],
       "profit_factor":report["execution"]["profit_factor"],
       "win_loss":(report["execution"]["wins"],report["execution"]["losses"]),
       "commission":args.commission,"slippage":args.slippage},indent=2))


if __name__=="__main__":
    main()
