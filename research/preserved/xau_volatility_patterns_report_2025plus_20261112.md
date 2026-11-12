# XAUUSD — expansão de volatilidade e estrutura de candles M1–M30, 2025+

**Salvo 12/11/2026. Backtest OHLC experimental, não MetaTrader com ticks reais. Não é lucro em dinheiro.**

## Metodologia

- Fonte 2025 Git fixada em `b2cfdc571ffac9eff9f2132ea6946da559d29af2`; fonte 2026 verificada por SHA256 `a587597bbf88c2d868a00a4e0019cd705cee6ca4f20b0485d6b745f19fcc8225`. Somente ouro XAUUSD a partir de 01/01/2025. 2026 somente parte de Q2/Q3 do dataset, e feeds diferem.
- 11 timeframes MT5: M1, M2, M3, M4, M5, M6, M10, M12, M15, M20, M30. 5 modelos comparados (EMA21 congelado + 4 originais), 55 comparações de timeframe/modelo e 66 janelas trimestrais.
- **NR7_BAR_BREAK**: 'NR7 intradiário', mínima amplitude das últimas 7 barras anteriores da mesma periodicidade; NÃO é o NR7 diário clássico.
- **INSIDE_MOTHER_BREAK**: barra fechada anterior inteiramente dentro da mãe de duas barras atrás; candle atual confirma rompimento da mãe, entrada no open seguinte.
- **VOL_COMPRESSION_RELEASE**: média de True Range das 6 barras anteriores <= 72% das 20 anteriores a elas; candle fecha rompendo 8 barras, com impulso >=1,4× range médio curto.
- **EFFICIENCY_ER20_BREAK**: Kaufman efficiency ratio 20 candles >=0,38 e rompimento confirmado das 12 barras anteriores.
- Simulação: candle fechado sem repintura/lookahead, próxima abertura, stop com margem ATR14 e stop-first em barras OHLC ambíguas, gaps desfavoráveis; TP1 1R (1/3), TP2 1,5R (1/3), final 1/3 Runner até SL original ou 96 horas de candles.
- Custos hipotéticos por trade round-trip: US$0,80 / US$1,20 / US$1,60 por onça; unidade do ponto assumida 0,01. DD de fechamento apenas, não intratrade; custos reais de corretora, bid/ask, swap, comissão e slippage ainda ausentes.

## Três hipóteses que passaram na triagem experimental

Triagem fixada antes dos resultados: lucro líquido positivo e PF >1,10 nos dois recortes com custo US$1,20/oz, pelo menos 100 trades 2025 e 50 trades no 2026 parcial, no mínimo 3 trimestres positivos de 2025 e 1 trimestre positivo de 2026.

| Modelo | N 2025 | Net pts 2025 custo0,8 | PF25 | MDD25 | N 2026 parcial | Net pts 2026 custo0,8 | PF26 | MDD26 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| M12 INSIDE_MOTHER_BREAK | 231 | 49.676 | 1,523 | 12.991 | 108 | 27.358 | 1,321 | 24.022 |
| M20 VOL_COMPRESSION_RELEASE | 140 | 21.794 | 1,303 | 13.902 | 66 | 33.451 | 1,631 | 11.341 |
| M30 EFFICIENCY_ER20_BREAK | 110 | 39.639 | 1,518 | 11.535 | 52 | 29.870 | 1,480 | 22.096 |

### Sensibilidade a custo maior

| Modelo | Líquido 2025 custo1,2 | Líquido 2026 custo1,2 | Líquido 2025 custo1,6 | Líquido 2026 custo1,6 |
|---|---:|---:|---:|---:|
| M12 INSIDE_MOTHER_BREAK | 40.436 | 23.038 | 31.196 | 18.718 |
| M20 VOL_COMPRESSION_RELEASE | 16.194 | 30.811 | 10.594 | 28.171 |
| M30 EFFICIENCY_ER20_BREAK | 35.239 | 27.790 | 30.839 | 25.710 |

## Distribuição por trimestre — custo US$0,80/oz

| Trimestre | Inside Bar M12 | Compression M20 | ER20 M30 |
|---|---:|---:|---:|
| 2025Q1 | -816 | -10.543 | -3.376 |
| 2025Q2 | 6.715 | 4.853 | 2.623 |
| 2025Q3 | 2.479 | 7.664 | 11.597 |
| 2025Q4 | 41.298 | 19.820 | 28.795 |
| 2026Q2 | 8.089 | 28.545 | 42.486 |
| 2026Q3 | 19.269 | 4.907 | -12.616 |

**Risco de concentração / falsa superioridade:** Inside Bar M12 ganhou +41.298 em Q4/2025, aproximadamente 83% de seus +49.676 pontos no ano; Q1/2025 foi negativo. Compressão M20 perdeu -10.543 pontos em Q1/2025 e fez +19.820 em Q4/2025. ER20 M30 perdeu -12.616 em Q3/2026, apesar de resultado positivo agregado no período.

## Todos os resultados anuais e modelos, custo US$0,80 e stress US$1,20

| TF | Modelo | N25 | Net25 | PF25 | MDD25 | N26 parcial | Net26 | PF26 | MDD26 | Net25 custo1,2 | Net26 custo1,2 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| M1 | EMA21_BASE | 2055 | -181.351 | 0,370 | 185.556 | 630 | -34.015 | 0,717 | 34.153 | -263.551 | -59.215 |
| M1 | NR7_BAR_BREAK | 1234 | -74.996 | 0,614 | 80.738 | 455 | 6.331 | 1,061 | 25.140 | -124.356 | -11.869 |
| M1 | INSIDE_MOTHER_BREAK | 884 | -35.351 | 0,775 | 64.008 | 467 | -31.859 | 0,766 | 37.599 | -70.711 | -50.539 |
| M1 | VOL_COMPRESSION_RELEASE | 990 | -68.248 | 0,559 | 77.431 | 416 | -21.221 | 0,792 | 46.343 | -107.848 | -37.861 |
| M1 | EFFICIENCY_ER20_BREAK | 1072 | -74.160 | 0,571 | 78.921 | 425 | -10.286 | 0,906 | 32.578 | -117.040 | -27.286 |
| M2 | EMA21_BASE | 1147 | -71.988 | 0,621 | 86.262 | 402 | -9.073 | 0,912 | 22.066 | -117.868 | -25.153 |
| M2 | NR7_BAR_BREAK | 789 | -9.928 | 0,931 | 34.505 | 450 | -23.087 | 0,814 | 40.642 | -41.488 | -41.087 |
| M2 | INSIDE_MOTHER_BREAK | 681 | -49.334 | 0,724 | 59.279 | 247 | 30.007 | 1,328 | 16.504 | -76.574 | 20.127 |
| M2 | VOL_COMPRESSION_RELEASE | 652 | -31.486 | 0,753 | 43.298 | 294 | -33.600 | 0,639 | 36.766 | -57.566 | -45.360 |
| M2 | EFFICIENCY_ER20_BREAK | 603 | 4.499 | 1,038 | 18.363 | 305 | 4.642 | 1,047 | 29.049 | -19.621 | -7.558 |
| M3 | EMA21_BASE | 969 | -75.413 | 0,610 | 97.280 | 388 | -27.574 | 0,770 | 33.544 | -114.173 | -43.094 |
| M3 | NR7_BAR_BREAK | 784 | -51.215 | 0,714 | 68.562 | 366 | -9.787 | 0,918 | 33.283 | -82.575 | -24.427 |
| M3 | INSIDE_MOTHER_BREAK | 536 | -20.485 | 0,868 | 37.362 | 251 | 5.427 | 1,049 | 29.993 | -41.925 | -4.613 |
| M3 | VOL_COMPRESSION_RELEASE | 513 | -36.256 | 0,720 | 54.467 | 223 | 10.560 | 1,154 | 27.872 | -56.776 | 1.640 |
| M3 | EFFICIENCY_ER20_BREAK | 491 | 491 | 1,004 | 20.532 | 246 | 21.988 | 1,263 | 18.467 | -19.149 | 12.148 |
| M4 | EMA21_BASE | 786 | -51.677 | 0,713 | 66.111 | 375 | -22.499 | 0,819 | 23.850 | -83.117 | -37.499 |
| M4 | NR7_BAR_BREAK | 687 | -33.565 | 0,799 | 41.560 | 336 | -16.714 | 0,877 | 26.975 | -61.045 | -30.154 |
| M4 | INSIDE_MOTHER_BREAK | 433 | -13.096 | 0,906 | 23.282 | 260 | -37.627 | 0,748 | 41.213 | -30.416 | -48.027 |
| M4 | VOL_COMPRESSION_RELEASE | 471 | -38.400 | 0,673 | 49.150 | 172 | 16.391 | 1,287 | 15.085 | -57.240 | 9.511 |
| M4 | EFFICIENCY_ER20_BREAK | 532 | -46.840 | 0,694 | 53.322 | 211 | -1.896 | 0,981 | 18.607 | -68.120 | -10.336 |
| M5 | EMA21_BASE | 695 | -45.317 | 0,729 | 59.207 | 257 | 1.667 | 1,018 | 30.183 | -73.117 | -8.613 |
| M5 | NR7_BAR_BREAK | 497 | 3.457 | 1,027 | 36.606 | 239 | 7.282 | 1,077 | 11.216 | -16.423 | -2.278 |
| M5 | INSIDE_MOTHER_BREAK | 385 | 1.794 | 1,013 | 27.728 | 210 | -27.880 | 0,791 | 39.564 | -13.606 | -36.280 |
| M5 | VOL_COMPRESSION_RELEASE | 367 | -16.291 | 0,821 | 30.066 | 200 | -26.304 | 0,691 | 33.047 | -30.971 | -34.304 |
| M5 | EFFICIENCY_ER20_BREAK | 405 | -16.841 | 0,874 | 26.428 | 164 | 31.645 | 1,479 | 13.304 | -33.041 | 25.085 |
| M6 | EMA21_BASE | 571 | -23.407 | 0,851 | 37.567 | 278 | -11.720 | 0,887 | 25.834 | -46.247 | -22.840 |
| M6 | NR7_BAR_BREAK | 505 | -16.534 | 0,886 | 29.131 | 194 | 52.582 | 1,767 | 11.976 | -36.734 | 44.822 |
| M6 | INSIDE_MOTHER_BREAK | 342 | 8.143 | 1,063 | 19.274 | 185 | -13.584 | 0,891 | 32.648 | -5.537 | -20.984 |
| M6 | VOL_COMPRESSION_RELEASE | 339 | 9.540 | 1,111 | 13.268 | 155 | 375 | 1,006 | 14.153 | -4.020 | -5.825 |
| M6 | EFFICIENCY_ER20_BREAK | 382 | -21.036 | 0,834 | 29.364 | 182 | 4.813 | 1,050 | 18.475 | -36.316 | -2.467 |
| M10 | EMA21_BASE | 410 | 621 | 1,005 | 31.798 | 242 | -18.669 | 0,833 | 30.353 | -15.779 | -28.349 |
| M10 | NR7_BAR_BREAK | 368 | -2.332 | 0,981 | 23.489 | 166 | 35.838 | 1,399 | 19.283 | -17.052 | 29.198 |
| M10 | INSIDE_MOTHER_BREAK | 250 | 3.249 | 1,026 | 16.207 | 127 | -17.085 | 0,831 | 31.796 | -6.751 | -22.165 |
| M10 | VOL_COMPRESSION_RELEASE | 231 | 17.458 | 1,223 | 17.060 | 126 | -7.068 | 0,903 | 25.123 | 8.218 | -12.108 |
| M10 | EFFICIENCY_ER20_BREAK | 255 | -9.001 | 0,925 | 21.986 | 125 | 10.451 | 1,118 | 22.221 | -19.201 | 5.451 |
| M12 | EMA21_BASE | 365 | -11.729 | 0,914 | 31.224 | 217 | -7.231 | 0,928 | 18.763 | -26.329 | -15.911 |
| M12 | NR7_BAR_BREAK | 341 | 832 | 1,006 | 28.812 | 166 | 4.355 | 1,045 | 20.527 | -12.808 | -2.285 |
| M12 | INSIDE_MOTHER_BREAK | 231 | 49.676 | 1,523 | 12.991 | 108 | 27.358 | 1,321 | 24.022 | 40.436 | 23.038 |
| M12 | VOL_COMPRESSION_RELEASE | 225 | -8.710 | 0,913 | 26.618 | 109 | 9.665 | 1,141 | 18.942 | -17.710 | 5.305 |
| M12 | EFFICIENCY_ER20_BREAK | 213 | 29.714 | 1,341 | 12.916 | 108 | 1.714 | 1,020 | 19.729 | 21.194 | -2.606 |
| M15 | EMA21_BASE | 320 | 14.839 | 1,138 | 16.346 | 156 | 6.527 | 1,082 | 21.230 | 2.039 | 287 |
| M15 | NR7_BAR_BREAK | 295 | -5.348 | 0,959 | 23.686 | 112 | 31.700 | 1,428 | 12.990 | -17.148 | 27.220 |
| M15 | INSIDE_MOTHER_BREAK | 224 | -13.353 | 0,906 | 50.261 | 96 | 10.927 | 1,133 | 16.510 | -22.313 | 7.087 |
| M15 | VOL_COMPRESSION_RELEASE | 190 | -15.652 | 0,848 | 28.203 | 111 | -8.625 | 0,889 | 27.323 | -23.252 | -13.065 |
| M15 | EFFICIENCY_ER20_BREAK | 175 | 26.539 | 1,299 | 13.855 | 96 | 5.811 | 1,065 | 26.316 | 19.539 | 1.971 |
| M20 | EMA21_BASE | 276 | -5.014 | 0,957 | 18.044 | 136 | 5.758 | 1,072 | 18.472 | -16.054 | 318 |
| M20 | NR7_BAR_BREAK | 237 | 29.991 | 1,276 | 12.107 | 129 | -5.355 | 0,945 | 23.395 | 20.511 | -10.515 |
| M20 | INSIDE_MOTHER_BREAK | 184 | -12.476 | 0,904 | 38.509 | 78 | 25.978 | 1,328 | 25.729 | -19.836 | 22.858 |
| M20 | VOL_COMPRESSION_RELEASE | 140 | 21.794 | 1,303 | 13.902 | 66 | 33.451 | 1,631 | 11.341 | 16.194 | 30.811 |
| M20 | EFFICIENCY_ER20_BREAK | 155 | 5.007 | 1,055 | 17.519 | 79 | 5.919 | 1,074 | 23.619 | -1.193 | 2.759 |
| M30 | EMA21_BASE | 214 | -9.214 | 0,917 | 19.391 | 105 | 21.290 | 1,290 | 13.848 | -17.774 | 17.090 |
| M30 | NR7_BAR_BREAK | 243 | -39.819 | 0,730 | 45.654 | 93 | 18.289 | 1,271 | 14.121 | -49.539 | 14.569 |
| M30 | INSIDE_MOTHER_BREAK | 146 | -19.304 | 0,847 | 29.414 | 71 | 17.279 | 1,223 | 26.063 | -25.144 | 14.439 |
| M30 | VOL_COMPRESSION_RELEASE | 121 | 25.716 | 1,421 | 11.999 | 66 | -9.203 | 0,874 | 23.844 | 20.876 | -11.843 |
| M30 | EFFICIENCY_ER20_BREAK | 110 | 39.639 | 1,518 | 11.535 | 52 | 29.870 | 1,480 | 22.096 | 35.239 | 27.790 |

## Veredito responsável

- As três novas estratégias passaram uma triagem **retrospectiva**, não validação prospectiva. Qualquer comparação de 55 pares em anos já inspecionados apresenta viés de seleção; não é cientificamente correto declarar uma estratégia superior ao longo prazo.
- Inside Bar M12 tem número de operações maior e resultado líquido agregado melhor do que EMA21 original M15 neste replay, mas diferenças de stop, risco por entrada, timeframe, drawdown intratrade e lotagem impedem comparação financeira direta.
- ER20 M30 é resistente a stress de custo, mas 2026Q3 foi significativamente negativo. Menos de 200 trades históricos agregados.
- Não foram incorporados robôs de produção e o registro dos **quatro candidatos escolhidos pelo usuário permanece intacto**.
- Para confirmar qualquer novo candidato: compilar MQL5, executar MT5 real ticks da corretora 2025+, custos reais, e novo período de demo totalmente fora da pesquisa atual, com parâmetros congelados, DD em equity, risco por trade e ganho de R por mês.

## Evidências

- [GitHub Actions concluído com sucesso](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/43245678768)
- [PR de pesquisa #78](https://github.com/lulualcides-sys/nexus-quant-paper/pull/78)
- [Resultados completos, incluindo modelos que perderam, salvos em JSON](xau_volatility_patterns_m1_m30_2025plus_20261112.json)
- [Quatro selecionados anteriormente](xau_selected_four_candidates_20261112.json)
