# AlphaXAU v1.02: backtest das regras técnicas hipotéticas (não da IA)

**Diagnóstico:** a imagem enviada era ilustrativa. AlphaXAU v1.02 é um EA de análise consultiva com botões manuais, não opera em OnTick e não tem sinal de compra/venda emitido pelo Ollama em cada candle. O MT5 desativa WebRequest no testador.

## Metodologia
XAUUSD M15; 2025 completo e 2026 parcial. Duas regras novas e explícitas extraídas dos insumos técnicos do EA: (A) início de regime EMA21/55 e (B) mesma tendência + BOS25. SL1,5ATR14, TP1,8R, 0,5% do patrimônio inicial por operação em risco estimado, US$10 mil em cada período, 100 oz/lote hipotéticas, lote mínimo 0,01 e máximo 0,50; custos por onça hipotéticos.

| Período | Hipótese | Custo US$/oz | Operações | Lucro líquido simulado US$ | PF | Acerto % | DD fechado % |
|---|---|---:|---:|---:|---:|---:|---:|
| 2025 | EMA21_55_REGIME_CHANGE | 0.8 | 856 | -1373.48 | 0.946 | 39.02 | 20.25 |
| 2025 | EMA21_55_REGIME_CHANGE | 1.2 | 858 | -3264.28 | 0.857 | 38.93 | 34.07 |
| 2025 | EMA21_55_REGIME_CHANGE | 1.6 | 846 | -4300.77 | 0.798 | 39.24 | 44.38 |
| 2025 | EMA21_55_BOS25 | 0.8 | 880 | -2801.84 | 0.882 | 37.16 | 30.95 |
| 2025 | EMA21_55_BOS25 | 1.2 | 875 | -4212.73 | 0.805 | 37.37 | 43.58 |
| 2025 | EMA21_55_BOS25 | 1.6 | 870 | -5206.15 | 0.742 | 37.36 | 53.33 |
| 2026_partial | EMA21_55_REGIME_CHANGE | 0.8 | 465 | -1709.16 | 0.857 | 35.27 | 19.92 |
| 2026_partial | EMA21_55_REGIME_CHANGE | 1.2 | 463 | -2067.12 | 0.825 | 35.21 | 21.63 |
| 2026_partial | EMA21_55_REGIME_CHANGE | 1.6 | 458 | -2565.80 | 0.781 | 34.93 | 26.44 |
| 2026_partial | EMA21_55_BOS25 | 0.8 | 435 | -1286.07 | 0.891 | 35.63 | 17.91 |
| 2026_partial | EMA21_55_BOS25 | 1.2 | 435 | -1740.50 | 0.851 | 35.63 | 20.62 |
| 2026_partial | EMA21_55_BOS25 | 1.6 | 434 | -2110.21 | 0.818 | 35.71 | 23.63 |

## Conclusão
As duas hipóteses tiveram prejuízo em ambos os períodos, inclusive com custos menores. **Reprovadas como estratégias automáticas.** Não atribuir esses resultados à IA Llama, cuja consulta não foi reproduzida.

## Limitações
Sem MetaEditor/MT5 real ticks. Dados M1 públicos reamostrados para M15; execução OHLC e custos hipotéticos; não incorpora tick Bid/Ask, slip, swap, especificações reais do contrato, margem ou DD intrabar. Histórico de 2026 cobre apenas 26/03–25/09/2026.

**GitHub Actions concluída:** https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/43746151888

Script Python original e resultados JSON arquivados nesta branch; artefato da execução contém logs dos negócios.
