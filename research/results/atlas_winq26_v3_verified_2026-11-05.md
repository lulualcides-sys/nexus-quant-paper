# ATLAS no contrato real WINQ26 — comparação de 05/11/2026

**Execução verificável:** [GitHub Actions 42058646269](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42058646269). Testes automatizados passaram e estudo com WINQ26 M1 foi executado com sucesso.

## Origem e integridade dos dados

- Fonte pública, terceiros: [wesleyzilva/tradetech](https://github.com/wesleyzilva/tradetech/tree/main/dados/candles/2026-2S_Q26), arquivo `WINQ26_F_0_1min.csv`; SHA1 de Git blob fixo `43c50f01882f1ac497a218549e0bff2964d94aa5`.
- Exportação declarada como Profit; **não foi auditada independentemente pela B3**.
- Série de um contrato real `WINQ26`, sem simular preços executáveis com o futuro contínuo ajustado `WINFUT`.
- Datas reservadas ANTES dos resultados: junho/2026 para desenvolvimento e julho/2026 como verificação cronologicamente posterior. Julho ainda é um **backtest retrospectivo**, não operação prospectiva.
- Cobertura de candles M1 na janela operacional: **junho: 21 pregões / 10.101 candles / mediana de 500 por pregão**; **julho: 18 pregões / 8.999 candles / mediana de 500 por pregão**.
- **A coluna `Volume` original representa volume financeiro; `Quantidade` representa contratos negociados.** O motor usa `Quantidade` em filtros de volume relativo. Valores e grade de tick foram validados no importador; nenhum dado faltante é fabricado.
- O contrato WINQ26 cobre meses anteriores a outubro de 2026: **não serve para verificar o pregão anunciado de 13/10/2026 pelo Tracker**.

## Execução simulada (não corretora)

Risco planejado de 0,75% por trade, banca virtual de R$ 5.000, no máximo 3 minicontratos inteiros. Ponto WIN = R$ 0,20/contrato; tick mínimo = 5 pontos. Entrada limitada a 50% do candle fechado, alvo 200%, stop −100%, risco/retorno geométrico nominal 1:1. Estimativa de custo ida+volta: R$ 4/contrato mais slippage de 1 tick por lado (centro da tabela). Limites de risco podem impedir novas operações. Stops e entradas no mesmo candle são tratados com regra pessimista. Sem book, quotes de corretora ou comprovante de ordem, não há execução real auditada.

## Resultado M1 — um tick de slippage por lado

| Modelo | Junho trades | Junho winrate | Junho líquido | Julho trades | Julho winrate | Julho líquido |
|---|---:|---:|---:|---:|---:|---:|
| ATLAS original | 61 | 42,62% | **−R$ 649** | 74 | 48,65% | **−R$ 541** |
| Exaustão V2 | 25 | 52,00% | −R$ 155 | 18 | 61,11% | −R$ 22 |
| Exaustão + direção | 6 | 66,67% | −R$ 9 | 4 | 25,00% | −R$ 80 |
| Confluência V3 | 20 | 45,00% | **−R$ 188** | 15 | 66,67% | **+R$ 31** |
| V3 + veto obstáculos | 20 | 45,00% | −R$ 188 | 15 | 66,67% | +R$ 31 |

A variante V3 com veto de pivôs **produziu resultados idênticos à V3 simples** no recorte. Não há prova de ganho incremental da regra de obstáculo.

### Sensibilidade do M1 a slippage (R$ de resultado líquido simulado)

| Modelo | Mês | 0 ticks por lado | 1 tick | 2 ticks |
|---|---|---:|---:|---:|
| Original | Junho | −537 | −649 | −762 |
| Original | Julho | −406 | −541 | −751 |
| Exaustão V2 | Junho | −93 | −155 | −217 |
| Exaustão V2 | Julho | +24 | −22 | −68 |
| Exaustão + direção | Junho | +5 | −9 | −23 |
| Exaustão + direção | Julho | −70 | −80 | −90 |
| Confluência V3 | Junho | −138 | −188 | −238 |
| Confluência V3 | Julho | +69 | +31 | **−7** |

**Conclusão de custos:** nenhum detector apresentou lucro líquido robusto nos dois meses ao custo assumido; o ganho V3 em julho desaparece sob custo de 2 ticks.

## Timeframes maiores

Com **a mesma banca e o mesmo risco**, M5 teve somente **1 trade encerrado em junho** pelo modelo original, resultado +R$30 com 1 tick de slippage por lado, e **0 em julho**; V2/V3 tiveram 0 trades. M15 teve 0 trades; M30/H1 tinham combinações sem histórico operacional suficiente, ou 0 trades. **Não são resultados positivos nem provas de precisão.** É necessário dimensionar o capital requerido para operar com stop proporcional ao candle sem exceder 0,75% de risco.

## Tracker versus ATLAS

A Greenhouse divulga 22 sinais no alvo, 5 stops e +8.819 pontos num único pregão de WIN M1 (13/10/2026). Fonte: [loja oficial](https://lojadagreenhouse.com.br/). São **números promocionais declarados pelo vendedor** e não execução independente auditada.

Nos nossos testes no WINQ26, o melhor winrate observado em julho para a V3 é 10 acertos em 15 operações (66,67%) distribuídas por 18 pregões, e a V3 perde em junho. **Não houve reprodução da seleção de sinais nem do resultado divulgado.**

## Barreiras para aprovação

- Regra objetiva registrada no código: **>=30 fechamentos em cada período**, lucro líquido positivo em junho E julho sob custo-base E estresse 2 ticks por lado, profit factor >=1,2 em cada e drawdown fechado <=8%. **Mesmo passando, NÃO há promoção automática:** exigir teste prospectivo independente e validação em outros vencimentos/meses.
- Não extrapolar retorno passado, não recalibrar thresholds depois de inspecionar julho e chamá-lo de holdout intacto.
- Não misturar os resultados do ouro GC=F com WIN, nem volume financeiro com quantidade de contratos.
- Não atribuir ao Tracker a fórmula independente proposta para desequilíbrio/estrutura/Fibonacci; a fórmula interna não foi obtida.
- As gravações públicas não contêm dados completos suficientes para rotular e verificar todas as setas do pregão comercial de outubro.
- O risco nominal depende da distância de stop; slippage/gaps podem exceder risco pretendido.
- Preservados ATLAS prospectivo e todos os outros robôs; **nenhuma alteração em operações reais ou paper-forward nesta pesquisa**.

**Códigos reproduzíveis:** `research/atlas_winq26_public.py` (fonte pinned), `research/atlas_confluence_v3.py` (hipóteses), `research/atlas_winq26_validation.py` (treino/holdout e gate), `research/atlas_win_backtest.py` (motor existente), `tests/test_atlas_winq26_v3.py` (regressão). Ledger JSON completo fica anexado como artifact GitHub Actions por prazo limitado.
