# WIN Price Action M1/M5 — backtest histórico realizado em 09/11/2026

**Veredito: REPROVADO para capital real.**
[Execução reproduzível GitHub Actions](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42637069642)
[Artefato ZIP com ledger JSON e relatório Markdown](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42637069642#artifacts)
[Implementação](../backtest_win_price_action_real.py)

## Origem

- WINQ26 contrato individual, preços M1 atribuídos a exportação Profit de repositório público, ainda não homologada contra boletim B3.
- Arquivo: \`wesleyzilva/tradetech/dados/candles/2026-2S_Q26/WINQ26_F_0_1min.csv\`
- Hash Git blob SHA1 *fixo*: \`43c50f01882f1ac497a218549e0bff2964d94aa5\`.
- Base total: **35.574 candles M1** entre 13/02/2026 e 24/07/2026; junho: **10.101 candles**, 21 pregões; julho: **8.999 candles**, 18 pregões. Sem preços sintéticos.
- 1 WIN; banco inicial R$ 2.000 reiniciado por mês para comparação; sem bloqueio de perdas diárias, apenas uma posição de cada vez; stop técnico, alvo nominal 2R.
- Custo: R$ 4 ida e volta estimados mais 0/1/2 ticks de slippage em cada lado (1 tick = 5 pontos; R$ 0,20/pt).
- Risco por trade 1% incluindo o custo de cenário, não limite da perda efetivamente executada. Sem negociação real.

## Resultado por mês (retrospectivo)

| Mês | Slippage por lado | Fechamentos | Acerto | Líquido R$ | Profit Factor | DD realizado | Máx reds |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2026-06 | 0 ticks | 9 | 33,33% | −81 | 0,198 | 4,35% | 3 |
| 2026-06 | **1 tick** | **7** | **42,86%** | **−49** | **0,222** | **2,65%** | **2** |
| 2026-06 | 2 ticks | 6 | 33,33% | −43 | 0,157 | 2,25% | 1 |
| 2026-07 | 0 ticks | 23 | 43,48% | −39 | 0,782 | 3,61% | 5 |
| 2026-07 | **1 tick** | **21** | **47,62%** | **−43** | **0,736** | **3,52%** | **4** |
| 2026-07 | 2 ticks | 17 | 47,06% | −79 | 0,455 | 5,07% | 6 |

**Não comparar só o lucro entre cenários**, pois o custo maior também afeta elegibilidade de entradas pelo limite de risco; o número e o conjunto de operações mudam.

### Setups base (1 tick/lado)

- Junho, rompimento + reteste: 7 operações; **−R$49**, PF 0,222; rejeições por risco 9.
- Julho, rompimento + reteste: 17 operações; **−R$3**, PF 0,974.
- Julho, lateralização/rejeição: 4 operações; **−R$40**, PF 0,167.
- Julho, 13 sinais recusados pelo teto de risco; 1 por gap. Junho: 289 eventos de gap contados no diagnóstico, majoritariamente interrupções do calendário do histórico, não 289 negociações perdidas.

## Limitações e decisão

- Resultados **negativos nos dois meses** ao custo de 1 tick; 28 negócios é amostra pequena e não demonstra edge.
- Julho é apenas um período retrospectivo posterior, não holdout intacto, porque as regras foram elaboradas depois de outros estudos sobre o mesmo contrato.
- O motor OHLC M1 não prova a sequência intraminuto dos toques de ordem, liquidez de livro, prioridade de fila, spreads da corretora, slippage extremo ou match de execução.
- Stop-loss pode executar pior; sem trava diária é possível perder a banca inteira.
- Não extrapolar para outros vencimentos; futura validação requer dados licenciados de outros contratos, mais operações por setup, teste prospectivo e custos reais da corretora.
- **Não ativar em corretora nem publicar como estratégia lucrativa.** Preservar ATLAS e outros robôs, sem misturar os resultados.

## Próximo trabalho recomendado

1. Verificar a capacidade de manter 1% por ordem sem rejeitar grande parte dos setups; comparar o mesmo conjunto de sinais com risco e custos realistas.
2. Auditar o critério de identificação de pivôs e classificação do regime, sem reotimizar cegamente os mesmos meses.
3. Obter mais meses e outros vencimentos reais, congelar regras antes do teste externo e registrar resultados líquidos por setup.
