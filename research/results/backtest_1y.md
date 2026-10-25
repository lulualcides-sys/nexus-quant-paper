# Nexus Quant | Backtest retrospectivo de 1 ano

**PERÍODO:** 24/10/2025 a 24/10/2026 (UTC).
**ATENÇÃO:** simulação retrospectiva com preços públicos de referência; **NÃO são operações da FBS, não há lucro real, nem garantia futura.**

**Banca por robô:** US$ 5.000 (cada robô pode negociar os cinco mercados). Risco planejado por entrada: 0,75% do saldo; máximo de 3 posições abertas; leverage nocional de até 3x por ativo e 5x agregado. Semposição financiada, sem impostos. Stops sujeitos a saltos de preço.

**Regras:** candle H1 fechado → entrada na abertura seguinte. Stop 1 ATR, objetivo 1,75 ATR, tempo máximo 48 candles. Ambiguidade entre stop/alvo no mesmo candle resolvida a favor do stop. Custos totais estimados por transação 3–10 pontos-base do valor nocional (inclui spread/slippage/comissões fictícias; taxas FBS podem divergir).

| Robô | Operações | Vitórias | Taxa de acerto | Lucro/Prejuízo | Retorno | Maior drawdown | Custos |
|---|---:|---:|---:|---:|---:|---:|---:|
| Trend Hunter | 713 | 281 | 39.4% | US$ -2,109.23 | -42.18% | 44.08% | US$ 2,670.94 |
| Pullback Master | 1221 | 454 | 37.2% | US$ -3,285.00 | -65.70% | 68.10% | US$ 3,229.66 |
| Momentum X | 1317 | 505 | 38.3% | US$ -3,740.53 | -74.81% | 76.26% | US$ 2,814.91 |
| Breakout Pro | 1353 | 486 | 35.9% | US$ -4,091.16 | -81.82% | 82.63% | US$ 2,962.04 |
| Reversal RSI | 1628 | 587 | 36.1% | US$ -4,153.58 | -83.07% | 83.74% | US$ 3,147.36 |

## Lucro/prejuízo atribuído a cada mercado

US$, contribuição ao saldo compartilhado de cada robô; não retorno isolado do ativo.

| Robô | EUR/USD | USD/JPY | Ouro (GC) | US500 (ES) | WTI (CL) |
|---|---:|---:|---:|---:|---:|
| Trend Hunter | -388.50 | -716.07 | +377.24 | -1,086.35 | -295.55 |
| Breakout Pro | -869.47 | -479.37 | -988.05 | -735.70 | -1,018.58 |
| Reversal RSI | -1,075.66 | -678.02 | -750.68 | -1,050.67 | -598.56 |
| Momentum X | -621.01 | -589.91 | -418.48 | -1,289.55 | -821.58 |
| Pullback Master | -813.05 | -744.47 | -631.86 | -916.11 | -179.51 |

## Amostra de dados

| Mercado | Ticker de referência | Candles totais | Candles no período | Primeiro candle | Último candle |
|---|---|---:|---:|---|---|
| EURUSD | EURUSD=X | 12316 | 6140 | 2025-10-24T00:00:00+00:00 | 2026-10-23T21:00:00+00:00 |
| USDJPY | JPY=X | 12247 | 6108 | 2025-10-24T00:00:00+00:00 | 2026-10-23T20:00:00+00:00 |
| XAUUSD | GC=F | 11455 | 5701 | 2025-10-24T00:00:00+00:00 | 2026-10-23T20:00:00+00:00 |
| US500 | ES=F | 11428 | 5704 | 2025-10-24T00:00:00+00:00 | 2026-10-23T21:00:00+00:00 |
| XTIUSD | CL=F | 11327 | 5693 | 2025-10-24T00:00:00+00:00 | 2026-10-23T20:00:00+00:00 |

## Limitações

- Ouro (GC=F), S&P500 (ES=F) e WTI (CL=F) são futuros contínuos usados como referência, não CFDs da FBS; rolagem do contrato pode criar saltos.
- EURUSD=X e JPY=X são cotações indicativas; não têm spread e execução reais da FBS.
- Resultado calculado depois de conhecer o ano completo, mas as decisões usam apenas candles anteriores.
- Sem ajuste por swap, tributos, financiamento de margem, microestrutura intrabar, falhas de rede ou restrições específicas da FBS.
- Um único ano pode incluir condições favoráveis demais; não prova persistência de lucro nem equivale a validação fora da amostra.
- O algoritmo não foi calibrado nos dados desse ano e não assume dinheiro depositado em corretora.

Fonte de candles: endpoints públicos Yahoo Finance Chart (sem SLA; podem mudar).
Mecânica e livros de negociação constam em `research/backtest_year.py` e `research/results/backtest_1y.json`.
