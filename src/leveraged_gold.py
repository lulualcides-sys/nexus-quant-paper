"""Five leveraged-research H4 gold paper books.

NO broker access or real positions. Two times the standard stop-risk budget
(1.5% vs 0.75%) with actual 2x notional exposure, capped at 3x. Stops tighten
to meet the budget before slippage, financing or gaps.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from src.strategies import make_indicators
from src.gold_forward import day_of
from research.screen_v2 import aggregate_hourly_to_h4, sign
from research.backtest_year import COST_BPS
from src.green_stop import MODES, check_mode, update_after_close

FILE=Path("state/leveraged_gold_v1.json")
CAPITAL=5000.0
CONFIG={
 "lev_channel20":("channel20","Channel 20 L"),
 "lev_momentum100":("momentum100","Momentum 100 L"),
 "lev_channel55":("channel55","Channel 55 L"),
 "lev_momentum40":("momentum40","Momentum 40 L"),
 "lev_trend_long":("trend_long_only","Trend Long L"),
}
RISK_FRACTION=0.015
# Actual starting exposure for each leveraged paper entry: 2x equity.
# Protective stops shrink when required, so sizing targets 1.5% planned risk.
TARGET_NOTIONAL_LEVERAGE=2.0
MAX_NOTIONAL_LEVERAGE=3.0
STOP_ATR=2.0
TARGET_R_MULTIPLE=1.75
MAX_HOLD_BARS=90
DAILY_ENTRY_LOSS_LIMIT=0.03
ACCOUNT_ENTRY_DRAWDOWN_LIMIT=0.15
# Research assumptions, NOT advertised FBS borrowing or spread costs.
COST_BPS_ROUNDTRIP=2*COST_BPS["XAUUSD"]  # conservative transaction costs
ANNUAL_BORROW_APR=0.08
# Enabled for FUTURE VIRTUAL entries after A/B research; previous positions keep their recorded entry mode.
LIVE_POLICY="green_runner"

def fresh(h4):
    if len(h4)<245:
        raise ValueError("Incomplete H4 historical warmup")
    return {"schema":1,"paper_only":True,"type":"leveraged-research",
      "h4_watermark":h4[-1]["time"],
      "books":{k:{"equity":CAPITAL,"peak_equity":CAPITAL,
                  "today":None,"day_start_equity":CAPITAL,
                  "frozen":False,"position":None,"closed":[]} for k in CONFIG}}

def mark_day(book,ts):
    d=day_of(ts)
    if book["today"] != d:
        book["today"]=d
        book["day_start_equity"]=book["equity"]

def blocked(book):
    if book["frozen"] or book["equity"] <= 0:
        return True
    day_start=book["day_start_equity"]
    if day_start>0 and book["equity"] <= day_start*(1-DAILY_ENTRY_LOSS_LIMIT):
        return True
    return False

def one_bar(book,name,h4,ind,i,*,mode="fixed"):
    check_mode(mode)
    row=h4[i];ts=row["time"];opening=row["open"]
    mark_day(book,ts)
    previous=book["position"]
    if previous is not None:
        p=previous
        p["held_bars"]=p.get("held_bars",0)+1
        direction=p["side"]
        stopped=(row["low"]<=p["stop"] if direction>0 else row["high"]>=p["stop"])
        targeted=(p.get("target") is not None and
             (row["high"]>=p["target"] if direction>0 else row["low"]<=p["target"]))
        price=None;reason=""
        if stopped:
            price=min(opening,p["stop"]) if direction>0 else max(opening,p["stop"])
            reason="STOP"
        elif targeted:
            price=p["target"];reason="TARGET"
        elif p["held_bars"]>=MAX_HOLD_BARS:
            price=row["close"];reason="TIME"
        if price is not None:
            gross=(price-p["entry"])*p["side"]*p["qty"]
            transaction=COST_BPS_ROUNDTRIP/10000*p["qty"]*((p["entry"]+price)/2)
            hours=max(0,(ts-p["start"])/3600)
            financing=p["borrowed"]*ANNUAL_BORROW_APR*hours/8760
            net=gross-transaction-financing
            book["equity"]+=net
            book["peak_equity"]=max(book["peak_equity"],book["equity"])
            if book["peak_equity"]>0 and book["equity"] <= book["peak_equity"]*(1-ACCOUNT_ENTRY_DRAWDOWN_LIMIT):
                book["frozen"]=True
            book["closed"].append({
               "entry_ts":p["start"],"exit_ts":ts,"side":p["side"],
               "entry":round(p["entry"],6),"exit":round(price,6),
               "net_usd":round(net,5),"gross_usd":round(gross,5),
               "transaction_cost":round(transaction,5),
               "funding_cost":round(financing,5),
               "notional_leverage":round(p["notional_leverage"],4),
               "exit_type":reason,"stop_policy":p.get("mode","fixed")
            })
            book["position"]=None
        else:
            # Evaluate this candle against OLD stop first, then tighten only
            # for the next H4 candle. Avoids same-bar lookahead profits.
            update_after_close(p,row,ts,COST_BPS_ROUNDTRIP,ANNUAL_BORROW_APR)
    # No reopen on the same four-hour candle as an exit.
    if previous is not None or blocked(book):
        return
    rule=CONFIG[name][0]
    current=sign(rule,h4,ind,i-1)
    prior=sign(rule,h4,ind,i-2)
    if not current or current==prior:
        return
    atr=ind[i-1]["atr"]
    if not atr or atr<=0 or opening<=0:
        return
    equity=book["equity"]
    # Real experimental paper leverage: open a 2x equity notional position.
    # Smaller stop distance controls *planned* loss to 1.5% of account.
    # Gaps, funding, slippage and fees can exceed the stop-risk budget.
    qty=min(TARGET_NOTIONAL_LEVERAGE,MAX_NOTIONAL_LEVERAGE)*equity/opening
    if qty<=0:
        return
    stop_distance=min(STOP_ATR*atr, RISK_FRACTION*equity/qty)
    if stop_distance<=0:
        return
    notional=qty*opening
    book["position"]={
       "side":current,"entry":opening,"start":ts,"qty":qty,
       "stop":opening-current*stop_distance,
       "entry_risk":stop_distance,
       "mode":mode,"green_protected":False,"peak_favorable":0.0,
       "target":(opening+current*TARGET_R_MULTIPLE*stop_distance
                 if MODES[mode]["target"] else None),
       "held_bars":0,"borrowed":max(0.0,notional-equity),
       "notional_leverage":notional/equity
    }

def update(state,hourly):
    h4=aggregate_hourly_to_h4(hourly)
    if len(h4)<245:raise ValueError("Insufficient complete H4 gold candles")
    if state is None:return fresh(h4)
    if not state.get("paper_only") or state.get("schema")!=1 or state.get("type")!="leveraged-research":
        raise ValueError("Unexpected state schema; refuse live/legacy state")
    old=state["h4_watermark"]
    times={b["time"] for b in h4}
    if old not in times:
        raise ValueError("Gold data gap prevents auditable incremental tracking")
    inds=make_indicators(h4)
    for i in range(241,len(h4)):
        if h4[i]["time"]<=old:continue
        for key in CONFIG:one_bar(state["books"][key],key,h4,inds,i,mode=LIVE_POLICY)
        state["h4_watermark"]=h4[i]["time"]
    return state

def stats(book):
    equity=CAPITAL
    peak=CAPITAL
    dd=0.0
    wins=0;losses=0
    for trade in book["closed"]:
        pnl=trade["net_usd"]
        equity+=pnl
        wins+=int(pnl>0);losses+=int(pnl<0)
        peak=max(peak,equity)
        dd=max(dd,100*(peak-equity)/peak)
    p=book["position"]
    return {"pnl_usd":book["equity"]-CAPITAL,
       "return_pct":100*(book["equity"]/CAPITAL-1),
       "drawdown_closed_pct":dd,"closed":len(book["closed"]),
       "wins":wins,"losses":losses,
       "effective_leverage":p["notional_leverage"] if p else 0.0,
       "frozen":book["frozen"]}

def process(hourly,path=FILE):
    old=json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    new=update(old,hourly)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(new,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return new
