# Nexus Quant GOLD V6 — outside-development-window validation (paper only)

## Why this exists

The historical V4 ~5.7% return came from a pre-inspected ~30-day Yahoo GC=F proxy sample with estimated execution costs. A number of exit experiments performed worse on an incomplete second feed. **Do not infer a 5.7% monthly return from that period.** Number of trades is for statistical power; it is not an obligatory 200-trades/month quota.

## Locked hypothesis before running V6

- Test the **unchanged frozen V4-without-Momentum rules**. No new confirmation filters, no search/optimization.
- Signal timeframe M5. M5 mid OHLC signal from Dukascopy bid/ask candle sides (not tick-synchronous highs). Signal after completed candle, filled at next complete M5 opening quote if adjacent.
- EMA20 reclaim, Channel12 break, Pivot Sweep, Range Edge Rejection priority as in V4. Momentum_2BAR disabled as in V4 post-hoc ablation; this was already retrospectively selected, so test is NOT independent hypothesis discovery.
- Stop 3×ATR(10), target 3R, timeout 36 closed M5 bars, 0.75% stop risk maximum, 1x nominal cap, whole ounce lots (0.01 lots for 100oz standard), one open XAU position. This is a **historical virtual portfolio**, not an order to a broker.
- Capital US$5,000 at each experiment; no reinvestment from or interference with original bots.

## Source, days, and execution

Use `https://datafeed.dukascopy.com/datafeed/XAUUSD/{YYYY}/{zero_based_MM}/{DD}/{BID|ASK}_candles_min_1.bi5` (Dukascopy candles). **June 25–30, 2026 is indicator warm-up only**. Evaluation uses full calendar months **July, August, September 2026**, prior to the V4 Oct-Nov development window. This is a *historical out-of-period transfer*, not prospective forward, and other previous project work may have inspected this broad historical period.

The downloads are LZMA `.bi5`, decoded as `>IIIIIf`, price scale 1000 USD/oz. Fail closed on unexpected scale, inverted BID/ASK, duplicate minute, missing single side, corrupt record, too few days, or missing quote files. Only complete synchronized 5-minute buckets; never interpolate missing minutes or substitute futures prices. Network errors abort the evaluation; **zero means unavailable, not break-even**. Source SHA256 per day and side recorded for audit. Separate provider and FBS quote execution are not equivalent.

- Long opens at ASK M5 open + slippage, closes at BID stop/target/close − slippage. Short opens at BID open − slippage, closes at ASK stop/target/close + slippage. **Actual Dukascopy spread is included in quote-side fills**, not charged a second time.
- Scenarios: additional execution slippage **US$0 / 0.15 / 0.75 / 1.50 per ounce PER SIDE**; swap, broker commission, requotes and broker-specific spread not modeled. Stops filled at worse opening quote after gap; favorable takeprofit gaps capped at limit price. Where intrabar stop and target both touched, **stop first** (conservative); actual tick sequence unavailable.
- No new entry if source is not 5-minute adjacent. An open position occupies a candle even if the stop is hit intra-bar; never reenter at the earlier open. A position can remain through a data gap and is evaluated using the next observed BID/ASK open (risk may be larger than stop plan).
- Drawdown covers **closed-trade realized equity only**; floating equity dips may be larger. Final open position marked to opposite quote. Not all overnight carry costs represented.

## Predeclared evaluation (no post-hoc tuning)

- Four scenarios with **the same signal rules and fixed stop/target**; report total gross/net, # unique closed trades, profit factor, win rate, max realized drawdown, no. per source signal, and isolated monthly folds (July/Aug/Sep) at US$5000 start each fold.
- Daily P&L bootstrap 3000 samples/seed 20261110 with 95% percentile CI for closed trades. Daily trades are serially correlated: the IID day bootstrap is **only a fragility diagnostic**, not a rigorous statistical guarantee or a true confidence interval under all time dependencies.
- **Research-screen** (not live approval) requires >=150 closed trades, positive July/Aug/Sep separately under BOTH US$0.15/side and US$0.75/side slippage, stress max closed-equity DD <=12%, and the daily bootstrap 95% range excludes 0 at normal costs. Even that wouldn't approve actual trading. If data unavailable, do not claim anything.
- No automatic optimization based on the test. Even if it loses, preserve both codes and negative results, explain why, and require future unexamined prices + real broker bid/ask costs before considering market orders.

## How to reproduce

```bash
python -m unittest tests.test_xau_v6_bidask_research -v
python -m research.xau_v6_bidask_research --workers 6
```

GitHub Actions: `.github/workflows/xau-v6-bidask-validation.yml`. This workflow reads historical public data, writes research JSON, archives it as a CI artifact and has **no write permissions, broker API, account credentials, production state changes, or automated trading**.