# Nexus Quant XAUUSD — Bateria 9: estrutura de sessões UTC

**Execução verificada em 12/11/2026. Somente pesquisa OHLC; sem ordens reais e sem teste de ticks reais no MT5.** Quatro novos modelos × M1/M5/M15/M30 = 16 novas configurações, mais 2 referências originais congeladas, em 2025 completo e 2026 parcial Q2/Q3.

## Resultado

- **2/16** novas configurações obtiveram saldo positivo em pontos nos dois recortes, mas ambas **falharam em R normalizado** num dos períodos.
- **1/16** apresentou R positivo nos dois períodos (ASIA_TREND_BREAK M15), mas o saldo em pontos do período parcial de 2026 foi negativo e o PF de pontos ficou abaixo de 1.
- **0/16** passaram a triagem de robustez completa.
- ER20 M30 e Shock Exhaustion M15 foram preservados e mantiveram os resultados positivos do histórico anterior.

**Critérios de triagem predefinidos:** N>=100/50; lucro em R nos dois recortes com custo de US$1,20/onça e stress US$1,60/onça; PF_R>1,20 em ambos; pelo menos 3 trimestres positivos em 2025 e 1 em 2026; maior trimestre não exceder 65% da soma de trimestres positivos. Essa triagem não substitui validação em dados novos.

## Principais hipóteses de pontos positivos

| Modelo | TF | 2025: N | 2025: pts líquidos | 2025: PF | 2026 parcial: N | 2026 parcial: pts líquidos | 2026: PF | 2025: net R | 2026: net R |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ASIA_TREND_BREAK | M30 | 77 | +45,7 | 1,001 | 32 | +7.335,8 | 1,235 | 1,192 | -1,258 |
| VWAP_EMA_RECLAIM | M30 | 91 | +36.048,3 | 1,723 | 52 | +11.101,3 | 1,219 | 24,131 | -2,024 |

**VWAP_EMA_RECLAIM M30:** +36.048,3 pontos em 2025 e +11.101,3 pontos no recorte de 2026; em R, +24,131 em 2025 mas **−2,024 em 2026**, não consistente para lotes ajustados por stop. **ASIA_TREND_BREAK M30:** 2025 +45,7 pontos de 77 trades (PF 1,001; praticamente zero) e 2026 +7.335,8 pontos de 32 trades, R de 2026 negativo. Ambos somente **hipóteses de pesquisa**, não selecionados para produção.

## Tabela completa — pontos com custo hipotético US$1,20 por onça

| Modelo | TF | Operações 2025 | Pontos 2025 | PF 2025 | Operações 2026 parcial | Pontos 2026 parcial | PF 2026 parcial | Net R 2025 | Net R 2026 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ASIA_SWEEP_RECLAIM | M1 | 529 | -66.334,9 | 0,286 | 251 | -31.258,3 | 0,478 | -637,721 | -123,463 |
| ASIA_SWEEP_RECLAIM | M5 | 262 | -37.067,3 | 0,454 | 126 | -24.223,3 | 0,611 | -122,785 | -15,748 |
| ASIA_SWEEP_RECLAIM | M15 | 151 | -22.469,9 | 0,639 | 76 | -29.724,0 | 0,491 | -29,729 | -18,938 |
| ASIA_SWEEP_RECLAIM | M30 | 128 | -40.094,4 | 0,469 | 51 | -7.040,4 | 0,84 | -41,591 | -3,857 |
| ASIA_TREND_BREAK | M1 | 340 | -36.172,8 | 0,484 | 168 | -18.431,7 | 0,659 | -245,916 | -10,469 |
| ASIA_TREND_BREAK | M5 | 182 | -10.630,9 | 0,833 | 94 | -15.589,7 | 0,754 | -40,135 | -5,976 |
| ASIA_TREND_BREAK | M15 | 103 | +10.068,3 | 1,197 | 58 | -385,8 | 0,993 | 6,122 | 5,031 |
| ASIA_TREND_BREAK | M30 | 77 | +45,7 | 1,001 | 32 | +7.335,8 | 1,235 | 1,192 | -1,258 |
| UTC13_RANGE_FAKEOUT | M1 | 504 | -51.995,8 | 0,471 | 210 | -16.648,3 | 0,692 | -432,145 | -42,356 |
| UTC13_RANGE_FAKEOUT | M5 | 209 | +12.567,5 | 1,23 | 106 | -6.553,6 | 0,876 | -36,596 | -12,718 |
| UTC13_RANGE_FAKEOUT | M15 | 137 | -4.134,7 | 0,939 | 66 | +2.031,3 | 1,045 | -18,031 | -6,593 |
| UTC13_RANGE_FAKEOUT | M30 | 99 | -14.072,8 | 0,826 | 49 | +6.177,4 | 1,164 | -15,975 | -0,699 |
| VWAP_EMA_RECLAIM | M1 | 471 | -32.318,2 | 0,672 | 222 | -15.682,6 | 0,758 | -226,224 | -52,699 |
| VWAP_EMA_RECLAIM | M5 | 207 | -33.040,5 | 0,605 | 108 | -20.643,4 | 0,663 | -47,234 | -26,544 |
| VWAP_EMA_RECLAIM | M15 | 130 | +4.968,0 | 1,073 | 61 | -11.016,6 | 0,787 | -2,778 | -2,903 |
| VWAP_EMA_RECLAIM | M30 | 91 | +36.048,3 | 1,723 | 52 | +11.101,3 | 1,219 | 24,131 | -2,024 |
| ER20_M30_FROZEN | M30 | 110 | +35.238,5 | 1,446 | 52 | +27.790,4 | 1,438 | 23,729 | 11,623 |
| SHOCK_M15_FROZEN | M15 | 90 | +23.640,8 | 1,424 | 45 | +13.113,5 | 1,321 | 27,857 | 11,682 |

## Limitações críticas

- Um ponto corresponde a **US$0,01 de movimento no preço por onça** na convenção do simulador; isso não equivale necessariamente à convenção de pontos da corretora e não é dinheiro na conta.
- Stop-first em candle OHLC ambíguo, entrada no open seguinte, TP1=1R para 1/3, TP2=1,5R para 1/3 e runner para 1/3, até 96 horas de candles; custos supostos US$0,80, US$1,20 e US$1,60 por onça roundtrip.
- Feed de 2025 e feed do período parcial de 2026 diferentes. Ambos já examinados por muitos testes anteriores: **não constituem validação fora da amostra**.
- Faixas de sessão são **horários fixos UTC**, não identificação real do horário de Londres/Nova York considerando DST; VWAP baseada em volume do OHLCV, não mercado de futuros centralizado.
- Não medidos spread dinâmico Bid/Ask, corretagem verdadeira, swap, slippage, especificações de contrato, lote mínimo, capital, correlação, drawdown intratrade ou execução real.
- Selecionar a melhor estratégia após observar 16 resultados amplia risco de mineração de dados; não ajustar mais limiares sobre esses mesmos históricos apenas para melhorar o lucro aparente.

## Evidências e preservação

- [GitHub Actions — execução e testes de causalidade bem-sucedidos](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/43272563139)
- [PR #83 — código experimental, draft sem merge](https://github.com/lulualcides-sys/nexus-quant-paper/pull/83)
- [JSON — 18 combinações, 36 painéis anuais e 108 trimestres](xau_batch9_session_all_2025plus_20261112.json)
- [Registro dos 10 candidatos selecionados, preservados](xau_selected_ten_candidates_20261112.json)
- [ER20 M30 e Shock M15 — duas prioridades antigas, preservadas](xau_top_two_priority_er20_m30_shock_m15_20261112.json)

**Decisão:** manter as duas estratégias novas como watchlist exploratória; não elevá-las acima das originais nem considerá-las aprovadas para negociação real.
