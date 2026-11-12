# XAUUSD — auditoria das saídas e do risco (lote 6, 12/11/2026)

**Resultado:** nenhuma nova saída apresentou desempenho líquido em R superior ao Runner original em ambos os recortes. Nenhuma passou integralmente na triagem pré-definida. Não publicar alteração em produção.

**Escopo:** XAUUSD, a partir de 2025, somente M1/M5/M15/M30 permitidos. Cinco estratégias estudadas (M5, M15 e M30), cinco perfis de saída, 25 comparações, dez painéis anuais e 30 painéis trimestrais. 2026 parcial, Q2/Q3. Dataset 2025 e 2026 de fontes diferentes; os dois períodos já foram explorados repetidamente e não constituem out-of-sample intacto.

**Método:** mesmos eventos de entrada, stops originais, TP1=1R, TP2=1,5R, um terço de posição por parcial, final até stop ou 96h de candles. Runner original; BE após TP2 e reversão BE já existentes; trailing de 2 ATR após TP2 com velas fechadas; saída programada em 24h executada no open seguinte. Replay OHLC com stop-first e gaps desfavoráveis; custos simulados de US$0,80, US$1,20 e US$1,60/onça por trade.

**Comparação correta de risco:** Net R=(lucro bruto na moeda de preço − custo hipotético por onça) ÷ distância inicial entrada-stop. Cada operação é normalizada a 1R de risco nominal. **Não é porcentagem da banca**, e pressupõe posições fracionárias ideais, sem regras de lotes, margem ou comissões reais.

## Baseline inalterado — R sob custo hipotético US$1,20/onça

| Estratégia | Trades 2025 | Net R 2025 | PF em R 2025 | DD R 2025 | Trades 2026 parcial | Net R 2026 | PF em R 2026 | DD R 2026 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| EMA21_RUNNER_M15 | 320 | 7,536 | 1,035 | 38,928 | 156 | 0,92 | 1,01 | 26,413 |
| EMA21_RSI_MACD_M30 | 113 | -10,011 | 0,859 | 27,103 | 54 | 4,526 | 1,172 | 12,644 |
| ER20_BREAK_M30 | 110 | 23,729 | 1,39 | 10,191 | 52 | 11,623 | 1,372 | 11,988 |
| SHOCK_EXHAUSTION_M5 | 190 | -20,499 | 0,842 | 46,62 | 101 | 6,387 | 1,107 | 19,99 |
| SHOCK_EXHAUSTION_M15 | 90 | 27,857 | 1,539 | 23,364 | 45 | 11,682 | 1,554 | 5,665 |

## As 25 comparações — custo hipotético US$1,20/onça

| Estratégia | Saída | N25 | Net R25 | PF R25 | N26 parcial | Net R26 | PF R26 | Delta R25 vs original | Delta R26 vs original |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| EMA21_RUNNER_M15 | RUNNER_96H | 320 | 7,536 | 1,035 | 156 | 0,92 | 1,01 | 0 | 0 |
| EMA21_RUNNER_M15 | BE_AFTER_TP2 | 439 | -38,038 | 0,875 | 254 | -27,46 | 0,815 | -45,574 | -28,38 |
| EMA21_RUNNER_M15 | REVERSAL_BE | 398 | -40,757 | 0,856 | 227 | -15,919 | 0,87 | -48,293 | -16,839 |
| EMA21_RUNNER_M15 | TRAIL_ATR2_AFTER_TP2 | 1032 | -218,914 | 0,693 | 526 | -57,892 | 0,819 | -226,45 | -58,812 |
| EMA21_RUNNER_M15 | TIME_EXIT_24H | 595 | -135,876 | 0,679 | 291 | -36,538 | 0,79 | -143,412 | -37,458 |
| EMA21_RSI_MACD_M30 | RUNNER_96H | 113 | -10,011 | 0,859 | 54 | 4,526 | 1,172 | 0 | 0 |
| EMA21_RSI_MACD_M30 | BE_AFTER_TP2 | 136 | -2,398 | 0,972 | 64 | -0,542 | 0,984 | 7,613 | -5,068 |
| EMA21_RSI_MACD_M30 | REVERSAL_BE | 130 | -6,485 | 0,919 | 62 | -1,375 | 0,955 | 3,526 | -5,901 |
| EMA21_RSI_MACD_M30 | TRAIL_ATR2_AFTER_TP2 | 169 | -5,982 | 0,943 | 78 | 0,87 | 1,02 | 4,029 | -3,656 |
| EMA21_RSI_MACD_M30 | TIME_EXIT_24H | 153 | -15,024 | 0,842 | 69 | 10,036 | 1,285 | -5,013 | 5,51 |
| ER20_BREAK_M30 | RUNNER_96H | 110 | 23,729 | 1,39 | 52 | 11,623 | 1,372 | 0 | 0 |
| ER20_BREAK_M30 | BE_AFTER_TP2 | 124 | 22,724 | 1,325 | 69 | -9,523 | 0,783 | -1,005 | -21,146 |
| ER20_BREAK_M30 | REVERSAL_BE | 120 | 21,177 | 1,308 | 69 | -10,263 | 0,766 | -2,552 | -21,886 |
| ER20_BREAK_M30 | TRAIL_ATR2_AFTER_TP2 | 197 | -6,2 | 0,943 | 94 | 0,883 | 1,017 | -29,929 | -10,74 |
| ER20_BREAK_M30 | TIME_EXIT_24H | 174 | 4,342 | 1,044 | 83 | 9,97 | 1,225 | -19,387 | -1,653 |
| SHOCK_EXHAUSTION_M5 | RUNNER_96H | 190 | -20,499 | 0,842 | 101 | 6,387 | 1,107 | 0 | 0 |
| SHOCK_EXHAUSTION_M5 | BE_AFTER_TP2 | 217 | -28,568 | 0,804 | 112 | 21,795 | 1,343 | -8,069 | 15,408 |
| SHOCK_EXHAUSTION_M5 | REVERSAL_BE | 215 | -32,732 | 0,775 | 112 | 20,53 | 1,323 | -12,233 | 14,143 |
| SHOCK_EXHAUSTION_M5 | TRAIL_ATR2_AFTER_TP2 | 315 | -65,135 | 0,689 | 177 | -8,681 | 0,92 | -44,636 | -15,068 |
| SHOCK_EXHAUSTION_M5 | TIME_EXIT_24H | 246 | -56,259 | 0,663 | 137 | 10,87 | 1,14 | -35,76 | 4,483 |
| SHOCK_EXHAUSTION_M15 | RUNNER_96H | 90 | 27,857 | 1,539 | 45 | 11,682 | 1,554 | 0 | 0 |
| SHOCK_EXHAUSTION_M15 | BE_AFTER_TP2 | 107 | -1,24 | 0,981 | 50 | 6,304 | 1,243 | -29,097 | -5,378 |
| SHOCK_EXHAUSTION_M15 | REVERSAL_BE | 104 | 18,571 | 1,294 | 50 | 5,574 | 1,215 | -9,286 | -6,108 |
| SHOCK_EXHAUSTION_M15 | TRAIL_ATR2_AFTER_TP2 | 128 | -22,05 | 0,735 | 68 | 0,094 | 1,003 | -49,907 | -11,588 |
| SHOCK_EXHAUSTION_M15 | TIME_EXIT_24H | 110 | -10,505 | 0,85 | 62 | 7,664 | 1,245 | -38,362 | -4,018 |

## Diagnóstico e decisão

- ER20 M30 Runner: **+23,729R em 2025 e +11,623R em 2026 parcial**, com N110/52 e PF_R 1,390/1,372 a custo1,20. Melhor comportamento entre as estratégias de referência quando se inclui risco nominal.
- Shock Exhaustion M15 Runner: **+27,857R e +11,682R** e PF_R 1,539/1,554, mas amostras de **90/45 operações**, abaixo do corte de 100/50. 2025Q2 e 2026Q3 ruins; não tratar como evidência conclusiva.
- EMA21+RSI+MACD M30 apresenta +7.720,5 pontos acumulados em 2025 com custo1,20, **mas −10,011R** com risco nominal padronizado. Tamanho do stop influencia fortemente a conclusão.
- Shock Exhaustion M5 apresenta +10.394,8 pontos em 2025 com custo1,20, mas **−20,499R** padronizados. É inadequado afirmar que a estratégia já possui vantagem positiva a risco fixo.
- Trailing ATR e 24h liberaram entradas adicionais, mas pioraram resultados em alguns recortes. Logo, são **comparações de políticas**, e não experimentos com número de trades fixo.
- Nenhum novo perfil melhorou o Net R em ambos os períodos. **Não mesclar as novas saídas nem sobrescrever os nove robôs catalogados.**
- O número de testes realizados em 2025/2026 aumenta o risco de seleção por acaso. Novas otimizações nesses mesmos períodos reduzem a confiabilidade.
- Próxima investigação prioritária: distribuição de risco/stop por trade dos candidatos M5/M30, e validação MQL5 com ticks e custos do broker em forward demo após congelar parâmetros.

## Evidências

- [GitHub Actions concluído com sucesso, após corrigir sintaxe inicial](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/43261053527)
- [PR draft #80, código isolado](https://github.com/lulualcides-sys/nexus-quant-paper/pull/80)
- [Dados completos, inclusive resultados negativos](xau_exit_risk_batch6_full_2025plus_20261112.json)
- [Nove candidatos preservados](xau_selected_nine_candidates_20261112.json)

**Atenção:** OHLC, não MT5 real ticks; não inclui bid-ask, spread variável, comissão, swap, slippage, lotes, patrimônio da conta, ou drawdown intratrade.
