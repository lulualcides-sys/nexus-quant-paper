# Nexus Quant — H4 frequency research (GC=F)

**Research-only; old windows already inspected, NOT fresh out-of-sample.**
No broker orders, no allocation, no auto-promotion.
Data SHA-256: \`dd3c85d8072a40a21d47a10ee39f2fba2efe98aa728a368f89b63bd6de72e203\`
Train H4 bars: 919; revisited H4 bars: 1219.

| Rule | Train signals | Revisited signals | Revisited closed trades | Net US$ | Net US$ costs ×2 | Max DD% |
|---|---:|---:|---:|---:|---:|---:|
| channel20 | 61 | 40 | 24 | +316.53 | +295.21 | 1.42 |
| channel35_lab | 55 | 30 | 20 | +189.02 | +171.43 | 2.76 |
| momentum100 | 21 | 34 | 18 | +297.42 | +281.76 | 1.24 |
| momentum60_lab | 27 | 45 | 28 | +482.00 | +454.60 | 2.04 |
| momentum40 | 38 | 37 | 21 | +330.77 | +311.87 | 2.88 |

## Decision gate
An increase in signal count alone is NOT an improvement. Compare net result,
cost ×2, drawdown, number of exits, and later prospective observations.
Historical review windows are already known to the team and may be overfit.
**Existing live/paper books remain unchanged.**
Sources: Yahoo GC=F 60m reference, aggregated to complete H4;
entry at next bar open, stop-first intrabar ordering, estimated costs.
