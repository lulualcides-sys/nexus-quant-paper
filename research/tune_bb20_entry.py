"""Predeclared alternative BB20 entry filters, historical comparison, no live changes.

Runs baseline using its actual update and counterfactuals using the SAME
exit/ATR/sizing and identical M15 bars. First 15 days development, later
15 days holdout (not a truly unseen sample because earlier results were seen).
Do not automatically select a 'winner' based on one month.
"""
from __future__ import annotations
import gzip
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import mean
from unittest.mock import patch
from functools import partial

from src import bb_rebound_mtf as bot
from src.strategies import make_indicators

BARS = Path("research/results/bb20_usdcad_m15_1mo_2026-10-26_bars.json.gz")
REPORT = Path("research/results/bb20_entry_comparison_2026-10-26.json")
SUMMARY = Path("research/results/bb20_entry_comparison_2026-10-26.md")
PROFILES = (
    "baseline", "touch", "touch_slope", "touch_wick",
    "touch_wick_slope", "touch_ema", "touch_ema_wick",
    "near_slope", "near_ema",
)


def decide(profile, bars, i, h1, inds, j, side, middle):
    prior, older = bars[i-1], bars[i-2]
    atr = inds[j]["atr"]
    if atr <= 0:
        return False
    span = prior["high"] - prior["low"]
    body = abs(prior["close"]-prior["open"])
    if span <= 0:
        return False
    if profile.startswith("near"):
        tolerance = 0.12 * atr
        closing_max = 0.55 * atr
    else:
        tolerance = bot.PIP * 0.8
        closing_max = 0.45 * atr
    if side > 0:
        touched = prior["low"] <= middle + tolerance
        reaction = (prior["open"] < prior["close"] and prior["close"] > middle
                    and prior["close"] > older["close"]
                    and prior["close"]-middle <= closing_max)
        wick = (min(prior["open"], prior["close"])-prior["low"] >= 0.25 * body
                and (prior["close"]-prior["low"])/span >= 0.60)
    else:
        touched = prior["high"] >= middle - tolerance
        reaction = (prior["open"] > prior["close"] and prior["close"] < middle
                    and prior["close"] < older["close"]
                    and middle-prior["close"] <= closing_max)
        wick = (prior["high"]-max(prior["open"], prior["close"]) >= 0.25 * body
                and (prior["high"]-prior["close"])/span >= 0.60)
    if not (touched and reaction):
        return False
    if "wick" in profile and not wick:
        return False
    if "slope" in profile:
        now = mean(b["close"] for b in h1[j-19:j+1])
        prev = mean(b["close"] for b in h1[j-22:j-2])
        if side*(now-prev) <= 0:
            return False
    if "ema" in profile:
        if side*(inds[j]["e50"]-inds[j]["e200"]) <= 0:
            return False
        if side*(inds[j]["e50"]-inds[j-4]["e50"]) <= 0:
            return False
    return True


def candidate_step(book, bars, i, h1, inds, m15_ind=None, profile="baseline"):
    current, prior = bars[i], bars[i-1]
    if book["position"]:
        if not bot.exit_position(book,current):
            bot.advance_trailing_stop(book,current)
        return
    if book["equity"] <= 0:
        return
    eligible = [j for j,b in enumerate(h1) if b["time"]+3600 <= prior["time"]]
    if not eligible:
        return
    j=eligible[-1]
    closed=h1[j]["time"]+3600
    if prior["time"] >= closed+3600 or book["last_entry_h1"] == h1[j]["time"]:
        return
    side=bot.h1_rejection(h1,inds,j)
    if not side:
        return
    middle=mean(b["close"] for b in h1[j-19:j+1])
    if not decide(profile,bars,i,h1,inds,j,side,middle):
        return
    atr=inds[j]["atr"]
    opened=current["open"]
    if atr<=0 or opened<=0:
        return
    distance=max(bot.STOP_ATR*atr,6*bot.PIP)
    qty=min(book["equity"]*bot.MAX_NOTIONAL,
            (book["equity"]*bot.RISK_FRACTION*opened)/distance)
    if qty<=0:
        return
    book["position"]={
        "side":side,"entry":opened,"entry_ts":current["time"],
        "entry_rule":"comparison_"+profile,
        "qty_usd":qty,"stop":opened-side*distance,
        "initial_r":distance,"best_close":opened,
        "stop_policy":bot.TRAIL_POLICY,"stop_updates":0,
        "green_protected":False,"target":None,"confirm_h1":h1[j]["time"],
    }
    book["last_entry_h1"]=h1[j]["time"]
    if not bot.exit_position(book,current):
        bot.advance_trailing_stop(book,current)


def score(bars, start, end, profile):
    warm=[b for b in bars if b["time"] < start]
    subset=[b for b in bars if b["time"] < end]
    if len(bot.to_h1(warm))<53:
        raise ValueError("Warmup insuficiente")
    old=bot.update(None,warm)
    if profile=="baseline":
        state=bot.update(old,subset)
    else:
        with patch.object(bot,"step",partial(candidate_step,profile=profile)):
            state=bot.update(old,subset)
    closed=state["closed"]
    wins=[x for x in closed if x["net_usd"]>0]
    losses=[x for x in closed if x["net_usd"]<0]
    net=state["equity"]-bot.CAPITAL
    last=subset[-1]["close"]
    pos=state["position"]
    open_pnl=None
    if pos:
        open_pnl=((last-pos["entry"])*pos["side"]-bot.ROUNDTRIP_PIPS*bot.PIP)*pos["qty_usd"]/last
    return {
        "closed":len(closed),"wins":len(wins),"losses":len(losses),
        "win_rate_pct":round(100*len(wins)/len(closed),2) if closed else None,
        "net_usd":round(net,5),
        "mtm_usd":round(net+(open_pnl or 0),5),
        "profit_factor":round(sum(x["net_usd"] for x in wins)/-sum(x["net_usd"] for x in losses),4) if losses else None,
        "open_position":bool(pos),
        "trades":closed,
    }


def main():
    with gzip.open(BARS, "rt", encoding="utf-8") as f:
        payload=json.load(f)
    bars=payload["candles"]
    # Use the exact original end timestamp from frozen 30-day report:
    meta=json.loads(Path("research/results/bb20_usdcad_m15_1mo_2026-10-26.json").read_text(encoding="utf8"))
    end=int(datetime.strptime(meta["timestamp_utc"],"%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc).timestamp())
    start=end-30*86400
    split=start+15*86400
    res={}
    for profile in PROFILES:
        res[profile]={
            "development":score(bars,start,split,profile),
            "holdout":score(bars,split,end+60,profile),
            "whole":score(bars,start,end+60,profile),
        }
    result={
        "dataset_sha256":meta["source_sha256"],
        "source":meta["source"],"period":"30 days",
        "development":"first 15 days", "holdout":"last 15 days",
        "selection_policy":"Holdout is retrospectively inspected; require at least 5 holdout trades and net > 0 in both halves before considering a live switch. Never choose only by win rate.",
        "variants":res,
        "warnings":[
            "Historical selection and the user's earlier results mean holdout is not fully independent.",
            "Costs estimates may understate real trading friction.",
            "Comparisons assume M15 next-bar-open fills possible; GitHub schedule can be delayed.",
            "No candidates are automatically deployed; forward proof remains necessary.",
        ],
    }
    REPORT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines=[
        "# Entrada BB20 — comparação controlada, sem troca automática do robô",
        "",
        "Mesmo histórico e mesmo risco/saída. Mudança apenas nos critérios de entrada.",
        "Treino: 15 dias iniciais; validação retrospectiva: 15 dias finais.",
        "",
        "| Filtro de entrada | 30d operações | 30d acerto | 30d P&L US$ | Treino P&L US$ | Validação operações | Validação acerto | Validação P&L US$ |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name,v in res.items():
        whole=v["whole"]; train=v["development"]; val=v["holdout"]
        rate="n/a" if whole["win_rate_pct"] is None else str(whole["win_rate_pct"])+"%"
        vrate="n/a" if val["win_rate_pct"] is None else str(val["win_rate_pct"])+"%"
        lines.append(f'| {name} | {whole["closed"]} | {rate} | {whole["net_usd"]:+.2f} | {train["net_usd"]:+.2f} | {val["closed"]} | {vrate} | {val["net_usd"]:+.2f} |')
    lines += ["", "**Validação não é prospectiva. Uma taxa de acerto alta com 1–3 trades não é prova de superioridade.**", ""]
    SUMMARY.write_text("\n".join(lines),encoding="utf-8")
    print("COMPARISON=" + json.dumps({name:{part:{k:r[part][k] for k in ("closed","wins","losses","win_rate_pct","net_usd","mtm_usd")} for part in ("development","holdout","whole")} for name,r in res.items()},ensure_ascii=False))
    print("REPORT=" + str(SUMMARY))


if __name__=="__main__":
    main()
