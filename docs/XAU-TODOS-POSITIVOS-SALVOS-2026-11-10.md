# Catálogo preservado — TODOS os robôs positivos de XAUUSD (M1, M5, M15 e M30)

**Registrado em 10/11/2026.** Arquivo principal e auditável:
[research/preserved/xau_all_positive_original_robots_20261110.json](../research/preserved/xau_all_positive_original_robots_20261110.json).

## O que foi salvo

Não foram criados robôs novos. Foram preservados **todos os resultados positivos observados** do conjunto original de 27 robôs + ATLAS, incluindo modelos que ficaram positivos somente no teste experimental de permanência. Há 52 registros positivos distribuídos entre cenários e janelas históricas, mas somente **14 regras originais distintas** entre os registros. Uma mesma regra pode aparecer em M15 de duas janelas distintas; as 15 posições H1 são apenas três sinais repetidos cinco vezes.

| Snapshot preservado | Timeframe | Positivos (slots) | Regras distintas positivas | Positivos com custos dobrados (slots) | Característica |
|---|---|---:|---:|---:|---|
| M15 completo — 24 sessões | M15 | 20 | 8 | 12 | Registro previamente salvo, intacto |
| M15 — janela pareada mais curta | M15 | 21 | 9 | 16 | Início alinhado com M30 |
| M30 — janela pareada | M30 | 8 | 8 | 6 | **Novo quadro positivo** |
| M1 — janela pareada | M1 | 1 | 1 | 0 | BB20 somente com custos normais |
| M5 — tempo máximo estendido (experimental) | M5 | 2 | 2 | 0 | Não altera sinais, mas muda saída por tempo |

**M5 original: nenhum positivo.** O M1 experimental teve resultado equivalente ao original, então seu mesmo resultado não foi contado duas vezes.

## Candidatos que suportaram custos dobrados

No M15 de 24 sessões (janela maior), quatro estratégias distintas mantiveram resultado positivo com o custo dobrado: Channel55 convencional (+US$ 6,27), Channel55 alavancado (+US$ 29,69), EMA20 Retest (+US$ 8,34) e RSI50 (+US$ 24,57). Os 15 livros H1 não são independentes.

No M30 de janela curta, seis ficaram positivos com custo dobrado: Momentum40 alavancado (+US$ 200,22, 4 operações), Channel20 alavancado (+US$ 151,17, 4), Momentum60 (+US$ 94,03, 2), Momentum100 convencional (+US$ 41,96, 7), Channel20 convencional (+US$ 38,05, 6) e Channel55 alavancado (+US$ 13,18, 4). As amostras de 2–7 fechamentos são insuficientes para aprovar dinheiro real.

Também foram preservados **todos os positivos frágeis**: M30 RSI Trend (+US$ 0,89, mas −US$ 24,88 com custos dobrados) e Momentum100 alavancado (+US$ 59,43, mas −US$ 163,02 com custos dobrados); M1 BB20 (+US$ 10,26, mas −US$ 3,03 com custos dobrados); M5 Channel20 alavancado (+US$ 2,31, mas −US$ 396,34 com custos dobrados) e Trend Long alavancado (+US$ 62,75, mas −US$ 256,65 com custos dobrados). Esses registros **não** são candidatos aprovados.

## Rastreabilidade e proteção

- Fonte de 24 sessões/primeiro M15: [GitHub Actions 42847239203](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42847239203), SHA256 JSON `3c5871014a7abf2c2abc68d1d28f3ea92bd289523f9b472d8aeb01031f6db6c7`.
- Fonte comparativa M30/M1/M5/M15: [GitHub Actions 42850833462](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42850833462), SHA256 JSON `9045ee88326ac5fa20b26dd52a73ca27deb8e4759e1cb5f402cf4619854aa758`.
- Código exato da investigação, que não foi promovido automaticamente: [commit f11e3b9](https://github.com/lulualcides-sys/nexus-quant-paper/tree/f11e3b97f77e10fb6703194a80335303b254c2db).
- Snapshot M15 anterior: [research/preserved/xau_m15_positive_20261110.json](../research/preserved/xau_m15_positive_20261110.json), que permanece sem alteração.
- Arquivo consolidado contém **ID de cada robô, timeframe, fonte de estratégia, resultado, resultado com custo dobrado, operações e categoria da simulação**. É um registro de configurações positivas com vínculos para motores existentes; **não cria processos em execução nem configura AutoTrading**.

Os modelos seguem paper-only em condições retrospectivas, usando cotações Dukascopy transformadas em candles MID com custos estimados em vez de preenchimentos reais da corretora. Muitos resultados são positivos só na amostra já explorada. Não somar os saldos das bancas nem confundir resultados repetidos em períodos diferentes com trades independentes. Nenhuma alteração na lógica de produção foi feita para salvar o catálogo.
