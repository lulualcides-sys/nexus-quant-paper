# ALPHA V2 — custo, regime e liquidez (research only)

Companion to draft [PR #34](https://github.com/lulualcides-sys/nexus-quant-paper/pull/34).
**Unchanged baseline:** all original ALPHA 01–10 signal rules. Filter wrapper is a separate research module; no imports into production src/, state/, scheduled workflows or any broker. The study MUST NOT send orders, merge itself or alter ATLAS paper.

## Hypotheses and frozen gating

New filter rejects raw ALPHA signals if the distance to the 1.8R target is less than **2× the modeled round-trip execution costs** in quote basis points. Model assumes 10bps taker fee + 1bps half-spread + 5bps slip, **each side** => 32bps round trip. This is an economic viability heuristic, not proof the target can be reached. Next, require volume >=60% of preceding 20 completed candles' average, ATR/close <=1.8%, and trend/regime aligned on completed EMA50/EMA200 with 24-bar slope. Overbought trend >78 RSI vetoed. Reversal setups avoid deep bearish regimes and RSI below 14. All thresholds were fixed **before downloading new July and November data**. No tuned per-bot thresholds.

No change to entry next-open, stop/target, all-in stop sizing (0.75% theoretical without gap), 5000 USDT virtual balance per pair, two-sided estimated costs and conservative intrabar collision. The filter is applied at the *signal candle close*. 0,5,10bps slip scenarios use **same frozen decision** based on the 5bps primary cost model.

## Data partitions

- **July 2026:** previously uninspected **backward** stress test; not chronological forward validation.
- **August–September 2026:** previously inspected development months, not new out-of-sample.
- **October 2026:** already inspected and contaminated by prior improvement decisions; diagnostic only.
- **November 1–7 2026:** previously uninspected **retrospective later-period** test; at most a single week, not paper forward.
- Fully month-aligned public SPOT Binance M1 ZIP files, plus seven daily archives for the November period. M5 reconstructed only from exact contiguous groups of 5 real M1. Each file verified against Binance's published .CHECKSUM SHA256. Any missing/invalid period stays unavailable; no synthetic P&L.
- Source terms: https://github.com/binance/binance-public-data

## Run and interpret

```
python -m unittest discover -s tests -p 'test_alpha_v2.py' -v
python -m research.alpha_v2.run --out artifacts/alpha-v2
```

`results.json`: per model/pair/period original baseline (5bps) vs filtered (5bps and 0/10bps stress on July, October, November), full financial metrics and counts of gate rejections. `results.md` comparison. `ledgers/` all virtual closed operations; `source_manifest.json` SHA256, periods, failures. A green CI verifies technical reproducibility only. No strategy is auto-approved by positive P&L: independent future periods, better execution-cost data and multiple hypothesis controls still required.

**Selection caution:** these filters were motivated by observed baseline losses; August/September/October are therefore development data. In the new checks, July is earlier than the development window and November 1–7 is not forward paper. Zero trades means inconclusive, not success.
