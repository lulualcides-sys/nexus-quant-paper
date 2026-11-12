# XAUUSD Price Action — adaptação do WIN para ouro, M1/M5

Pesquisa iniciada em 10/11/2026. **Não é um robô operacional, um Expert Advisor nem um teste de conta MT5.**

## Metodologia implementada

- Referência conceitual: [WIN Price Action M1/M5, PR #49](https://github.com/lulualcides-sys/nexus-quant-paper/pull/49), rompimento e reteste da microtendência, rejeição dos extremos da lateralização.
- Adaptação independente do código [`research/xau_price_action_m1m5.py`](../research/xau_price_action_m1m5.py): sinais M1 condicionados a contexto **M5 fechado**; sinais M5 condicionados a contexto **M15 fechado**. Tolerância, declividade e distâncias de stop dimensionadas pela faixa/ATR local, não por pontos/tick da B3.
- Dados: instrumento **XAUUSD spot**, cotações históricas de mercado `bidPrice`/`askPrice` da Dukascopy, via open source `dukascopy-node@1.51.1`. Sem delta real de agressão e sem volume financeiro da bolsa. Não são os preços da corretora MT5 do usuário.
- Regras preestabelecidas: sinal apenas após candle fechado, entrada a mercado no primeiro quote até 30 segundos depois do fechamento, compra em ask, venda em bid, spread de entrada até US$ 0,90/oz, no máximo uma posição; stop atrás da rejeição/reteste, alvo padrão 2R, filtro mínimo de payoff líquido `0,85`, stop técnico entre 0,15 e 2,5 ATR. Não extrapolar o ATR do WIN.
- Execução: stop ao toque do lado correto bid/ask, gaps desfavoráveis mantidos; alvo em ordem limite sem fill pior que limite; encerramento por tempo após 20 barras ou no último quote da janela. Comissão hipotética **US$ 0,30 por onça por roundtrip** e slippage adverso **US$ 0,10 por onça em entrada/stop/saída a mercado**, além do spread real observado no arquivo. Margem, contrato, comissão efetiva, swap e fila de ordens não testados.
- Unidade de análise: **US$ por 1 onça teórica de ouro**, não saldo de conta, lote MetaTrader, contrato WIN nem mil dólares.
- Dois setups contabilizados separadamente. Status de implementação: código Python e CI; nenhuma ordem live, nenhuma integração com EA; `main` e robôs existentes preservados.

## Primeiro backtest em dados históricos, 08–19/06/2026

**GitHub Actions SUCCESS:** [run 42795744443](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42795744443), 15 testes de regras/execução + 5 de consolidação, dez pregões previstos das 12h às 17h UTC. **9 datas válidas**, 10/06/2026 inteira excluída por cotações cruzadas/inválidas no registro 11.598. Artefato `xauusd-price-action-gold-M1-M5-june-research` com SHA256 por CSV, resultado de cada entrada, saídas, custo e splits.

| Métrica | M1 | M5 |
|---|---:|---:|
| Sinais | 8 | 4 |
| Operações executadas na simulação | 7 | 4 |
| Vitórias/derrotas | 3/4 | 1/3 |
| Resultado líquido hipotético US$/oz | **+21,200** | **−6,524** |
| Profit Factor | 2,770 | 0,318 |
| Primeira semana (8–12/06) | +28,810 | −5,280 |
| Segunda semana (15–19/06) | −7,610 | −1,244 |
| Intervalo bootstrap descritivo de PnL por dia (2,5%–97,5%) | −19,190 a +73,480 | −20,384 a +6,092 |

### Decomposição da hipótese M1

- **Microtendência/rompimento/reteste:** 6 operações, resultado **+US$ 5,426/oz**.
- **Lateralização/rejeição:** 1 operação, resultado **+US$ 15,774/oz**. Esse único acerto representa aproximadamente **74%** do lucro líquido total; o resultado está concentrado e é frágil.
- Lucro em apenas 3 de 7 operações. **O intervalo de bootstrap por sessões inclui perdas**, e a segunda semana foi negativa.
- **Não aprovar para trade por aparecer lucro em sete operações.** O M5 permanece negativo com quatro fills.

## Replicação adicional em maio de 2026

[Workflow May](../.github/workflows/xau-price-action-may-replication.yml) fixa 20 pregões úteis de 04/05 a 29/05/2026, mesmo modelo e custos, com duas semanas em cada bloco e descarte da sessão inteira em caso de feed inválido. Maio é cronologicamente **anterior** ao período de descoberta de junho; não será chamado de *teste futuro prospectivo*. Não selecionar nem ajustar parâmetros após observar o mês.

## Critérios antes de considerar aprovado

1. Número suficiente de operações verificadas (idealmente pelo menos 100 em datas realmente posteriores à concepção), sem concentrar lucro em uma ou duas entradas.
2. Replicar resultado líquido positivo após custos conservadores, diferentes regimes e intervalos de incerteza que não sugiram vantagem ilusória.
3. Captura autorizada e resultados diretamente no terminal MT5 e feed da corretora, verificando contrato/volume, horários, spread, swaps, comissões, slippage, slippage em stop, latência e rejeição de ordens.
4. Nenhuma publicação de robô real sem aprovação explicitamente fundamentada.

**Decisão no momento do primeiro teste:** versão de pesquisa isolada, sem merge e sem negociação automática.

## Replicação mantendo os parâmetros: 04–29/05/2026

**GitHub Actions SUCCESS:** [run 42796282799](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42796282799), três jobs aprovados, **20 sessões previstas e 20 válidas**, sem descartar nenhum dia. Mesmo código, mesmos dois setups, filtro de risco, custo hipotético e horário UTC usados na execução de junho.

- [Código do consolidador de maio](../research/xau_pa_may_replication.py), [quatro testes adicionais](../tests/test_xau_pa_may_replication.py), [workflow](../.github/workflows/xau-price-action-may-replication.yml).
- M1: **18 sinais**, **16 operações preenchidas**, 1 vitória e 15 derrotas; resultado **−US$ 37,010 por onça**, PF **0,104**. Primeira metade de maio: **−US$ 20,173/oz**; segunda metade: **−US$ 16,837/oz**.
- Composição M1: rompimento/reteste 11 trades **−US$ 23,723/oz**; lateralização/rejeição 5 trades **−US$ 13,287/oz**. 14 stops, 1 alvo, 1 fechamento por tempo.
- M5: **nenhum sinal ou operação** em 20 sessões; resultado monetário 0 significa **ausência de operações, não empate ou estratégia sem risco**. O contexto M15 mais restritivo resulta em poucos sinais.
- Intervalo bootstrap descritivo de P&L M1 ao reamostrar sessões: aproximadamente **−US$ 56,234 a −US$ 18,782/oz**. Não é garantia estatística de perda futura, mas mostra ausência de evidência robusta nesta amostra.
- Os dados são cotações históricas da Dukascopy, não de conta MT5 do usuário; preços de ouro spot sem lote real. Maio é **anterior** a junho; não constitui teste prospectivo fora da amostra, ainda que os parâmetros tenham sido preservados.

### Consolidação descritiva (sem escolher dias ou setups)

| Período | Sessões válidas | Operações M1 | V/D | P&L M1 (US$/oz) | Operações M5 | P&L M5 |
|---|---:|---:|---:|---:|---:|---:|
| Maio/2026 | 20 | 16 | 1/15 | **−37,010** | 0 | 0 (sem operações) |
| Junho/2026 (08–19) | 9 | 7 | 3/4 | **+21,200** | 4 | **−6,524** |
| **Total descritivo** | **29** | **23** | **4/19** | **−15,810** | **4** | **−6,524** |

**Conclusão atualizada:** Price Action adaptado ao ouro **não tem expectativa líquida positiva demonstrada**. Resultado positivo em uma janela pequena de junho não resistiu à replicação histórica de maio. Não reduzir stop, remover perdas ou otimizar filtros nos mesmos 29 pregões e alegar validação independente. Precisa de dados posteriores realmente não usados, regras pré-congeladas, mais de 100 trades e custos/condições do broker documentados. Nenhum código de robô operacional ou configuração de conta foi modificado.

**Estado:** PR da pesquisa em DRAFT e isolada da main; backtests reais de cotações concluídos, mas nenhuma operação real/MT5 nem identidade com qualquer indicador comercial comprovadas.
