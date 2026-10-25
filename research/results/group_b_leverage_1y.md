# Nexus Quant — Grupo B, simulação alavancada de 12 meses

**Todos os valores são SIMULADOS; nenhuma operação foi executada na FBS.**

Período: 24/10/2025 a 24/10/2026, histórico de futuros GC=F. O grupo B tem 5 bancas separadas de US$ 5.000, exposição virtual 2× por entrada, risco-stop planejado 1,5% e trava de entradas após perdas. Taxa de ida e volta 14 pontos-base e financiamento estimado 8% a.a. sobre valor emprestado.

| Robô | Operações | Win rate | Lucro/prejuízo líquido | Saldo final | Retorno 12m | DD fechado | Transação | Financiamento |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Channel 55 L | 30 | 53.3% | US$ +601.73 | US$ 5,601.73 | +12.03% | 5.31% | US$ 429.60 | US$ 20.22 |
| Channel 20 L | 37 | 48.6% | US$ +354.05 | US$ 5,354.05 | +7.08% | 8.66% | US$ 527.97 | US$ 25.46 |
| Momentum 40 L | 28 | 50.0% | US$ +349.46 | US$ 5,349.46 | +6.99% | 8.67% | US$ 417.20 | US$ 27.48 |
| Trend Long L | 19 | 52.6% | US$ +346.39 | US$ 5,346.39 | +6.93% | 5.31% | US$ 270.46 | US$ 15.85 |
| Momentum 100 L | 28 | 53.6% | US$ +313.50 | US$ 5,313.50 | +6.27% | 6.02% | US$ 407.87 | US$ 29.27 |

**Soma hipotética das 5 contas:** US$ +1,965.13 de resultado; US$ 26,965.13 de saldo final sobre US$ 25.000 iniciais. Não é uma carteira real nem prova de diversificação; as 5 estratégias usam o mesmo ouro.

## Limitações importantes

- O intervalo já foi consultado em análises anteriores; há risco de seleção retrospectiva.
- Dados do futuro GC=F não são preços de CFD negociáveis na FBS.
- A estratégia usa stops e alvos analisados por OHLC H4; não há simulação tick-a-tick.
- Não contempla liquidações compulsórias de margem nem os custos exatos de qualquer corretora.
- Uma posição aberta ao final do teste é liquidada virtualmente no último fechamento observado.
- O drawdown informado é realizado em fechamentos; o risco intrabar pode ser maior.
- Resultados dos 5 robôs estão correlacionados; alavancagem amplia resultados positivos e negativos.

Código executável em `research/backtest_group_b.py` e registro completo no JSON correspondente.
