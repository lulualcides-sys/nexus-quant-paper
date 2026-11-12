# WIN Liquidity Sweep M1/M5 — novo robô independente, 09/11/2026

**Status: protótipo de pesquisa offline; NÃO aprovado para capital real.**
Não modifica WIN Price Action, ATLAS, outros robôs, monitor, estados, ordens ou corretora.

## Estratégia

- M1: lê somente 20 candles anteriores do mesmo pregão, e exige preço varrer uma máxima/mínima anterior e fechar de volta dentro da faixa; vela de rejeição direcional.
- Volume de contratos: ao menos 90% da mediana dos 20 minutos anteriores. Não utiliza volume financeiro como quantidade.
- Contexto M5 completo: veta reversão contra movimento excessivamente forte; sem olhar futuro.
- VWAP aproximada: preço típico dos candles M1 da sessão ponderado por quantidade de contratos, NÃO VWAP real tick a tick. Apenas compra abaixo e venda acima desse proxy; sem VWAP como ablação pré-definida.
- Compra/venda na abertura da próxima vela M1, se gap aceitável. Stop Red de 5 pontos além da extremidade varrida, Stop Win com alvo 1,8R; saída por tempo máximo de 35 candles ou fim da sessão.
- 1 WIN no máximo simultaneamente; não há trava de perdas diárias. Banca inicial R$2.000, risco inicial planejado até 1% por trade incluindo custo assumido. Stops podem executar pior que o orçamento.
- Custo-base estimado: R$4 de taxa ida e volta + 1 tick de slippage por lado = R$6. Não são tarifas verificadas da corretora. Cenários 0 e 2 ticks/lado também calculados.

## Backtest com candles de mercado de fonte pública

- WINQ26, exportação Profit declarada por terceiro, sem auditoria independente B3. Git blob SHA1 fixo 43c50f01882f1ac497a218549e0bff2964d94aa5.
- Dados: 35.574 candles M1 do contrato WINQ26 entre fevereiro e julho de 2026.
- Workflow corrigido e verificado: https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42659540202 (versão original preservada como referência).
- 11 testes técnicos passaram; backtest e upload dos ledgers JSON e Markdown concluídos. Dois testes novos verificam buracos nos candles durante operações e risco aberto ao fim do histórico.

## Resultado líquido: R$6 estimados por operação completa

| Período | Candles | VWAP: trades | VWAP: R$ | Sem VWAP: trades | Sem VWAP: R$ |
|---|---:|---:|---:|---:|---:|
| Fev-Mar 2026 | 390 | 0 | 0 | 0 | 0 |
| Abr-Mai 2026 | 13.748 | 2 | -7 | 4 | -39 |
| Junho 2026 | 11.296 | 19 | -114 | 34 | -172 |
| Julho 2026 | 10.140 | 31 | -65 | 51 | -82 |

Junho VWAP: 36,84% acerto, PF 0,424, DD realizado 6,956%. Julho VWAP: 48,39% acerto, PF 0,745, DD realizado 6,712%. O histórico de fevereiro-março é pouco representativo.

## Conclusão

**Não passou a triagem histórica.** A auditoria encontrou operações atravessando minutos sem candles M1 observáveis. Em abril–maio, após eliminar a hipótese indevida de continuidade de posições sobre lacunas, os resultados líquidos passaram de +R$29 para **−R$7** com VWAP e de +R$31 para **−R$39** sem VWAP. Esse ajuste não é melhoria de rentabilidade; é correção de integridade. No cenário-base, uma das duas saídas com VWAP e três das quatro sem VWAP exigiram liquidação hipotética após lacuna e são **não verificáveis**, impossibilitando qualquer aprovação. Junho/julho permaneceram negativos. O filtro VWAP reduziu perdas comparado à ablação, mas ambas perderam em junho e julho.

Dados OHLC não demonstram ordem intrabar exata, prioridade de fila nem preço real de execução. Os meses desta fonte já foram estudados em outras pesquisas e não formam holdout externo intacto. Não recalibrar retrospectivamente até produzir lucro aparente. Para promover, exigir dados reais inéditos de outros vencimentos, custo verificado, pelo menos 100 trades por configuração e teste prospectivo.

Arquivos: research/win_liquidity_sweep.py (estratégia); research/win_liquidity_sweep_backtest.py (runner PINNED), tests/test_win_liquidity_sweep.py (11 testes), .github/workflows/win-liquidity-sweep.yml (execução CI).

Comandos: python -m unittest discover -s tests -p test_win_liquidity_sweep.py -v; python -m research.win_liquidity_sweep_backtest.

**Robô distinto da PR #49, mantido em branch própria. Nenhuma ordem real.**

## Integridade do motor (correção após o estudo inicial)

O replay agora registra `UNVERIFIABLE_DATA_GAP` quando existe lacuna temporal de M1 durante uma operação e a cancela no próximo preço observado com hipótese adversa. **Não há como saber se o stop, alvo ou ambos foram executados no intervalo faltante**; por isso essa saída contamina o backtest para fins de aprovação, mesmo que seja registrada com preço pessimista. Posições abertas ao fim da amostra são marcadas a mercado separadamente, sem inventar fechamento. O gate reprova lacunas e posições abertas.

Resumo corrigido com 1 tick por lado: abril-maio VWAP 1 saída não verificável de 2; sem VWAP 3 de 4; junho VWAP 0 de 19; junho sem VWAP 1 de 34; julho 0 em ambos. Fonte: [CI 42659540202](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42659540202).

## Teste econômico adicional: payoff líquido mínimo 1:1

- [GitHub Actions: simulação e testes após filtro](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42660644963).
- Na versão de base, abril–maio teve payoff líquido mediano 0,823:1; junho e julho tiveram 0,750:1. **Todas as 52 operações de abril a julho com VWAP ficaram abaixo de 1:1 após os custos modelados.**
- Um filtro opcional exige alvo líquido pelo menos igual à perda líquida prevista, sem alterar a estratégia base ou a ausência de trava diária. **Resultado: zero operações em abril, maio, junho e julho sob R$4 de taxas + um tick de slippage por lado.** Zero perda não representa lucro nem vantagem demonstrada.
- Em cenário de custos menores, o filtro pode permitir operações, mas resultados históricos não validam lucro e parâmetros não devem ser escolhidos apenas por esse cenário.
- A configuração inicial tem risco planejado de até 1% (R$20) e custo R$6 por ciclo, limitando stop bruto a 70 pontos WIN. Com alvo bruto de 1,8R e stop bruto máximo de R$14, a melhor razão lucro/perda líquida planejada é (1,8 × 14 − 6) / (14 + 6) = 0,96:1, antes de perdas de execução adicionais. Portanto um filtro de 1:1 tende matematicamente a impedir todas as entradas nessa configuração.
- **Decisão:** não aumentar o risco só para permitir a entrada e não considerar o filtro uma cura. A investigação requer custos reais da plataforma, desenho de alvo e stop economicamente viáveis, e novo conjunto de dados para validação.
