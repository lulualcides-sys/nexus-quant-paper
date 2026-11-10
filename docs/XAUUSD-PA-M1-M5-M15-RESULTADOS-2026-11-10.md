# XAUUSD — M1, M5 e M15 | backtest com exemplos reais de cotação

**10/11/2026 • Pesquisa isolada, sem ordens reais.**

## Código, dados e testes

- [Código PA M1/M5/M15](../research/xau_pa_timeframes.py) e [testes de sinal](../tests/test_xau_pa_timeframes.py).
- [Execução comprovada GitHub Actions](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42837669453): pipeline SUCCESS, 38 testes aprovados (12 novos e 26 anteriores de feed/execução). Artifact: xau-pa-m1-m5-m15-actual-bidask-six-session-paper, com seis livros de operações hipotéticas e checksums SHA256.
- Fonte: Dukascopy XAUUSD bid/ask (não a corretora MT5), obtido por dukascopy-node 1.51.1, seis sessões fixadas antes do teste: 28, 29 e 30/10 e 03, 04 e 05/11 de 2026, sempre 12:00–17:00 UTC. **Seis sessões válidas; nenhuma sessão em quarentena.**
- Custos pessimistas: spread histórico do bid/ask + comissão hipotética US$ 0,60 por onça no roundtrip + slippage US$ 0,20 por onça em stops/saídas de mercado. Não representam a tabela de uma corretora específica.

**As unidades de P&L são US$ por UMA onça virtual, não lucro de uma conta real, um lote MT5 ou uma carteira.** Nenhum robô foi promovido à main.

## Padrões avaliados

| TF | Regra original do laboratório | Entrada de pesquisa | Stop | Alvo bruto |
|---|---|---|---|---|
| M1 | Rompimento de microestrutura e reteste confirmado | Ordem limite no fechamento do candle de confirmação, só após candle encerrado | Extremo do reteste + margem ATR | 1,5R |
| M5 | Varredura acima/abaixo do extremo dos 12 candles anteriores com rejeição do pavio | Ordem limite pós-fechamento | Extremo da varredura + ATR | 1,8R |
| M15 | Rejeição do suporte/resistência de faixa lateral com dez candles e volatilidade controlada | Ordem limite pós-fechamento | Exterior da faixa | Meio da faixa, mínimo 0,8R |

Entradas requerem preço bid/ask posterior atingindo o limite, stop/target são avaliados pela ordem cronológica dos ticks observados, com custos e spread de ambos os lados. Sem preenchimento retroativo nem alteração em H4.

## Resultados líquidos após o cenário de fricção dobrada

| Modelo | Primeiros 3 dias | Últimos 3 dias | Total 6 dias | Operações fechadas | V/D | PF |
|---|---:|---:|---:|---:|---:|---:|
| M1 rompimento/reteste | −10,482 | −9,573 | **−20,055** | 15 | 6/9 | 0,6294 |
| M5 varredura/rejeição | +0,106 | +6,706 | **+6,812** | 8 | 4/4 | 1,2536 |
| M15 reação lateral | −3,347 | 0,000 | **−3,347** | 2 | 1/1 | 0,2735 |

Valores em US$/oz virtual. Os blocos cronológicos não são validação prospectiva: já houve outras pesquisas com datas de 2026. A amostra M5 de oito trades é insuficiente para selecionar uma estratégia vencedora. M15 fez ZERO entradas na segunda metade.

## Exemplos de operações simuladas, extraídos dos ledgers preservados

Horários UTC e preços cotados em US$/oz. Não são preços atuais ou instruções de trade.

| TF | Operação | Preço de entrada | Stop | Alvo | Preço de saída | Motivo | P&L US$/oz |
|---|---|---:|---:|---:|---:|---|---:|
| M1 | Compra 03/11 às 12:25 | 3915,334 | 3911,593 | 3920,945 | 3911,385 | Stop 12:30 | **−4,549** |
| M1 | Venda 05/11 às 14:40 | 4116,937 | 4120,757 | 4111,207 | 4111,207 | Alvo 14:41 | **+5,130** |
| M5 | Venda 29/10 às 13:40 | 4031,345 | 4038,495 | 4018,476 | 4018,476 | Alvo 14:12 | **+12,269** |
| M5 | Compra 30/10 às 13:40 | 3936,788 | 3922,847 | 3961,881 | 3922,406 | Stop 13:49 | **−14,982** |
| M15 | Compra 29/10 às 16:50 | 4016,085 | 4008,605 | 4023,660 | 4017,945 | Fim da sessão 16:59 | **+1,260** |
| M15 | Compra 30/10 às 16:30 | 3900,015 | 3889,413 | 3911,237 | 3896,008 | Fim da sessão 16:59 | **−4,607** |

Stops podem ser executados pior que o preço de referência pelo bid/ask real e slippage. Fim da sessão é saída forçada pelas cinco horas do recorte, NÃO saída gerada pela regra da estratégia.

## Decisão

M1: resultado negativo nos dois blocos; não aprovar. M5: único positivo, mas amostra muito pequena; somente ampliar evidência sem aumentar lotes. M15: duas operações não bastam para classificar o modelo; precisa de janelas mais longas que evitem liquidação forçada às 17:00.

**Nenhuma estratégia é lucrativa comprovadamente em MT5.** Requer feed/custos da corretora, análise em período novo não utilizado para desenvolvimento, muito mais operações e risco controlado. A pesquisa permanece isolada na PR #60, sem merge.
