# XAUUSD — Segunda leva de indicadores (M1 a M30, 2025+)

**Data:** 12/11/2026. **Somente pesquisa histórica; não é teste de ticks MT5 nem lucro real.**

## Escopo preservado

- Apenas XAUUSD e dados de 2025 em diante; 2026 é parcial (Q2 e Q3 na fonte disponível).
- Todos os 11 timeframes oficiais MT5 de M1 a M30.
- Modelos testados: EMA21 Runner original; Supertrend ATR(10) ×3; CCI20 Reclaim; Williams %R14 Reclaim; Hull MA21 Pullback.
- Mesmas saídas: 1/3 em 1R, 1/3 em 1,5R, último terço até o stop inicial ou máximo proporcional a 96 horas de candles.
- Próxima abertura após sinal em candle fechado; em candle ambíguo o stop vem antes do TP; gaps preenchidos conservadoramente.
- Custo hipotético US$ 0,80/1,20/1,60 por onça por round-trip; POINT 0,01 assumido; sem Bid/Ask real, swap, slippage, comissão, margem ou drawdown intratrade.

## Destaque: Hull21 Pullback M20

| Métrica | 2025 | 2026 parcial |
|---|---:|---:|
| Entradas | 254 | 130 |
| Pontos líquidos estimados (custo 0,80) | **+27.277,8** | **+22.320,3** |
| Profit Factor (custo 0,80) | 1,261 | 1,272 |
| MDD em pontos (equity apenas ao fechar trades) | 15.180,4 | 14.593,1 |
| Pontos líquidos (custo 1,20) | +17.117,8 | +17.120,3 |
| PF (custo 1,20) | 1,155 | 1,200 |
| Pontos líquidos (custo 1,60) | +6.957,8 | +11.920,3 |

### Concentração trimestral — Hull M20 a custo 0,80

| Trimestre | Pontos estimados |
|---|---:|
| 2025 Q1 | −7.105,8 |
| 2025 Q2 | +9.662,8 |
| 2025 Q3 | +2.025,9 |
| 2025 Q4 | +22.694,9 |
| 2026 Q2 | +17.744,8 |
| 2026 Q3 | +4.575,5 |

**Atenção:** Q4 representa aproximadamente 83% do resultado líquido de 2025. A distribuição não é estável em todos os trimestres. Os anos já foram estudados e 55 combinações de timeframe/modelo foram consideradas; isso cria viés de seleção.

## Outro candidato de pesquisa: Supertrend ATR10 ×3, M3

Com custo hipotético 0,80: +6.023,3 pontos em 2025 (95 entradas, PF 1,162) e +15.676,5 pontos em 2026 parcial (49 entradas, PF 1,537). **Não passou a triagem**: menos de 100/50 entradas, PF 2025 abaixo de 1,10 sob custo 1,20 e 2025 se torna negativo com custo 1,60.

## Decisão

**Somente Hull21 M20** passou a triagem conservadora experimental desta segunda leva: mais de 100 e 50 trades, PF > 1,10, saldo positivo nos dois anos sob custo hipotético 1,20.

Os **dois candidatos prioritários escolhidos pelo usuário não foram substituídos**: EMA21 Runner M15 e EMA21+RSI+MACD M30. Hull M20 permanece apenas terceira possibilidade de pesquisa, não habilitada para trading real.

Faltam EA MQL5 compilado, testes MT5 com ticks Bid/Ask de corretora, especificação de contrato e custos reais, forward prospectivo e avaliação de drawdown intratrade. Não declarar vantagem futura nem lucro consistente.

## Evidências

- [GitHub Actions final — success](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/43232369781)
- [PR #76 — código novo, testes e pipeline](https://github.com/lulualcides-sys/nexus-quant-paper/pull/76)
- [JSON de métricas anuais e trimestrais de todos os modelos](xau_indicator_batch2_full_2025plus_20261112.json)
- [Registro dos dois candidatos prioritários](xau_two_priority_candidates_for_mt5_validation_20261112.json)

**Estado: resultados salvos para pesquisa; não aprovado para conta real.**
