"""Deeper public-promo signal forensics, *NOT* original Tracker source code.

Compare hard-coded Greenhouse marketing gallery labels to its OWN recreated
one-minute OHLC bars. Evaluate reproducible price-only patterns and candle
anchor offsets without executing website scripts, fitting thresholds, or
pretending this is independently authenticated B3 data.

The original proprietary signal algorithm is not published on this page.
No real volumes (contracts, aggression, bid/ask) appear in the compressed OHLC.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from statistics import median
import hashlib
import json
import random
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

from research.greenhouse_public_gallery_decode import (
    PAGE, decode_literal, record_to_candles, geom_for_candle
)

def features(bars, idx, direction, lookback=20):
    if idx not in bars:
        return None
    b=bars[idx]
    earlier=[bars.get(k) for k in range(idx-lookback,idx)]
    if any(x is None for x in earlier):
        return None
    prior_hi=max(x["high"] for x in earlier)
    prior_lo=min(x["low"] for x in earlier)
    r=b["high"]-b["low"]
    if r<=0:
        return None
    buy=direction=="c"
    wick=(min(b["open"],b["close"])-b["low"]) if buy else (
           b["high"]-max(b["open"],b["close"]))
    body_aligned=(b["close"]>b["open"]) if buy else (b["close"]<b["open"])
    swept=(b["low"]<=prior_lo-5) if buy else (b["high"]>=prior_hi+5)
    returned=(b["close"]>prior_lo) if buy else (b["close"]<prior_hi)
    # No need for real volume: the promo chart array has OHLC only.
    return {
        "body_aligned":body_aligned,
        "wick_35_pct":wick/r>=.35,
        "swept_20bar_extreme":swept,
        "closed_back_inside_extreme":returned,
        "full_price_sweep_hypothesis":body_aligned and wick/r>=.35 and swept and returned,
        "candle_range":r,
        "wick_fraction":round(wick/r,3),
        "range_vs_last_20_median":round(r/median(x["high"]-x["low"] for x in earlier),3) if median(x["high"]-x["low"] for x in earlier)>0 else None,
        "prior_range":prior_hi-prior_lo,
        "close_to_prior_mid_signed":round(((b["close"]-(prior_hi+prior_lo)/2) * (1 if buy else -1)),1),
    }


def binomial_guard(records):
    """Emit an honest null baseline, not a p-value or significance claim."""
    return None


def audit():
    req=urllib.request.Request(PAGE,headers={"User-Agent":"Mozilla/5.0 public-only research"})
    with urllib.request.urlopen(req,timeout=30) as response:
        blob=response.read(1_000_000)
    data=decode_literal(blob.decode("utf-8-sig"))
    candles=[record_to_candles(raw) for raw in data["d"]]
    outputs=[]
    for raw in data["s"]:
        number,day,minute,direction,entry,target,stop,result,exit_min,displayed_pts=raw[:10]
        day=int(day);minute=int(minute);entry=int(entry);target=int(target);stop=int(stop)
        matching=[]
        for offset in range(-20,21):
            other=candles[day].get(minute+offset)
            if not other:
                continue
            geom=geom_for_candle(other,direction)
            if geom is None:
                continue
            errors=[abs(int(a)-b) for a,b in zip((entry,target,stop),geom)]
            matching.append({"offset":offset,"max_error":round(max(errors),2),
                             "mean_error":round(sum(errors)/3,2),
                             "match_within_5pt":max(errors)<=5.01})
        matching.sort(key=lambda r:(r["max_error"],abs(r["offset"])))
        this=features(candles[day],minute,direction)
        prior=features(candles[day],minute-1,direction)
        outputs.append({
            "id":int(number),"day":f"{3+day:02}/11/2026",
            "minute":minute,"direction":direction,"claimed_outcome":result,
            "anchor_candidates_top5":matching[:5],
            "anchor_at_reported_minute":next((m for m in matching if m["offset"]==0),None),
            "anchor_at_previously_closed_minute":next((m for m in matching if m["offset"]==-1),None),
            "any_past_or_same_anchor_within_5pt":any(m["offset"]<=0 and m["match_within_5pt"] for m in matching),
            "any_future_anchor_within_5pt":any(m["offset"]>0 and m["match_within_5pt"] for m in matching),
            "first_past_or_same_matching_offset":next((m["offset"] for m in sorted(matching,key=lambda x:-x["offset"])
                                                      if m["offset"]<=0 and m["match_within_5pt"]),None),
            "price_features_at_label":this,
            "price_features_prior_closed_bar":prior,
            "claimed_entry":entry,"claimed_target":target,"claimed_stop":stop,
        })

    def stat_offsets(rows,name):
        entries=[r for r in rows if r[name] is not None]
        return {"present":len(entries),
                "aligned_body":sum(x[name]["body_aligned"] for x in entries),
                "wick_fraction_at_least_35pct":sum(x[name]["wick_35_pct"] for x in entries),
                "swept_recent_20bar_extreme":sum(x[name]["swept_20bar_extreme"] for x in entries),
                "swept_and_closed_inside":sum(x[name]["swept_20bar_extreme"] and x[name]["closed_back_inside_extreme"] for x in entries),
                "full_price_only_hypothesis":sum(x[name]["full_price_sweep_hypothesis"] for x in entries),
                "median_wick_fraction":round(median(x[name]["wick_fraction"] for x in entries),3) if entries else None,
                "median_range":round(median(x[name]["candle_range"] for x in entries),2) if entries else None}

    # Baseline: same day, similar distribution of buy/sell labels, randomly
    # selected from bars with sufficient previous bars. Not a formal test of edge.
    rng=random.Random(20261109)
    random_labels=[]
    for day_idx in range(2):
        cand=candles[day_idx]
        eligible=[t for t in sorted(cand) if features(cand,t,"c") is not None]
        count=sum(int(raw[1])==day_idx for raw in data["s"])
        sample=rng.sample(eligible,k=min(count,len(eligible)))
        directions=[str(raw[3]) for raw in data["s"] if int(raw[1])==day_idx]
        rng.shuffle(directions)
        for t,direction in zip(sample,directions):
            random_labels.append({"price_features_at_label":features(cand,t,direction)})
    same=stat_offsets(outputs,"price_features_at_label")
    prior=stat_offsets(outputs,"price_features_prior_closed_bar")
    null=stat_offsets(random_labels,"price_features_at_label")
    report={
        "status":"FORENSICS_OF_PROMOTIONAL_CANVAS_NOT_TRACKER_INTERNAL_LOGIC",
        "source_url":PAGE,
        "public_html_sha256":hashlib.sha256(blob).hexdigest(),
        "n_promotional_signals":len(outputs),
        "candle_counts_per_day":[len(x) for x in candles],
        "data_contains_real_volume":False,
        "data_contains_bid_ask_or_aggression":False,
        "n_exact_anchor_same_minute":sum(bool(r["anchor_at_reported_minute"]) and r["anchor_at_reported_minute"]["match_within_5pt"] for r in outputs),
        "n_exact_anchor_previous_minute":sum(bool(r["anchor_at_previously_closed_minute"]) and r["anchor_at_previously_closed_minute"]["match_within_5pt"] for r in outputs),
        "n_anchor_at_or_before_label_in_20min":sum(r["any_past_or_same_anchor_within_5pt"] for r in outputs),
        "n_anchor_after_label_in_20min":sum(r["any_future_anchor_within_5pt"] for r in outputs),
        "price_hypothesis_at_label":same,
        "price_hypothesis_prior_closed_bar":prior,
        "baseline_random_same_days_one_draw":null,
        "note_baseline":"A single deterministic random sample, NOT a hypothesis significance test or out-of-sample estimate",
        "records":outputs,
        "cannot_infer":["Proprietary signal generation from marketing HTML",
                        "Causal non-repainting behavior from hindsight annotation",
                        "Aggressor flow/volume because promo arrays lack this data",
                        "Whether the promotional OHLC matches actual market history",
                        "Real executions, fills, average slippage or net profitability"]
    }
    return report


def main():
    report=audit()
    output={k:v for k,v in report.items() if k!="records"}
    print("PROMO_FORENSICS_START")
    print(json.dumps(output,ensure_ascii=False,indent=2))
    print("PROMO_FORENSICS_EXAMPLES")
    for row in report["records"][:3]+report["records"][-2:]:
        print(json.dumps(row,ensure_ascii=False))
    print("PROMO_FORENSICS_END")
    folder=Path("research/results");folder.mkdir(parents=True,exist_ok=True)
    (folder/"tracker_public_43_signals_deeper_forensics.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


if __name__=="__main__":
    main()
