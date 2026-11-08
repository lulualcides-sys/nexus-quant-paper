# ALPHA 10 — isolated research, NOT operational

Branch: `research/alpha-10-m1m5-20261108`. This laboratory does not import `src.runner`, does not change `state/`, schedules, ATLAS, bots, brokerage connections, or Telegram. No real trades are possible.

## Frozen protocol (08 November 2026, before seeing final-month results)

- Source: Binance public **spot** OHLCV, exact pair `BTCUSDT` and `ETHUSDT`, not futures, 1-minute full monthly archives for **2026-08**, **2026-09**, **2026-10**; M5 is strictly a 5x aggregation of the same source's M1.
- Verify official provider `.CHECKSUM` SHA256 of each zip, full 1m coverage, UTC grid, duplicates, OHLCV bounds and declared spot tick `0.01 USDT` at download. If a source fails, **NOT_VALIDATED**, never fabricate candles. If a historical symbol tick changed, investigate independently; do not round invalid prices to force acceptance.
- Time split fixed: August training / September validation / October **final retrospective holdout**. No parameter search; rules in `bots/` are frozen before reading October P&L. Forward paper remains missing.
- Long-only spot, 5000 **USDT** virtual per robot/market (NOT R$30,000), 0.75% maximum theoretical initial risk/entry; notional capped below 100% cash, one concurrent position, no leverage, no martingale. Return units remain **USDT**, with no invented BRL/USD conversion.
- Candle-close at `t` signals only entry at NEXT M1/M5 candle open. Signal modules receive a read-only prefix of candles, preventing future access. 1.5 ATR stop (minimum 0.1% price); 1.8 R target; maximum 120 M1 bars or 24 M5 bars. Inside bar, STOP first on both-hit ambiguity. No fill at an unobserved past candle, and no quote/order-book simulation.
- Costs are explicit **assumptions**, not venue-verified: 10 bps taker commission per side, 1 bps half-spread per side, plus stress 0/5/10 bps slippage **per side**. WIN tick size NEVER transferred to crypto.
- Separate train/validation/test ledgers, plus separate costs, drawdowns, monthly returns and bootstrap CI of daily OOS net P&L when >=100 closed trades across >=15 active days. 20 model/pair hypotheses are compared; single-month/bootstrap intervals are not multiple-test-adjusted. Zero trades = inconclusive, not a measured 0 return.
- **Technical approval count is always zero** pending sufficient independent periods, measured execution costs and forward evidence. Positive OOS net/PF alone does not approve any model.

## Strategies
| File | Market timeframe | Economic hypothesis |
|---|---|---|
| alpha01_volume_exhaustion.py | M1 | Sweeps + candle volume exhaustion |
| alpha02_breakout_retest.py | M5 | Confirmed breakout then retest |
| alpha03_vwap_deviation.py | M1 | Mean reversion below observed day VWAP |
| alpha04_ema_atr_pullback.py | M5 | Trend pullback and ATR risk |
| alpha05_liquidity_rejection_proxy.py | M1 | OHLCV lower wick proxy; not real absorption |
| alpha06_volatility_momentum.py | M5 | Expanding volatility momentum |
| alpha07_regime_mean_revert.py | M5 | Weak-trend mean reversion |
| alpha08_opening_range_crypto.py | M5 | UTC-day opening window proxy (24/7 crypto; not exchange auction) |
| alpha09_consolidation_continuation.py | M1 | Range compression and breakout |
| alpha10_adaptive_regime.py | M5 | Predefined trend/range switch |

## Reproduction

```sh
python -m unittest tests/test_alpha_lab.py -v
python -m research.alpha.run --out artifacts/alpha
```

No third-party Python dependency required. `artifacts/alpha/source_manifest.json` includes SHA256s, provider URLs, UTC months and checked row counts. `results.json` contains three splits, 0/5/10 bps scenarios, ledger paths, costs, P&L, sample sizes and status. `results.md` ranks OOS candidate/market combinations. Ledger CSVs contain timestamps, raw and modeled fills, sizes, costs, net USDT, and exit reason. GitHub Actions uploads these as an immutable-run artifact retained 30 days; binary market data are not committed.

Use public source terms at https://github.com/binance/binance-public-data and https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md. Backtest selection bias: Bailey et al., *The Probability of Backtest Overfitting*, DOI 10.21314/JCF.2016.322.

## Known boundaries

Candles cannot identify queue priority, spread by second, market impact, precise intra-bar path, exchange outages or actual fillability; stop-first is deliberately conservative but still approximate. Stop-gaps can exceed 0.75% modeled intended risk. This is research, not financial evidence for production deployment. July/October 2026 ATLAS WIN source research and rejected PR #33 are intentionally **not used**. Binance public-archive download access, tick metadata and historical integrity are runtime gates.
