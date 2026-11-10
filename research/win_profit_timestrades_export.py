"""Adapt a LOCAL Profit Times & Trades-like CSV to private NQ flow research.

The Profit interface can display trade side in Times & Trades, but its CSV
layout is configurable. This tool accepts documented/basic column names,
NOT an assertion that every Profit installation exports this exact format.

REQUIRED: time/date, executed price, executed quantity, explicit aggressor.
Symbol/date must be in each trade OR explicitly supplied by the operator.
If the aggressor field is absent, FAIL; never infer from candle direction.
If trade ID is absent, identical prints are *not deduplicated* because they
can be legitimate separate fills; provenance of duplicates is marked unknown.

Does NOT scrape/bypass Profit, download private vendor history, use a DLL,
log in to broker, send orders, or publish licensed files.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
from datetime import date
from pathlib import Path

from research.win_licensed_tape_csv import (
    WIN,norm,parse_brazil_number,parse_event_time,iso_date,
    build_minutes,private_output,source_hash,sniff_delimiter
)
from research.win_flow_public_label_comparison import independent_signals
from research.win_volume_bars_cvd import Policy,build_closed_volume_bars,detect_absorption

COLS={
    "data":"day","date":"day","dia":"day",
    "hora":"time","horario":"time","tempo":"time","time":"time",
    "datahora":"datetime","datetime":"datetime","timestamp":"datetime",
    "preco":"price","price":"price","valor":"price","cotacao":"price",
    "quantidade":"qty","qtd":"qty","quantity":"qty",
    "agressor":"side","tipoagressao":"side","tipo":"side","aggression":"side",
    "ativo":"symbol","ticker":"symbol","symbol":"symbol","instrumento":"symbol",
    "numerodonegocio":"trade_id","numeronegocio":"trade_id",
    "idnegocio":"trade_id","negocio":"trade_id",
}
def side(text):
    val=norm(text)
    if val in {"2","c","compra","comprador","compradora",
               "buy","buyer","agressaocompra","agressaocompradora"}:
        return 1
    if val in {"3","v","venda","vendedor","vendedora",
               "sell","seller","agressaovenda","agressaovendedora"}:
        return -1
    return 0

def normalize_utc_trade_timestamp(day_text,time_text):
    # Validate the Portuguese standard dates, then delegate to the
    # existing DST-safe São Paulo timezone parser.
    day=iso_date(day_text).isoformat()
    return parse_event_time(day,time_text)

def iter_profit_export(path,*,symbol=None,day=None):
    """Yield canonical trades with strict case-insensitive column mapping."""
    if symbol is not None:
        symbol=symbol.upper()
        if not WIN.fullmatch(symbol):
            raise ValueError("Only an explicit WIN expiry is allowed (e.g. WINZ26)")
    if day is not None:day=iso_date(day).isoformat()
    with open(path,"r",encoding="utf-8-sig",newline="") as fh:
        head=fh.readline()
        if not head:raise ValueError("Empty file")
        fh.seek(0)
        reader=csv.DictReader(fh,delimiter=sniff_delimiter(head))
        mapped={}
        for original in reader.fieldnames or []:
            name=COLS.get(norm(original))
            if name is None:continue
            if name in mapped:
                raise ValueError(f"Ambiguous columns for {name}")
            mapped[name]=original
        required={"price","qty","side"}
        if not required.issubset(mapped):
            raise ValueError("Need price, quantity and explicit aggressor column")
        if "datetime" not in mapped and "time" not in mapped:
            raise ValueError("Need time or full datetime column")
        if "day" not in mapped and "datetime" not in mapped and day is None:
            raise ValueError("Need date in CSV or explicit --date")
        if "symbol" not in mapped and symbol is None:
            raise ValueError("Need contract in CSV or explicit --symbol")
        seen_ids=set()
        seen_date=None
        seen_symbol=None
        last_stamp=-1
        count=0
        for row_idx,row in enumerate(reader,2):
            if not row or all(not str(x or "").strip() for x in row.values()):
                continue
            current_symbol=(
                str(row[mapped["symbol"]]).strip().upper()
                if "symbol" in mapped else symbol)
            if not current_symbol or not WIN.fullmatch(current_symbol):
                raise ValueError("Invalid or missing explicit WIN expiry")
            if symbol and symbol!=current_symbol:
                raise ValueError("Export contains another WIN expiry")
            if seen_symbol and current_symbol!=seen_symbol:
                raise ValueError("Mixed expiry contracts")
            seen_symbol=current_symbol
            if "datetime" in mapped:
                full=str(row[mapped["datetime"]]).strip()
                m=re.fullmatch(r"(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})[ T]+(\d{1,2}:\d{2}:\d{2}(?:[.,]\d{1,6})?)",full)
                if not m:
                    raise ValueError("Invalid full datetime in row "+str(row_idx))
                date_text,time_text=m.group(1),m.group(2)
            else:
                date_text=row[mapped["day"]] if "day" in mapped else day
                time_text=row[mapped["time"]]
            current_day=iso_date(date_text).isoformat()
            if day and current_day!=day:
                raise ValueError("Export contains another date")
            if seen_date and current_day!=seen_date:
                raise ValueError("Multiple sessions mixed")
            seen_date=current_day
            stamp=normalize_utc_trade_timestamp(current_day,time_text)
            if stamp<last_stamp:
                raise ValueError("Out-of-order trade timestamps")
            last_stamp=stamp
            price=parse_brazil_number(row[mapped["price"]])
            qty=parse_brazil_number(row[mapped["qty"]])
            if price<=0 or abs(price/5-round(price/5))>1e-8:
                raise ValueError("Invalid WIN tick price")
            if qty<=0 or not qty.is_integer():
                raise ValueError("Invalid executed-contract quantity")
            if "trade_id" in mapped:
                ident=str(row[mapped["trade_id"]]).strip()
                if not ident or ident in seen_ids:
                    raise ValueError("Missing/duplicate trade ID")
                seen_ids.add(ident)
            count+=1
            if count>2_000_000:raise ValueError("Fail closed at trade cap")
            yield {"time_msc":stamp,"price":price,"quantity":int(qty),
                   "aggressor":side(row[mapped["side"]]),"symbol":current_symbol,
                   "day":current_day,"has_exchange_trade_id":"trade_id" in mapped}
        if count==0:raise ValueError("No trades in file")

def analyze_profit_export(path,*,symbol=None,day=None,target_contracts=500):
    source=Path(path)
    checked=list(iter_profit_export(source,symbol=symbol,day=day))
    count=len(checked)
    if count<1:raise ValueError("No trades")
    ident_status=all(x["has_exchange_trade_id"] for x in checked)
    minimal=({"time_msc":x["time_msc"],"price":x["price"],
              "quantity":x["quantity"],"aggressor":x["aggressor"]}
             for x in checked)
    # Read-only import and one deterministic, closed-bar signal model.
    from itertools import tee
    a,b=tee(minimal,2)
    minutes,quality=build_minutes(a)
    volume_policy=Policy(target_contracts=target_contracts)
    vbars,vmeta=build_closed_volume_bars(b,volume_policy)
    signals,checks=independent_signals(minutes)
    v_signals=detect_absorption(vbars,volume_policy)
    return {
        "status":"PRIVATE_PROFIT_EXPORT_CANDIDATE_RESEARCH_NO_BROKER_TRADES",
        "symbol":checked[0]["symbol"],"day":checked[0]["day"],
        "raw_source_sha256":source_hash(source),
        "trade_events":count,
        "exchange_trade_ids_available":ident_status,
        "duplicate_event_verification_if_no_id":"NOT_AVAILABLE" if not ident_status else "IDS_CHECKED",
        "m1_quality":quality,"m1_signals":signals,"m1_detector":checks,
        "volume_bars":vbars,"volume_bars_quality":vmeta,"volume_absorption_signals":v_signals,
        "trade_initiator_side_provided_by_file_not_inferred":True,
        "market_data_provenance_requires_user_license":True,
        "no_live_order_approval":True,
        "original_greenhouse_tracker_recovered":False,
    }

def main():
    ap=argparse.ArgumentParser(description="Private Profit Times&Trades-like CSV with explicit side: analyze without broker login")
    ap.add_argument("--csv",required=True)
    ap.add_argument("--symbol",default=None)
    ap.add_argument("--date",default=None)
    ap.add_argument("--volume-bar-contracts",type=int,default=500)
    ap.add_argument("--out",default="private_mt5/nq_profit_tape_analysis.json")
    opts=ap.parse_args()
    result=analyze_profit_export(opts.csv,symbol=opts.symbol,day=opts.date,
                                 target_contracts=opts.volume_bar_contracts)
    private_hash=private_output(result,opts.out)
    print(json.dumps({
        "status":result["status"],
        "symbol":result["symbol"],"day":result["day"],
        "trade_events":result["trade_events"],
        "aggressor_data_source":"EXPLICIT_CSV_COLUMN",
        "historical_trades_authenticated_by_exchange":False,
        "closed_volume_bars":len(result["volume_bars"]),
        "independent_volume_signals":len(result["volume_absorption_signals"]),
        "private_output":str(Path(opts.out).resolve()),
        "private_sha256":private_hash,
    },ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
