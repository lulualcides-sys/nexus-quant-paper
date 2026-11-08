# V8: No volume veto, require only confirmed breakout and strong retest close

### Diagnosis first — prior V7 four-market retrospective data

Four observed V5 control ledgers: BNB -1122.38 USDT (139 trades), XRP
-198.74 (92), ADA -859.33 (77), DOGE -126.84 (77). V7 added five
conditions and decreased BNB -741.90, XRP +153.70, ADA -750.80,
DOGE -261.12 (all 5bps modelled slippage per side). In the DIAGNOSTIC
classification of original V5 trades (which is NOT a V7/V8 executed
portfolio), rejecting **weak breakout strength** had net-negative results
on every examined market: BNB -504.81, XRP -355.59, ADA -496.45,
DOGE -326.03. Rejecting weak retest close LOCATION likewise: BNB
-54.00, XRP -194.36, ADA -64.89, DOGE -99.40. The additional volume
veto instead rejected winners in XRP +147.10, ADA +93.79, DOGE +259.53.
Avoiding a close too far above level also rejected winners in ADA
+127.47 and DOGE +211.34. Therefore those latter two conditions lack
robust ex ante justification, even before adding more market tests.

### Single frozen candidate — thresholds NOT fitted here
- Require original ALPHA02 M5 breakout/retest signal, H1/H4 trend
  guard V5 (unchanged).
- Last COMPLETED breakout M5 close >= prior high + 0.20× that bar's M5 ATR.
- Retest M5 candle closes in upper 40% of its own high–low range.
- Remove V7 artificial breakout-volume and 'chase' restrictions; original
  ALPHA02 already requires bullish retest close above broken level.
- ALL stops/target/exits/slippage/fees/quantity, 24h cooldown and 72h
  hold identical to frozen V5 continuous engine: no V6 profit protection.
- Start with 5000 USDT PER MARKET book, continuous across 22 months,
  theoretical 0.75% stop risk including fees+spread+slip.
- Scenario costs (each side) = 10bps taker + 1bp half-spread +
  slippage 0/5/10bps, not actual exchange order book fills.
- **New, never previously evaluated markets**: AVAX, LINK, LTC Binance
  public SPOT Jan 2025–Oct 2026; 66 verified monthly M1 files with
  SHA256 provider checksums. Each tested against untouched V5 and V7.
- Same monthly price and fills; causal use of only closed M5/H1/H4,
  no retrospective exclusion of stop trades after seeing the exit.
- Each result stored in raw ledger CSV and JSON. Must label zero trade
  sample as inconclusive; must not proclaim consistent profits based on
  a single 22-month backtest from correlated crypto assets.

All historical results here are retrospective, despite new market
checks. **Real profit is not guaranteed; no permission to promote to
production or operate money.** If negative, reject and explain. If
positive, require independent forward paper with real spread/slippage
and robust statistical confidence before activation.
