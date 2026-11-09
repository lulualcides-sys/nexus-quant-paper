"""Decode publicly EMBEDDED reenactment chart data for 03/04 Nov 2026.

Not the Tracker indicator. This analyzes the promotional site's own
compact static canvas dataset (publicly distributed to every visitor).
No site access control, member content, injected code or JS execution.
No claim that these were actual filled trades or authenticated B3 quotes.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path

PAGE="https://lojadagreenhouse.com.br/ofertatracker/"
UA="NexusQuantPublicPromoDatasetVerification/1.0"
DAY=["03/11/2026","04/11/2026"]

def decode_literal(html):
    match=re.search(r"\bvar\s+D\s*=\s*\{d\s*:",html)
    if not match:
        raise ValueError("Public gallery compressed dataset not found")
    start=match.end()-3
    # Discover balanced object by scanning, never eval any JS.
    begin=html.find("{",match.start())
    quote=None;escape=False;depth=0;end=None
    for i in range(begin,min(len(html),begin+300000)):
        c=html[i]
        if quote:
            if escape:escape=False
            elif c=="\\":escape=True
            elif c==quote:quote=None
            continue
        if c in ("'",'"'):quote=c;continue
        if c=="{":depth+=1
        elif c=="}":
            depth-=1
            if depth==0:
                end=i+1;break
    if end is None:
        raise ValueError("Unbounded promo chart literal")
    text=html[begin:end]
    text=re.sub(r"(?<=[{,])\s*([A-Za-z_]\w*)\s*:",lambda m:'"'+m.group(1)+'":',text)
    data=ast.literal_eval(text)
    if not isinstance(data,dict) or set(data)!={"d","s"}:
        raise ValueError("Unexpected public compressed chart structure")
    return data

def record_to_candles(encoded):
    minute=int(encoded[0]);prev=int(encoded[1]);k=2
    bars={}
    while k<len(encoded):
        o=prev+int(encoded[k])*5
        h=o+int(encoded[k+1])*5
        l=o-int(encoded[k+2])*5
        c=o+int(encoded[k+3])*5
        if l>min(o,c) or h<max(o,c) or l>h:
            raise ValueError("Public recreated candle inconsistent")
        bars[minute]={"open":o,"high":h,"low":l,"close":c}
        prev=c;minute+=1;k+=4
    return bars

def geom_for_candle(c,dir):
    h,l=c["high"],c["low"]
    r=h-l
    if r<=0:return None
    if dir=="c":
        return (l+.5*r,l+2*r,l-r)
    return (h-.5*r,h-2*r,h+r)

def audit(html):
    data=decode_literal(html)
    if len(data["d"])!=2 or len(data["s"])<5:
        raise ValueError("Unexpected number of public data blocks")
    candles=[record_to_candles(x) for x in data["d"]]
    records=[]
    for x in data["s"]:
        if len(x)<10:
            raise ValueError("Public record missing required fields")
        n,day,t,dir,e,a,stop,result,exit_min,p=x[:10]
        if day not in (0,1) or dir not in ("c","v") or result not in ("w","l"):
            raise ValueError("Invalid gallery classification")
        n,day,t,e,a,stop,exit_min,p=map(int,(n,day,t,e,a,stop,exit_min,p))
        if not all(z%5==0 for z in (e,a,stop)):
            raise ValueError("Off-tick public displayed WIN price")
        target_distance=abs(a-e)
        stop_distance=abs(e-stop)
        if (dir=="c" and not a>e>stop) or (dir=="v" and not a<e<stop):
            raise ValueError("Incorrect direction of public target/stop")
        exact={}
        for off in (0,-1):
            bar=candles[day].get(t+off)
            if bar is None:continue
            candidate=geom_for_candle(bar,dir)
            if candidate:
                errors=[abs(actual-pred) for actual,pred in zip((e,a,stop),candidate)]
                exact[str(off)]={"max_error_points":round(max(errors),1),
                                 "mean_error_points":round(sum(errors)/3,2),
                                 "all_within_5_points":max(errors)<=5.01}
        records.append({"signal_number":n,"date":DAY[day],
                        "time":f"{t//60:02}:{t%60:02}",
                        "direction":"compra" if dir=="c" else "venda",
                        "entry":e,"target":a,"stop":stop,
                        "outcome":result,"listed_points":p,
                        "gross_target_points":target_distance,
                        "gross_stop_points":stop_distance,
                        "gross_distance_asymmetry":abs(target_distance-stop_distance),
                        "close_time":f"{exit_min//60:02}:{exit_min%60:02}",
                        "candidate_candle_geometry_error":exact})
    days={}
    for day in DAY:
        rows=[s for s in records if s["date"]==day]
        days[day]={"signals":len(rows),"target_winners":sum(s["outcome"]=="w" for s in rows),
                   "stops":sum(s["outcome"]=="l" for s in rows),
                   "claimed_points_sum":sum(s["listed_points"] for s in rows)}
    asymmetric=[r for r in records if r["gross_distance_asymmetry"]>5]
    match0=sum(r["candidate_candle_geometry_error"].get("0",{}).get("all_within_5_points",False) for r in records)
    matchMinus1=sum(r["candidate_candle_geometry_error"].get("-1",{}).get("all_within_5_points",False) for r in records)
    return {"status":"PUBLIC_PROMOTIONAL_RECREATION_NOT_BROKER_FILLED_TRADES",
            "published_by":"lojadagreenhouse.com.br",
            "days":days,
            "records":records,
            "records_total":len(records),
            "rounded_1_to_1_within_five_points":sum(r["gross_distance_asymmetry"]<=5 for r in records),
            "asymmetry_more_than_five_points":len(asymmetric),
            "geometry_matches_recreated_signal_candle_within_5pt":match0,
            "geometry_matches_recreated_prior_candle_within_5pt":matchMinus1,
            "candle_counts":[len(c) for c in candles],
            "cannot_verify":["Indicator's original proprietary trigger logic",
                             "Whether labels were frozen live, not retrospectively added",
                             "Exchange quotes and time alignment",
                             "Broker order fills or taxes, actual position sizes",
                             "Streak selection bias or performance outside these two days"]}

def main():
    req=urllib.request.Request(PAGE,headers={"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=30) as r:
        b=r.read(1_000_000)
    text=b.decode("utf-8-sig")
    a=audit(text)
    a["public_html_sha256"]=hashlib.sha256(b).hexdigest()
    # Print aggregate plus a few first and last records; do not spam raw site data.
    excerpt={"status":a["status"],"days":a["days"],
             "records_total":a["records_total"],
             "candle_counts":a["candle_counts"],
             "rounded_1_to_1_within_five_points":a["rounded_1_to_1_within_five_points"],
             "asymmetry_more_than_five_points":a["asymmetry_more_than_five_points"],
             "geometry_matches_recreated_signal_candle_within_5pt":a["geometry_matches_recreated_signal_candle_within_5pt"],
             "geometry_matches_recreated_prior_candle_within_5pt":a["geometry_matches_recreated_prior_candle_within_5pt"],
             "examples":a["records"][:2]+a["records"][-2:],
             "limitations":a["cannot_verify"]}
    print("PUBLIC_GALLERY_AUDIT_START")
    print(json.dumps(excerpt,ensure_ascii=False,indent=2))
    print("PUBLIC_GALLERY_AUDIT_END")
    folder=Path("research/results");folder.mkdir(parents=True,exist_ok=True)
    (folder/"tracker_public_gallery_2026_11_03_04.json").write_text(json.dumps(a,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__":
    main()
