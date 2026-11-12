# Ouro — todos os robôs originais no M30 e comparação correta M1/M5/M15

**10/11/2026 | EXPERIMENTO.** [Execução e artefatos verificados](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42850833462). O pipeline foi concluído com sucesso; 24 pregões validamente gravados em XAUUSD (Dukascopy bid/ask, candles MID) e checksum do relatório original validado. O script de comparação é [research/xau_m30_matched.py](../research/xau_m30_matched.py).

**Janela de operações alinhada entre todos os timeframes:** de **21/10/2026 às 14:30 UTC** até **05/11/2026**, usando os candles anteriores apenas para aquecimento. Assim, estes números **NÃO substituem** o [snapshot M15 positivo anterior salvo na main](https://github.com/lulualcides-sys/nexus-quant-paper/blob/main/research/preserved/xau_m15_positive_20261110.json), que abrangia o período completo.

A pesquisa abrange os **27 slots do conjunto original mais ATLAS**, mas são **16 regras distintas** quando as três regras H1 são repetidas cinco vezes no mesmo ouro. O BB20 do USD/CAD usa sua regra SMA/H1 original, mas dimensionamento convertido para ouro; ATLAS mede alterações de quotes, não volume de negociações. Os sinais originais dos demais motores não foram substituídos. As despesas são estimativas por nocional (7 bps convencional e 14 bps alavancado), com stress de dobro; os fills usam candles MID, não execução MT5 bid/ask por tick.

## Comparação das 16 regras distintas

Dólares por **banca virtual independente**; não somar como carteira. Os números M30 são realizados em posições fechadas (não incluem marcação a mercado de posições abertas).

| Robô original | M1 US$ | M5 US$ | M15 US$ | M30 US$ | M30 ×2 custos | Ops M30 |
|---|---:|---:|---:|---:|---:|---:|
| RSI Trend (`gold_h4:rsi_trend`) | -587.02 | -228.50 | -215.27 | **+0.89** | -24.88 | 8 |
| Channel 20 (`gold_h4:channel20`) | -503.08 | -169.41 | +114.96 | **+57.93** | +38.05 | 6 |
| Pullback 20 (`gold_h4:pullback20`) | -468.72 | -263.71 | -162.14 | **-100.87** | -123.70 | 7 |
| Momentum 100 (`gold_h4:momentum100`) | -456.23 | -187.15 | -102.91 | **+62.41** | +41.96 | 7 |
| Channel 55 (`gold_h4:channel55`) | -410.17 | -45.00 | +146.96 | **-4.30** | -20.52 | 5 |
| Channel 20 alav. (`leveraged_h4:lev_channel20`) | -759.87 | -155.79 | +270.14 | **+208.51** | +151.17 | 4 |
| Momentum 100 alav. (`leveraged_h4:lev_momentum100`) | -753.24 | -479.26 | -147.06 | **+59.43** | -163.02 | 6 |
| Channel 55 alav. (`leveraged_h4:lev_channel55`) | -763.09 | -303.22 | +393.00 | **+69.45** | +13.18 | 4 |
| Momentum 40 alav. (`leveraged_h4:lev_momentum40`) | -764.44 | -458.93 | +91.94 | **+257.94** | +200.22 | 4 |
| Trend Long alav. (`leveraged_h4:lev_trend_long`) | -420.73 | -97.26 | +111.70 | **0.00** | 0.00 | 0 |
| EMA20 Retest (`experimental_h1:XAUUSD:ema20_retest`) | -186.88 | -28.90 | +15.21 | **-6.67** | -10.14 | 8 |
| Channel 10 (`experimental_h1:XAUUSD:channel10`) | -120.92 | -33.76 | +1.24 | **-10.87** | -13.22 | 7 |
| RSI50 (`experimental_h1:XAUUSD:rsi50`) | -158.95 | -24.37 | +26.42 | **-15.46** | -18.02 | 7 |
| Momentum60 (`momentum60_h4:momentum60`) | -428.78 | -167.36 | -31.35 | **+100.62** | +94.03 | 2 |
| BB20 reteste (`usdcad_m15:bb20`) | +10.26 | -0.05 | -42.75 | **-26.01** | -26.72 | 1 |
| ATLAS (`atlas_28:atlas`) | -128.81 | -67.88 | -82.25 | **-88.76** | -104.09 | 5 |

## Resultado agregado por número de modelos

| Indicador | M1 | M5 | M15 | M30 |
|---|---:|---:|---:|---:|
| Regras distintas positivas / 16 | 1 | 0 | 9 | 8 |
| Regras distintas positivas com custos ×2 / 16 | 0 | 0 | 8 | 6 |
| Entradas positivas considerando os 28 slots | 1 | 0 | 21 | 8 |
| Fechamentos (16 regras distintas) | 1.972 | 368 | 138 | 81 |

**M30 tem seis resultados positivos sob custo dobrado:** Momentum40 alavancado, Channel20 alavancado, Momentum60, Momentum100 convencional, Channel20 convencional e Channel55 alavancado. Contagens por regra de 2 a 7 negociações; **nenhuma é estatisticamente aprovada para operação real**.

## M1 e M5: teste de permanência (sem mudar o sinal de compra/venda)

Mantive os indicadores, regras de entrada, ATR stops e custos. Alterei apenas o tempo máximo de saída no cenário de pesquisa para corresponder ao relógio M15: **M1 ×15 e M5 ×3**. Não houve otimização de parâmetros após olhar a amostra.

| Indicador | M1 original | M1 tempo M15 | M5 original | M5 tempo M15 |
|---|---:|---:|---:|---:|
| Regras positivas / 16 | 1 | 1 | 0 | 2 |
| Regras positivas com custo dobrado / 16 | 0 | 0 | 0 | 0 |

O M5 tornou Channel20 alavancado (+US$ 2,31, 15 operações) e Trend Long alavancado (+US$ 62,75, 4 operações) positivos somente sob custos normais. Ambos ficaram negativos no cenário de custos dobrados. Logo **o ajuste de permanência não constitui uma melhora robusta**; os originais foram preservados, e nenhuma configuração foi publicada para live.

## Condições e limitações

O histórico é conhecido, não é validação prospectiva, preços MID não são book executável de uma corretora e financiamento/spread/slippage podem divergir. O timeframes mais longos geram menos operações, e uma taxa positiva em 2–7 negociações é frágil. Não são ganhos depositados, não existe rentabilidade futura garantida, nem combinação de bancas em carteira. A origem histórica original permanece identificada pelo SHA256 `3c5871014a7abf2c2abc68d1d28f3ea92bd289523f9b472d8aeb01031f6db6c7`.

Os **28 slots individuais** com lucro/prejuízo normal, estresse ×2, operações, DD e as variantes M1/M5 estão no artifact `XAU-original-28-M1-M5-M15-M30-frozen-matched-and-clock-A-B` do [run 42850833462](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42850833462).
