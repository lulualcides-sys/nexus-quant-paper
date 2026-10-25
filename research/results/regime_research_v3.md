# Nexus Quant — V3, pesquisa ampliada com condições de mercado

**Não há lucro garantido e nenhum resultado veio de uma conta FBS.**

Dez regras pré-definidas x cinco mercados = 50 modelos em D1. Comparação com todos os resultados, inclusive perdedores.
Janela 1 (desenvolvimento) 2022-07 a 2023-12; janela 2 (validação) 2024; janela 3 (revisão retrospectiva) 2025 a 2026-10-24.
As janelas posteriores já foram consultadas em pesquisas anteriores, portanto **não são holdouts genuinamente inéditos**.
Risco planejado 0,75% por entrada, exposição nocional máxima 2x, entrada somente na abertura seguinte, stop/alvo ATR, permanência máxima 80 candles D1.
Custos por giro completo de 5–15 bp no nocional, com cenário alternativo de custos em dobro. Slippage real, swaps, impostos, variações de contrato e restrições de margem FBS não reproduzidos.

## Pré-seleção apenas com desenvolvimento + validação

| Mercado | Melhor estratégia elegível | Dev. | Validação | Revisão 2025–26 | Custos x2 na revisão | Drawdown rev. |
|---|---|---:|---:|---:|---:|---:|
| EURUSD | Nenhuma passou nas exigências | — | — | — | — | — |
| USDJPY | Nenhuma passou nas exigências | — | — | — | — | — |
| XAUUSD | rsi_trend | +1.26% | +4.32% | +2.13% | +1.83% | 4.95% |
| US500 | momentum120 | +3.11% | +2.17% | -1.59% | -1.79% | 3.35% |
| XTIUSD | Nenhuma passou nas exigências | — | — | — | — | — |

## Distribuição de resultados (não ocultar as perdas)

| Mercado | Positivos desenvolvimento | Positivos validação | Positivos revisão | Resistentes a custos em dobro na revisão |
|---|---:|---:|---:|---:|
| EURUSD | 2/10 | 1/10 | 5/10 | 5/10 |
| USDJPY | 6/10 | 4/10 | 1/10 | 1/10 |
| XAUUSD | 7/10 | 7/10 | 9/10 | 9/10 |
| US500 | 6/10 | 9/10 | 3/10 | 2/10 |
| XTIUSD | 5/10 | 0/10 | 8/10 | 8/10 |

## Avaliação

Retornos anuais altos em backtest **não são** prova de estabilidade. É permitido ter meses negativos. Os filtros exigem expectativa líquida positiva, perdas limitadas e resistência ao dobro dos custos na validação.
Sem dados de ordens da corretora, a avaliação é *research only*. Nenhuma candidata será ativada em conta real ou promovida automaticamente para a carteira de sinais futuros.

Fontes científicas: Moskowitz et al. (2012) — time series momentum; Moreira & Muir (2017) — volatility managed portfolios; Bailey & López de Prado (2014) — selection bias.

Dados: Yahoo Finance diário, EURUSD=X / JPY=X (indicativos); GC=F / ES=F / CL=F (futuros, não equivalentes a CFDs da FBS).
