# Nexus Quant — pesquisa de fusão de indicadores (somente GOLD)

**Status:** quatro novos robôs experimentais, independentes dos 27 anteriores e dos ATLAS preservados; **nenhum aprovado para dinheiro real**. Não há garantia de lucro. As regras são hipóteses próprias derivadas dos indicadores, não cópias exatas nem sinais idênticos ao TradingView.

## Hipóteses implementadas

| Robô | Gatilho fechado | Fontes reutilizadas |
|---|---|---|
| `BOS_DTC_QKE` | Rompimento de pivô confirmado, Z-score >0,5, EMA 30>35>40>45>50>60 e candle de impulso | Market Structure Dynamics, DTC v1.36, QKE Ultra Fast |
| `RANGE_DTC_QKE` | Rompe range anterior de 20 candles com buffer 0,15 ATR, EMA stack e impulso | Auto Range Detector (interpretação causal simplificada), DTC, QKE |
| `OB_RETEST` | Após BOS, salva último candle oposto (10 candles), entra em reteste + rejeição de zona dentro de 64 barras | Market Structure Dynamics / Order Blocks, pivôs, tendência EMA |
| `SWEEP_REVERSAL` | Varredura de pivô anteriormente confirmado com fechamento de volta | Monster Arrows v2 / liquidez; regra independente, sem seu filtro HTF original |

**Não utilizados como lógica verificável:** `Drawing Toolbox.ex4`, `Trend Wave Indicator.ex4`, `WyckoffFullSuite_v3.1.ex5`, `Support & Resistance BC Zones.ex5`. São binários compilados e o conteúdo executável não foi auditado; seria incorreto afirmar que suas fórmulas estão implementadas. Há apenas ideias gerais de suporte/resistência e varredura, não equivalência.

## Política do backtest

- XAUUSD proxy `GC=F` de Yahoo, **não** cotação negociável do broker. Dados M5 (1 mês) agregados para M15 e M30 somente em blocos inteiros e sem lacunas; M1 separadamente (5 dias). Recortes temporais diferentes não são equivalentes.
- Entrada na **abertura da próxima vela íntegra** após sinal fechado. Candle de sinal jamais gera fill intrabar.
- Stop `1,5 ATR(10)` fixo para os dois cenários de custos; sem entrada quando o alvo teórico de 1,8R não cobre pelo menos 3 vezes o custo nominal de referência de 14 bps. Alvo `1,8R`; limite 48 velas. Saída stop-first quando stop e alvo são tocados na mesma vela. Gap adverso executa no preço de abertura pior. Sem alavancagem, exposição nominal no máximo 1×, limite de risco-stop planejado 0,75%. O risco efetivo pode exceder em gaps.
- Custo completo de ida e volta: **14 e 28 bps** do nocional; não inclui swap exato, execução real por bid/ask, notícia, rolagem de futuro, tick-data ou taxa específica da corretora.
- Três segmentos cronológicos; posições reiniciadas em cada segmento. O histórico já foi examinado no projeto e não deve ser chamado de holdout independente.
- Candidato retrospectivo apenas com >=30 operações fechadas, P&L marcado a mercado positivo em cada segmento em 14/28 bps e drawdown realizado <=10%. Mesmo que passe, permanece não aprovado para capital real até validação prospectiva independente com dados e custos da corretora.
- Nunca somar os quatro lucros como carteira sem simular correlação, sobreposição de posições e risco agregado.

**Execução:** `python -m unittest tests.test_indicator_fusion_bots -v` e `python -m research.run_indicator_fusion`. A pesquisa gera `research/results/indicator_fusion_latest.json` apenas na execução local ou em um workflow isolado; não edita arquivos em `state/` nem motores já aprovados.

## Nota de segurança

Não usar sinais para operar automaticamente. Sem endpoint de ordens ou API MT5. Testes unitários comprovam invariantes do código, não performance real nem equivalência com as fontes Pine.

## Audit 11/10 — engine chronology and fee decomposition

Audit fix: when a position is open at a candle's start, its eventual intrabar exit does not authorize an entry at that candle's earlier open. The previous replay could retroactively enter after an intrabar stop/target. New test reproduces and guards this chronology error.

Added no-fee and 7bps diagnostic controls alongside original 14/28bps scenarios. Approval thresholds stay strictly 14 and 28bps; no-fee profitability **never** counts as viability. Output includes gross closed PnL, estimated fees, stop/target/time exits. Fees are an all-in roundtrip estimate on GC=F proxy, not broker XAUUSD execution. These are not optimization or signal improvements.