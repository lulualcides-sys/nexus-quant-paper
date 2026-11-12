# XAUUSD: pesquisa de liquidez, falsas rupturas e sessões — M1 a M30 (2025+)

**Resultado histórico experimental, não operação real nem relatório do Strategy Tester do MT5.** Auditoria em 12/11/2026.

## Escopo e racional

- Foco em **estrutura e comportamento de preço**, sem cruzamentos EMA/RSI/MACD para as quatro novas entradas. EMA21 original permaneceu intacta como controle.
- Quatro setups: varredura e retorno à máxima/mínima de ontem (UTC); varredura/retorno à faixa asiática 00–06 UTC (após 07 UTC); rompimento com reteste do primeiro intervalo 08–09 NY, com DST; rompimento sustentado da máxima/mínima anterior.
- Exatamente uma entrada por dia ou sessão em cada variante. Isso limita taxa de trades e precisa ser avaliado contra a oportunidade de outros robôs.
- Apenas XAUUSD, **2025 completo**, **2026 parcial (somente Q2/Q3)**, todos os 11 gráficos padrão de minutos M1/M2/M3/M4/M5/M6/M10/M12/M15/M20/M30.
- Fonte 2025 Git pinado `b2cfdc571ffac9eff9f2132ea6946da559d29af2`; fonte 2026 SHA256 verificada `a587597bbf88c2d868a00a4e0019cd705cee6ca4f20b0485d6b745f19fcc8225`. Feeds distintos.
- Próxima abertura após fechamento de candle confirmado, stop antes de alvo no mesmo candle ambíguo, gaps desfavoráveis, sem posições simultâneas, mesma saída 1/3 em 1R e 1/3 em 1,5R, restante até stop ou 96 horas de candles (não corridas).
- Custos fixos estimados de US$0,80/1,20/1,60 por onça por round-trip, ponto de preço assumido US$0,01, sem spread variável, slippage, comissão, swap, volume real ou MDD intratrade.
- Pesquisa embasada em hipóteses de volatilidade sazonal e ORB como mapa de liquidez, **não** em presunção de edge: https://openmarketjournal.com/research/gold-opening-range-breakout e https://swiftedge.uk/research/opening-range-breakouts .

## Resultado 1 — faixa asiática, M12: candidato para teste posterior

| Métrica | 2025 | 2026 parcial |
|---|---:|---:|
| Operações | 87 | 72 |
| Pontos líquidos simulados com custo US$0,80 | 13.383 | 9.446 |
| Profit Factor com custo US$0,80 | 1,411 | 1,215 |
| MDD pontos, somente trades encerrados | 16.098 | 11.847 |
| Net pts custo US$1.2 | 9.903 | 6.566 |
| Net pts custo US$1.6 | 6.423 | 3.686 |

### Faixa asiática M12 — distribuição trimestral (custo US$0,80)

| Período | Trades | Pontos líquidos | PF |
|---|---:|---:|---:|
| 2025Q1 | 9 | 609 | 1,202 |
| 2025Q2 | 19 | -10.030 | 0,091 |
| 2025Q3 | 28 | 2.182 | 1,377 |
| 2025Q4 | 31 | 20.622 | 2,621 |
| 2026Q2 | 34 | 13.163 | 1,581 |
| 2026Q3 | 38 | -3.717 | 0,826 |

**Cautela:** Q2/2025 teve -10.030 pts, Q4/2025 teve +20.622 pts, e Q3/2026 teve -3.717. Embora passe no filtro conservador de 3 trimestres positivos de 2025 e 1 de 2026 ao custo 1,20, não é consistência trimestral nem amostra independente. Não ativar em live.

## Resultado 2 — rompimento de ontem M20: anomalia estatística, não aprovado

| Métrica | 2025 | 2026 parcial |
|---|---:|---:|
| N | 88 | 34 |
| Net pontos, custo US$0,80 | 4.071 | 43.775 |
| PF custo US$0,80 | 1,074 | 2,950 |
| MDD, pontos encerrados | 14.114 | 5.946 |

**Aparência fora da curva enganosa:** o M20 breakout entregou +43.775 pontos e PF 2,95 em somente 34 trades de 2026 parcial. No entanto, em 2025 deu apenas +4.071 pontos a custo 0,80 e **-2.969 pontos** a custo 1,60, e 2025Q4 foi negativo. Não supera os três escolhidos quando se exige repetição entre ambientes e custos.

## Todas as 55 combinações dos 5 modelos e 11 TF — preço por onça simulado

| TF | Modelo | N25 | Net25 custo0,8 | PF25 | Net25 custo1,2 | N26 parcial | Net26 custo0,8 | PF26 | Net26 custo1,2 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| M1 | EMA21_BASE | 2055 | -181.351 | 0,370 | -263.551 | 630 | -34.015 | 0,717 | -59.215 |
| M1 | YDAY_SWEEP_RECLAIM | 153 | -12.658 | 0,524 | -18.778 | 70 | -14.775 | 0,373 | -17.575 |
| M1 | ASIA_SWEEP_RECLAIM | 113 | -4.517 | 0,730 | -9.037 | 97 | -15.172 | 0,399 | -19.052 |
| M1 | NY_ORB_BREAK_RETEST | 182 | 458 | 1,015 | -6.822 | 98 | -26.142 | 0,125 | -30.062 |
| M1 | YDAY_BREAK_HOLD | 132 | -5.085 | 0,804 | -10.365 | 61 | -9.552 | 0,686 | -11.992 |
| M2 | EMA21_BASE | 1147 | -71.988 | 0,621 | -117.868 | 402 | -9.073 | 0,912 | -25.153 |
| M2 | YDAY_SWEEP_RECLAIM | 145 | -14.265 | 0,564 | -20.065 | 75 | -24.385 | 0,233 | -27.385 |
| M2 | ASIA_SWEEP_RECLAIM | 101 | 8.337 | 1,443 | 4.297 | 89 | -6.204 | 0,802 | -9.764 |
| M2 | NY_ORB_BREAK_RETEST | 174 | 4.017 | 1,107 | -2.943 | 87 | -22.154 | 0,293 | -25.634 |
| M2 | YDAY_BREAK_HOLD | 131 | -18.481 | 0,439 | -23.721 | 56 | 6.802 | 1,251 | 4.562 |
| M3 | EMA21_BASE | 969 | -75.413 | 0,610 | -114.173 | 388 | -27.574 | 0,770 | -43.094 |
| M3 | YDAY_SWEEP_RECLAIM | 141 | -12.407 | 0,644 | -18.047 | 67 | -15.404 | 0,447 | -18.084 |
| M3 | ASIA_SWEEP_RECLAIM | 100 | 2.053 | 1,105 | -1.947 | 85 | 10.878 | 1,335 | 7.478 |
| M3 | NY_ORB_BREAK_RETEST | 167 | 5.893 | 1,159 | -787 | 65 | 3.690 | 1,123 | 1.090 |
| M3 | YDAY_BREAK_HOLD | 125 | -6.149 | 0,830 | -11.149 | 51 | 21.554 | 1,862 | 19.514 |
| M4 | EMA21_BASE | 786 | -51.677 | 0,713 | -83.117 | 375 | -22.499 | 0,819 | -37.499 |
| M4 | YDAY_SWEEP_RECLAIM | 139 | -12.555 | 0,647 | -18.115 | 63 | -15.619 | 0,441 | -18.139 |
| M4 | ASIA_SWEEP_RECLAIM | 98 | -2.966 | 0,889 | -6.886 | 83 | -11 | 1,000 | -3.331 |
| M4 | NY_ORB_BREAK_RETEST | 160 | -12.083 | 0,732 | -18.483 | 68 | 9.289 | 1,363 | 6.569 |
| M4 | YDAY_BREAK_HOLD | 117 | -7.290 | 0,809 | -11.970 | 51 | -10.746 | 0,727 | -12.786 |
| M5 | EMA21_BASE | 695 | -45.317 | 0,729 | -73.117 | 257 | 1.667 | 1,018 | -8.613 |
| M5 | YDAY_SWEEP_RECLAIM | 130 | -16.365 | 0,620 | -21.565 | 63 | -23.361 | 0,334 | -25.881 |
| M5 | ASIA_SWEEP_RECLAIM | 105 | -4.554 | 0,850 | -8.754 | 87 | -2.001 | 0,953 | -5.481 |
| M5 | NY_ORB_BREAK_RETEST | 156 | -9.534 | 0,783 | -15.774 | 65 | 1.490 | 1,061 | -1.110 |
| M5 | YDAY_BREAK_HOLD | 112 | 896 | 1,023 | -3.584 | 53 | -5.703 | 0,857 | -7.823 |
| M6 | EMA21_BASE | 571 | -23.407 | 0,851 | -46.247 | 278 | -11.720 | 0,887 | -22.840 |
| M6 | YDAY_SWEEP_RECLAIM | 125 | -11.533 | 0,750 | -16.533 | 56 | -10.320 | 0,661 | -12.560 |
| M6 | ASIA_SWEEP_RECLAIM | 95 | 1.865 | 1,059 | -1.935 | 78 | 11.907 | 1,290 | 8.787 |
| M6 | NY_ORB_BREAK_RETEST | 152 | -13.513 | 0,720 | -19.593 | 63 | -12.135 | 0,654 | -14.655 |
| M6 | YDAY_BREAK_HOLD | 115 | -16.080 | 0,636 | -20.680 | 46 | 24.294 | 1,930 | 22.454 |
| M10 | EMA21_BASE | 410 | 621 | 1,005 | -15.779 | 242 | -18.669 | 0,833 | -28.349 |
| M10 | YDAY_SWEEP_RECLAIM | 118 | -21.315 | 0,635 | -26.035 | 55 | -14.485 | 0,582 | -16.685 |
| M10 | ASIA_SWEEP_RECLAIM | 97 | -17.429 | 0,608 | -21.309 | 74 | 16.336 | 1,419 | 13.376 |
| M10 | NY_ORB_BREAK_RETEST | 120 | -23.475 | 0,560 | -28.275 | 55 | -4.512 | 0,890 | -6.712 |
| M10 | YDAY_BREAK_HOLD | 106 | -2.917 | 0,943 | -7.157 | 44 | 22.306 | 1,660 | 20.546 |
| M12 | EMA21_BASE | 365 | -11.729 | 0,914 | -26.329 | 217 | -7.231 | 0,928 | -15.911 |
| M12 | YDAY_SWEEP_RECLAIM | 108 | -982 | 0,979 | -5.302 | 50 | -24.280 | 0,400 | -26.280 |
| M12 | ASIA_SWEEP_RECLAIM | 87 | 13.383 | 1,411 | 9.903 | 72 | 9.446 | 1,215 | 6.566 |
| M12 | NY_ORB_BREAK_RETEST | 106 | -6.585 | 0,832 | -10.825 | 50 | -4.022 | 0,870 | -6.022 |
| M12 | YDAY_BREAK_HOLD | 105 | -17.038 | 0,692 | -21.238 | 42 | -884 | 0,977 | -2.564 |
| M15 | EMA21_BASE | 320 | 14.839 | 1,138 | 2.039 | 156 | 6.527 | 1,082 | 287 |
| M15 | YDAY_SWEEP_RECLAIM | 105 | -7.491 | 0,865 | -11.691 | 49 | -14.168 | 0,584 | -16.128 |
| M15 | ASIA_SWEEP_RECLAIM | 87 | 4.673 | 1,124 | 1.193 | 73 | -3.168 | 0,937 | -6.088 |
| M15 | NY_ORB_BREAK_RETEST | 90 | 7.613 | 1,218 | 4.013 | 47 | -6.150 | 0,822 | -8.030 |
| M15 | YDAY_BREAK_HOLD | 100 | -23.547 | 0,612 | -27.547 | 43 | 13.962 | 1,375 | 12.242 |
| M20 | EMA21_BASE | 276 | -5.014 | 0,957 | -16.054 | 136 | 5.758 | 1,072 | 318 |
| M20 | YDAY_SWEEP_RECLAIM | 103 | -9.677 | 0,838 | -13.797 | 55 | -39.003 | 0,314 | -41.203 |
| M20 | ASIA_SWEEP_RECLAIM | 95 | -34.724 | 0,435 | -38.524 | 70 | -9.720 | 0,830 | -12.520 |
| M20 | NY_ORB_BREAK_RETEST | 86 | 6.965 | 1,177 | 3.525 | 36 | -27.413 | 0,260 | -28.853 |
| M20 | YDAY_BREAK_HOLD | 88 | 4.071 | 1,074 | 551 | 34 | 43.775 | 2,950 | 42.415 |
| M30 | EMA21_BASE | 214 | -9.214 | 0,917 | -17.774 | 105 | 21.290 | 1,290 | 17.090 |
| M30 | YDAY_SWEEP_RECLAIM | 94 | -10.684 | 0,823 | -14.444 | 41 | -9.663 | 0,769 | -11.303 |
| M30 | ASIA_SWEEP_RECLAIM | 74 | -4.455 | 0,899 | -7.415 | 65 | -3.238 | 0,941 | -5.838 |
| M30 | NY_ORB_BREAK_RETEST | 61 | 14.210 | 1,337 | 11.770 | 30 | -32.305 | 0,117 | -33.505 |
| M30 | YDAY_BREAK_HOLD | 77 | -11.611 | 0,823 | -14.691 | 35 | -4.533 | 0,890 | -5.933 |

## Decisão sem viés de seleção

- Pré-triagem histórica: N 2025>=80, N 2026 parcial>=30, PF >1,10 e net positivo nos dois períodos sob custo 1,20, pelo menos três dos quatro trimestres de 2025 positivos e um dos dois disponíveis de 2026 positivo.
- **Somente M12 ASIA_SWEEP_RECLAIM passou** esse filtro em 55 combinações, mas a triagem não representa amostra fora do estudo nem autorização de negociação.
- A varredura asiática M12 apresentou ~87 operações em 2025 e 72 no recorte 2026: ela não atende uma meta de centenas de entradas mensais.
- O cenário a US$1,60/oz ainda é hipotético; swap e ticks podem eliminar a margem positiva.
- Já houve dezenas de combinações testadas sobre 2025/2026 nesta pesquisa; **não há amostra verdadeiramente intacta OOS**. A seleção do vencedor entre 55 pares infla a chance de resultado aleatório.
- Os três robôs expressamente salvos pelo usuário **permanecem os mesmos**, sem overwrite nem merge da nova pesquisa.
- Próxima etapa: MQL5 com execução em demo; tick Bid/Ask de corretora, slippage, spread, comissão e swap, risco por operação e teste prospectivo de parâmetros congelados. Avaliar MDD intratrade e sequência de perdas.

## Trilha de verificação

- [CI concluída com sucesso](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/43234997282)
- [PR #77 da pesquisa, draft](https://github.com/lulualcides-sys/nexus-quant-paper/pull/77)
- JSON completo: `research/preserved/xau_liquidity_session_m1_m30_2025plus_20261112.json`.
- Três candidatos anteriores: `research/preserved/xau_selected_three_candidates_20261112.json`.
