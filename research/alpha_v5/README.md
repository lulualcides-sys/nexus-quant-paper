# ALPHA V5 — audit-driven filter correction, no profit guarantee

**Hypothesis fixed and committed BEFORE accessing new SOLUSDT 2025 P&L.**

**Actual diagnosis from 769 V4 filled/closed simulated trades, 5bps slippage
each side, BTC/ETH July–October and SOL January–October:**

| Exit category | Count | Net (USDT virtual) |
|---|---:|---:|
| Stop | 371 | -13,835.58 |
| Take profit | 169 | +12,177.97 |
| H1 regime / time exit next open | 229 | -3,975.24 |

Of early closes <=1h, 52 H1/time exits lost **-827 USDT** after costs.
The mismatch: V4 allowed a bullish setup while the most recent H1 close
could already be **below EMA50**, even though a subsequent check exits if
H1 is below EMA50. Confirmation on H1, H4 is a falsifiable causal hypothesis
to avoid contradictory and range-market long entries. These aggregates are
**multiple independent notional books**, not an executable portfolio.

## Exactly what changes

The 10 ALPHA entry rules, their M1/M5 timeframes, order fill model,
1.5H1 ATR stop, 4H1 ATR target, 72h timeout, 24h cooldown, 0.75%
theoretical risk, 10bps taker fee, 1bp half-spread and 0/5/10bps slippage
per side **remain identical to V4**. V5 adds ONLY:

- completed H1 EMA20 > EMA50 and last closed H1 close > EMA50, eliminating
  entry/exit contradiction;
- completed H4 EMA20 > EMA50, EMA50 rising against exactly 12 prior completed
  H4 bars and last closed H4 close > EMA20;
- 60 fully closed H4 candle warmup. No partial H1/H4 or future candles.

## Tests and evidence

- Diagnostic Jan–Oct 2026 SOLUSDT, previously examined and thus NOT unseen;
- NEW backward transfer Jan–Dec **2025 SOLUSDT**, original V4 strategy never
  tested on this market/period in these experiments. This is retrospective,
  earlier than development window, **not chronological forward OOS**.
- Two identical execution engines V4 and V5, 10 bot families, only the entry
  gate differs. Full Binance official SHA256 checked M1 ZIP and timestamp,
  strict missing/duplicate OHLCV rejection, no interpolation.
- Each month restarts 5000 USDT independent book; open month-end positions
  are **not** misrepresented as closed. We report their marked equity separately.
- 0,5,10 bps per side: every run yields CSV ledgers, JSON financial metrics
  including DD, win rate, PF, confidence interval when possible and source hashes.
- Study only, draft PR, no main merge, no paper/real orders.

**If V5 is not better in 2025 and 2026 after costs, it fails. A positive
historical interval never establishes stable profit; multi-hypothesis testing
and later forward paper data are required.**
