# BB20 M15 central-SMA pullback — realigned strategy comparison

Historical research only, **no live policy changed**. Frozen observations, same risk/runner.
First half train / second half validation are not fully independent from prior review.

| Entry rule | Full trades | Full win% | Full net USD | Train net USD | Validation trades | Validation win% | Validation net USD |
|---|---:|---:|---:|---:|---:|---:|---:|
| ema20_touch_h1stop | 37 | 29.73 | -8.73 | -12.32 | 15 | 53.33 | +3.64 |
| ema50_touch_h1stop | 34 | 35.29 | +0.38 | -4.10 | 16 | 50.0 | +4.50 |
| slope_touch_h1stop | 39 | 33.33 | -3.58 | -10.86 | 16 | 56.25 | +7.37 |
| ema20_wick_h1stop | 27 | 25.93 | -7.75 | -9.55 | 8 | 50.0 | +1.82 |
| ema50_wick_h1stop | 26 | 30.77 | -4.17 | -4.67 | 8 | 50.0 | +0.50 |
| slope_wick_h1stop | 28 | 25.0 | -7.33 | -8.23 | 10 | 40.0 | +0.91 |
| ema20_touch_m15stop | 86 | 26.74 | -17.50 | -17.44 | 38 | 44.74 | -0.06 |
| ema50_touch_m15stop | 84 | 27.38 | -15.18 | -15.89 | 38 | 44.74 | +0.73 |
| ema50_cross_m15stop | 63 | 26.98 | -10.23 | -10.34 | 30 | 40.0 | +0.12 |

A positive result alone is not proof; sample may be too small and execution indicative.
