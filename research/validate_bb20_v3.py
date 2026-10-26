"""Audit the DEPLOYED BB20 v3 signal with the same frozen 2026-10-26 M15 bars.

Preserves original v2 historical outcomes. Does not touch simulated paper
accounts or suggest broker execution.
"""
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

from research.backtest_bb20_mtf import analyze

SOURCE = Path("research/results/bb20_usdcad_m15_1mo_2026-10-26_bars.json.gz")
ORIGINAL = Path("research/results/bb20_usdcad_m15_1mo_2026-10-26.json")
OUT = Path("research/results/bb20_m15_v3_engine_validation_2026-10-26.json")
MD = Path("research/results/bb20_m15_v3_engine_validation_2026-10-26.md")


def main():
    baseline = json.loads(ORIGINAL.read_text(encoding="utf-8"))
    with gzip.open(SOURCE, "rt", encoding="utf-8") as f:
        rows = json.load(f)["candles"]
    date = datetime.strptime(baseline["timestamp_utc"], "%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc)
    now = int(date.timestamp())
    result = analyze(rows, now, source="frozen Yahoo CAD=X M15 archive")
    if result["source_sha256"] != baseline["source_sha256"]:
        raise ValueError("Data fingerprint changed: REFUSE to compare")
    if result["closed_n"] != 34 or abs(result["realized_pnl_usd"] - 0.38277) > 0.03:
        raise AssertionError(
            f"Live-entry engine does not match pre-registered v3 research! "
            f"Trades={result['closed_n']}, pnl={result['realized_pnl_usd']}."
        )
    if result["win_rate_pct"] is None or abs(result["win_rate_pct"] - 35.2941) > 0.01:
        raise AssertionError("Win rate differs between candidate and deployed logic")
    result["deployed_entry_rule"] = "bb20_m15_sma20_touch_h1_ema50_trend_v3"
    result["deployed_trailing_rule"] = "close_trailing_no_tp_v1"
    result["provenance"] = {
        "frozen_sha256": baseline["source_sha256"],
        "v2_historical_pnl_usd": baseline["realized_pnl_usd"],
        "v2_historical_trades": baseline["closed_n"],
        "note": "Identical historical data. Changes include M15 line and H1 trend; this is in-sample selection, not independently validated."
    }
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    MD.write_text(
        "# Audit: BB20 H1 trend + M15 SMA20 pullback, deployed engine\n\n"
        "- Candles: frozen USD/CAD M15 from Sep 26 to Oct 26, 2026.\n"
        "- Old v2: " + str(baseline["closed_n"]) + " closed, " +
        format(baseline["realized_pnl_usd"], "+.2f") + " USD realized.\n"
        "- New v3: " + str(result["closed_n"]) + " closed, " +
        format(result["realized_pnl_usd"], "+.2f") + " USD realized, " +
        format(result["win_rate_pct"], ".2f") + "% wins.\n"
        "- Open position marked separately: " +
        format(result["pnl_including_open_usd"], "+.2f") + " USD total.\n"
        "- No change to initial risk 0.75%, H1 ATR stop, no-TP trailing stop.\n"
        "- **Only the entry location and H1 confirmation changed**; data-derived performance is not proof of future profits.\n"
        "- First half lost about US$ 4.10 and second half gained about US$ 4.50 when evaluated independently: this is unstable.\n"
        "- The brokerage has no real or FBS fills. Yahoo M15 candles may differ from actual bid/ask.\n\n"
        "Saved transaction-level audit: [JSON](bb20_m15_v3_engine_validation_2026-10-26.json).\n",
        encoding="utf-8"
    )
    print("VALIDATED_V3=" + json.dumps({
        "trades": result["closed_n"],"wins": result["wins_n"],
        "losses": result["losses_n"],"win_pct": result["win_rate_pct"],
        "net_usd": result["realized_pnl_usd"],
        "total_mtm_usd": result["pnl_including_open_usd"],
        "source_sha256": result["source_sha256"]
    }))


if __name__ == "__main__":
    main()
