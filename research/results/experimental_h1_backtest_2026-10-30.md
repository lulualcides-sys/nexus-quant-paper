# Auditoria dos 15 robôs H1 — regras congeladas

Simulações com preços públicos Yahoo, não ordens da corretora FBS.
Treino: 24/10/2024 a 23/10/2025 UTC. Período posterior: 24/10/2025 a 24/10/2026 UTC.
Período posterior já analisado em outras pesquisas: NÃO é amostra intocada.
Banca US$ 1.000/bot, risco-stop planejado 0,25%/op., exposição máxima 1x.
Stop 1,5 ATR, trailing após 1R, saída até 36 candles H1.
Inclui custos de giro estimados e cenário com custos dobrados.
Gaps e stops estimados, resultados USD; USDJPY convertido de ienes.
Operações em aberto ao fim de cada janela foram forçadas a fechar no último candle.

| Mercado | Estratégia | Op. treino | Treino US$ | Op. posteriores | Acerto | Posterior US$ | DD MTM | Custo 2x US$ |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EURUSD | ema20_retest | 268 | -86.44 | 253 | 41.5% | -19.03 | 4.65% | -90.57 |
| EURUSD | channel10 | 218 | -35.20 | 224 | 34.4% | -71.08 | 7.66% | -131.20 |
| EURUSD | rsi50 | 251 | -78.32 | 240 | 39.6% | -49.58 | 5.66% | -115.32 |
| USDJPY | ema20_retest | 246 | -4.84 | 251 | 39.8% | -67.21 | 7.74% | -133.25 |
| USDJPY | channel10 | 212 | +18.15 | 209 | 38.8% | -67.12 | 8.69% | -121.64 |
| USDJPY | rsi50 | 224 | -7.26 | 236 | 41.5% | -58.40 | 7.92% | -120.61 |
| XAUUSD | ema20_retest | 237 | +13.42 | 215 | 38.6% | -29.12 | 4.91% | -82.09 |
| XAUUSD | channel10 | 191 | +68.62 | 194 | 46.4% | -12.94 | 4.01% | -61.47 |
| XAUUSD | rsi50 | 213 | +19.69 | 215 | 38.6% | -52.21 | 7.26% | -103.98 |
| US500 | ema20_retest | 233 | -83.79 | 225 | 43.6% | -42.20 | 7.53% | -117.29 |
| US500 | channel10 | 225 | -101.43 | 206 | 39.8% | -73.46 | 11.93% | -141.37 |
| US500 | rsi50 | 221 | -106.31 | 209 | 38.3% | -80.82 | 11.36% | -148.48 |
| XTIUSD | ema20_retest | 225 | -43.86 | 241 | 42.7% | +33.26 | 6.88% | -20.91 |
| XTIUSD | channel10 | 221 | -35.85 | 206 | 36.9% | -42.88 | 10.50% | -85.70 |
| XTIUSD | rsi50 | 213 | -57.44 | 224 | 40.6% | -14.05 | 8.67% | -62.93 |

**Positivos no período posterior: 1/15.**
**Positivos com custos 2x: 0/15.**

Nenhuma estratégia aprovada para dinheiro real por este teste.
Validação prospectiva, dados executáveis e custos da corretora são necessários.
Não escolher o melhor retrospectivamente como se fosse lucro futuro garantido.
