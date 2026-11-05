# ATLAS V4 — resultados verificados, WINQ26 M1 e WINM26 M5

**Data:** 05/11/2026. **GitHub Actions com testes e backtests concluídos:** [run 42076776535](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42076776535).

> **Decisão:** nenhuma das variantes V4 foi aprovada para produção ou para substituir o ATLAS em paper-forward. Os resultados não comprovam vantagem persistente nem reproduzem a fórmula fechada do indicador Tracker.

## Evidências e metodologia

- Dados externos: exportações Profit/Nelogica do projeto público `wesleyzilva/tradetech`, não verificadas diretamente na B3. Fonte WINQ26 M1: `dados/candles/2026-2S_Q26/WINQ26_F_0_1min.csv`, blob Git fixo `43c50f01882f1ac497a218549e0bff2964d94aa5`. Fonte WINM26 M5: `dados/candles/2026-1S_M26/WINM26_F_0_5min.csv`, blob Git fixo `6ee0eebd10e24ac40c073efe73883c313e6c27b1`.
- Todas as regras V4 permaneceram iguais entre os contratos: `v4_sweep_quality`, `v4_sweep_trend`, `v4_sweep_vwap` e `v4_breakout_retest`, confrontadas com V1 e V3. Rejeição de pavio, volume relativo/absoluto, ATR, horário, EMA20/50, VWAP intradiário fechado e rompimento com ordem de retorno. Os parâmetros **não foram recalibrados depois de inspecionar o teste do WINQ26**.
- Execução simulada no motor existente, ordem limitada a 50% do candle fechado no candle seguinte, alvo +200%, stop −100%, relação geométrica nominal 1:1. Tick WIN=5 pontos, R$0,20/ponto/minicontrato. Taxa estimada de R$4 por contrato na ida+volta e slippage simulado de 0, 1 ou 2 ticks **em cada lado**.
- Banca virtual M1 de R$5.000 versus banca virtual M5 de R$30.000, ambas com risco nominal planejado 0,75%, até 3 contratos inteiros. **Não comparar o P&L absoluto entre M1 e M5, pois os tamanhos de capital e candles são diferentes.**
- Maio/2026 no WINM26 cobre apenas até dia 14: **mês parcial**. Junho/julho WINQ26 foram previamente examinados em testes V1/V3; por isso não constituem holdout íntegro ou validação prospectiva para o V4.

## WINQ26 M1 — P&L líquido com 1 tick por lado

| Modelo | Maio | Junho | Julho | Trades fechados em maio/junho/julho |
|---|---:|---:|---:|---|
| V1 | -R$619 | -R$649 | -R$541 | 40/61/74 |
| V3 | -R$365 | -R$188 | +R$31 | 18/20/15 |
| V4 rejeição | R$0 | -R$190 | +R$4 | 0/23/30 |
| V4 tendência | R$0 | -R$95 | -R$33 | 0/7/7 |
| V4 VWAP | R$0 | -R$105 | +R$31 | 0/7/7 |
| V4 rompimento | -R$24 | -R$271 | -R$305 | 2/34/56 |

**Gate quantitativo: 0/6 passaram.** Uma amostra de 7 fechamentos em um mês é insuficiente para defender um filtro, mesmo com winrate de 71,43%.

**Diagnóstico de maio:** V4 rejeição emitiu 6 sinais e 0 entradas; V4 tendência emitiu 2 sinais e 0 entradas; V4 VWAP emitiu 0 sinais. Assim, zero P&L em maio não significa proteção lucrativa: o filtro pode ser inviável no vencimento ainda menos líquido.

**Sensibilidade (2 ticks por lado):** rejeição −R$244 junho e +R$5 julho; tendência −R$111/−R$51; VWAP −R$123/+R$15; rompimento −R$343/−R$425; V3 −R$238/−R$7. Diferenças não monotônicas isoladas entre 1 e 2 ticks podem ocorrer quando a banca líquida altera a quantidade inteira de contratos e o caminho de operações, **não** são vantagem com pior execução.

## Teste em outro contrato — WINM26 M5, banca virtual R$30.000

| Modelo | Março | Abril | Maio parcial | Trades março/abril/maio |
|---|---:|---:|---:|---|
| V1 original | +R$83 | +R$284 | +R$824 | 35/25/17 |
| V3 | +R$148 | +R$458 | -R$329 | 5/9/2 |
| V4 rejeição | -R$674 | +R$761 | +R$42 | 9/9/5 |
| V4 tendência | -R$351 | +R$283 | +R$64 | 2/4/3 |
| V4 VWAP | R$0 | -R$95 | -R$75 | 0/2/2 |
| V4 rompimento | -R$1.370 | -R$19 | -R$48 | 24/28/10 |

O modelo V1, **sem filtros novos**, foi o único positivo nesses três recortes M5, com 77 fechamentos totalizados. O ganho somado dos três testes mensais independentes seria R$1.191, mas **não equivale a uma curva contínua de capital**. Com stress 2 ticks por lado, março = −R$37, abril = +R$198 e maio parcial = +R$760. Há um mês negativo no stress e o terceiro é incompleto; **não aprovar ou afirmar estabilidade**.

O V4 rejeição teve +R$761 em abril com apenas 9 fechamentos, mas −R$674 em março com outros 9. A variação é forte e não permite inferir que o modelo seja confiável.

## Consequências práticas

1. **Rejeitar por enquanto** VWAP como estratégia principal, rompimento e filtro de tendência: baixo número de operações ou perdas repetidas.
2. **Investigar M5 com banca compatível** como hipótese separada. Não comparar seus lucros absolutos com M1/R$5.000; primeiro testar novos contratos, mais meses completos, spread, custos realistas e tamanho de risco com dados genuínos.
3. Analisar as causas dos 0 fills, dos stops e dos sinais excessivos por horário e regime de volatilidade **somente em estudo exploratório**; qualquer filtro escolhido após observar esses períodos exige novos dados para validação.
4. Congelar os resultados negativos (não apagá-los nem ajustar parâmetros para reescrever o histórico). Precisão de sinal, lucratividade e réplica do Tracker são questões diferentes.
5. **Sem alterações no motor ATLAS prospectivo, outros 27 robôs, dinheiro real, automatização de ordens ou credenciais.**

### Fontes de referência

- B3: [especificação mini Ibovespa WIN](https://www.b3.com.br/pt_br/produtos-e-servicos/negociacao/renda-variavel/futuro-mini-de-ibovespa.htm).
- Pesquisa sobre risco de seleção de backtests: [Bailey e López de Prado (2014), Deflated Sharpe Ratio](https://doi.org/10.3905/jpm.2014.40.5.094).
- Resultados completos com ledger por trade, métricas de custos e hashes de origem ficam nos artifacts anexados à execução do GitHub Actions enquanto forem retidos pela plataforma.
