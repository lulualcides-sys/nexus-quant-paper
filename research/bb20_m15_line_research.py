"""Backtest the actual requested BB20 entry: H1 TREND, M15 SMA20 TOUCH/REBOUND.

Frozen Yahoo M15 data. All entry/stop variants are predeclared and scored on
first / last 15 days separately; never auto-deploy after inspecting outcomes.
"""
from __future__ import annotations
import gzip
import json
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from statistics import mean
from unittest.mock import patch

from src import bb_rebound_mtf as bot

BARS = Path("research/results/bb20_usdcad_m15_1mo_2026-10-26_bars.json.gz")
OUT = Path("research/results/bb20_m15_true_touch_comparison_2026-10-26.json")
MD = Path("research/results/bb20_m15_true_touch_comparison_2026-10-26.md")
CONFIGS = (
    ("ema20_touch_h1stop", "ema20", "touch", "h1"),
    ("ema50_touch_h1stop", "ema50", "touch", "h1"),
    ("slope_touch_h1stop", "slope", "touch", "h1"),
    ("ema20_wick_h1stop", "ema20", "wick", "h1"),
    ("ema50_wick_h1stop", "ema50", "wick", "h1"),
    ("slope_wick_h1stop", "slope", "wick", "h1"),
    ("ema20_touch_m15stop", "ema20", "touch", "m15"),
    ("ema50_touch_m15stop", "ema50", "touch", "m15"),
    ("ema50_cross_m15stop", "ema50", "cross", "m15"),
)


def trend(h1, ind, j, mode):
    if j < 55:
        return 0
    p=ind[j]
    b=h1[j]
    if mode=="ema20":
        if p["e20"] > p["e50"] and b["close"] > p["e20"]:
            return 1
        if p["e20"] < p["e50"] and b["close"] < p["e20"]:
            return -1
    if mode=="ema50":
        if p["e50"] > p["e200"] and b["close"] > p["e50"] and p["e50"] > ind[j-4]["e50"]:
            return 1
        if p["e50"] < p["e200"] and b["close"] < p["e50"] and p["e50"] < ind[j-4]["e50"]:
            return -1
    if mode=="slope":
        middle=mean(x["close"] for x in h1[j-19:j+1])
        old_middle=mean(x["close"] for x in h1[j-23:j-3])
        if middle>old_middle and b["close"]>middle:
            return 1
        if middle<old_middle and b["close"]<middle:
            return -1
    return 0


def reaction(bars, i, feats, side, mode):
    b=bars[i-1]; prev=bars[i-2]; ind=feats[i-1]
    avg=mean(x["close"] for x in bars[i-20:i])
    prev_avg=mean(x["close"] for x in bars[i-21:i-1])
    a=ind["atr"]
    spread=b["high"]-b["low"]
    body=abs(b["close"]-b["open"])
    if a<=0 or spread<=0:
        return False
    if side>0:
        touched = b["low"] <= avg + 0.10*a
        rebounded = b["close"]>avg and b["close"]>b["open"] and b["close"]>prev["close"]
        not_chasing = 0 < b["close"]-avg <= 0.75*a
        wick = min(b["close"],b["open"])-b["low"] >= 0.35*body and (b["close"]-b["low"])/spread >= 0.65
        cross = prev["close"] < prev_avg and b["close"] > avg
    else:
        touched = b["high"] >= avg - 0.10*a
        rebounded = b["close"]<avg and b["close"]<b["open"] and b["close"]<prev["close"]
        not_chasing = 0 < avg-b["close"] <= 0.75*a
        wick = b["high"]-max(b["close"],b["open"]) >= 0.35*body and (b["high"]-b["close"])/spread >= 0.65
        cross = prev["close"] > prev_avg and b["close"] < avg
    return touched and rebounded and not_chasing and (
        (mode=="touch") or (mode=="wick" and wick) or (mode=="cross" and cross)
    )


def run_step(book,bars,i,h1,inds,*,feats,trend_mode,trigger,stop_mode):
    current, prior = bars[i], bars[i-1]
    if book["position"] is not None:
        if not bot.exit_position(book,current):
            bot.advance_trailing_stop(book,current)
        return
    if book["equity"] <= 0 or i<25:
        return
    eligible=[j for j,b in enumerate(h1) if b["time"]+3600 <= prior["time"]]
    if not eligible:
        return
    j=eligible[-1]
    # Avoid stale trend data when FX market was closed over the weekend.
    if prior["time"] - (h1[j]["time"]+3600) > 3600:
        return
    side=trend(h1,inds,j,trend_mode)
    if not side or not reaction(bars,i,feats,side,trigger):
        return
    # No more than one entry per completed H1, avoids repeated scalp churn.
    if book["last_entry_h1"] == h1[j]["time"]:
        return
    atr_h1=inds[j]["atr"]
    atr15=feats[i-1]["atr"]
    opened=current["open"]
    if stop_mode=="h1":
        dist=max(1.2*atr_h1,6*bot.PIP)
    else:
        wick_distance = side*(opened-prior["low"]) if side>0 else prior["high"]-opened
        dist=max(0.9*atr15,wick_distance + 0.20*atr15,6*bot.PIP)
    if dist<=0 or opened<=0:
        return
    qty=min(book["equity"]*bot.MAX_NOTIONAL,(book["equity"]*bot.RISK_FRACTION*opened)/dist)
    if qty<=0:
        return
    book["position"]={
        "side":side,"entry":opened,"entry_ts":current["time"],
        "entry_rule":f"m15_sma20_touch_h1_{trend_mode}_{trigger}_{stop_mode}",
        "qty_usd":qty, "stop":opened-side*dist,
        "initial_r":dist, "best_close":opened,
        "stop_policy":bot.TRAIL_POLICY,"stop_updates":0,
        "green_protected":False,"target":None,
        "confirm_h1":h1[j]["time"],
    }
    book["last_entry_h1"]=h1[j]["time"]
    if not bot.exit_position(book,current):
        bot.advance_trailing_stop(book,current)


def score(bars,start,end,profile):
    warm=[b for b in bars if b["time"] < start]
    subset=[b for b in bars if b["time"] < end]
    if len(bot.to_h1(warm)) < 53:
        raise ValueError("Warmup H1 insuficiente")
    state=bot.update(None,warm)
    inds15=bot.make_indicators(subset)
    _,trend_mode,trigger,stop_mode=profile
    worker=partial(run_step,feats=inds15,trend_mode=trend_mode,trigger=trigger,stop_mode=stop_mode)
    with patch.object(bot,"step",worker):
        state=bot.update(state,subset)
    closed=state["closed"]
    wins=[t for t in closed if t["net_usd"]>0]
    losses=[t for t in closed if t["net_usd"]<0]
    net=state["equity"]-bot.CAPITAL
    pos=state["position"]
    float_pnl=None
    if pos:
        end_price=subset[-1]["close"]
        float_pnl=((end_price-pos["entry"])*pos["side"]-bot.ROUNDTRIP_PIPS*bot.PIP)*pos["qty_usd"]/end_price
    return {
        "n":len(closed),"wins":len(wins),"losses":len(losses),
        "hit_pct":round(100*len(wins)/len(closed),2) if closed else None,
        "net":round(net,5),"mtm":round(net+(float_pnl or 0),5),
        "trades":closed,"open":bool(pos)
    }


def main():
    with gzip.open(BARS,"rt",encoding="utf-8") as stream:
        bars=json.load(stream)["candles"]
    prior=json.loads(Path("research/results/bb20_usdcad_m15_1mo_2026-10-26.json").read_text(encoding="utf-8"))
    end=int(datetime.strptime(prior["timestamp_utc"],"%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc).timestamp())
    start=end-30*86400
    split=start+15*86400
    results={}
    for profile in CONFIGS:
        name=profile[0]
        results[name]={
            "train":score(bars,start,split,profile),
            "validation":score(bars,split,end+60,profile),
            "full":score(bars,start,end+60,profile),
        }
    OUT.write_text(json.dumps({
        "frozen_data_sha256":prior["source_sha256"],
        "strategy":"H1 confirms trend; M15 touches M15 SMA20 and closes in direction; no breakout required; trailing unchanged",
        "separation":"First 15 days training, last 15 retrospective validation",
        "results":results,
        "warning":"Pre-inspected historical period. Even positive validation is NOT forward proof; spreads hypothetical."
    },indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    lines=["# BB20 M15 central-SMA pullback — realigned strategy comparison","",
        "Historical research only, **no live policy changed**. Frozen observations, same risk/runner.",
        "First half train / second half validation are not fully independent from prior review.","",
        "| Entry rule | Full trades | Full win% | Full net USD | Train net USD | Validation trades | Validation win% | Validation net USD |",
        "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name,v in results.items():
        a,b,c=v["train"],v["validation"],v["full"]
        lines.append(f'| {name} | {c["n"]} | {c["hit_pct"]} | {c["net"]:+.2f} | {a["net"]:+.2f} | {b["n"]} | {b["hit_pct"]} | {b["net"]:+.2f} |')
    lines += ["","A positive result alone is not proof; sample may be too small and execution indicative.",""]
    MD.write_text("\n".join(lines),encoding="utf-8")
    print("M15_TOUCH_COMPARISON="+json.dumps({n:{period:{k:d[k] for k in ("n","wins","losses","hit_pct","net","mtm")} for period,d in rr.items()} for n,rr in results.items()}))


if __name__=="__main__":
    main()
