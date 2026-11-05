"""Import manually obtained B3 'Negócio a Negócio - Listados' trades.

NO automated download: B3 public consultation page forbids scraping.
Purpose: faithfully build WINV26 2026-10-13 M1 candles, then compare
only independently verified on-screen Tracker arrows. Never synthesize
empty minutes, never claim tick-touch equals a brokerage limit fill.

B3 header fields required (pt-BR): CodigoInstrumento, DataNegocio,
HoraFechamento, PrecoNegocio, QuantidadeNegociada,
CodigoIdentificadorNegocio, AcaoAtualizacao, TipoSessaoPregao.
Action 0 = new trade; 2 = cancellation in tested B3 fixture; unexpected
actions and orphan cancellations fail closed. Ties use trade sequence ID.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from io import TextIOWrapper
from pathlib import Path
from zipfile import ZipFile, is_zipfile

from research.win_price_data import TZ, _number, _tick_check
from research.atlas_win_oct13 import SYMBOL, DATE, MIN_CANDLES, labels_from_csv
from research.atlas_confluence_v3 import VARIANTS, v3_signal

REQUIRED = {
    "CodigoInstrumento", "AcaoAtualizacao", "PrecoNegocio",
    "QuantidadeNegociada", "HoraFechamento", "CodigoIdentificadorNegocio",
    "TipoSessaoPregao", "DataNegocio",
}
MAX_FILE_BYTES = 1_500_000_000
MAX_UNCOMPRESSED_BYTES = 1_500_000_000


def _hash_file(path):
    digest = sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _open_text(path):
    """Open single CSV/TXT or one-member ZIP from a *local*, manual download."""
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("Missing or oversized manually supplied B3 file")
    if is_zipfile(path):
        archive = ZipFile(path)
        members = [x for x in archive.infolist() if not x.is_dir()
                   and x.filename.lower().endswith((".csv", ".txt"))]
        if len(members) != 1 or members[0].file_size > MAX_UNCOMPRESSED_BYTES:
            archive.close()
            raise ValueError("B3 ZIP must contain one CSV/TXT member of acceptable size")
        raw = archive.open(members[0], "r")
        wrapper = TextIOWrapper(raw, encoding="utf-8-sig", errors="strict", newline="")
        return archive, wrapper, members[0].filename
    raw = path.open("r", encoding="utf-8-sig", newline="")
    return None, raw, path.name


def _trade_time(day, raw):
    """HHMMSSmmm, preserve millisecond order for identical minute candles."""
    s = str(raw).strip()
    if len(s) != 9 or not s.isdigit():
        raise ValueError(f"Invalid 9-digit trade clock: {s!r}")
    hh, mm, ss, ms = int(s[:2]), int(s[2:4]), int(s[4:6]), int(s[6:])
    if hh > 23 or mm > 59 or ss > 59:
        raise ValueError("Invalid B3 trade time")
    if not (9 * 60 <= hh * 60 + mm < 18 * 60 + 25):
        return None  # ignore trades outside regular WIN session
    return datetime.strptime(day + " " + s[:6], "%Y-%m-%d %H%M%S").replace(
        microsecond=ms * 1000, tzinfo=TZ)


def parse_b3_trades(path):
    """Two-phase WINV26 filtering and cancellation resolution; no lookahead.

    The entire file is used only to resolve final official trade corrections.
    Such revised historical data cannot by itself reconstruct *when* a live
    subscriber learned of a cancelled trade; do not claim live equivalence.
    """
    import csv
    original = Path(path)
    provenance = {
        "source_file": original.name,
        "sha256": _hash_file(original),
        "source": "B3 Listados negócios a negócio, user-supplied",
        "automatically_downloaded": False,
        "exchange_authenticated": False,
    }
    archive, stream, member = _open_text(original)
    trades = {}
    cancelled = set()
    counters = defaultdict(int)
    try:
        reader = csv.DictReader(stream, delimiter=";")
        if not reader.fieldnames:
            raise ValueError("Empty B3 header")
        names = {s.strip().lstrip("\ufeff") for s in reader.fieldnames}
        if not REQUIRED.issubset(names):
            raise ValueError("Missing B3 deal fields: " + ",".join(sorted(REQUIRED-names)))
        for line, record in enumerate(reader, 2):
            counters["read_rows"] += 1
            if not record.get("CodigoInstrumento") or record["CodigoInstrumento"].strip() != SYMBOL:
                continue
            if record.get("DataNegocio", "").strip() != DATE:
                continue
            counters["matched_contract_rows"] += 1
            if record.get("TipoSessaoPregao", "").strip() != "1":
                counters["non_regular_session"] += 1
                continue
            dt = _trade_time(DATE, record["HoraFechamento"])
            if dt is None:
                counters["outside_session"] += 1
                continue
            ident = str(record.get("CodigoIdentificadorNegocio") or "").strip()
            if not ident or not ident.isdecimal():
                raise ValueError(f"Line {line}: invalid trade ID")
            key = int(ident)
            action = str(record["AcaoAtualizacao"]).strip()
            if action == "2":
                if key in cancelled:
                    raise ValueError(f"Line {line}: duplicate cancellation {key}")
                cancelled.add(key)
                counters["cancellation_records"] += 1
                continue
            if action != "0":
                raise ValueError(f"Line {line}: unsupported trade action {action}")
            price = _number(record["PrecoNegocio"])
            quantity = _number(record["QuantidadeNegociada"])
            _tick_check(price)
            if quantity <= 0 or int(quantity) != quantity:
                raise ValueError(f"Line {line}: invalid traded quantity")
            if key in trades:
                raise ValueError(f"Line {line}: duplicate trade ID {key}")
            trades[key] = (dt, key, price, int(quantity))
            counters["trade_records"] += 1
    finally:
        stream.close()
        if archive is not None:
            archive.close()
    missing = cancelled - set(trades)
    if missing:
        raise ValueError(f"Orphan cancellations: {len(missing)} (first {min(missing)})")
    remaining = [trade for key, trade in trades.items() if key not in cancelled]
    remaining.sort(key=lambda x: (x[0], x[1]))
    daily = defaultdict(list)
    for dt, ident, price, qty in remaining:
        minute = dt.replace(second=0, microsecond=0)
        daily[minute].append((dt, ident, price, qty))
    bars = []
    for minute in sorted(daily):
        ordered = daily[minute]
        prices = [x[2] for x in ordered]
        ts = int(minute.astimezone(timezone.utc).timestamp())
        bars.append({
            "time": ts, "open": prices[0], "high": max(prices),
            "low": min(prices), "close": prices[-1],
            "volume": sum(x[3] for x in ordered),
            "trade_count": len(ordered),
        })
    if not bars:
        raise ValueError("No valid WINV26 B3 trades on 2026-10-13")
    if len({b["time"] for b in bars}) != len(bars):
        raise AssertionError("Minute consolidation duplicated timestamps")
    provenance["member"] = member
    provenance["counters"] = dict(counters)
    provenance["surviving_trades"] = len(remaining)
    provenance["surviving_minutes"] = len(bars)
    provenance["market_day"] = DATE
    provenance["symbol"] = SYMBOL
    return bars, provenance


def match_signals(bars, provenance, evidence_csv=None):
    """Alignment study only, never a fake 27-trade brokerage backtest."""
    labels = labels_from_csv(evidence_csv)
    regular = [b for b in bars if 9 * 60 + 10 <= (
        datetime.fromtimestamp(b["time"], timezone.utc).astimezone(TZ).hour * 60 +
        datetime.fromtimestamp(b["time"], timezone.utc).astimezone(TZ).minute
    ) < 17 * 60 + 30]
    report = {
        "contract": SYMBOL, "date": DATE, "provenance": provenance,
        "status": "awaiting_verified_data_and_labels",
        "m1_candles": len(regular),
        "minimum_required": MIN_CANDLES,
        "verified_labels": len(labels),
        "promotional_claim_27_signals_not_verified": True,
        "reproduced_tracker_formula": False,
        "trades_executed": False, "winrate": None, "net_brl": None,
        "matches": None,
    }
    if len(regular) < MIN_CANDLES:
        report["status"] = "insufficient_win_v26_m1_coverage"
        return report
    if not labels:
        report["status"] = "awaiting_verified_tracker_labels"
        return report
    lookup = {bar["time"]: i for i, bar in enumerate(bars)}
    if any(ts not in lookup for ts, _ in labels):
        raise ValueError("Video label without authentic WINV26 candle")
    report["matches"] = {}
    for variant in VARIANTS:
        eligible = [(lookup[ts], s) for ts, s in labels if lookup[ts] >= 75]
        hits = sum(v3_signal(bars, i, variant) == s for i, s in eligible)
        report["matches"][variant] = {
            "checked": len(eligible),
            "same_market_candle_and_side": hits,
            "agreement_pct": round(100 * hits / len(eligible), 2) if eligible else None,
        }
    report["status"] = "video_label_alignment_only"
    return report


def main():
    import argparse
    import json
    parser = argparse.ArgumentParser(description="Offline B3 manually obtained tick data, WINV26 Oct13")
    parser.add_argument("--b3-file", required=True)
    parser.add_argument("--tracker-labels", default=None)
    parser.add_argument("--out", default="research/results/atlas_b3_oct13_replay.json")
    args = parser.parse_args()
    bars, source = parse_b3_trades(args.b3_file)
    report = match_signals(bars, source, args.tracker_labels)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "m1": report["m1_candles"],
                      "verified_labels": report["verified_labels"],
                      "source_sha256": source["sha256"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
