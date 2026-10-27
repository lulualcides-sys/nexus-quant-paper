# BB20 — experimento robustez, cinco gráficos, 40 dias

**Janela:** 2026-09-17 00:07 UTC a 2026-10-27 00:07 UTC (20 dias desenvolvimento, 20 validação retrospectiva).
**Preços:** Yahoo Finance M15, custos estimados, nenhuma operação FBS.
**Hipótese:** no H1 EMA50/200 confirmam lado, M15 toca e reage na SMA20, trailing sem alvo fixo.
**O risco permanece 0,75% planejado e 1x nocional em cada banca independente de US$ 1.000.**

## Comparação principal
| Variante | Período | Fechadas | Positivas (mercados) | Lucro líquido virtual USD |
|---|---|---:|---:|---:|
| Original | train | 104 | 3/5 | -37.68 |
|  | validation | 105 | 0/5 | -69.11 |
|  | full | 209 | 1/5 | -104.41 |
| Escolhida pelo desenvolvimento | train | 60 | 4/5 | +4.91 |
|  | validation | 68 | 0/5 | -69.25 |
|  | full | 130 | 3/5 | -65.01 |

**Escolhida por treino:** wick_rejection__trail_1p0R
**Aprovada pela validação:** NÃO

## Baseline e candidata, por mercado (validação somente)
| Mercado | Base n | Base % acerto | Base resultado | Selecionada n | Selecionada % acerto | Selecionada resultado |
|---|---:|---:|---:|---:|---:|---:|
| EURUSD | 18 | 22.22 | -9.11 | 8 | 12.5 | -7.53 |
| USDJPY | 18 | 27.78 | -9.72 | 10 | 20.0 | -5.08 |
| XAUUSD | 27 | 25.93 | -10.66 | 19 | 31.58 | -14.43 |
| US500 | 19 | 31.58 | -9.34 | 15 | 33.33 | -7.83 |
| XTIUSD | 23 | 34.78 | -30.29 | 16 | 31.25 | -34.39 |

## Todos os 36 testes - desenvolvimento e validação
| Família | Trailing R | Dev operações | Dev saldo USD | Val operações | Val saldo USD | Val positivos |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 1.0 | 104 | -37.68 | 105 | -69.11 | 0/5 |
| baseline | 1.5 | 75 | -56.90 | 84 | -92.50 | 0/5 |
| baseline | 2.0 | 64 | -92.29 | 68 | -45.82 | 1/5 |
| adx18 | 1.0 | 64 | -42.10 | 63 | -11.99 | 2/5 |
| adx18 | 1.5 | 46 | -30.14 | 54 | -42.32 | 1/5 |
| adx18 | 2.0 | 41 | -50.02 | 43 | -9.75 | 2/5 |
| adx23 | 1.0 | 46 | -24.70 | 47 | -21.72 | 1/5 |
| adx23 | 1.5 | 31 | -7.96 | 39 | -35.91 | 1/5 |
| adx23 | 2.0 | 26 | -19.33 | 31 | -21.61 | 1/5 |
| ema_separation | 1.0 | 94 | -27.08 | 82 | -31.51 | 1/5 |
| ema_separation | 1.5 | 68 | -35.62 | 66 | -68.82 | 0/5 |
| ema_separation | 2.0 | 56 | -73.97 | 53 | -23.61 | 1/5 |
| strong_trend | 1.0 | 53 | -27.88 | 51 | -0.88 | 2/5 |
| strong_trend | 1.5 | 36 | -8.88 | 42 | -35.75 | 0/5 |
| strong_trend | 2.0 | 31 | -21.43 | 33 | -3.34 | 2/5 |
| wick_rejection | 1.0 | 60 | +4.91 | 68 | -69.25 | 0/5 |
| wick_rejection | 1.5 | 48 | -5.54 | 55 | -74.52 | 0/5 |
| wick_rejection | 2.0 | 43 | -43.86 | 52 | -55.24 | 0/5 |
| session_liquid | 1.0 | 73 | -12.63 | 79 | -18.66 | 1/5 |
| session_liquid | 1.5 | 54 | -28.09 | 66 | -74.11 | 0/5 |
| session_liquid | 2.0 | 49 | -56.81 | 53 | -29.28 | 1/5 |
| adx_session | 1.0 | 43 | -20.60 | 46 | +19.92 | 2/5 |
| adx_session | 1.5 | 33 | -6.62 | 41 | -28.54 | 0/5 |
| adx_session | 2.0 | 30 | -17.34 | 32 | +2.21 | 1/5 |
| volatility | 1.0 | 60 | -38.04 | 41 | -16.28 | 1/5 |
| volatility | 1.5 | 50 | -62.13 | 34 | -45.53 | 0/5 |
| volatility | 2.0 | 44 | -85.99 | 27 | -11.70 | 1/5 |
| rsi_follow | 1.0 | 95 | -49.41 | 94 | -67.21 | 0/5 |
| rsi_follow | 1.5 | 73 | -62.49 | 73 | -76.81 | 0/5 |
| rsi_follow | 2.0 | 62 | -91.71 | 62 | -27.08 | 1/5 |
| adx_wick | 1.0 | 33 | +17.45 | 42 | -6.93 | 1/5 |
| adx_wick | 1.5 | 29 | +1.81 | 34 | -30.60 | 0/5 |
| adx_wick | 2.0 | 25 | -14.47 | 32 | -6.81 | 1/5 |
| slope20 | 1.0 | 81 | -29.24 | 79 | -54.22 | 1/5 |
| slope20 | 1.5 | 61 | -37.15 | 70 | -81.11 | 1/5 |
| slope20 | 2.0 | 52 | -61.04 | 56 | -11.53 | 1/5 |

## Advertências
- Exploramos 36 combinações; selecionar a melhor no treino cria risco de overfitting.
- Os dados de validação pertencem a um período parcialmente investigado anteriormente.
- Mesmo um resultado positivo não valida operações reais nem rentabilidade recorrente.
- Futuros GC=F, ES=F e CL=F usam exposição fracionária fictícia; não representam contratos executáveis com US$ 1.000.
- Yahoo não fornece os bid/ask e a liquidez FBS; spreads e slippage reais podem ser maiores.
- Todos os cinco gráficos foram exigidos; nenhuma falha foi substituída por lucro zero.
- Stops simulados com gaps adversos e avanço pelo fechamento M15 posterior, sem olhar o futuro.
- OHLC originais preservados em arquivos compactados por ticker para auditoria.
- **Nenhuma configuração nova foi ativada automaticamente nos robôs de produção virtual.**
