# ALPHA V3 — single next hypothesis, still research only

All 10 original rules and V2 filter study remain intact. V2 drastically reduced trades and losses but **never established positive expectancy** in July or Nov 1–7. The economic hypothesis for V3 is that M1/M5 scalp holding 2h with 32bps roundtrip estimated friction makes most hypothetical target distances uneconomic.

**Frozen 08 Nov 2026 before accessing May or June source:**
- Same spot BTCUSDT/ETHUSDT M1 and M5, 5000 USDT virtual/asset, 0.75% complete modeled stop risk, 10bps taker + 1bps half spread each side, stress 0/5/10bps per side.
- Same original 10 signal hypotheses; new causal volume>=80% prior 20 avg, non-bearish EMA50/200 and rising EMA200, no extreme RSI/ATR, projected 8 ATR gross target >=3× full roundtrip primary costs.
- Fixed stop 2 ATR, target 8 ATR, max 12 hours of holding; time-exit created after the closed candle, executed at **next candle open**, not retrospective same close. Intrabar stop wins same-bar collisions. No borrowing, no short selling, no real execution.
- New independent **backward holdouts** May and June 2026; previously inspected August and September diagnostic development only. July/October/Nov already seen and deliberately not reused as 'new' evidence.
- Source: Binance public spot monthly ZIP with official SHA256 .CHECKSUM for all assets/months, UTC, strict OHLCV/tick/continuity checks; no synthetic profit.
- V3 vs unchanged V1 and V2 under same windows/cost assumptions, ledgers CSV by model/market/month/fee; JSON and Markdown reports.
- No auto-approval, no parameter search on holdout, no paper forward, no multiple-testing-adjusted inference yet.

Run:

```bash
python -m unittest discover -s tests -p 'test_alpha_v3.py' -v
python -m research.alpha_v3.run --out artifacts/alpha-v3
```

New price/exits are a separately labeled and falsifiable research model, not evidence of a real-money profit strategy. Any zero/insufficient trade count means INCONCLUSIVE.
