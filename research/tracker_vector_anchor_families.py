"""Exhaustive *predeclared* public vector anchor hypotheses and null checks.

We test whether the demo's 43 claimed stop/entry/target levels originate
from a single candle BODY, candle WICK, or a small past rolling RANGE.
All candidate windows use current or PAST reconstructed M1 chart candles;
there is no future price. No proprietary indicator code.
"""
from __future__ import annotations

import hashlib
import json
import random
import urllib.request
from collections import Counter
from pathlib import Path
from statistics import median

from research.greenhouse_public_gallery_decode import PAGE,decode_literal,record_to_candles
from research.tracker_vector_discovery_43 import derive_implied_vector

WINDOWS=(1,2,3,5,8,13,20)
END_LAGS=(0,1,2)
ANCHOR_TYPES=("wick_range","body_range","close_range")
TOL=5.01

def endpoints(candles,minute,window,kind):
    rows=[candles.get(i) for i in range(minute-window+1,minute+1)]
    if any(b is None for b in rows):
        return None
    if kind=="wick_range":
        return (max(b["high"] for b in rows),min(b["low"] for b in rows))
    if kind=="body_range":
        return (max(max(b["open"],b["close"]) for b in rows),
                min(min(b["open"],b["close"]) for b in rows))
    if kind=="close_range":
        return (max(b["close"] for b in rows),min(b["close"] for b in rows))
    raise ValueError(kind)

def compare_anchors(bars,minute,vector):
    candidates=[]
    for kind in ANCHOR_TYPES:
        for lag in END_LAGS:
            for window in WINDOWS:
                result=endpoints(bars,minute-lag,window,kind)
                if result is None:
                    continue
                hi,lo=result
                worst=max(abs(hi-vector["implied_high"]),abs(lo-vector["implied_low"]))
                candidates.append({
                    "kind":kind,"lag":lag,"window":window,"max_endpoint_error":round(worst,3),
                    "matching":worst<=TOL
                })
    candidates.sort(key=lambda x:(x["max_endpoint_error"],x["lag"],x["window"],x["kind"]))
    return candidates

def run(candles,raw_records,*,permutation_repetitions=100,random_seed=20261109):
    records=[]
    for raw in raw_records:
        _,day,minute,direction,entry,target,stop,*rest=raw
        day=int(day);minute=int(minute)
        side=1 if direction=="c" else -1
        implied=derive_implied_vector(int(entry),int(target),int(stop),side)
        rows=compare_anchors(candles[day],minute,implied)
        records.append({
            "id":int(raw[0]),"day":day,"minute":minute,
            "implied_vector":implied,"matched_any_hypothesis":any(x["matching"] for x in rows),
            "matched_past_only":any(x["matching"] and x["lag"]>=1 for x in rows),
            "best":rows[0] if rows else None,
            "matching_hypotheses":[x for x in rows if x["matching"]]
        })
    hypotheses=[(kind,lag,n) for kind in ANCHOR_TYPES for lag in END_LAGS for n in WINDOWS]
    matrix={}
    for kind,lag,n in hypotheses:
        name=f"{kind}|lag={lag}|len={n}"
        selected=[r for r in records if any(x["kind"]==kind and x["lag"]==lag and
                                           x["window"]==n and x["matching"]
                                           for x in r["matching_hypotheses"])]
        matrix[name]={
            "matches":len(selected),
            "matched_days":sorted(set(r["day"] for r in selected)),
            "no_future_bars":True
        }
    # Randomize *TIMES* of published pricing vectors within each day's
    # reconstructed price path to estimate alignment by chance. This does not
    # make promotional labels unbiased or prove original formula.
    rng=random.Random(random_seed)
    chance=[]
    valid_minutes=[
        [x for x in sorted(c) if x>=min(c)+20 and x<=max(c)-5] for c in candles
    ]
    for j in range(permutation_repetitions):
        total=0
        for r in records:
            sample_min=rng.choice(valid_minutes[r["day"]])
            rows=compare_anchors(candles[r["day"]],sample_min,r["implied_vector"])
            total+=int(any(x["matching"] for x in rows))
        chance.append(total)
    observed=sum(r["matched_any_hypothesis"] for r in records)
    chance_ge=sum(x>=observed for x in chance)
    return {
        "status":"PUBLIC_MARKETING_VECTOR_ANCHOR_RESEARCH_NOT_TRACKER_INTERNAL",
        "fixed_hypothesis_families":ANCHOR_TYPES,
        "windows":WINDOWS,
        "end_lags":END_LAGS,
        "hypothesis_count":len(hypotheses),
        "tolerance_points":TOL,
        "signals":len(records),
        "matching_any_model":observed,
        "matching_past_only":sum(r["matched_past_only"] for r in records),
        "best_per_hypothesis":dict(sorted(matrix.items(),key=lambda x:-x[1]["matches"])[:15]),
        "permutation_time_shift_checks":{
            "repetitions":permutation_repetitions,
            "seed":random_seed,
            "mean_random_matches":round(sum(chance)/len(chance),3) if chance else None,
            "median_random_matches":median(chance) if chance else None,
            "max_random_matches":max(chance) if chance else None,
            "proportion_random_gte_observed":round(chance_ge/len(chance),3) if chance else None,
            "not_a_formal_significance_test":True
        },
        "record_details":records,
        "weaknesses":[
            "63 predeclared geometric hypotheses; best in-sample family not independent evidence",
            "Public promo OHLC may be reconstructed or edited, labels can be selected after the fact",
            "Randomizing times changes price alignment and cannot model editorial selection",
            "Opening/closing price availability does not show fill order or original signal",
            "No classified volume/flow; no verification of market data or live algorithm",
        ],
        "approved_as_exact_replica":False,
        "approved_for_live":False
    }

def main():
    with urllib.request.urlopen(urllib.request.Request(PAGE,headers={"User-Agent":"Mozilla/5.0 public educational audit"}),timeout=30) as r:
        blob=r.read(1_000_000)
    source=decode_literal(blob.decode("utf-8-sig"))
    bars=[record_to_candles(x) for x in source["d"]]
    report=run(bars,source["s"])
    report["source_html_sha256"]=hashlib.sha256(blob).hexdigest()
    public={k:v for k,v in report.items() if k!="record_details"}
    print("VECTOR_ANCHOR_HYPOTHESES_START")
    print(json.dumps(public,ensure_ascii=False,indent=2))
    print("VECTOR_ANCHOR_HYPOTHESES_END")
    folder=Path("research/results")
    folder.mkdir(parents=True,exist_ok=True)
    (folder/"tracker_vector_anchor_family_43.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

if __name__=="__main__":main()
