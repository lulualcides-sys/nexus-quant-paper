"""ATLAS: compare public Tracker labels against real WINV26 on 13/10/2026.

A label requires *market* time and evidence of a post-close signal; video
playback time or marketing claims are NOT labels or trade execution records.
"""
from __future__ import annotations
import argparse, csv, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from research.win_price_data import TZ, _number, _tick_check, read_win_csv
from research.atlas_confluence_v3 import VARIANTS, v3_signal

SYMBOL = "WINV26"
DATE = "2026-10-13"
MIN_CANDLES = 400

def parse_time(d, t):
    for f in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try: return datetime.strptime(d+" "+t, f)
        except ValueError: pass
    raise ValueError("Invalid Profit market timestamp")

def convert_profit(original, dest):
    """Require actual 9-column Profit output; Quantity != financial Volume."""
    b = Path(original).read_bytes()
    if len(b) > 25000000: raise ValueError("File too large")
    rows = []
    for n, p in enumerate(csv.reader(b.decode("utf-8-sig").splitlines(), delimiter=";"), 1):
        if not p or p[0].strip().lower() == "ativo": continue
        if len(p) != 9 or p[0].strip().upper() != SYMBOL:
            raise ValueError(f"Row {n}: WINV26 and nine Profit columns required")
        dt = parse_time(p[1].strip(),p[2].strip())
        if dt.date().isoformat() > DATE: raise ValueError("Future market date included")
        o,h,l,c = [_number(x) for x in p[3:7]]
        money, quantity = _number(p[7]), _number(p[8])
        for price in (o,h,l,c): _tick_check(price)
        if l>min(o,c) or h<max(o,c) or money<=0 or quantity<=0 or int(quantity)!=quantity:
            raise ValueError(f"Row {n}: invalid candle or quantity")
        rows.append((dt,o,h,l,c,int(quantity)))
    if len(rows) < 100: raise ValueError("Insufficient WIN candles")
    rows.sort(key=lambda x:x[0])
    if len({r[0] for r in rows}) != len(rows): raise ValueError("Duplicate minutes")
    with Path(dest).open("w",encoding="utf-8",newline="") as f:
        writer=csv.writer(f,delimiter=";")
        writer.writerow(["Ativo","Data","Hora","Open","High","Low","Close","Volume"])
        for dt,o,h,l,c,q in rows:
            writer.writerow([SYMBOL,dt.strftime("%d/%m/%Y"),dt.strftime("%H:%M:%S"),
                             int(o),int(h),int(l),int(c),q])
    parsed = read_win_csv(dest,expected_symbol=SYMBOL)
    if parsed["timeframe_seconds"]!=60: raise ValueError("Real M1 data required")
    return parsed, {"filename":Path(original).name,
                    "sha256":hashlib.sha256(b).hexdigest(),
                    "independently_exchange_verified":False,
                    "quantity_is_traded_contract_count":True}

def labels_from_csv(path):
    if not path: return []
    out=[]
    with Path(path).open(encoding="utf-8-sig",newline="") as f:
        reader=csv.DictReader(f)
        required={"date","market_time","side","evidence_url","observed_after_close"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError("Missing evidence fields")
        for row in reader:
            if row["date"]!=DATE or row["side"] not in ("buy","sell") or row["observed_after_close"]!="yes":
                raise ValueError("Invalid video label")
            if not row["evidence_url"].startswith("https://"): raise ValueError("Unverifiable label")
            dt=parse_time("13/10/2026",row["market_time"])
            ts=int(dt.replace(tzinfo=TZ).astimezone(timezone.utc).timestamp())
            out.append((ts,1 if row["side"]=="buy" else -1))
    if len(set(t for t,s in out))!=len(out): raise ValueError("Ambiguous duplicate labels")
    return out

def analyze(input_path, label_path=None):
    with TemporaryDirectory() as d:
        bars,prov=convert_profit(input_path,Path(d)/"normalized.csv")
    candles=bars["bars"]
    day=[b for b in candles if datetime.fromtimestamp(
        b["time"],timezone.utc).astimezone(TZ).date().isoformat()==DATE]
    labels=labels_from_csv(label_path)
    result={"contract":SYMBOL,"date":DATE,"source":prov,
            "target_day_m1_candles":len(day),"minimum_expected_candles":MIN_CANDLES,
            "claimed_27_signals_not_necessarily_trades":True,
            "verified_video_labels":len(labels),"tracker_formula_known":False,
            "financial_performance_validated":False,"comparisons":None}
    if len(day)<MIN_CANDLES:
        result["status"]="insufficient_m1_data";return result
    if not labels:
        result["status"]="awaiting_verified_video_labels";return result
    lookup={x["time"]:i for i,x in enumerate(candles)}
    if any(ts not in lookup for ts,s in labels): raise ValueError("Labels not on real candles")
    result["comparisons"]={}
    for var in VARIANTS:
        eligible=[(lookup[ts],s) for ts,s in labels if lookup[ts]>=75]
        n=sum(v3_signal(candles,i,var)==s for i,s in eligible)
        result["comparisons"][var]={
           "exact_time_direction_matches":n,
           "verified_labels_checked":len(eligible),
           "agreement_pct":round(100*n/len(eligible),2) if eligible else None}
    result["status"]="label_comparison_only_not_profitability"
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--winv26-csv",required=True)
    ap.add_argument("--verified-labels")
    ap.add_argument("--out",default="research/results/atlas_win_oct13.json")
    a=ap.parse_args()
    result=analyze(a.winv26_csv,a.verified_labels)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],"label_count":result["verified_video_labels"],
                      "m1_count":result["target_day_m1_candles"]}))
if __name__=="__main__": main()
