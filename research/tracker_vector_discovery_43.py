"""Independent vector geometry and held-day validation on public Tracker DEMO.

Clean-room research, not original Greenhouse code. This page contains
reconstructed OHLC and curated labels for only two sessions. Not exchange
ticks, not all possible true signals, not enough for reliable edge claims.

No lookahead in feature computation. Thresholds chosen on one day can only be
evaluated on the other day; no report claims true out-of-sample market edge.
"""
from __future__ import annotations
import hashlib
import json
import math
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import median

from research.greenhouse_public_gallery_decode import PAGE,decode_literal,record_to_candles

# Hand-chosen structure features; direction +1 buy / -1 sell. Do not fit
# on both days, no paid indicator features or future candles.
LOOKBACK=20
TICK=5.0

def vec_features(bars,minute,side,lookback=LOOKBACK):
    if side not in (-1,1) or minute not in bars: return None
    prev=[bars.get(j) for j in range(minute-lookback,minute)]
    if any(x is None for x in prev): return None
    bar=bars[minute]
    h,l,o,c=bar["high"],bar["low"],bar["open"],bar["close"]
    r=h-l
    if r<=0:return None
    prior_max=max(x["high"] for x in prev)
    prior_min=min(x["low"] for x in prev)
    mids=[(x["high"]+x["low"])/2 for x in prev]
    mean_range=sum(x["high"]-x["low"] for x in prev)/len(prev)
    prior5=bars.get(minute-5)
    if prior5 is None:return None
    lower=min(o,c)-l
    upper=h-max(o,c)
    wick=lower if side==1 else upper
    opp=prior_min if side==1 else prior_max
    signed_body=side*(c-o)
    signed_prevtrend=side*(prev[-1]["close"]-prior5["close"])
    # Features all measurable at close of this bar, never future prices.
    sweep_dist=(prior_min-l) if side==1 else (h-prior_max)
    rejection=(c-prior_min) if side==1 else (prior_max-c)
    near_extreme=(prior_min-l) if side==1 else (h-prior_max)
    close_directional=(c-l)/r if side==1 else (h-c)/r
    prior20_range=prior_max-prior_min
    return {
        "dir_body":round(signed_body/r,6),
        "dir_close":round(close_directional,6),
        "dir_wick":round(wick/r,6),
        "sweep_pts":round(sweep_dist,2),
        "sweep_scaled":round(sweep_dist/max(mean_range,TICK),6),
        "rejection_pts":round(rejection,2),
        "near_extreme_scaled":round(near_extreme/max(mean_range,TICK),6),
        "range_ratio":round(r/max(mean_range,TICK),6),
        "pretrend_5":round(signed_prevtrend/max(mean_range,TICK),6),
        "prior20_range":round(prior20_range,2),
        "bar_range":round(r,2),
        "body_positive":int(signed_body>0),
        "has_sweep":int(sweep_dist>=TICK and rejection>0),
        "wick_35":int(wick/r>=.35),
        "full_old_price_rule":int(signed_body>0 and wick/r>=.35 and sweep_dist>=TICK and rejection>0),
        "reversal_score":int(signed_body>0)+int(close_directional>=.60)+int(wick/r>=.15)+int(sweep_dist>=TICK and rejection>0)+int(signed_prevtrend<0),
    }

def derive_implied_vector(entry,target,stop,side):
    """The public 50 / 200 / -100 scheme has exact gross 1:1 distance.

    Infer R from combined target/stop so tick-rounded levels can deviate by 5.
    This reconstruction is mathematically constrained, not identification of
    the original candle or proprietary signal trigger.
    """
    if side not in (-1,1):
        raise ValueError("side")
    if not (side*target>side*entry>side*stop):
        raise ValueError("price ordering")
    total=side*(target-stop)
    r=total/3.
    base=entry-side*.5*r
    hi=base+r if side==1 else base
    lo=base if side==1 else base-r
    return {
        "implied_candle_range":round(r,3),
        "implied_high":round(hi,3),
        "implied_low":round(lo,3),
        "entry_target_distance":abs(target-entry),
        "entry_stop_distance":abs(entry-stop),
        "gross_imbalance_points":abs(abs(target-entry)-abs(entry-stop)),
    }

def rank_auc(labeled_scores):
    """Mann-Whitney AUC with ties; scores observed BEFORE label outcome."""
    pos=[s for s,y in labeled_scores if y]
    neg=[s for s,y in labeled_scores if not y]
    if not pos or not neg:return None
    wins=0
    for p in pos:
        wins+=sum(1 if p>n else 0.5 if p==n else 0 for n in neg)
    return round(wins/(len(pos)*len(neg)),4)

def threshold_with_frozen_budget(rows,feature,pick_n,sign=1):
    """Train-only top-N ranking; choose threshold without seeing test day."""
    values=sorted((sign*x["features"][feature] for x in rows),reverse=True)
    if not values:return None
    index=max(0,min(len(values)-1,pick_n-1))
    return values[index]

def evaluate_holdout(train,test,feature,sign):
    """Top-N budget fixed from TRAIN day's label rate; no test-day N oracle."""
    positives=sum(x["label"] for x in train)
    fraction=positives/len(train) if train else 0
    predicted_n=max(1,round(fraction*len(train))) # train label frequency only
    threshold=threshold_with_frozen_budget(train,feature,predicted_n,sign)
    if threshold is None:return None
    pred=[x for x in test if sign*x["features"][feature]>=threshold]
    tp=sum(x["label"] for x in pred)
    pos_test=sum(x["label"] for x in test)
    precision=tp/len(pred) if pred else 0.
    recall=tp/pos_test if pos_test else 0.
    base=pos_test/len(test) if test else 0.
    return {
        "train_positive":positives,"train_candidates":len(train),
        "test_positive":pos_test,"test_candidates":len(test),
        "threshold_from_training_only":round(threshold,4),
        "predicted":len(pred),"true_positive":tp,
        "false_positive_marketing_unlabeled":len(pred)-tp,
        "precision_promotional_labels":round(precision,4),
        "recall_promotional_labels":round(recall,4),
        "baseline_positive_fraction":round(base,4),
        "lift_vs_promotional_label_frequency":round(precision/base,3) if base else None,
    }

def build_demo(bars,marks):
    result={}
    for day in (0,1):
        data=[]
        targets={(int(row[2]), 1 if row[3]=="c" else -1)
                 for row in marks if int(row[1])==day}
        for minute in sorted(bars[day]):
            for side in (-1,1):
                features=vec_features(bars[day],minute,side)
                if features is None:continue
                data.append({"minute":minute,"side":side,"label":int((minute,side) in targets),
                             "features":features})
        result[day]=data
    return result

def analyze(candles,records):
    if len(candles)!=2 or len(records)!=43:
        raise ValueError("Demo changed: require independent review")
    barsets=[record_to_candles(x) for x in candles]
    observations=build_demo(barsets,records)
    anchor_records=[]
    for record in records:
        _,day,minute,direction,entry,target,stop,*rest=record
        day,minute=int(day),int(minute)
        side=1 if direction=="c" else -1
        inferred=derive_implied_vector(int(entry),int(target),int(stop),side)
        ref=barsets[day]
        # Anchor search only at or BEFORE label, not future, and no same candle
        # inference as a presumed pre-close signal. Report both explicitly.
        anchors=[]
        for lag in range(0,41):
            idx=minute-lag
            candle=ref.get(idx)
            if not candle:continue
            err=max(abs(inferred["implied_high"]-candle["high"]),
                    abs(inferred["implied_low"]-candle["low"]))
            anchors.append({"lag":lag,"max_range_endpoint_error":round(err,2)})
        anchors.sort(key=lambda a:(a["max_range_endpoint_error"],a["lag"]))
        anchor_records.append({
            "id":record[0],"day":int(day),"minute":minute,
            "side":side,
            "implied_vector":inferred,
            "best_previous_40_min_anchor":anchors[0] if anchors else None,
            "matches_5pt_with_current_or_past_40min":any(x["max_range_endpoint_error"]<=5.01 for x in anchors),
            "matches_5pt_with_previous_only_40min":any(x["lag"]>=1 and x["max_range_endpoint_error"]<=5.01 for x in anchors),
        })
    features=[
        ("reversal_score",1),
        ("dir_close",1),
        ("dir_body",1),
        ("dir_wick",1),
        ("sweep_scaled",1),
        ("range_ratio",1),
        ("pretrend_5",-1),
    ]
    comparisons={}
    for name,sign in features:
        comparisons[name]={
            "train_03_test_04":evaluate_holdout(observations[0],observations[1],name,sign),
            "train_04_test_03":evaluate_holdout(observations[1],observations[0],name,sign),
            "within_day03_auc_unselected_directions":rank_auc([(sign*x["features"][name],x["label"]) for x in observations[0]]),
            "within_day04_auc_unselected_directions":rank_auc([(sign*x["features"][name],x["label"]) for x in observations[1]]),
        }
    report={
        "status":"RECONSTRUCTED_MARKETING_CANVAS_ONLY_NOT_ORIGINAL_TRACKER",
        "promotional_dates":["2026-11-03","2026-11-04"],
        "promo_signals":len(records),
        "promo_candle_counts":[len(x) for x in barsets],
        "all_candidates_per_day":{str(k):len(v) for k,v in observations.items()},
        "directional_label_count_per_day":{str(k):sum(x["label"] for x in v) for k,v in observations.items()},
        "matched_vector_current_or_past_40":sum(x["matches_5pt_with_current_or_past_40min"] for x in anchor_records),
        "matched_vector_past_only_40":sum(x["matches_5pt_with_previous_only_40min"] for x in anchor_records),
        "vector_gross_imbalance_max":max(x["implied_vector"]["gross_imbalance_points"] for x in anchor_records),
        "inferred_candle_ranges_median":median(x["implied_vector"]["implied_candle_range"] for x in anchor_records),
        "criteria":comparisons,
        "anchor_records":anchor_records,
        "no_original_tracker_signal_rule_recovered":True,
        "not_an_oos_validation":True,
        "no_live_approval":True,
        "warnings":[
            "The third-party website supplies reconstructed candles, not exchange-authenticated prices",
            "All other minute-direction pairs are unmarked in the promo, NOT verified true negatives",
            "Two public promotional sessions were already inspected in prior research: no independent holdout",
            "Selecting the strongest rule after viewing all holdout results constitutes multiple testing",
            "No order book, aggressor volume, tick chronology, real fills, B3 margin or broker fees included",
            "This is a descriptive label reconstruction task, not investment profitability evidence",
            "The graphic's signal minute may not be the original indicator signal candle",
        ],
    }
    return report

def main():
    req=urllib.request.Request(PAGE,headers={"User-Agent":"Mozilla/5.0 public data for research"})
    with urllib.request.urlopen(req,timeout=30) as response:
        html=response.read(1_000_000)
    public=decode_literal(html.decode("utf-8-sig"))
    report=analyze(public["d"],public["s"])
    report["source_html_sha256"]=hashlib.sha256(html).hexdigest()
    clean={k:v for k,v in report.items() if k!="anchor_records"}
    print("VECTOR_FORENSICS_START")
    print(json.dumps(clean,ensure_ascii=False,indent=2))
    print("VECTOR_FORENSICS_END")
    folder=Path("research/results")
    folder.mkdir(parents=True,exist_ok=True)
    (folder/"tracker_vector_research_43.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

if __name__=="__main__":
    main()
