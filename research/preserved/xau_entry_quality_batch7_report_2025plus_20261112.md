# Nexus Quant / XAUUSD — pesquisa de entradas por risco e custo (lote 7)

**Execução verificada em 12/11/2026:** 25 combinações de entrada, cinco candidatos, 2025 e 2026 parcial (Q2/Q3), 30 recortes trimestrais. Timeframes autorizados M1/M5/M15/M30; os candidatos desta bateria operam em M5/M15/M30. Replay OHLC com os sinais/stops e Runner96h originais, não Strategy Tester com ticks reais.

**Regra pré-fixada antes dos resultados:** custo hipotético de US$1,20/onça deve ser no máximo 10% da distância entrada–stop; teste complementar de risco entre 0,7 e 2,2 ATR e qualidade >=0,35. Comissões, spread variável, swap, slippage e execução Bid/Ask da corretora não foram medidos. Pontos e Net R são simulações.

## Melhor ganho exploratório, mas frequência insuficiente

**EMA21 + RSI + MACD M30**: o filtro custo/stop <=10% produziu +8,235R (PF_R 1,367, 40 negócios) em 2025 e +10,746R (PF_R 1,620, 42 negócios) no recorte parcial 2026, contra -10,011R e +4,526R do original. Sob stress de custo US$1,60/onça ainda gerou +7,232R e +9,752R. **Não passou** triagem: abaixo de 100 trades em 2025 e 50 no período parcial 2026, reduzindo 113 para 40 operações em 2025, e somente 2 dos 4 trimestres 2025 positivos; +10,667R no quarto trimestre concentram quase todo ganho. NÃO promover para produção.

**EMA21 Runner M15** com filtro de stop entre 0,7 e 2,2 ATR: +10,059R/+10,546R contra +7,536R/+0,920R do original, mas PF_R 2025 só 1,055 e stress a custo US$1,60 gera -14,356R em 2025. **Falhou** triagem.

**ER20 M30** segue mais consistente SEM filtros na amostra: +23,729R e +11,623R (custo US$1,20). Nenhum filtro aumentou ambos os recortes.

**Shock M15** original melhor do que as variantes de filtro no agregado. Shock M5 melhorou sob qualidade>=0,35, mas permaneceu negativo no risco normalizado em 2025.

## Todas as 25 comparações no custo hipotético de US$1,20/onça

| Candidato | Regra de entrada | Operações 2025 | Net R2025 | PF R2025 | Operações 2026 parcial | Net R2026 | PF R2026 | Diferença R25 | Diferença R26 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| EMA21_RUNNER_M15 | UNFILTERED | 320 | 7,536 | 1,035 | 156 | 0,92 | 1,01 | 0 | 0 |
| EMA21_RUNNER_M15 | RISK_ATR_0P7_TO_2P2 | 292 | 10,059 | 1,055 | 138 | 10,546 | 1,14 | 2,523 | 9,626 |
| EMA21_RUNNER_M15 | COST_TO_STOP_LE_10PCT | 51 | 10,384 | 1,42 | 87 | 0,85 | 1,021 | 2,848 | -0,07 |
| EMA21_RUNNER_M15 | QUALITY_GE_0P35 | 314 | 14,728 | 1,07 | 150 | 4,652 | 1,054 | 7,192 | 3,732 |
| EMA21_RUNNER_M15 | RISK_AND_QUALITY | 290 | 10,247 | 1,056 | 137 | 10,184 | 1,135 | 2,711 | 9,264 |
| EMA21_RSI_MACD_M30 | UNFILTERED | 113 | -10,011 | 0,859 | 54 | 4,526 | 1,172 | 0 | 0 |
| EMA21_RSI_MACD_M30 | RISK_ATR_0P7_TO_2P2 | 100 | -8,576 | 0,857 | 47 | 8,52 | 1,418 | 1,435 | 3,994 |
| EMA21_RSI_MACD_M30 | COST_TO_STOP_LE_10PCT | 40 | 8,235 | 1,367 | 42 | 10,746 | 1,62 | 18,246 | 6,22 |
| EMA21_RSI_MACD_M30 | QUALITY_GE_0P35 | 112 | -8,715 | 0,875 | 54 | 4,526 | 1,172 | 1,296 | 0 |
| EMA21_RSI_MACD_M30 | RISK_AND_QUALITY | 100 | -8,648 | 0,856 | 47 | 8,52 | 1,418 | 1,363 | 3,994 |
| ER20_BREAK_M30 | UNFILTERED | 110 | 23,729 | 1,39 | 52 | 11,623 | 1,372 | 0 | 0 |
| ER20_BREAK_M30 | RISK_ATR_0P7_TO_2P2 | 115 | 13,303 | 1,196 | 47 | 15,442 | 1,542 | -10,426 | 3,819 |
| ER20_BREAK_M30 | COST_TO_STOP_LE_10PCT | 67 | 13,269 | 1,351 | 46 | 15,53 | 1,582 | -10,46 | 3,907 |
| ER20_BREAK_M30 | QUALITY_GE_0P35 | 111 | 22,078 | 1,356 | 50 | 12,372 | 1,41 | -1,651 | 0,749 |
| ER20_BREAK_M30 | RISK_AND_QUALITY | 115 | 12,211 | 1,18 | 47 | 15,442 | 1,542 | -11,518 | 3,819 |
| SHOCK_EXHAUSTION_M5 | UNFILTERED | 190 | -20,499 | 0,842 | 101 | 6,387 | 1,107 | 0 | 0 |
| SHOCK_EXHAUSTION_M5 | RISK_ATR_0P7_TO_2P2 | 189 | -47,256 | 0,653 | 96 | 5,59 | 1,098 | -26,757 | -0,797 |
| SHOCK_EXHAUSTION_M5 | COST_TO_STOP_LE_10PCT | 15 | 5,514 | 1,802 | 37 | -12,257 | 0,456 | 26,013 | -18,644 |
| SHOCK_EXHAUSTION_M5 | QUALITY_GE_0P35 | 182 | -14,07 | 0,885 | 99 | 7,801 | 1,135 | 6,429 | 1,414 |
| SHOCK_EXHAUSTION_M5 | RISK_AND_QUALITY | 182 | -40,454 | 0,688 | 95 | 6,112 | 1,109 | -19,955 | -0,275 |
| SHOCK_EXHAUSTION_M15 | UNFILTERED | 90 | 27,857 | 1,539 | 45 | 11,682 | 1,554 | 0 | 0 |
| SHOCK_EXHAUSTION_M15 | RISK_ATR_0P7_TO_2P2 | 85 | 18,879 | 1,356 | 44 | 8,093 | 1,347 | -8,978 | -3,589 |
| SHOCK_EXHAUSTION_M15 | COST_TO_STOP_LE_10PCT | 38 | 12,61 | 1,607 | 35 | 6,749 | 1,426 | -15,247 | -4,933 |
| SHOCK_EXHAUSTION_M15 | QUALITY_GE_0P35 | 86 | 22,89 | 1,459 | 45 | 11,682 | 1,554 | -4,967 | 0 |
| SHOCK_EXHAUSTION_M15 | RISK_AND_QUALITY | 82 | 12,815 | 1,245 | 44 | 8,093 | 1,347 | -15,042 | -3,589 |

## O efeito trimestral que impede conclusão exagerada

| Trimestre | EMA RSI MACD M30 original (R) | EMA RSI MACD M30 filtro custo/stop (R) | Operações filtro |
|---|---:|---:|---:|
| 2025Q1 | -17,837 | 0,32 | 4 |
| 2025Q2 | -3,771 | -1,405 | 11 |
| 2025Q3 | 3,036 | -1,347 | 4 |
| 2025Q4 | 8,562 | 10,667 | 21 |
| 2026Q2 | 2,691 | 4,573 | 25 |
| 2026Q3 | 1,835 | 6,173 | 17 |

## Controle e próximos passos

- **Zero candidatos passaram todos os critérios:** N>=100/50, >=75% da frequência original, lucro em R e PF_R>1,10 nos dois períodos a custo1,20, lucro também no stress1,60, pelo menos 3 trimestres positivos em 2025 e 1 em 2026, DD_R até 110% do baseline, melhora simultânea nos dois recortes.
- O filtro custo/stop é **apenas uma hipótese congelada para teste prospectivo**, não comprovação de lucro. Ajustar o limiar para fazer subir quantidade sem amostra externa seria otimização sobreajustada.
- **Não alterar nenhum dos nove candidatos catalogados, sinais, stops originais ou Runner original.** As variantes permanecem em PR draft e não operam em live.
- O próximo trabalho útil: obter dados prospectivos de corretora com Bid/Ask e ticks reais, verificar a dimensão contratual de XAUUSD, lotagem arredondada, slippage, comissão, spread e swap; comparar expectativa em R com riscos e gastos reais.
- 2025 e 2026 parcial já foram usados intensivamente por baterias anteriores; esta amostra não é teste fora da amostra independente, e a seleção de melhores entre 25 configurações aumenta falso positivo.

## Evidências

- [GitHub Actions concluída com testes de regressão e sinais intactos](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/43262541010)
- [PR #81, isolada e não mesclada](https://github.com/lulualcides-sys/nexus-quant-paper/pull/81)
- [Dados completos anuais/trimestrais e custo stress](xau_entry_quality_batch7_full_2025plus_20261112.json)
- [Nove robôs anteriores preservados](xau_selected_nine_candidates_20261112.json)
