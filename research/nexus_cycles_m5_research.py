"""Run CA/C1/C2 M5 research on declared CSV/JSON or Yahoo GC=F proxy.

Use: python -m research.nexus_cycles_m5_research --input M5.csv --source "broker OHLC"
Or:  python -m research.nexus_cycles_m5_research --yahoo-proxy

No live order placement. Yahoo GC=F is NOT XAUUSD spot, and its quotes
cannot establish FBS execution profitability.
"""
import argparse
import json
import time
import urllib.request
from pathlib import Path

from src.nexus_cycles_m5 import Settings, chronological_report, load_bars, validate_bars


def fetch_yahoo_gc_m5():
    errors = []
    # Both endpoints refer to the same underlying provider, not independent feeds.
    for host in ("query1.finance.yahoo.com", "query2.finance.yahoo.com"):
        url = "https://" + host + "/v8/finance/chart/GC%3DF?interval=5m&range=1mo"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0", "Accept": "application/json"
        })
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                payload = json.load(response)
            result = ((payload.get("chart") or {}).get("result") or [None])[0]
            if not result:
                raise ValueError("No chart result")
            symbol = (result.get("meta") or {}).get("symbol")
            if symbol != "GC=F":
                raise ValueError("Wrong symbol, refusing unrelated market")
            quotes = ((result.get("indicators") or {}).get("quote") or [None])[0]
            if quotes is None:
                raise ValueError("Missing quote")
            now = int(time.time())
            bars = []
            for i, stamp in enumerate(result.get("timestamp") or []):
                ts = int(stamp)
                if ts % 300 or ts + 300 > now - 120:
                    continue
                try:
                    bars.append({
                        "time": ts,
                        **{k: float(quotes[k][i]) for k in ("open", "high", "low", "close")}
                    })
                except (ValueError, TypeError, KeyError, IndexError):
                    continue
            rows = validate_bars(bars)
            if len(rows) < 500:
                raise ValueError("Not enough completed M5 data")
            return rows
        except Exception as ex:
            errors.append(host + ": " + type(ex).__name__)
    raise RuntimeError("Yahoo GC=F M5 unavailable: " + "; ".join(errors))


def main(argv=None):
    p = argparse.ArgumentParser(description="Paper-only isolated M5 cycle research")
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", help="UTC timestamped 5-minute CSV/JSON with time/open/high/low/close")
    source.add_argument("--yahoo-proxy", action="store_true", help="fetch GC=F futures M5 (not XAUUSD)")
    p.add_argument("--source", default="user_supplied", help="Required source attribution for user CSV")
    p.add_argument("--fees-bps", type=float, default=8.0, help="illustrative ROUNDTRIP fee/spread, not measured")
    p.add_argument("--slippage-bps", type=float, default=2.0, help="illustrative adverse per-side slip")
    p.add_argument("--output", default="reports/research/nexus_cycles_m5.json")
    args = p.parse_args(argv)
    bars = fetch_yahoo_gc_m5() if args.yahoo_proxy else load_bars(args.input)
    source_name = ("Yahoo Finance GC=F 5m futures PROXY - not broker/spot fills"
                   if args.yahoo_proxy else args.source)
    config = Settings(fees_roundtrip_bps=args.fees_bps,
                      slippage_each_side_bps=args.slippage_bps)
    result = chronological_report(bars, cfg=config, source=source_name)
    result["data_bars"] = len(bars)
    result["first_utc"] = bars[0]["time"] if bars else None
    result["last_utc"] = bars[-1]["time"] if bars else None
    result["research_only"] = True
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf8")
    print("Wrote " + str(out))
    for variant, info in result["variants"].items():
        print(variant + " holdout " + str(info["holdout"]) +
              " cost stress " + str(info["holdout_2x_cost"]))
    print("UNVALIDATED HYPOTHESIS — no historical or real-money profit claimed")


if __name__ == "__main__":
    main()
