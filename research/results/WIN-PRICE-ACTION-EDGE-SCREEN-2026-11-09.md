# WIN Price Action: busca de vantagem líquida (09/11/2026)

## Veredito

**NÃO DEMONSTRADA vantagem matemática líquida e robusta.** Foram testadas 9 hipóteses predefinidas e uma replicação em segundo contrato. Houve lucro ocasional em julho, mas as variantes falharam em junho e/ou tiveram amostras insuficientes. Não ativar ordens reais.

### Proveniência e execução

- WINQ26, CSV M1 original declarado exportação Profit, dados públicos de terceiros sem auditoria independente B3; Git blob SHA1 \`43c50f01882f1ac497a218549e0bff2964d94aa5\`. Amostra: 35.574 candles, 13/02/2026–24/07/2026.
- [Execução real do estudo das 9 hipóteses — GitHub Actions](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42638198989); relatório e métricas JSON disponíveis no artifact da execução.
- Segundo contrato: WINJ26, Git blob SHA1 \`7fcc91ebde3e674f910ac82eef00b6bf19541151\`, 5.129 candles M1, 22/08/2025–30/12/2025, [execução independente](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42638683735). Série insuficiente para aferir desempenho estatístico.
- Configuração comum: banca R$2.000 reiniciada em cada janela; máximo 1 WIN; risco inicial planejado 1% por negócio incluindo custos; sem trava de perda diária; stop técnico (Red) e alvo (Win), saída conservadora quando há ambiguidade intrabar.
- Estimativa de custos: corretagem e taxas ida+volta R$4, slippage de 1 tick por lado totalizando R$6 por operação. Não é custo verificado na corretora. Stops podem sofrer deslizamento superior.

## Resultado da triagem WINQ26 (R$ líquidos com 1 tick/lado)

| Variante | Fev-Mar | Abr-Mai | Junho | Julho |
|---|---:|---:|---:|---:|
| Base: tendência e lateralização | 0 | +8 | −49 | −43 |
| Somente rompimento/reteste | 0 | +8 | −49 | −3 |
| Somente lateralização | 0 | 0 | 0 | −40 |
| Rompimento alvo 1,5R | 0 | −12 | −38 | +27 |
| Rompimento alvo 3R | 0 | −12 | −53 | +9 |
| Rompimento candle forte | 0 | 0 | −59 | −3 |
| Rompimento + volume | 0 | +8 | −33 | +23 |
| Rompimento + M5 momentum | 0 | −4 | −21 | −16 |
| Rompimento apenas pela manhã | 0 | 0 | 0 | +4 |

**Atenção:** valores zerados podem significar zero operações. Julho já foi utilizado em pesquisa ATLAS, portanto não é validação prospectiva independente. Triar hipóteses pela melhor performance histórica é susceptível a seleção e sobreajuste.

### Replicação WINJ26 (R$ com 1 tick/lado)

| Variante | Operações | PnL líquido | PF |
|---|---:|---:|---:|
| Base | 2 | −7 | 0,632 |
| Somente rompimento/reteste | 1 | +12 | N/D |
| Rompimento + volume | 0 | 0 | N/D |
| Rompimento com alvo 1,5R | 0 | 0 | N/D |

Nenhum modelo alcança 30 negociações nesse segundo contrato; o resultado +R$12 equivale a UMA operação e não constitui sinal de edge.

## Diagnóstico econômico e próximos critérios

- Com banca de R$2.000, risco planejado de R$20 por operação e custo aproximado de R$6, restam R$14 de margem bruta para o stop; num WIN (R$0,20/ponto), isso corresponde a **70 pontos**. Se o stop técnico real exigir mais, o algoritmo rejeita a oportunidade. Apertar o stop só para forçar entradas distorceria o método.
- Mais cenários otimizados na mesma amostra não resolvem o problema de evidência; pode aumentar falsos positivos.
- Próximo experimento útil: obter **outros vencimentos completos de WIN M1**, independentemente licenciados, com 100+ sinais reais por setup, o horário e custos da corretora. Pré-registrar variante, congelar parâmetros, acompanhar OOS temporal e paper-forward por sinal, e separar os setups.
- Não mexer nos outros robôs, na main ou na corretora. Todos os resultados permanecem em PR de pesquisa e artifacts GitHub Actions.

## Reprodução

- \`research/win_pa_variant_screen.py\` executa os nove filtros usando a fonte PINNED WINQ26, com janelas cronológicas.
- \`research/win_pa_winj26_replication.py\` lê segundo vencimento com hash de blob verificado.
- \`research/win_price_action.py\` mantém controle de no máximo uma posição, stop-loss e take-profit, sem limite diário de perdas.

**Status:** trabalho de identificação de candidata feito; **estratégia lucrativa validada não obtida**.
