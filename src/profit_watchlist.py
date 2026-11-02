"""Read-only post-launch profitability research for two gold H4 controls + WTI H1.

Only CLOSED virtual trades with entry timestamp >= fixed observation cutoff.
No resetting or changing gold state. WTI shadow has its own book. Missing books
are unknown, never reported as 0 gain. Double-transaction-cost sensitivity is
a FIXED-FILL counterfactual, not a replayed double-cost backtest (changing fills,
position size, slippage and margin could alter results). No real money labels.
"""
from __future__ import annotations

from datetime import datetime,timezone
from math import isfinite

from src.gold_forward import CAPITAL as GOLD_CAPITAL
from src.experimental_h1 import CAPITAL as H1_CAPITAL

# Forward-evidence cutoff deliberately later than the research selection.
CUTOFF_TS=int(datetime(2026,11,2,6,30,tzinfo=timezone.utc).timestamp())
WATCH={"gold_h4:channel20":("Channel 20 H4","gold_h4",GOLD_CAPITAL),
       "gold_h4:channel55":("Channel 55 H4","gold_h4",GOLD_CAPITAL),
       "wti_filtered:channel10":("WTI Channel10 H1 filtrado","wti_filtered",H1_CAPITAL)}
MIN_CLOSED={"gold_h4":20,"wti_filtered":60}

def _num(v,name):
    if not isinstance(v,(int,float)) or not isfinite(v):
        raise ValueError(name+" absent/non-finite")
    return float(v)

def _watch(book,name,group,capital,*,cutoff):
    if not isinstance(book,dict):
        return {"status":"unavailable","name":name,"group":group,
                "reason":"book_missing","trades":None,"net_usd":None,
                "double_transaction_fee_fixed_fills_usd":None}
    closed=book.get("closed")
    if not isinstance(closed,list):
        return {"status":"unavailable","name":name,"group":group,
                "reason":"closed_journal_invalid","trades":None,"net_usd":None,
                "double_transaction_fee_fixed_fills_usd":None}
    selected=[]
    for trade in closed:
        if not isinstance(trade,dict):
            raise ValueError("Corrupt trade record")
        stamp=trade.get("entry_ts")
        exit_ts=trade.get("exit_ts")
        if not all(isinstance(x,(int,float)) and isfinite(x) for x in (stamp,exit_ts)):
            raise ValueError("Trade timestamps incomplete; cannot claim new evidence")
        if exit_ts<stamp:
            raise ValueError("Trade exit before entry")
        if stamp>=cutoff and exit_ts>=cutoff:
            selected.append(trade)
    total=0.
    fees=0.
    gross=0.
    wins=0
    peak=0.
    cumulative=0.
    dd=0.
    for trade in sorted(selected,key=lambda x:(x["exit_ts"],x["entry_ts"])):
        net=_num(trade.get("net_usd"),"closed trade net")
        fee=_num(trade.get("cost_usd",trade.get("transaction_cost")),"closed transaction cost")
        if fee<0:
            raise ValueError("Negative transaction cost")
        total+=net
        fees+=fee
        gross+=net+fee
        cumulative+=net
        peak=max(peak,cumulative)
        dd=max(dd,(peak-cumulative)/capital*100.)
        wins+=int(net>0)
    stressed=total-fees
    count=len(selected)
    return {
       "status":"insufficient_sample" if count<MIN_CLOSED[group] else
                "research_only_review",
       "name":name,"group":group,"trades":count,
       "wins":wins,"losses":sum(t["net_usd"]<0 for t in selected),
       "net_usd":round(total,5),
       "gross_before_transaction_cost_usd":round(gross,5),
       "transaction_cost_usd":round(fees,5),
       "double_transaction_fee_fixed_fills_usd":round(stressed,5),
       "average_net_per_closed_trade_usd":round(total/count,5) if count else None,
       "win_rate_pct":round(wins/count*100,2) if count else None,
       "closed_only_drawdown_over_initial_capital_pct":round(dd,4),
       "min_closed_for_review":MIN_CLOSED[group],
       "research_positive_after_fixed_fill_stress":count>=MIN_CLOSED[group] and stressed>0 and total>0,
       "validated_real_money":False,
    }

def build(*,now,conventional,wti):
    if not isinstance(now,(int,float)) or not isfinite(now) or now<CUTOFF_TS:
        raise ValueError("Invalid as-of timestamp")
    books=conventional.get("books",{}) if isinstance(conventional,dict) and conventional.get("paper_only") else {}
    wti_book=wti.get("book") if isinstance(wti,dict) and wti.get("paper_only") and wti.get("experimental_only") else None
    rows={}
    for key,(name,group,capital) in WATCH.items():
        book=wti_book if group=="wti_filtered" else books.get(key.split(":")[1])
        row=_watch(book,name,group,capital,cutoff=CUTOFF_TS)
        if group=="wti_filtered" and wti is not None:
            row["first_shadow_observation_ts"]=wti.get("first_observation_ts")
            row["h1_watermark"]=wti.get("h1_watermark")
        rows[key]=row
    return {
        "schema":1,"as_of_utc":datetime.fromtimestamp(now,timezone.utc).isoformat(),
        "observation_starts_utc":datetime.fromtimestamp(CUTOFF_TS,timezone.utc).isoformat(),
        "paper_only":True,"additional_shadow_not_part_of_27":True,
        "original_27_unchanged":True,"trading_orders_executed":False,
        "read_only":True,"watchlist":rows,
        "future_money_profit_guaranteed":False,
        "stress_warning":"fee doubled at SAME logged fills; unlike replay, no size, slippage, stop or margin simulation",
        "censor_warning":"Only positions entered AND closed since cutoff; old positions excluded",
    }

def telegram_line(result):
    if result.get("schema")!=1 or not result.get("paper_only"):
        raise ValueError("Not a virtual watchlist")
    status=[]
    for key in WATCH:
        x=result["watchlist"][key]
        if x["status"]=="unavailable":
            status.append(key.split(":")[-1]+" sem dados")
        else:
            status.append(key.split(":")[-1]+": "+str(x["trades"])+" fech., US$ "+f"{x['net_usd']:+.2f}")
    return "🧪 Evidência nova (2 H4 + WTI filtro): "+" | ".join(status)
