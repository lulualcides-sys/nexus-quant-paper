# XAUUSD — Bateria 8: quatro hipóteses novas contra ER20 M30 e Shock M15
**Data:** 12/11/2026 • **Status:** testes automatizados aprovados, nenhuma estratégia nova homologada

## Resumo objetivo

**16 configurações novas** (quatro modelos em M1, M5, M15 e M30). **Zero** com retorno líquido positivo em R nos dois recortes históricos a custo hipotético de US$1,20 por onça. **13** deram prejuízo em ambos; **3** deram resultados de sinais opostos. Dois controles previamente preservados permaneceram positivos em ambos e foram confirmados pela paridade com a bateria 6.

Não adicionar à relação de candidatos selecionados. Guardar todos os fracassos para evitar repetir experimentos.

## Estratégias examinadas

- RSI2 + EMA50/EMA200: reversão de RSI(2) após extremo, a favor de tendência.
- Donchian24 failed break: rompimento da faixa de 24 candles fechados e retorno contrário ao nível.
- VWAP diária: recuperação do preço ponderado pelo volume proxy diário em barras fechadas após 00h30 UTC.
- Momentum3 shallow retrace: dois candles fortes consecutivos, recuo raso e retomada perto da EMA50.
- ER20 M30 e Shock M15: referências congeladas, sem mudar as entradas originais.

**Métrica:** R por trade = lucro simulado após custo dividido pelo risco no stop original; não é percentual da conta. Custo roundtrip fixo hipotético US$0,80/US$1,20/US$1,60/onça; preenchimento no open do candle seguinte; stop-first em barras ambíguas; alvos de 1R e 1,5R, 1/3 cada; runner final até stop ou 96 horas de candles. Trimestres avaliados separadamente, sem capital real, lotes, spreads broker ou tickets.

## 18 pares modelo/timeframe — custo US$1,20/onça

| Modelo | TF | Trades 2025 | R líquido 2025 | PF em R 2025 | Trades 2026 parcial | R líquido 2026 | PF em R 2026 | R 2025 custo1,60 | R 2026 custo1,60 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| RSI2 + tendência EMA200 | M1 | 1525 | -2.055,046 | 0,266 | 715 | -359,168 | 0,538 | -2.825,715 | -551,139 |
| RSI2 + tendência EMA200 | M5 | 613 | -275,451 | 0,528 | 278 | -76,49 | 0,605 | -401,727 | -106,937 |
| RSI2 + tendência EMA200 | M15 | 298 | -66,303 | 0,714 | 160 | -26,989 | 0,743 | -99,337 | -36,646 |
| RSI2 + tendência EMA200 | M30 | 182 | -24,432 | 0,796 | 100 | -14,099 | 0,74 | -37,695 | -18,33 |
| Falso rompimento Donchian24 | M1 | 1024 | -794,637 | 0,449 | 577 | -332,167 | 0,402 | -1.147,182 | -438,035 |
| Falso rompimento Donchian24 | M5 | 458 | -156,087 | 0,576 | 241 | -78,206 | 0,577 | -221,079 | -95,601 |
| Falso rompimento Donchian24 | M15 | 277 | -87,453 | 0,539 | 133 | -39,408 | 0,547 | -109,382 | -44,685 |
| Falso rompimento Donchian24 | M30 | 153 | -17,32 | 0,814 | 89 | -22,755 | 0,618 | -25,805 | -25,371 |
| Retomada VWAP diária | M1 | 651 | -313,982 | 0,541 | 339 | -123,205 | 0,52 | -471,039 | -164,908 |
| Retomada VWAP diária | M5 | 356 | -90,413 | 0,671 | 169 | -29,912 | 0,737 | -130,13 | -39,099 |
| Retomada VWAP diária | M15 | 224 | -32,694 | 0,78 | 87 | 37,031 | 1,716 | -46,956 | 34,439 |
| Retomada VWAP diária | M30 | 165 | -3,085 | 0,966 | 91 | -20,306 | 0,66 | -10,214 | -22,394 |
| Momentum 3 candles + reteste | M1 | 711 | -609,026 | 0,31 | 278 | 8,88 | 1,04 | -811,02 | -34,871 |
| Momentum 3 candles + reteste | M5 | 206 | -94,352 | 0,379 | 94 | -23,183 | 0,636 | -119,657 | -29,103 |
| Momentum 3 candles + reteste | M15 | 65 | -15,272 | 0,715 | 29 | -9,34 | 0,493 | -20,922 | -10,603 |
| Momentum 3 candles + reteste | M30 | 40 | -8,634 | 0,678 | 13 | 4,059 | 1,671 | -10,38 | 3,807 |
| ER20 M30 — referência original | M30 | 110 | 23,729 | 1,39 | 52 | 11,623 | 1,372 | 18,772 | 10,36 |
| Shock Exhaustion M15 — referência original | M15 | 90 | 27,857 | 1,539 | 45 | 11,682 | 1,554 | 23,627 | 10,53 |

## O que os resultados demonstram e o que não demonstram

- **2025:** todas as 16 combinações novas perderam em R. Não existe fundamento para declarar uma delas candidata lucrativa.
- **2026 parcial:** VWAP M15 subiu +37,031R e PF_R 1,716, mas perdeu −32,694R em 2025. É uma divergência de períodos e não permite promoção.
- **RSI2 e falso rompimento Donchian:** as oito configurações perderam nos dois recortes. Não repetir o mesmo experimento com parâmetros reajustados no mesmo histórico apenas para gerar lucro aparente.
- **Controles preservados:** ER20 M30 +23,729R/+11,623R (N110/N52); Shock M15 +27,857R/+11,682R (N90/N45), ambos custo1,20. O desempenho histórico do ER20 depende de 2025Q3/Q4, e o Shock ainda tem menos operações que o mínimo inicial de 100/50.
- **Critérios pré-declarados das estratégias novas:** no mínimo 100/50 operações em 2025/2026 parcial, retorno positivo em R nos dois recortes e no stress custo1,60, PF_R >1,20 nos dois, pelo menos três trimestres positivos em 2025 e um em 2026, menos de 65% da soma dos trimestres positivos concentrados em um único trimestre. **Nenhuma passou.**

## Próximo investimento com melhor relação benefício/custo

Em vez de buscar mais backtests verdes no mesmo histórico, usar MQL5 Strategy Tester **Every tick based on real ticks** ou dados prospectivos de uma corretora, com Bid/Ask, spread, comissões, swap, slippage e tamanhos de lote. Congelar parâmetros do ER20 M30 e do Shock M15. Também investigar o custo de execução em horários de spreads altos e uma validação que não seleciona parâmetros usando dados já vistos.

## Evidências e preservação

- [CI da bateria 8, execução completa com sucesso](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/43270307806)
- [PR de pesquisa #82, não mesclada nem ativa](https://github.com/lulualcides-sys/nexus-quant-paper/pull/82)
- [JSON completo de 36 painéis anuais e 108 trimestrais](xau_batch8_independent_all_2025plus_20261112.json)
- [Dez candidatos preservados sem alteração](xau_selected_ten_candidates_20261112.json)
- [18 configurações previamente positivas dos lotes 6 e 7](xau_positive_variants_all_batches6_7_20261112.json)

**Limitações:** 2025 completo e 2026 parcial Q2/Q3 de feeds diferentes; ambos períodos já foram examinados em muitas pesquisas e não são verdadeiramente fora da amostra. 36 painéis anuais, 108 trimestrais, seleção múltipla. Replay OHLC, não backtest com tick real de corretora. Não há qualquer afirmação de rentabilidade futura ou conta real.
