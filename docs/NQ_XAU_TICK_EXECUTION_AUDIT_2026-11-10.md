# NQ XAUUSD — auditoria de execução bid/ask e robustez (10/11/2026)

**Escopo:** pesquisa independente, não réplica de sinais do Tracker Greenhouse; não é recomendação, robô ou estratégia aprovada.

## Código, fonte e histórico rastreável

- [Indicador MT5 para XAUUSD M1/M5](../indicators/mt5/NQ_XAU_Quote_Tracker_Research.mq5) — MQL5 visual, sem ordens; compilação MetaEditor oficial da revisão mais recente em [run 42760710846](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42760710846) com **0 erros/0 avisos**.
- [Detector determinístico](../research/xau_quote_tracker_reference.py) e [montagem de candles de bid/ask](../research/xau_dukascopy_replay.py).
- [Motor de execução em quotes](../research/xau_quote_execution_backtest.py) e [testes adversariais](../tests/test_xau_quote_execution_backtest.py).
- [Consolidação cronológica](../research/xau_quote_robustness_panel.py) e [workflow ampliado](../.github/workflows/xau-15-session-robustness.yml).
- Ferramenta de dados aberta: [dukascopy-node](https://github.com/Leo4815162342/dukascopy-node), versão fixada **1.51.1** no workflow. Dados públicos históricos de **XAUUSD, bid/ask**, cinco horas por sessão (12–17 UTC). As cotações não correspondem necessariamente ao feed de uma conta MT5 do usuário. O arquivo bruto de ticks NÃO é publicado junto ao relatório; os artefatos incluem indicadores de proveniência, hashes e lançamentos simulados.

## Regras de execução, definidas antes do teste

- Sinal apenas depois que a vela se fecha; nunca se usam ticks futuros na decisão.
- Próximos três candles: **compra limite quando ASK atinge ou cai abaixo de 50% do Fibonacci**; **venda limite quando BID atinge ou supera 50%**. Expira sem execução depois desse prazo. Não contabilizar uma seta como operação preenchida.
- Limites de entrada e take profit **nunca recebem preço pior que o próprio limite**. Comprar/vender e zerar posições usa respectivamente o lado adequado do spread, como na documentação [MQL5 Trade Functions](https://www.mql5.com/en/docs/trading).
- Longos: stop disparado por BID, alvo por BID; curtos: stop disparado por ASK, alvo por ASK. Gaps podem piorar o stop. Saída por tempo depois de 20 candles ou liquidação no último quote da sessão.
- Simulação de **uma única posição** e ordem pendente por vez. Não presume múltiplas posições nem execução de mercado real.
- Cenário básico: comissão **US$ 0/oz** e slippage **US$ 0**. Cenário com atrito: comissão total hipotética **US$ 0,30 por onça** + **US$ 0,10/oz de slippage em stop/saída a mercado**, nunca em ordens limitadas. Não são tarifas verificadas da corretora, e não incluem swaps, latência, impacto ou rejeição.
- Os resultados em USD representam **uma onça teórica**, não tamanho do contrato, conta ou lote verificado por corretora.

A primeira execução de quatro sessões identificou uma inconsistência no stress do limit order: ele aplicava slippage para além da própria ordem limite. Isso foi corrigido ANTES da amostra consolidada de 14 sessões. A repetição corrigida passou em [run 42781887677](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42781887677), incluindo **16 testes de execução + 10 de quote + 21 do indicador**, e os quatro dias tiveram resultado líquido **−US$ 4,976/oz** no cenário de atrito.

## Amostra ampliada

**Execução verificada:** [GitHub Actions 42781887672](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42781887672), artefato `xau-14-clean-session-quote-robustness-audit`, com **5 testes de consolidação + 16 testes de execução aprovados**, 14 dias completos. Código e parâmetros congelados, sem otimização após ver perdas.

**Pré-seleção:** 15 pregões úteis de 19/10 a 06/11/2026. Um dos 15, **06/11/2026**, apresentou quote inválido/cruzado em registro bruto 31.309 e falhou na validação. A sessão inteira foi **excluída por qualidade de dado**, não por sua performance; 14 pregões permaneceram. [Falha auditável da primeira tentativa](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42781215341). É incorreto chamar os 14 dias de uma amostra aleatória/imparcial de todos os regimes de mercado.

### Tabela por timeframe, dados reais do feed, P&L ainda hipotético

| Indicador | Sinais | Entradas preenchidas | Expiradas | Vitórias | Derrotas | Líquido básico US$/oz | Líquido atrito US$/oz | PF com atrito |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **M1** | 20 | 12 | 8 | 4 | 8 | −17,730 | **−22,130** | 0,490 |
| **M5** | 7 | 4 | 3 | 2 | 2 | +16,637 | **+15,237** | 1,798 |

Máximo drawdown realizado com atrito: M1 **US$ 37,32/oz**; M5 **US$ 19,085/oz**. Esses valores não representam drawdown percentual de conta.

### Diagnóstico cronológico, não validação de performance independente

Separamos as dez sessões até **30/10** das quatro de novembro (02, 03, 04 e 05/11). No trecho mais tardio, **M1** realizou 7 operações (3 positivas, 4 negativas), encerrando em **−US$ 4,976/oz** com atrito (PF **0,793**). **M5** apresentou **um sinal não preenchido, nenhuma posição encerrada**: lucro e PF nesse trecho são **indeterminados**, não zero acerto ou prova de robustez.

No conjunto, o M5 mostra lucro teórico em **quatro operações** e não tem nenhuma operação na janela tardia. A seleção do M5 como “vencedor” seria **sobreajuste por seleção de timeframe**. Nenhum modelo comprovou expectativa líquida positiva durável nem coincidência com o Tracker comercial.

## Decisão e pendências

**NÃO aprovar para ordens ao vivo ou demo autônoma** e **NÃO integrar os robôs existentes**. A PR deve permanecer em DRAFT porque:

1. Não há algoritmo original Greenhouse disponível publicamente; comparar setas de forma cientificamente válida exigiria gravação integral, mesmo período, feed e intervalo completo de todos os sinais reais.
2. O tester econômico é uma aproximação de bid/ask Dukascopy com premissas explícitas, **não** é resultado de MT5 de corretora. Provar que um EX5 compila **não** comprova que o gráfico, o feed e os alertas estão funcionando em uma sessão MT5 conectada ao usuário.
3. A vantagem econômica M1 é negativa e a amostra M5 é pequena/inconclusiva. Não ajustar thresholds com base nas mesmas 14 sessões e depois chamar o novo resultado de “fora da amostra”.
4. São necessários dados e custos do broker autorizado do usuário, captura efetiva de M1/M5 no terminal, condições de execução, documentação de spreads e uma janela futura mantida fora do desenvolvimento.

**Status verificável da etapa atual:** código, CI, dados históricos auditados, gerenciamento de ordem simulada e relatórios entregues no GitHub. Lucro real, equivalência com o Tracker original e conexão MT5 **não estão comprovados**.

## Verificação cronológica adicional — 9 de novembro de 2026

- **Fonte independente:** [GitHub Actions 42786406929](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42786406929), artefato `xauusd-20261109-predeclared-holdout`, período 2026-11-09 12:00–17:00 UTC, `dukascopy-node@1.51.1`.
- **Cotações históricas:** 149.860 registros de bid/ask, SHA256 `134eea932b88394af88c347f5c0446d522e32bb7fcef683c3e979eeea46e3024`.
- **Parâmetros e custos inalterados:** M1 1 sinal de pesquisa, 1 entrada limite preenchida, 0 vitórias, 1 derrota, líquido hipotético de **−US$ 3,776 por onça** com comissão roundtrip US$ 0,30/oz e slippage stop/mercado US$ 0,10/oz. M5 **zero sinais e nenhuma operação**.
- **Validações:** 16 testes de execução, 21 do indicador e 10 de ingestão; workflow aprovado. Não houve escolha de parâmetros após observar o resultado. No entanto, o próprio dia já foi examinado nesta pesquisa e não poderá servir como novo holdout para versões futuras.

**Leitura científica:** 14 pregões da auditoria anterior + 1 pregão posterior apenas confirmam que a hipótese atual do M1 continua insuficiente e negativa; o M5 não ganhou evidência adicional. Não somar retornos de diferentes cenários nem afirmar operação real de corretora. Uma eventual hipótese nova precisará de data futura ainda não vista, e não ser declarada vencedora nas mesmas datas.
