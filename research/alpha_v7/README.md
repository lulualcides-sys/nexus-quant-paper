# V7 — original breakout/retest versus a single frozen entry-quality hypothesis

**No actual trading, no paper forwarding, no approval.**

## Diagnostic basis (previously inspected V5 continuous)
BNBUSDT: 139 trades, 85 stops = -2,742.58 USDT, 36 take-profits
= +1,981.74, and 18 H1/time exits = -361.55. Total -1,122.38.
XRPUSDT: 92 trades, 53 stops = -1,974.88, 26 take-profits
= +2,015.36, 13 H1/time exits = -239.22. Total -198.74.

A significant part of the P&L loss is on failed long breakout/retests,
not from a math/commission failure. A signal can satisfy last 210 hours
H1/H4 EMA trend and still make a weak or low-participation break.
Entry time of day and *future trade duration* are NOT selected as filters,
because post-entry outcomes are unavailable before placing an order.

## Frozen before reading ADA/DOGE outcomes

The only new condition is closed M5 breakout + retest **quality**:
- Original signal ALPHA02 + all existing V5 H1/H4 trend requirements;
- breakout `i-1` close must be at least 0.20× M5 ATR above 20-bar prior high;
- breakout volume >=1.2× the **prior** 20-bar average;
- retest `i` must close >=0.12× breakout ATR above that prior high;
- retest closes in the top 40% of its M5 candle range;
- retest may not close >1.50× breakout ATR above the broken level.

One fixed filter with five conjunctive physical requirements, no grid
search or parameter optimization. The test checks whether it rejects
failed breakouts **before** entering. No lookahead. Everything else
identical between versions: 22 contiguous months, no monthly reset, 5000
USDT virtual capital per asset, long-only, 0.75% all-in stop risk, target
4×H1 ATR, stop 1.5×H1 ATR, 72h time cap and 24h cooldown.
Model costs are 10bps taker fee +1bp half spread + 0/5/10bps slippage
**each side**; at 5bps slippage model full round trip cost is 32bps.

BTC/ETH/SOL have been inspected already. BNB and XRP observed previously
in V6; useful development diagnostics only. ADA/DOGE are **additional
historical market** checks (highly correlated, NOT independent future
out-of-sample). All data is public Binance SPOT official monthly M1 ZIP
verified against provider SHA256, 2025-01 through 2026-10; all 88 monthly
files must be present/verified to declare study complete. All fills are
simulated without real orderbook, funding, quote, actual lot rounding or
historical Binance symbol-filters verification. No risk-free profitability.

Outputs: `results.json`, `results.md`, `source_manifest.json` and
24 CSV ledgers (4 markets × 2 versions × 3 slippage scenarios). Per-market
signal-quality veto counts are calculated on V5 control entries but are
NOT substituted for realized V7 entries/outcomes (different cooldown state).

**Do not promote any backtest-positive version** without genuine later
paper-forward performance, cost audit and sufficient independent evidence.
