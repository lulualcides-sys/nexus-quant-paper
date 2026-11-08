# ALPHA V4 — H1 regime, original ALPHA M1/M5 entries (RESEARCH)

**Frozen 08 November 2026 before testing SOLUSDT.** This is a new cross-market falsification hypothesis, not a promise of returns. Prior tests V1–V3 failed; separate PR #35 already examined 22 months of BTC/ETH. Therefore BTC/ETH July–October are **previously exposed** and cannot be called new independent evidence. SOLUSDT July–October offers a different market never used in our ALPHA experiments; it is retrospective and correlated with major crypto, not prospective forward paper.

## Fixed assumptions

- Strategy set: the **10 original** `research/alpha/bots/` hypotheses (unaltered) on their own M1/M5 timeframes.
- Gate: only the most recently CLOSED H1 candle, EMA50>EMA200, EMA50 ascending 12 H1 bars, H1 close above EMA20, H1 RSI 48–76, at least 0.7× prior 20 bar volume. Gate not evaluated before 210 completed H1 bars. The projected 4×H1 ATR target must exceed three times the modeled full 32bps round-trip principal costs.
- Entry: earliest *next* M1/M5 candle open after the signal closes. Stop = 1.5× last closed H1 ATR (minimum 0.2% entry price); target = 4× same H1 ATR; H1 close under EMA50 or 72h maximum triggers exit next candle OPEN; after closing a position, 24h cooldown. Stop first for candle with both target and stop, pessimistic gap below stop.
- Fees: 0.10% taker and 0.01% assumed half-spread **per side**, slippage scenarios 0/0.05/0.10% **per side**. These are scenario assumptions, not observed level-two fill data. No market order, leverage, short, grid, averaging losses. Risk max theoretical stop-loss 0.75% per book including modeled both-way friction, no gap guarantee.
- Capital: 5,000 USDT virtual **per combination** (30 independent books; neither single R$30k bank nor live fills).
- Data: Binance public SPOT M1 monthly July–October 2026, BTCUSDT/ETHUSDT/SOLUSDT; official SHA256 `.CHECKSUM` verified for each zip, microsecond open converted to Unix seconds, complete UTC minute grid, OHLCV/price-precision validation. M5 and H1 generated from exact groups of completed M1 candles. No fabrication/interpolation. `SOLUSDT` precision threshold 0.001 is historical sanity checking, **not** certified exact 2026 exchange trading tick. Real order validity would require archived exchangeInfo and step-size evidence.
- Monthly isolation: no carry-over of open positions between months; month-end OPEN positions reported separately, **not** silently booked as win/loss. Realized results must be compared with attention to open exposure. 
- Source: https://github.com/binance/binance-public-data . No third-party Python dependencies.
- Metrics: sample size, win rate, net PnL USDT, PF, costs, DD, 0/5/10 bps, confidence interval by day when sample sufficient, and complete CSV ledger by robot/market/month/scenario.

## Reproduce

```bash
python -m unittest discover -s tests -p 'test_alpha_v4.py' -v
python -m research.alpha_v4.run --out artifacts/alpha-v4
```

**No version may be automatically promoted**: results here are monthly backtests not forward trading, BTC/ETH historical data already looked at, one market SOL only, costs approximate, multiple testing not adjusted. If negative, reject. If positive but insufficient, classify **INCONCLUSIVE** until long genuine future paper and execution verification. Never change the history to get a positive number.
