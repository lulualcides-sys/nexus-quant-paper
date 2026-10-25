# Nexus Quant | Backtest retrospectivo de 1 ano

**PERÍODO:** 24/10/2025 a 24/10/2026 (UTC).
**ATENÇÃO:** simulação retrospectiva com preços públicos de referência; **NÃO são operações da FBS, não há lucro real, nem garantia futura.**

**Banca por robô:** US$ 5.000 (cada robô pode negociar os cinco mercados). Risco planejado por entrada: 0,75% do saldo; máximo de 3 posições abertas; leverage nocional de até 3x por ativo e 5x agregado. Semposição financiada, sem impostos. Stops sujeitos a saltos de preço.

**Regras:** candle H1 fechado → entrada na abertura seguinte. Stop 1 ATR, objetivo 1,75 ATR, tempo máximo 48 candles. Ambiguidade entre stop/alvo no mesmo candle resolvida a favor do stop. Custos totais estimados por transação 3–10 pontos-base do valor nocional (inclui spread/slippage/comissões fictícias; taxas FBS podem divergir).

| Robô | Operações | Vitórias | Taxa de acerto | Lucro/Prejuízo | Retorno | Maior drawdown | Custos |
|---|---:|---:|---:|---:|---:|---:|---:|
| Trend Hunter | 705 | 278 | 39.4% | US$ -2,142.59 | -42.85% | 44.81% | US$ 2,635.96 |
| Pullback Master | 1204 | 453 | 37.6% | US$ -3,190.02 | -63.80% | 66.33% | US$ 3,230.30 |
| Momentum X | 1300 | 501 | 38.5% | US$ -3,623.63 | -72.47% | 74.06% | US$ 2,836.74 |
| Breakout Pro | 1338 | 479 | 35.8% | US$ -4,108.58 | -82.17% | 82.99% | US$ 2,939.89 |
| Reversal RSI | 1610 | 576 | 35.8% | US$ -4,151.80 | -83.04% | 83.79% | US$ 3,135.84 |

## Lucro/prejuízo atribuído a cada mercado

US$, contribuição ao saldo compartilhado de cada robô; não retorno isolado do ativo.

| Robô | EUR/USD | USD/JPY | Ouro (GC) | US500 (ES) | WTI (CL) |
|---|---:|---:|---:|---:|---:|
| Trend Hunter | -371.30 | -703.08 | +305.78 | -1,005.30 | -368.69 |
| Breakout Pro | -886.90 | -443.74 | -996.19 | -693.79 | -1,087.97 |
| Reversal RSI | -1,085.65 | -683.03 | -739.71 | -1,028.79 | -614.61 |
| Momentum X | -626.43 | -584.97 | -389.06 | -1,360.35 | -662.82 |
| Pullback Master | -797.82 | -725.97 | -564.38 | -920.27 | -181.58 |

## Amostra de dados

| Mercado | Ticker de referência | Candles totais | Candles no período | Primeiro candle | Último candle |
|---|---|---:|---:|---|---|
| EURUSD | EURUSD=X | 12253 | 6077 | 2025-10-24T00:00:00+00:00 | 2026-10-23T21:00:00+00:00 |
| USDJPY | JPY=X | 12185 | 6046 | 2025-10-24T00:00:00+00:00 | 2026-10-23T20:00:00+00:00 |
| XAUUSD | GC=F | 11392 | 5638 | 2025-10-24T00:00:00+00:00 | 2026-10-23T20:00:00+00:00 |
| US500 | ES=F | 11364 | 5640 | 2025-10-24T00:00:00+00:00 | 2026-10-23T21:00:00+00:00 |
| XTIUSD | CL=F | 11262 | 5628 | 2025-10-24T00:00:00+00:00 | 2026-10-23T20:00:00+00:00 |

## Limitações

- Ouro (GC=F), S&P500 (ES=F) e WTI (CL=F) são futuros contínuos usados como referência, não CFDs da FBS; rolagem do contrato pode criar saltos.
- EURUSD=X e JPY=X são cotações indicativas; não têm spread e execução reais da FBS.
- Resultado calculado depois de conhecer o ano completo, mas as decisões usam apenas candles anteriores.
- Sem ajuste por swap, tributos, financiamento de margem, microestrutura intrabar, falhas de rede ou restrições específicas da FBS.
- Um único ano pode incluir condições favoráveis demais; não prova persistência de lucro nem equivale a validação fora da amostra.
- O algoritmo não foi calibrado nos dados desse ano e não assume dinheiro depositado em corretora.

Fonte de candles: endpoints públicos Yahoo Finance Chart (sem SLA; podem mudar).
Mecânica e livros de negociação constam em `research/backtest_year.py` e `research/results/backtest_1y.json`.
