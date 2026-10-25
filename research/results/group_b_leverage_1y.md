# Nexus Quant — Grupo B, simulação alavancada de 12 meses

**Todos os valores são SIMULADOS; nenhuma operação foi executada na FBS.**

Período: 24/10/2025 a 24/10/2026, histórico de futuros GC=F. O grupo B tem 5 bancas separadas de US$ 5.000, exposição virtual 2× por entrada, risco-stop planejado 1,5% e trava de entradas após perdas. Taxa de ida e volta 14 pontos-base e financiamento estimado 8% a.a. sobre valor emprestado.

| Robô | Operações | Win rate | Lucro/prejuízo líquido | Saldo final | Retorno 12m | DD fechado | Transação | Financiamento |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Momentum 100 L | 29 | 58.6% | US$ +714.79 | US$ 5,714.79 | +14.30% | 5.64% | US$ 427.79 | US$ 25.94 |
| Channel 55 L | 30 | 50.0% | US$ +381.55 | US$ 5,381.55 | +7.63% | 5.31% | US$ 427.13 | US$ 16.52 |
| Momentum 40 L | 32 | 46.9% | US$ +181.44 | US$ 5,181.44 | +3.63% | 11.47% | US$ 475.05 | US$ 29.49 |
| Channel 20 L | 37 | 46.0% | US$ +136.26 | US$ 5,136.26 | +2.73% | 8.66% | US$ 523.69 | US$ 24.95 |
| Trend Long L | 19 | 47.4% | US$ +134.53 | US$ 5,134.53 | +2.69% | 5.31% | US$ 269.14 | US$ 12.19 |

**Soma hipotética das 5 contas:** US$ +1,548.57 de resultado; US$ 26,548.57 de saldo final sobre US$ 25.000 iniciais. Não é uma carteira real nem prova de diversificação; as 5 estratégias usam o mesmo ouro.

## Limitações importantes

- O intervalo já foi consultado em análises anteriores; há risco de seleção retrospectiva.
- Dados do futuro GC=F não são preços de CFD negociáveis na FBS.
- A estratégia usa stops e alvos analisados por OHLC H4; não há simulação tick-a-tick.
- Não contempla liquidações compulsórias de margem nem os custos exatos de qualquer corretora.
- Uma posição aberta ao final do teste é liquidada virtualmente no último fechamento observado.
- O drawdown informado é realizado em fechamentos; o risco intrabar pode ser maior.
- Resultados dos 5 robôs estão correlacionados; alavancagem amplia resultados positivos e negativos.

Código executável em `research/backtest_group_b.py` e registro completo no JSON correspondente.
