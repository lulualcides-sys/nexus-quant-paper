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
