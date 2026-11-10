"""Read-only local import of LICENSED Nelogica/Profit tick-by-tick historical CSV.

Reference column layout (official Nelogica):
 Ativo, Data, Tempo, Número do negócio, Preço, Quantidade, Volume,
 Agente comprador, Agente vendedor, Agressor, After

The original files are proprietary to their owner/licensor and must NOT be
committed, redistributed or sent to Github. We keep ONLY minute aggregates
in an ignored private_mt5 folder. This program does not read account IDs
or use the buy/sell agent codes.

Agressor:
  2 = buying aggressor; 3 = selling aggressor (official ProfitDLL TradeType).
  Explicit 'COMPRA'/'VENDA' also accepted; all other values are UNKNOWN.
Unknown never becomes invented delta.

This is an independently devised flow approximation, NOT the original
Greenhouse Tracker formula. No order sending or broker account access.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import tempfile
import unicodedata
from collections import defaultdict
from datetime import date,datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from research.win_flow_public_label_comparison import independent_signals, compare, public_markers_from_html

SP=ZoneInfo("America/Sao_Paulo")
WIN=re.compile(r"WIN[GJMQVZ]\d\d\Z",re.I)
HARD_CAP_TRADES=2_000_000
CRITICAL={"ativo","data","tempo","numerodonegocio","preco","quantidade","agressor"}
ALIASES={
    "ativo":"ativo","ticker":"ativo",
    "data":"data","date":"data",
    "tempo":"tempo","hora":"tempo","time":"tempo",
    "numerodonegocio":"numerodonegocio","nnegocio":"numerodonegocio",
    "idnegocio":"numerodonegocio",
    "preco":"preco","price":"preco",
    "quantidade":"quantidade","qtd":"quantidade",
    "agressor":"agressor","tipodeagressao":"agressor","aggression":"agressor",
}

def norm(text):
    normalized=unicodedata.normalize("NFKD",str(text or "").strip())
    return re.sub(r"[^a-z0-9]","",normalized.encode("ascii","ignore").decode().lower())

def parse_brazil_number(raw):
    value=str(raw or "").strip().replace(" ","")
    if not value:raise ValueError("Missing numeric field")
    if "," in value:
        value=value.replace(".","").replace(",",".")
    number=float(value)
    if not math.isfinite(number):
        raise ValueError("Non-finite numeric value")
    return number

def iso_date(raw):
    s=str(raw).strip()
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}",s):
        return datetime.strptime(s,"%d/%m/%Y").date()
    return date.fromisoformat(s)

def parse_event_time(day_raw,time_raw):
    day=iso_date(day_raw)
    stamp=str(time_raw).strip().replace(",",".")
    if not re.fullmatch(r"\d{1,2}:\d{2}:\d{2}(?:\.\d{1,6})?",stamp):
        raise ValueError("Expected local Profit trade time HH:MM:SS[.milliseconds]")
    fmt="%H:%M:%S.%f" if "." in stamp else "%H:%M:%S"
    t=datetime.strptime(stamp,fmt).time()
    local=datetime.combine(day,t,tzinfo=SP)
    # Require explicit America/Sao_Paulo because broker times vary by server.
    return int(local.astimezone(timezone.utc).timestamp()*1000)

def side(raw):
    s=norm(raw)
    if s in {"2","compra","comprador","buy","agressaodecompra","c"}:
        return 1
    if s in {"3","venda","vendedor","sell","agressaodevenda","v"}:
        return -1
    return 0

def sniff_delimiter(header):
    candidates=(";","\t",",")
    return max(candidates,key=lambda delim:header.count(delim))

def safe_trade_rows(path,expected_symbol,expected_day,*,max_events=HARD_CAP_TRADES):
    if not WIN.fullmatch(expected_symbol):
        raise ValueError("Use WIN with an explicit exchange expiry, e.g. WINZ26")
    if date.fromisoformat(expected_day).weekday()>4:
        raise ValueError("Cannot use weekend as regular exchange session")
    count=0
    last_ms=None
    seen_ids=set()
    with open(path,"r",encoding="utf-8-sig",newline="") as fh:
        raw_header=fh.readline()
        if not raw_header:
            raise ValueError("Empty source CSV")
        fh.seek(0)
        delimiter=sniff_delimiter(raw_header)
        reader=csv.DictReader(fh,delimiter=delimiter)
        columns={ALIASES[norm(name)]:name for name in reader.fieldnames or []
                 if norm(name) in ALIASES}
        absent=CRITICAL-set(columns)
        if absent:
            raise ValueError("Missing official licensed tick fields: "+",".join(sorted(absent)))
        for row_number,row in enumerate(reader,start=2):
            if not row or all(not str(x or "").strip() for x in row.values()):
                continue
            if row_number>max_events+1:
                raise ValueError("Local trade count exceeds safe memory cap")
            symbol=str(row[columns["ativo"]]).strip().upper()
            if symbol!=expected_symbol.upper():
                raise ValueError(f"Unexpected contract at source CSV row {row_number}; no continuous-roll mixing")
            dt=iso_date(row[columns["data"]])
            if dt.isoformat()!=expected_day:
                raise ValueError("Multiple day dates in one input; require explicit day")
            trade_id=str(row[columns["numerodonegocio"]]).strip()
            if not trade_id or trade_id in seen_ids:
                raise ValueError("Missing or duplicate trade ID in one session")
            seen_ids.add(trade_id)
            ms=parse_event_time(row[columns["data"]],row[columns["tempo"]])
            if last_ms is not None and ms<last_ms:
                raise ValueError("Out-of-order trade sequence: refuse misleading signed flow")
            last_ms=ms
            price=parse_brazil_number(row[columns["preco"]])
            quantity=parse_brazil_number(row[columns["quantidade"]])
            if price<=0 or abs(price/5-round(price/5))>1e-8:
                raise ValueError("Off-grid/nonpositive WIN transaction price")
            if quantity<=0 or not quantity.is_integer():
                raise ValueError("Nonpositive/noninteger executed contract quantity")
            count+=1
            yield {"time_msc":ms,"price":price,"quantity":int(quantity),
                   "aggressor":side(row[columns["agressor"]])}
    if count<1:
        raise ValueError("No executed trades in licensed CSV")

def build_minutes(events,*,source_tag="Nelogica_licensed_tick_csv"):
    minutes={}
    total_events=0
    unknown_codes=0
    for event in events:
        stamp=event["time_msc"]
        key=stamp//60000*60
        price,qty=event["price"],event["quantity"]
        a=minutes.get(key)
        if a is None:
            a={"time":key,"open":price,"high":price,"low":price,
               "close":price,"real_volume":0,
               "buy_volume":0.,"sell_volume":0.,"unknown_volume":0.,
               "classified_trade_count":0,"trade_count":0,
               "first_trade_msc":stamp,"last_trade_msc":stamp,
               "last_15s_delta":0.,"price_qty":defaultdict(float)}
            minutes[key]=a
        a["high"]=max(a["high"],price)
        a["low"]=min(a["low"],price)
        a["close"]=price
        a["real_volume"]+=qty
        a["trade_count"]+=1
        a["last_trade_msc"]=stamp
        a["price_qty"][int(price)]+=qty
        side_flag=event["aggressor"]
        if side_flag==1:
            a["buy_volume"]+=qty
            a["classified_trade_count"]+=1
            if stamp%60000>=45000:a["last_15s_delta"]+=qty
        elif side_flag==-1:
            a["sell_volume"]+=qty
            a["classified_trade_count"]+=1
            if stamp%60000>=45000:a["last_15s_delta"]-=qty
        else:
            a["unknown_volume"]+=qty
            unknown_codes+=1
        total_events+=1
    records=[]
    prev=None
    for minute in sorted(minutes):
        a=minutes[minute]
        total=a["real_volume"]
        classified=a["buy_volume"]+a["sell_volume"]
        rejects=[]
        if prev is not None and minute-prev!=60:
            rejects.append("m1_gap_before")
        prev=minute
        if total<=0:rejects.append("no_executed_contracts")
        if a["classified_trade_count"]<25:
            rejects.append("too_few_classified_trades")
        coverage=classified/total if total else 0
        if coverage<.60:
            rejects.append("insufficient_aggressor_classification")
        if a["first_trade_msc"]>minute*1000+15000 or \
           a["last_trade_msc"]<minute*1000+45000:
            rejects.append("incomplete_minute_trade_coverage")
        p=a["price_qty"]
        records.append({
            "time":minute,"open":a["open"],"high":a["high"],"low":a["low"],
            "close":a["close"],"real_volume":total,
            "buy_volume":a["buy_volume"],"sell_volume":a["sell_volume"],
            "unknown_volume":a["unknown_volume"],
            "classified_trade_count":a["classified_trade_count"],
            "trade_count":a["trade_count"],
            "classified_share":round(coverage,6),
            "delta":round(a["buy_volume"]-a["sell_volume"],4),
            "delta_fraction":round((a["buy_volume"]-a["sell_volume"])/classified,6)
                              if classified else None,
            "last_15s_delta":a["last_15s_delta"],
            "poc_price":min(p,key=lambda x:(-p[x],x)),
            "vwap":round(sum(x*n for x,n in p.items())/total,4),
            "valid_flow":not rejects,"reject_reasons":rejects,
            "source_bar_derived_from_same_ticks":True,
            "independent_m1_volume_crosscheck_performed":False,
        })
    return records,{"source":source_tag,"executed_trade_rows":total_events,
                    "unclassified_trade_rows":unknown_codes,
                    "minute_bars":len(records),
                    "valid_flow_minutes":sum(bool(x["valid_flow"]) for x in records),
                    "rejected_minutes":sum(not x["valid_flow"] for x in records),
                    "real_tick_prices_used_for_reconstructed_OHLC":True,
                    "independent_broker_candle_crosscheck":False,
                    "no_trading_orders_or_real_fill_claims":True}

def private_output(result,path):
    dest=Path(path).resolve()
    if "private_mt5" not in dest.parts:
        raise ValueError("Output MUST remain in private_mt5, excluded from Git")
    dest.parent.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf-8")
    name=None
    try:
        with tempfile.NamedTemporaryFile(mode="wb",dir=dest.parent,delete=False,
                                         prefix=".licensed_tape_",suffix=".tmp") as fp:
            fp.write(raw);name=fp.name
        os.replace(name,dest);name=None
    finally:
        if name is not None:Path(name).unlink(missing_ok=True)
    return hashlib.sha256(raw).hexdigest()

def main():
    p=argparse.ArgumentParser(description="Licensed Profit/Nelogica trade CSV -> private NQ flow diagnostics; no broker connection")
    p.add_argument("--csv",required=True)
    p.add_argument("--symbol",default="WINZ26")
    p.add_argument("--date",required=True,help="YYYY-MM-DD (trades contain local Sao Paulo timestamps)")
    p.add_argument("--output",default="private_mt5/nq_licensed_tape_research.json")
    p.add_argument("--compare-public",action="store_true",
                   help="Compare with public Greenhouse 03/04-Nov promotional labels; exploratory")
    args=p.parse_args()
    source=Path(args.csv)
    if not source.is_file():
        p.error("Licensed source CSV file was not found")
    rows,quality=build_minutes(safe_trade_rows(source,args.symbol,args.date))
    signals,decision=independent_signals(rows)
    result={"status":"LICENSED_LOCAL_TICK_SOURCE_RESEARCH_NOT_TRACKER",
            "symbol":args.symbol,"date":args.date,
            "source_csv_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
            "quality":quality,"detector":decision,
            "signals":signals,"minutes":rows,
            "original_tracker_source_recovered":False,
            "profitability_demonstrated":False,
            "live_trading_permitted":False}
    if args.compare_public:
        from research.greenhouse_public_gallery_decode import PAGE
        import urllib.request
        req=urllib.request.Request(PAGE,headers={"User-Agent":"NexusQuantPublicReference/1.0"})
        with urllib.request.urlopen(req,timeout=30) as response:
            html=response.read(1_000_000).decode("utf-8-sig")
        labels=[x for x in public_markers_from_html(html) if x["date"]==args.date]
        result["exploratory_public_label_overlap"]={
            "exact":compare(signals,labels,0),
            "plus_minus_1min":compare(signals,labels,1),
            "non_representative_marketing_labels":True,
        }
    sha=private_output(result,args.output)
    print(json.dumps({"status":result["status"],"source":"licensed private CSV",
                      "trades":quality["executed_trade_rows"],
                      "minutes":quality["minute_bars"],
                      "valid_flow_minutes":quality["valid_flow_minutes"],
                      "independent_signals":len(signals),
                      "output":str(Path(args.output).resolve()),"sha256":sha,
                      "broker_or_market_orders":0},ensure_ascii=False,indent=2))
if __name__=="__main__":
    main()
