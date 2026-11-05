"""Memory-bounded B3 WINV26 tick->M1 aggregation for a manually acquired file.

Two passes: 1) enumerate cancellations; 2) aggregate noncancelled trades.
No trade tuples are retained in RAM. Unique deal IDs live in a temporary
SQLite primary-key table on disk, while only minute-level OHLC aggregates
remain in memory. This makes a 500MB+ B3 TXT feasible without allocating
millions of dict/tuple entries. Full-size runtime still needs real-world
benchmarking before making performance guarantees.

This import does not collect any B3 data online, does not execute orders,
and cannot establish how a live indicator responded to later corrections.
"""
from __future__ import annotations

import csv
import sqlite3
from collections import defaultdict
from datetime import timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from research.atlas_b3_ticks_oct13 import (
    DATE, SYMBOL, REQUIRED, _hash_file, _open_text, _trade_time,
)
from research.win_price_data import _number, _tick_check


def _records(path):
    archive, stream, member = _open_text(path)
    try:
        reader = csv.DictReader(stream, delimiter=";")
        if not reader.fieldnames:
            raise ValueError("Empty B3 header")
        reader.fieldnames = [s.strip().lstrip("\ufeff") for s in reader.fieldnames]
        names = set(reader.fieldnames)
        if not REQUIRED.issubset(names):
            raise ValueError("Missing B3 deal fields: " + ",".join(sorted(REQUIRED-names)))
        for line, record in enumerate(reader, 2):
            yield line, record
    finally:
        stream.close()
        if archive is not None:
            archive.close()


def _id(record, line):
    raw=str(record.get("CodigoIdentificadorNegocio") or "").strip()
    if not raw.isdecimal():
        raise ValueError(f"Line {line}: invalid trade ID")
    # Normalize 0012 and 12 as the same exchange identifier.
    return raw.lstrip("0") or "0"


def _belongs(record):
    return (str(record.get("CodigoInstrumento") or "").strip() == SYMBOL
            and str(record.get("DataNegocio") or "").strip() == DATE)


def _clock_sort(dt, identifier):
    return (dt, int(identifier))


def _new_agg(dt, identifier, price, quantity):
    key=_clock_sort(dt, identifier)
    return [key, key, price, price, price, price, quantity, 1]


def _accumulate(aggregate, dt, identifier, price, quantity):
    key=_clock_sort(dt, identifier)
    if key < aggregate[0]:
        aggregate[0]=key
        aggregate[2]=price
    if key > aggregate[1]:
        aggregate[1]=key
        aggregate[5]=price
    aggregate[3]=max(aggregate[3],price)
    aggregate[4]=min(aggregate[4],price)
    aggregate[6]+=quantity
    aggregate[7]+=1


def parse_b3_trades_streaming(path):
    """Return same M1+provenance interface as older in-memory importer.

    SQLite makes duplicate-ID detection exact on disk. Two passes are
    mandatory to ensure a cancellation logged later removes the original.
    Missing targets and unrecognized action codes fail closed.
    """
    path=Path(path)
    # Hash first for traceability; read only from local manually acquired file.
    provenance={
        "source_file":path.name,
        "sha256":_hash_file(path),
        "source":"B3 Listados negócios a negócio, user-supplied",
        "automatically_downloaded":False,
        "exchange_authenticated":False,
        "importer":"sqlite_two_pass_streaming_v1",
        "intraday_revisions_reconstructed_in_hindsight":True,
    }
    counters=defaultdict(int)
    cancellations=set()
    for line,record in _records(path):
        counters["read_rows"]+=1
        if not _belongs(record):
            continue
        counters["matched_contract_rows"]+=1
        identifier=_id(record,line)
        action=str(record.get("AcaoAtualizacao") or "").strip()
        if action=="2":
            if identifier in cancellations:
                raise ValueError(f"Line {line}: duplicate cancellation {identifier}")
            cancellations.add(identifier)
            counters["cancellation_records"]+=1
        elif action!="0":
            raise ValueError(f"Line {line}: unsupported trade action {action}")
    # These are only the minute-level candles; never accumulate raw deals.
    minutes={}
    cancelled_trade_ids_seen=set()
    with TemporaryDirectory(prefix="atlas-b3-ids-") as work:
        db=sqlite3.connect(str(Path(work)/"uniqueness.sqlite3"))
        try:
            db.execute("CREATE TABLE seen (id TEXT PRIMARY KEY) WITHOUT ROWID")
            db.execute("BEGIN")
            for line,record in _records(path):
                if not _belongs(record):
                    continue
                action=str(record.get("AcaoAtualizacao") or "").strip()
                if action=="2":
                    continue
                identifier=_id(record,line)
                if identifier in cancellations:
                    if identifier in cancelled_trade_ids_seen:
                        raise ValueError(f"Line {line}: duplicate cancelled original {identifier}")
                    cancelled_trade_ids_seen.add(identifier)
                    counters["cancelled_trades_removed"]+=1
                    continue
                if str(record.get("TipoSessaoPregao") or "").strip()!="1":
                    counters["non_regular_session"]+=1
                    continue
                dt=_trade_time(DATE,record["HoraFechamento"])
                if dt is None:
                    counters["outside_session"]+=1
                    continue
                price=_number(record["PrecoNegocio"])
                quantity=_number(record["QuantidadeNegociada"])
                _tick_check(price)
                if quantity<=0 or int(quantity)!=quantity:
                    raise ValueError(f"Line {line}: invalid traded quantity")
                try:
                    db.execute("INSERT INTO seen (id) VALUES (?)",(identifier,))
                except sqlite3.IntegrityError as exc:
                    raise ValueError(f"Line {line}: duplicate trade ID {identifier}") from exc
                minute=dt.replace(second=0,microsecond=0)
                if minute not in minutes:
                    minutes[minute]=_new_agg(dt,identifier,price,int(quantity))
                else:
                    _accumulate(minutes[minute],dt,identifier,price,int(quantity))
                counters["trade_records"]+=1
            missing=cancellations-cancelled_trade_ids_seen
            if missing:
                raise ValueError(f"Orphan cancellations: {len(missing)} (first {min(missing)})")
            db.commit()
        finally:
            db.close()
    bars=[]
    for minute,agg in sorted(minutes.items()):
        stamp=int(minute.astimezone(timezone.utc).timestamp())
        bars.append({
            "time":stamp,"open":agg[2],"high":agg[3],
            "low":agg[4],"close":agg[5],
            "volume":agg[6],"trade_count":agg[7],
        })
    if not bars:
        raise ValueError("No valid WINV26 B3 trades on 2026-10-13")
    provenance["counters"]=dict(counters)
    provenance["surviving_trades"]=sum(b["trade_count"] for b in bars)
    provenance["surviving_minutes"]=len(bars)
    provenance["market_day"]=DATE
    provenance["symbol"]=SYMBOL
    provenance["member"]=next((_open_text(path)[2],),path.name)
    return bars,provenance
