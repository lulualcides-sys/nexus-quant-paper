# ALPHA V6 — continuous execution, protective stop and genuine new-market challenge

This is an isolated draft-PR research experiment, **not a strategy approved for investment**.

## Fixed before reading any new BNB/XRP P&L

Existing ALPHA02 retest signal, confirmed H1/H4 trend filter from ALPHA V5,
1.5× ATR H1 initial stop, 4× ATR H1 take-profit, 72h maximum hold, 24h
cooldown, 0.75% all-in stop risk and assumed 10bps spot taker fee + 1bp
half-spread + 0,5,10bps slippage **per side** all unchanged.

**Major measurement repair:** V5 replay reset the historical features, bankroll,
stop and open positions at *each* calendar-month boundary, and repeated a
~10-day H4/H1 warmup on every month. V6 composes all 22 real months first,
verifies exactly contiguous M1, then constructs M5/H1/H4 once and carries the
bankroll, stops and pending H1 exits across boundaries. Both baseline and
candidate use this identical repaired, continuous engine, so their results
are comparable; V5 monthly books and V5 continuous books are NOT equivalent.

**ONE new candidate change**: after a closed M5 candle gains at least 2× the
H1 ATR measured at entry, the next candle may use a stop at the maximum of:
- original stop (never widen risk),
- exact assumed-fee-inclusive exit breakeven,
- that completed M5 close minus 2× the same frozen entry H1 ATR.

Stop is NOT applied to the candle which triggered it. All same-bar stop/target
collisions resolve to stop. Gaps can cause losses beyond theoretical 0.75%.
Unrealized month-end trades are carried forward. Final unrealized exposure is
marked including estimated exit frictions but never reported as closed profit.

## Comparisons and hard limitations

- SOLUSDT 2025-Jan–2026-Oct: **previously inspected**, development diagnostic.
- BNBUSDT and XRPUSDT 2025-Jan–2026-Oct: NEW market retrospective,
  separately reported and not forward / paper evidence; correlated to SOL.
- Real Binance public SPOT monthly M1 OHLCV ZIPs with published SHA256 checked;
  no replacement, rounding or synthetic missing bar fill; no claim of exact
  historic trading tick / lot precision since exchangeInfo not archived.
- 5000 USDT **independent virtual book per market**, not a shared 15,000-USDT
  portfolio nor a converted 30,000 BRL account. Fees are modeled, not actual
  recorded fills. Source asset: https://github.com/binance/binance-public-data
- Report all three assets even if losing, 0,5,10bps scenarios and **all**
  ledger CSVs, by exit month and period. If any monthly source missing or
  malformed, raise job failure rather than claim validation.

**Approval rule:** zero automatic approvals even for positive backtests.
One candidate family preselected from SOL results, at least two new correlated
markets, multiple hypothesis selection bias and no prospective orderbook/fill
data. Prospective paper trading is required before any live claim or order.
