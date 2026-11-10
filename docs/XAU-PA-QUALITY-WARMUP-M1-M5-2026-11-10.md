# XAUUSD Price Action — filtros e aquecimento M1/M5, pesquisa 10/11/2026

Este relatório registra **duas melhorias reais de metodologia**, não uma alegação de lucro.
[PR #61](https://github.com/lulualcides-sys/nexus-quant-paper/pull/61) permanece DRAFT, sem ordens ou publicação na `main`.

## 1. Hipótese independente de qualidade de candle

Comparou **controle original intacto** vs **quality_v1** predefinido: fechamento forte de reteste, pavio de rejeição da lateralização, volume apenas de mudanças de preços `bid/ask` (não volume agressor), proporção candle/ATR para rejeitar volatilidade anormal. Nenhum filtro ajustado após observar o resultado.

**Execução aprovada:** [GitHub Actions 42800867239](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42800867239); [código](../research/xau_pa_quality_experiment.py), [auditoria](../research/xau_pa_quality_scorecard.py), [testes](../tests/test_xau_pa_quality_experiment.py), [workflow](../.github/workflows/xau-pa-quality-m1m5-two-periods.yml). Julho 06–17 e setembro 07–18 de 2026, **9 sessões válidas por mês** (uma quarentenada em cada janela).

| TF | Comparação | Julho sinais/fills | Julho líquido US$/oz | Setembro sinais/fills | Setembro líquido US$/oz |
|---|---|---|---:|---|---:|
| M1 | Controle original | 14 / 13 | −32,928 | 5 / 4 | −7,888 |
| M1 | Qualidade v1 | 7 / 7 | −22,180 | 2 / 2 | −1,588 |
| M5 | Controle original | 1 / 1 | +4,218 | 0 / 0 | 0,000 |
| M5 | Qualidade v1 | 0 / 0 | 0,000 | 0 / 0 | 0,000 |

**Conclusão:** o filtro diminuiu o prejuízo e a frequência no M1, mas continuou negativo; a redução de operações M5 deixou o modelo sem preenchimentos. Um filtro que evita perdas depois de observadas não demonstra expectativa positiva.

## 2. Correção do desenho do backtest — indicadores aquecidos por 3h

**Problema auditado:** o experimento histórico original usava somente o fluxo entre 12h e 17h UTC. O Price Action M5 depende de contexto M15 com 12 candles (aproximadamente três horas de formação), deixando cerca de duas horas efetivas com informação suficiente. Isso pode artificialmente reduzir a quantidade de sinais.

**Nova experiência sem modificar regras:** baixar uma única fonte XAUUSD Dukascopy `bid/ask` entre **09h–17h UTC**, usar 09h–12h para aquecer ATR, pivôs e M5/M15, e **executar somente 12h–17h UTC**, com o MESMO fluxo de cotações nas três variantes. Comparar controle antigo sem histórico, controle aquecido e controle aquecido mais filtro de qualidade. Os custos e parâmetros do modelo original foram preservados. Simulação fechada por dia, nunca sobreposta.

**Execução aprovada:** [GitHub Actions 42801708754](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42801708754), três jobs SUCCESS, **20 datas previstas e 20 válidas** em março (09–20/03) e outubro (12–23/10), nenhum feed quarentenado. [Código da correção](../research/xau_pa_warmup_study.py), [consolidador](../research/xau_pa_warmup_scorecard.py), [testes](../tests/test_xau_pa_warmup_study.py) e [workflow](../.github/workflows/xau-pa-warmup-m1m5-march-october.yml).

| TF | Variante | Março sinais/fills | Março líquido US$/oz | Outubro sinais/fills | Outubro líquido US$/oz |
|---|---|---|---:|---|---:|
| M1 | Controle 12h–17h sem aquecimento | 14 / 11 | −16,777 | 10 / 8 | −8,612 |
| M1 | Controle com aquecimento 09h–12h | 18 / 15 | −35,331 | 17 / 13 | −25,778 |
| M1 | Aquecimento + qualidade v1 | 8 / 7 | −20,578 | 10 / 8 | −18,227 |
| M5 | Controle sem aquecimento | 1 / 1 | −5,547 | 4 / 3 | −18,247 |
| M5 | Controle com aquecimento | 5 / 5 | −9,007 | 9 / 6 | −9,801 |
| M5 | Aquecimento + qualidade v1 | 3 / 3 | +9,563 | 2 / 2 | −13,647 |

**Conclusões do desenho corrigido:**
- O M5 apresentou **mais oportunidades reais de sinal** com contexto histórico completo, confirmando que a janela curta reduzia a amostra de entradas. Controle M5: 1→5 sinais em março e 4→9 em outubro, com o mesmo horário de negociação.
- Esse avanço metodológico **não criou vantagem econômica**. M5 aquecido ficou negativo nas duas amostras; qualidade M5 teve +US$ 9,563/oz com apenas três fills em março e −US$ 13,647/oz com dois fills em outubro.
- O M1 também encontrou mais sinais com o histórico ampliado, mas ficou **mais negativo**. Não utilizar maior frequência como critério único de sucesso.
- Os dados são históricos e foram consultados em outras pesquisas de XAU; não são um `forward` genuinamente intocado. As duas janelas são comparações históricas, não testes de corretora.

## Premissas econômicas e riscos

- Todos os valores de tabela acima usam **cenário de custos dobrados**, comissão hipotética de **US$ 0,60/oz ida+volta**, slippage adverso de **US$ 0,20/oz em cada lado de mercado**, além do spread observado entre BID e ASK da Dukascopy. Não são tarifas verificadas da corretora do usuário.
- Resultados em **dólares por UMA onça hipotética**, não dólares em conta, saldo brasileiro, milhares ou 1 lote MT5. Broker lot size, swap, latência, rejeições de ordem, alavancagem, margem e slippage real não estão modelados integralmente.
- Custos maiores podem excluir sinais pelo veto econômico do próprio simulador; cada cenário mantém seu próprio ledger, **não supor fills idênticos ou que o resultado sempre diminui com mais custos**.
- As simulações não enviam ordens. O código original do WIN, do Tracker XAUUSD e demais robôs não foi editado.

## Decisão e próximos critérios

**NÃO APROVADO.** Um resultado positivo de três trades não é robustez. O resultado verificável desta iteração é a redução de viés metodológico de warmup e a descoberta de que o filtro de qualidade NÃO resolve a expectativa negativa. Não escolher `quality_v1` como vencedor.

Próxima pesquisa com valor: congelar uma hipótese econômica nova, registrar os critérios previamente, testar em feed integral de corretora MT5 demo com spread/tarifas reais e em datas futuras intocadas. Exigir dezenas/centenas de operações, consistência entre meses, custo e drawdown auditado antes de publicar qualquer Expert Advisor.
