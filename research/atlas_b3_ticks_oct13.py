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
    """Memory-bounded, two-pass deal-level parser (preserves public API)."""
    from research.atlas_b3_streaming import parse_b3_trades_streaming
    return parse_b3_trades_streaming(path)


def match_signals(bars, provenance, evidence_csv=None, coverage_csv=None):
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
    # A count threshold alone does NOT establish continuous M1 coverage:
    # 400+ real trades can still omit a decisive market minute. Mirror the
    # strict session gate used by the Profit importer; do not synthesize bars.
    from research.atlas_win_oct13 import SESSION_START, SESSION_END
    minutes = set()
    for bar in regular:
        clock = datetime.fromtimestamp(bar["time"], timezone.utc).astimezone(TZ)
        if clock.date().isoformat() == DATE:
            minute = clock.hour * 60 + clock.minute
            if SESSION_START <= minute < SESSION_END:
                minutes.add(minute)
    expected = set(range(SESSION_START, SESSION_END))
    missing = sorted(expected - minutes)
    report["session_expected_m1"] = len(expected)
    report["session_observed_m1"] = len(minutes)
    report["missing_session_minutes"] = len(missing)
    report["missing_first_20"] = [f"{m//60:02d}:{m%60:02d}" for m in missing[:20]]
    report["session_complete"] = not missing
    if len(minutes) < MIN_CANDLES:
        report["status"] = "insufficient_win_v26_m1_coverage"
        return report
    if missing:
        report["status"] = "incomplete_session_no_signal_replay"
        return report
    if coverage_csv is not None:
        from research.atlas_tracker_observability import (
            parse_coverage_csv, score_observable_intervals,
        )
        # A complete continuous recording MAY genuinely show zero Tracker
        # arrows. Its user-supplied coverage claim is not independently proven.
        report["observable_alignment"] = score_observable_intervals(
            bars, labels, parse_coverage_csv(coverage_csv)
        )
        report["status"] = "conditional_full_observation_metrics_not_live"
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
    parser.add_argument("--observed-windows", default=None,
                        help="CSV attesting continuous complete Tracker signal recording")
    parser.add_argument("--out", default="research/results/atlas_b3_oct13_replay.json")
    args = parser.parse_args()
    bars, source = parse_b3_trades(args.b3_file)
    report = match_signals(bars, source, args.tracker_labels, args.observed_windows)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "m1": report["m1_candles"],
                      "verified_labels": report["verified_labels"],
                      "source_sha256": source["sha256"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
