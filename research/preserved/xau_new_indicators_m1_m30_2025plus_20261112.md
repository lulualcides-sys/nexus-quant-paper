# XAUUSD — novos indicadores M1–M30, 2025 em diante

**Arquivo permanente, criado em 12/11/2026.** Estudo computacional com dados OHLC. **Não é resultado da corretora ou MT5 Strategy Tester.**

## Escopo e implementação

- **Somente ouro XAUUSD e dados a partir de 01/01/2025 UTC.** Cobertura: M1, M2, M3, M4, M5, M6, M10, M12, M15, M20 e M30.
- 2025: quatro trimestres elegíveis. 2026: **somente 2026Q2 e 2026Q3** disponíveis na fonte pinada. Não extrapolar para um ano completo.
- Fontes: 2025 `b2cfdc571ffac9eff9f2132ea6946da559d29af2`; 2026 SHA256 `a587597bbf88c2d868a00a4e0019cd705cee6ca4f20b0485d6b745f19fcc8225`. As fontes não são o mesmo broker.
- Mesmo motor de execução conservador do Runner96h: sinal após candle fechado, entrar na próxima abertura; prioridade ao stop em candle ambíguo; gap desfavorável; um trade por vez; mesma cauda de tempo e TP1 1R, TP2 1,5R (1/3 da posição cada); restante em stop/time limit.
- Indicadores sem pivôs futuros/sem repintar: ADX/DI14; Donchian24; RSI14 com Bollinger20; MACD12-26-9; Keltner EMA20 + ATR14; Stochastic14/3; confirmações de EMA21 com ADX ou RSI/MACD.
- Custos simulados US$ 0,80 / US$ 1,20 / US$ 1,60 por onça por round-trip; **POINT=0,01 presumido**. Sem Bid/Ask, spread, comissão e swap reais do broker, lotagem ou slippage observado.
- **66 trimestres/timeframes** e **88 comparações de ano/modelo/timeframe**; sem selecionar apenas resultados positivos. Regressões e testes sem acesso ao futuro passaram.
- Evidência CI concluída: https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/43227184319

## Modelos avaliados

1. `EMA21_BASE` — original preservado.
2. `EMA21_ADX_DI` — confirma força direcional do sinal da EMA21 com ADX/DI.
3. `EMA21_RSI_MACD` — filtra sinal da EMA21 por RSI14 e histograma MACD 12/26/9.
4. `ADX_DONCHIAN24` — rompimento da máxima/mínima das 24 barras anteriores com ADX/DI.
5. `RSI_BOLLINGER20` — rejeição das bandas de Bollinger associada ao RSI.
6. `MACD_RSI_TREND` — cruzamento de histograma MACD, RSI e EMA alinhadas.
7. `KELTNER_SQUEEZE` — compressão de Bollinger dentro de Keltner com rompimento confirmado.
8. `STOCH_REJECTION` — reversão após cruzamento do Stochastic K/D, usando candle fechado.

## Candidatos destacados (ainda NÃO homologados)

| Modelo | 2025 N | 2025 net (custo 0,8) | PF 2025 | 2026 parcial N | 2026 net (0,8) | PF 2026 | Net 2025 (custo 1,6) | Net 2026 (custo 1,6) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| M15 EMA21_BASE | 320 | 14.839 | 1,138 | 156 | 6.527 | 1,082 | -10.761 | -5.953 |
| M30 EMA21_RSI_MACD | 113 | 12.241 | 1,200 | 54 | 19.683 | 1,518 | 3.201 | 15.363 |
| M30 KELTNER_SQUEEZE | 91 | 12.069 | 1,223 | 45 | 9.100 | 1,199 | 4.789 | 5.500 |
| M5 KELTNER_SQUEEZE | 342 | 2.981 | 1,033 | 139 | 11.274 | 1,190 | -24.379 | 154 |

### Distribuição por trimestre — candidatos M30 (0,8 USD/oz)

| Ano/trimestre | M30 EMA21+RSI+MACD | M30 Keltner Squeeze | M30 EMA21 original |
|---|---:|---:|---:|
| 2025Q1 | -5.351 | 2.877 | 1.804 |
| 2025Q2 | -637 | 3.315 | -2.633 |
| 2025Q3 | 6.809 | 5.769 | -4.229 |
| 2025Q4 | 11.420 | 108 | -4.156 |
| 2026Q2 | 11.836 | -3.916 | 26.595 |
| 2026Q3 | 7.847 | 13.016 | -5.305 |

**Leitura correta:** M30 EMA21+RSI+MACD teve **prejuízo no primeiro semestre de 2025**, apesar de fechar o ano positivo. Em 2026 só há Q2/Q3, que ficaram positivos. Não confundir isso com lucros consistentes mês a mês. O M30 Keltner foi positivo em todos os quatro trimestres de 2025, mas perdeu em 2026Q2. Volume de trades de M30 é muito menor que M1/M5.

## Todos os resultados (custo hipotético 0,8 USD/oz)

| TF | Indicador | Trades 2025 | Líquido 2025 pts | PF 2025 | MDD 2025 pts | Trades 2026 parcial | Líquido 2026 pts | PF 2026 | MDD 2026 pts |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| M1 | EMA21_BASE | 2055 | -181.351 | 0,370 | 185.556 | 630 | -34.015 | 0,717 | 34.153 |
| M1 | EMA21_ADX_DI | 1288 | -88.767 | 0,514 | 93.024 | 601 | -34.278 | 0,713 | 34.412 |
| M1 | EMA21_RSI_MACD | 1396 | -111.059 | 0,450 | 114.200 | 545 | -30.558 | 0,732 | 34.404 |
| M1 | ADX_DONCHIAN24 | 1063 | -61.203 | 0,649 | 66.066 | 453 | -6.814 | 0,933 | 25.431 |
| M1 | RSI_BOLLINGER20 | 1382 | -95.995 | 0,538 | 97.339 | 726 | -35.699 | 0,772 | 40.601 |
| M1 | MACD_RSI_TREND | 1129 | -76.953 | 0,594 | 80.810 | 427 | -5.278 | 0,948 | 20.966 |
| M1 | KELTNER_SQUEEZE | 1049 | -70.534 | 0,567 | 74.896 | 543 | -38.094 | 0,686 | 40.050 |
| M1 | STOCH_REJECTION | 1329 | -64.415 | 0,613 | 87.034 | 865 | -81.275 | 0,486 | 81.473 |
| M2 | EMA21_BASE | 1147 | -71.988 | 0,621 | 86.262 | 402 | -9.073 | 0,912 | 22.066 |
| M2 | EMA21_ADX_DI | 763 | -29.124 | 0,781 | 40.805 | 388 | -40.279 | 0,594 | 40.360 |
| M2 | EMA21_RSI_MACD | 768 | -21.743 | 0,834 | 26.549 | 352 | -13.015 | 0,863 | 37.308 |
| M2 | ADX_DONCHIAN24 | 804 | -54.084 | 0,672 | 57.981 | 291 | 19.822 | 1,231 | 21.165 |
| M2 | RSI_BOLLINGER20 | 1104 | -99.251 | 0,515 | 99.774 | 516 | -24.380 | 0,828 | 38.964 |
| M2 | MACD_RSI_TREND | 795 | -50.153 | 0,708 | 61.576 | 336 | -35.183 | 0,727 | 41.898 |
| M2 | KELTNER_SQUEEZE | 752 | -50.827 | 0,647 | 54.315 | 245 | 12.829 | 1,188 | 15.372 |
| M2 | STOCH_REJECTION | 1109 | -66.072 | 0,622 | 69.336 | 506 | -15.451 | 0,863 | 35.001 |
| M3 | EMA21_BASE | 969 | -75.413 | 0,610 | 97.280 | 388 | -27.574 | 0,770 | 33.544 |
| M3 | EMA21_ADX_DI | 560 | -10.318 | 0,904 | 37.326 | 295 | -33.909 | 0,690 | 47.166 |
| M3 | EMA21_RSI_MACD | 668 | -55.843 | 0,632 | 62.763 | 255 | 10.044 | 1,140 | 15.669 |
| M3 | ADX_DONCHIAN24 | 547 | -8.254 | 0,936 | 26.995 | 262 | 17.402 | 1,195 | 19.883 |
| M3 | RSI_BOLLINGER20 | 789 | -52.987 | 0,676 | 54.069 | 410 | -62.830 | 0,573 | 70.441 |
| M3 | MACD_RSI_TREND | 571 | -32.031 | 0,777 | 50.351 | 274 | -26.712 | 0,756 | 36.633 |
| M3 | KELTNER_SQUEEZE | 467 | 809 | 1,008 | 12.716 | 232 | -18.627 | 0,795 | 27.209 |
| M3 | STOCH_REJECTION | 810 | -44.008 | 0,688 | 61.821 | 403 | -22.589 | 0,796 | 36.170 |
| M4 | EMA21_BASE | 786 | -51.677 | 0,713 | 66.111 | 375 | -22.499 | 0,819 | 23.850 |
| M4 | EMA21_ADX_DI | 464 | -2.086 | 0,979 | 26.852 | 239 | -2.017 | 0,976 | 19.114 |
| M4 | EMA21_RSI_MACD | 489 | -12.272 | 0,897 | 37.140 | 298 | -44.084 | 0,594 | 46.035 |
| M4 | ADX_DONCHIAN24 | 493 | -9.250 | 0,929 | 32.627 | 188 | 29.090 | 1,395 | 16.808 |
| M4 | RSI_BOLLINGER20 | 553 | 8.265 | 1,067 | 15.305 | 395 | -69.778 | 0,563 | 74.798 |
| M4 | MACD_RSI_TREND | 516 | -27.759 | 0,810 | 56.640 | 255 | -20.765 | 0,813 | 34.796 |
| M4 | KELTNER_SQUEEZE | 385 | -5.768 | 0,940 | 22.378 | 180 | -18.302 | 0,782 | 21.168 |
| M4 | STOCH_REJECTION | 658 | -25.318 | 0,804 | 34.111 | 255 | 10.107 | 1,133 | 16.100 |
| M5 | EMA21_BASE | 695 | -45.317 | 0,729 | 59.207 | 257 | 1.667 | 1,018 | 30.183 |
| M5 | EMA21_ADX_DI | 428 | -2.785 | 0,971 | 21.812 | 206 | -11.227 | 0,847 | 20.162 |
| M5 | EMA21_RSI_MACD | 421 | 4.019 | 1,038 | 24.222 | 223 | -8.409 | 0,905 | 34.931 |
| M5 | ADX_DONCHIAN24 | 416 | -4.432 | 0,963 | 15.430 | 186 | 5.952 | 1,066 | 20.665 |
| M5 | RSI_BOLLINGER20 | 568 | -16.261 | 0,880 | 40.641 | 307 | -20.339 | 0,837 | 33.968 |
| M5 | MACD_RSI_TREND | 421 | -26.123 | 0,808 | 35.878 | 184 | -6.200 | 0,931 | 22.234 |
| M5 | KELTNER_SQUEEZE | 342 | 2.981 | 1,033 | 17.648 | 139 | 11.274 | 1,190 | 14.094 |
| M5 | STOCH_REJECTION | 662 | -31.956 | 0,759 | 55.470 | 299 | -24.683 | 0,754 | 27.524 |
| M6 | EMA21_BASE | 571 | -23.407 | 0,851 | 37.567 | 278 | -11.720 | 0,887 | 25.834 |
| M6 | EMA21_ADX_DI | 347 | 12.603 | 1,146 | 24.385 | 208 | -31.077 | 0,657 | 31.180 |
| M6 | EMA21_RSI_MACD | 382 | -16.466 | 0,845 | 29.362 | 196 | 6.142 | 1,076 | 20.354 |
| M6 | ADX_DONCHIAN24 | 395 | 3.777 | 1,032 | 22.457 | 175 | 7.392 | 1,081 | 20.171 |
| M6 | RSI_BOLLINGER20 | 464 | -12.674 | 0,902 | 29.571 | 249 | -4.749 | 0,959 | 35.659 |
| M6 | MACD_RSI_TREND | 450 | -36.931 | 0,748 | 59.916 | 220 | -31.491 | 0,709 | 35.927 |
| M6 | KELTNER_SQUEEZE | 296 | 3.943 | 1,043 | 16.819 | 138 | -14.728 | 0,803 | 27.134 |
| M6 | STOCH_REJECTION | 577 | -32.564 | 0,735 | 32.733 | 314 | -46.419 | 0,584 | 46.419 |
| M10 | EMA21_BASE | 410 | 621 | 1,005 | 31.798 | 242 | -18.669 | 0,833 | 30.353 |
| M10 | EMA21_ADX_DI | 264 | 7.548 | 1,085 | 20.840 | 165 | -24.341 | 0,719 | 25.099 |
| M10 | EMA21_RSI_MACD | 280 | -10.065 | 0,906 | 25.461 | 132 | -5.645 | 0,916 | 18.615 |
| M10 | ADX_DONCHIAN24 | 294 | -12.069 | 0,898 | 41.849 | 112 | 7.718 | 1,098 | 17.340 |
| M10 | RSI_BOLLINGER20 | 439 | -45.092 | 0,701 | 56.563 | 231 | -41.424 | 0,685 | 56.224 |
| M10 | MACD_RSI_TREND | 267 | 15.565 | 1,145 | 21.465 | 154 | -37.045 | 0,623 | 38.031 |
| M10 | KELTNER_SQUEEZE | 212 | 15.741 | 1,199 | 12.353 | 129 | -64.174 | 0,355 | 64.174 |
| M10 | STOCH_REJECTION | 399 | -24.980 | 0,767 | 29.706 | 179 | 145 | 1,002 | 18.245 |
| M12 | EMA21_BASE | 365 | -11.729 | 0,914 | 31.224 | 217 | -7.231 | 0,928 | 18.763 |
| M12 | EMA21_ADX_DI | 232 | 9.179 | 1,120 | 17.182 | 138 | -6.225 | 0,906 | 21.299 |
| M12 | EMA21_RSI_MACD | 261 | -30.366 | 0,706 | 31.289 | 138 | 696 | 1,010 | 13.358 |
| M12 | ADX_DONCHIAN24 | 239 | 8.612 | 1,083 | 28.958 | 117 | 2.389 | 1,027 | 19.799 |
| M12 | RSI_BOLLINGER20 | 365 | -14.711 | 0,880 | 26.516 | 177 | -15.115 | 0,860 | 53.902 |
| M12 | MACD_RSI_TREND | 242 | -11.017 | 0,900 | 26.041 | 128 | -29.343 | 0,682 | 35.695 |
| M12 | KELTNER_SQUEEZE | 178 | 8.381 | 1,098 | 27.644 | 103 | -29.649 | 0,648 | 30.628 |
| M12 | STOCH_REJECTION | 336 | 13.362 | 1,174 | 19.346 | 161 | 1.182 | 1,020 | 11.849 |
| M15 | EMA21_BASE | 320 | 14.839 | 1,138 | 16.346 | 156 | 6.527 | 1,082 | 21.230 |
| M15 | EMA21_ADX_DI | 187 | 1.254 | 1,019 | 18.802 | 110 | 7.763 | 1,146 | 17.996 |
| M15 | EMA21_RSI_MACD | 215 | -12.711 | 0,858 | 15.436 | 101 | -13.272 | 0,815 | 22.127 |
| M15 | ADX_DONCHIAN24 | 237 | -33.173 | 0,754 | 37.853 | 105 | -1.325 | 0,984 | 18.343 |
| M15 | RSI_BOLLINGER20 | 305 | -41.788 | 0,712 | 47.290 | 183 | -56.551 | 0,568 | 61.924 |
| M15 | MACD_RSI_TREND | 197 | 4.805 | 1,048 | 25.005 | 114 | -23.845 | 0,723 | 26.457 |
| M15 | KELTNER_SQUEEZE | 150 | 22.491 | 1,316 | 17.954 | 79 | -1.324 | 0,978 | 14.094 |
| M15 | STOCH_REJECTION | 314 | -18.215 | 0,799 | 22.223 | 145 | -5.479 | 0,918 | 27.047 |
| M20 | EMA21_BASE | 276 | -5.014 | 0,957 | 18.044 | 136 | 5.758 | 1,072 | 18.472 |
| M20 | EMA21_ADX_DI | 160 | -15.979 | 0,765 | 21.278 | 99 | 1.480 | 1,030 | 8.124 |
| M20 | EMA21_RSI_MACD | 157 | -12.711 | 0,848 | 23.401 | 83 | -2.433 | 0,964 | 18.011 |
| M20 | ADX_DONCHIAN24 | 183 | -9.124 | 0,920 | 29.162 | 81 | 13.313 | 1,178 | 17.605 |
| M20 | RSI_BOLLINGER20 | 305 | -6.983 | 0,944 | 31.452 | 131 | -13.418 | 0,869 | 38.907 |
| M20 | MACD_RSI_TREND | 141 | 11.119 | 1,129 | 22.898 | 96 | -48.991 | 0,538 | 49.699 |
| M20 | KELTNER_SQUEEZE | 118 | 31.103 | 1,544 | 8.345 | 67 | -11.382 | 0,797 | 23.128 |
| M20 | STOCH_REJECTION | 277 | -17.815 | 0,796 | 22.448 | 119 | 5.406 | 1,087 | 16.969 |
| M30 | EMA21_BASE | 214 | -9.214 | 0,917 | 19.391 | 105 | 21.290 | 1,290 | 13.848 |
| M30 | EMA21_ADX_DI | 109 | -8.610 | 0,853 | 24.947 | 87 | -28.614 | 0,554 | 28.614 |
| M30 | EMA21_RSI_MACD | 113 | 12.241 | 1,200 | 12.275 | 54 | 19.683 | 1,518 | 17.735 |
| M30 | ADX_DONCHIAN24 | 131 | -8.189 | 0,916 | 32.481 | 74 | 2.333 | 1,028 | 21.806 |
| M30 | RSI_BOLLINGER20 | 206 | 5.771 | 1,054 | 19.583 | 111 | -15.694 | 0,851 | 54.293 |
| M30 | MACD_RSI_TREND | 120 | -1.471 | 0,985 | 19.160 | 64 | -10.075 | 0,868 | 32.938 |
| M30 | KELTNER_SQUEEZE | 91 | 12.069 | 1,223 | 14.102 | 45 | 9.100 | 1,199 | 21.996 |
| M30 | STOCH_REJECTION | 186 | -12.860 | 0,845 | 36.372 | 81 | -12.013 | 0,803 | 22.375 |

## Seleção, riscos e decisão

- Critério de triagem **definido antes da leitura**: custos estressados US$ 1,20 positivos nos dois recortes, PF superior a 1,10 em ambos, ao menos 100 trades em 2025 e 50 em 2026 parcial. Somente **M30 EMA21_RSI_MACD** passou; isso NÃO é homologação.
- M30 Keltner foi positivo mesmo a US$ 1,60, mas tem 91 trades em 2025 e 45 no recorte 2026, abaixo do limite de amostra adotado.
- M5 Keltner foi positivo em ambos no custo US$ 0,80, mas tornou-se negativo em 2025 ao elevar custo a 1,20, portanto é muito sensível a fricção.
- Aumentar sinais sem expectativa líquida positiva em M1/M5 ampliaria custos e drawdown; nenhuma otimização retrospectiva desses anos prova retorno futuro.
- Dados de 2025/26 já foram vistos em outros projetos e estas sete famílias foram comparadas agora. Escolher o melhor resultado entre 88 combinações introduz **viés de seleção/múltiplas tentativas**. A validação decisiva deve ser futura e fora da pesquisa atual.
- Falta tick Bid/Ask, comissão, swap, liquidez, diferença de contrato XAUUSD, execução/latência do MT5, margem/lotagem, drawdown intratrade e teste forward com regras congeladas.
- Não ativar robô em conta real, não modificar `main` de código nem substituir snapshots positivos já preservados. O PR #75 permanece draft para desenvolvimento experimental.

### Trilha de auditoria

- Código/PR: https://github.com/lulualcides-sys/nexus-quant-paper/pull/75
- Execução CI aprovada: https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/43227184319
- Registro JSON completo com os 88 resultados, 3 custos e 66 recortes trimestrais: `research/preserved/xau_new_indicators_all_tf_2025plus_20261112.json`.

**Estado: salvo para pesquisa e validação futura, NÃO aprovado para trading real.**
