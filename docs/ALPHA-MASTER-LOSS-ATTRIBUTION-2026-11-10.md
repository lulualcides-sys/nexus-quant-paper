# Alpha Master — rastreabilidade das perdas dos 27 robôs (10/11/2026)

## Escopo auditado
A branch de pesquisa implementa a função \`attribute_trades\` sobre o diário de posições **fechadas** que cada motor já produziu. É usada diretamente no backtest original dos **27 robôs planejados**: 5 ouro H4, 5 ouro H4 com alavancagem virtual, 15 H1, BB20 USD/CAD M15 e Momentum60 H4.

**Objetivo:** informar o que ocorreu com as operações simuladas, não inventar explicações para todas as perdas ou prometer lucro. Inclui hora da entrada em UTC, mês da saída, motivo de saída, valor líquido e custo anotado por trade, média por operação, payoff, profit factor e piores cinco perdas.

## Correção técnica
O relatório anterior mostrava totais por robô, mas não era capaz de apontar quais tipos de saída concentravam as perdas. Agora \`research/backtest_27.py\` acrescenta \`loss_attribution\` por robô ao JSON e uma tabela legível ao Markdown. O bloco de atribuição usa apenas as operações já registradas e não altera nenhuma ordem, trade, preço, risco ou estado.

- Saídas sem tipo identificado são \`UNKNOWN\`, não \`STOP\` por suposição.
- Custos de \`cost_usd\` e \`transaction_cost\` são nomes alternativos do mesmo custo, não somados duas vezes. \`funding_cost\` é somado separadamente.
- Falta de custo ou timestamp fica **explícita**. Não transforma ausência de dados em custo de zero.
- Entrada e saída são timestamp UTC; todos os buckets por hora são **UTC**, não horário de São Paulo.
- Períodos, fonte Yahoo e custos de pesquisa existentes continuam exatamente os mesmos.

## Testes e execução
1. \`python -m unittest discover -s tests -p 'test_trade_attribution_27.py' -v\`
2. \`python -m unittest discover -s tests -p 'test_backtest_27.py' -v\`
3. \`python -m research.backtest_27\` somente com feed histórico válido; Action preserva o JSON e o Markdown como artifacts, sem escrever arquivos em \`state/\`.

O workflow \`.github/workflows/backtest-27.yml\` inclui os novos testes e a regressão preexistente e só roda replay de mercado após os testes offline.

## Próxima iteração — melhoria econômica
A atribuição encontra **onde** se concentram perdas; ela NÃO prova **por que** o sinal falhou. Antes de mexer em parâmetros, comparar cada trade com candles causais e, quando disponível, BID/ASK e marcações de price action feitas antes da entrada; verificar motivos \`STOP\`, \`TIME\`, \`TARGET\`, custo e faixas de horário em período reservado. A decisão de alteração deve ser registrada por estratégia, com comparação pareada e reversão de hipóteses que piorem os resultados.

Os robôs de cripto e os experimentos M1/M5 nas PRs DRAFT continuam isolados e sem alteração. Não mesclar esta PR apenas por CI verde: auditoria melhor não representa estratégia lucrativa.

**Status: SOMENTE PESQUISA; nenhuma estratégia ou operação real aprovada.**
