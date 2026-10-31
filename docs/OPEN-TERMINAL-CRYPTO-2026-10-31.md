# NEXUS Quant — OpenTerminal and crypto research (31/10/2026)

Original inspiration: https://github.com/ErTasselli/OpenTerminal (MIT).
OpenTerminal was evaluated for data-provider architecture, news, macro calendar and cache.
We did **not** install OpenTerminal, copy its whole UI, or integrate paid endpoints.

## Implemented
1. `src/market_quality.py`: fail-closed OHLC/time checks, age cap, ordered timestamps, no incomplete candles. Cripto additionally rejects discontinuous H1 candles.
2. `src/feed.py`: existing EUR/USD, USD/JPY, gold future GC=F, ES=F, CL=F historical feed still Yahoo only; retries query2 hostname after query1 failure and validates age/quality before entering H1/H4 paper engine. These are **two Yahoo domains, NOT two independent providers**.
3. `src/crypto_paper.py`: 4 isolated H1 virtual research books (BTCUSDT and ETHUSDT × EMA20 pullback in EMA50>EMA200 trend, Channel20 breakout). Long-only Binance spot, no leverage, no real order, no margin, no exchange secrets.
4. `src/crypto_runner.py` + `.github/workflows/crypto-paper.yml`: hourly 24/7 scans and one standalone Telegram **daily-only** crypto digest, independent from existing finance monitors; no entry/exit alerts.
5. `tests/test_crypto_paper.py`, `tests/test_market_quality.py`, `tests/test_crypto_runner.py`: deterministic offline coverage, state safety, missing feeds, fees and gap fill. All test claims require CI passing; actual Binance connectivity requires separate live verification.

## Crypto rules and risk
- Each of 4 books starts with **1,000 USDT virtual** on first observation; *no historical trades invented*.
- Symbol/venue: `BTCUSDT`, `ETHUSDT` on **Binance Spot**, H1 only, public market data from `data-api.binance.vision` or `api.binance.com` (same exchange, two endpoints, not independent markets).
- Signal from **completed previous bar**; position in paper model at **next candle open**; these are modeled/hypothetical fills (not actual executed quotes). Trades are simulated only on post-initialization candles, and they can be processed retroactively after downtime. Never represent results as actual broker performance.
- Buying only; maximum notional 1× own virtual equity, maximum planned stop loss **0.5%** per new trade before slippage and gaps. Stop 1.5× ATR; trailing based on completed closes after +1R, 2× ATR behind best close. Time/EMA50 exit.
- Assumed fee: 0.10% each side; slippage: 0.05% each side, modeled. No funding, financing, or short sales. Values in **USDT**, not settled fiat USD.
- Stop gaps use adverse open. No new entry in the same candle after exit. UTC market bars and America/Sao_Paulo report day.
- Cached/outdated quotes never used for paper decisions. If entire feed is unavailable, journal must not add trades; financial monitor unchanged.
- Spot USDT can depeg; availability of endpoints in GitHub-hosted runtime is not guaranteed. Binance may rate-limit or geoblock market data. Never circumvent provider restrictions.

## Remaining P2 (NOT DONE)
- Independent, instrument-equivalent **second** financial price vendor (Yahoo mirrors alone are not independence); no futures↔ETF substitution.
- Macro calendar filter: needs archived event times and robust point-in-time methodology before adding to strategy decisions. Do not presume event filtering improves profitability.
- Crypto longer walk-forward backtest and verified prospective track record before promoting any strategy or increasing exposure.
- Cross-source pricing sanity and discrepancy alerts; only when source licensing and compatible timestamps/markets are confirmed.

**Deployment:** Only after passing PR CI and explicit merge to `main` will scheduled GitHub Actions activate. No real-money trades and no guaranteed profit.
