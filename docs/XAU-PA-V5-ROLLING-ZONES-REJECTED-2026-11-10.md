# XAUUSD Price Action v5 — auditoria da hipótese de zonas móveis (10/11/2026)

**Conclusão: candidato REJEITADO para integração.** A v5 aumentou as operações, mas agravou o prejuízo. O critério de aceitação combina melhoria de frequência E de expectativa líquida; essa hipótese falhou.

## Objetivo controlado

O usuário opera:
- Rompimento da microtendência (LTA/LTD) **seguido de reteste** antes da entrada.
- Toque e rejeição de suporte/resistência **somente em lateralização**.
- Máximo de **uma posição simultânea** em XAUUSD, compartilhada entre M1 e M5.
- Sem limitação diária arbitrária de entradas ou perdas.

A v4 experimental criava suporte/resistência por dois pivôs confirmados antes do início das operações e não os alterava durante a sessão. A v5 testa **somente** atualizar as zonas automáticas ao longo da sessão, com **dois pivôs confirmados anteriores a cada candle de sinal**; não altera a regra de LTA/LTD, reteste, gestão, stop, alvo, horário, custo ou número de posições. O modo `manual` **nunca altera** marcas fornecidas pelo usuário.

**Código e testes:** [motor v5](../research/xau_pa_rolling_zones_v5.py), [consolidador](../research/xau_pa_rolling_zones_v5_scorecard.py), [12 testes específicos](../tests/test_xau_pa_rolling_zones_v5.py), [workflow](../.github/workflows/xau-pa-v5-causal-zones-feb-july.yml). Também executados 11 testes da v4, 12 da v3 e sete da trava global: **42 testes por bloco histórico**.

## Evidência executada

[GitHub Actions 42810101914](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42810101914): **três jobs SUCCESS**, com históricos completos de cada operação, timestamps e SHA256 dos dados. Artefatos:
- `xau-pa-v5-frozen-february-quote-ledgers` ID 13762067887;
- `xau-pa-v5-frozen-july-quote-ledgers` ID 13761547946;
- `xau-pa-v5-blind-comparison-M1-M5-shared-report` ID 13762147789.

Fonte: XAUUSD spot BID/ASK da Dukascopy, 09h–21h UTC; aquecimento 09h–12h sem ordens; negociações simuladas entre 12h e 21h. Fevereiro 09–13, julho 20–24 de 2026, **dez datas previamente escolhidas, nove válidas**. 12/02 foi excluído **inteiramente** porque o registro 88.408 continha BID/ASK inválidos. Não houve escolha retrospectiva de operações.

Custos de stress: spread observado BID/ASK, comissão **hipotética US$ 0,60 por onça pela operação completa** e slippage adverso **US$ 0,20 por onça em cada lado de ordem a mercado**. Não são tarifas de conta real, nem backtest do broker MT5. P&L é **USD por 1 onça hipotética**, NÃO saldo de conta ou 1 lote.

## Resultado — por período e timeframe

| Timeframe / trava | Política | Fevereiro sinais / fills | Fevereiro US$/oz | Julho sinais / fills | Julho US$/oz | Total fills | Total US$/oz |
|---|---|---:|---:|---:|---:|---:|---:|
| M1 | v4 zonas fixas | 16 / 12 | −5,453 | 11 / 8 | −13,958 | 20 | **−19,411** |
| M1 | v5 zonas móveis | 31 / 18 | −20,317 | 33 / 13 | −12,850 | 31 | **−33,167** |
| M5 | v4 zonas fixas | 0 / 0 | 0,000 | 5 / 5 | −10,988 | 5 | **−10,988** |
| M5 | v5 zonas móveis | 1 / 0 | 0,000 | 8 / 8 | −22,678 | 8 | **−22,678** |
| **M1+M5 trava única** | **v4 zonas fixas** | **16 / 12** | **−5,453** | **16 / 13** | **−24,946** | **25** | **−30,399** |
| **M1+M5 trava única** | **v5 zonas móveis** | **32 / 18** | **−20,317** | **41 / 21** | **−35,528** | **39** | **−55,844** |

*Nota de arredondamento:* alguns subtotais acima exibem três casas decimais; o ledger completo contém os valores de precisão usados para a auditoria. Total combinado v5 exato **−55,844479 USD/oz**; total combinado v4 exato **−30,399 USD/oz**.

**V4 global:** 32 sinais, 25 execuções, 7 vitórias, 18 derrotas, −US$30,399/oz.

**V5 global:** 73 sinais, 39 execuções, 10 vitórias, 29 derrotas, −US$55,844479/oz.

A v5 adicionou 14 operações, com maior prejuízo. A taxa de acerto **caiu** de 28,0% para 25,6%.

## Diagnóstico causal das perdas da v5

Decomposição do livro **SHARED**, v5:
- **Rejeição de faixa/lateralização:** 19 fills, **3 vitórias**, **−US$42,295479/oz**. Esta decomposição corresponde exclusivamente a **fevereiro e julho**.
- **Rompimento LTA/LTD e reteste:** 20 fills, **7 vitórias**, **−US$13,549/oz**.
- **Total:** 39 fills, 10 vitórias, −US$55,844479/oz.

Detalhe:
- Fevereiro: 8 trades de faixa, **1 vitória**, −US$23,73355/oz. Reteste: 10 trades, cinco vitórias, +US$3,417/oz.
- Julho: 11 trades de faixa, **duas vitórias**, −US$18,561929/oz. Reteste: dez trades, duas vitórias, −US$16,966/oz.
- Fevereiro: 11 saídas por STOP no SHARED v5; julho: 17. Total **28 stops em 39 fills**. O STOP próximo da máxima/mínima do candle de reteste ou rejeição é uma hipótese do código — não posição de stop confirmada do trader.

### Onde o código ainda pode divergir da análise manual

- **Marcações não coincidem comprovadamente com o gráfico do usuário.** As linhas são derivadas de pivôs de cotações da Dukascopy; uma zona automaticamente recalculada pode não ser a região que ele marcou e considerou válida.
- **Regime lateral é aproximado matematicamente**, e as 19 entradas de faixa ilustram que o detector classifica como operáveis regiões que podem não ter relevância discricionária.
- **Stop Win/Red não foram parametrizados a partir de exemplos reais do usuário.** O motor usa hipóteses: stop atrás da rejeição + ATR e alvo em aproximadamente 2R, sujeitos a custo, restrição de distâncias e saída por tempo.
- **Não há auditoria operação a operação contra trades manuais anotados pelo usuário**; logo não é possível declarar fidelidade ou prometer rentabilidade.

## Decisão prática

1. **NÃO promover v5 como padrão.** Preservar a v4 apenas como referência de pesquisa, e manter `manual` como o único modo que aceita fielmente níveis fornecidos pelo trader sem inventá-los.
2. **NÃO desligar a lógica de lateralização só para esconder um componente que perdeu.** Os 19 fills negativos indicam uma hipótese para investigação; eliminá-los retrospectivamente faria o resultado histórico parecer artificialmente melhor. Uma política sem lateralização exigiria validação numa amostra realmente intocada.
3. **NÃO aumentar o risco, alavancagem ou tamanho da posição** para compensar a taxa de acerto baixa; isso aumenta o prejuízo esperado.
4. Antes de outra rodada de ajustes, priorizar **validação de fidelidade**: comparar preço/horário das linhas LTA/LTD, suporte/resistência, confirmação do rompimento, candle de reteste, Stop Red e Stop Win contra exemplos reais datados, e identificar falsos positivos com evidência. Só depois congelar uma hipótese e testar em período futuro sem seleção de resultados.

**Status:** PR #61 aberta em rascunho. Nenhum código de produção aprovado modificado, nenhuma ordem em broker, nenhuma estratégia declarada lucrativa.
