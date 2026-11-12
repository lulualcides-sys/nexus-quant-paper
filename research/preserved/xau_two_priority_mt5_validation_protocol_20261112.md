# XAUUSD — Protocolo de validação dos 2 candidatos prioritários

**Data:** 12/11/2026. **Objetivo:** testar fielmente os candidatos preservados antes de liberar negociação. Nenhuma destas simulações históricas comprova lucro real.

## Robôs congelados para reproduzir no MT5

| ID | TF | Entrada | Saídas |
|---|---|---|---|
| XAU_EMA21_RUNNER_M15 | M15 | EMA21 Pullback com EMA21 acima/abaixo EMA55 e vela de confirmação fechada | 1/3 em 1R, 1/3 em 1,5R, último terço até SL original ou 384 candles M15 |
| XAU_EMA21_RSI_MACD_M30 | M30 | Mesmo EMA21 Pullback + RSI14 e histograma MACD12/26/9 em concordância (compra RSI estritamente entre 52 e 78 e hist >0; venda RSI entre 22 e 48 e hist <0) | 1/3 em 1R, 1/3 em 1,5R, último terço até SL original ou 192 candles M30 |

**Stop histórico EMA21:** candle de sinal e EMA21, com margem 0,12 ATR14; sinal no fechamento de candle confirmado; entrada no open da barra seguinte; cada robô uma posição por vez e cooldown de uma barra. Stops prevalecem quando a barra OHLC toca SL e alvo no mesmo candle. Não mudar parâmetros durante a validação.

## Limites e procedimento de teste

1. **Implementar e compilar um EA MQL5 fiel para cada sinal.** Os scripts Python do repositório não são EAs compilados; não declarar MT5 testado antes de compilar e executar no MetaEditor/Strategy Tester.
2. No MT5 da corretora, verificar especificação de XAUUSD: tamanho do ponto, tick size, tick value, volume mínimo/passo, valor do contrato, spread, comissão, swap, preço Bid/Ask. Definir lotagem conservadora e risco máximo de 0,75% por posição na conta demo de teste. O objetivo histórico de drawdown 10–15% é limite de segurança, não promessa.
3. Configurar período **01/01/2025 até o histórico mais recente realmente disponível**, separando 2025 completo e 2026 parcial; modo **Every tick based on real ticks** onde houver ticks de verdade. Em mercados com apenas OHLC, registrar explicitamente a falta de ticks. Desabilitar otimizações durante a primeira reprodução.
4. Registrar todas as operações e fills: timestamp UTC e horário broker, direção, open, SL, tamanho, fills de TP1/TP2, runner, spread no instante, slippage, comissão, swap, volume, lucro/prejuízo líquido e motivo da saída. Comparar sinais individuais com o replay Python antes de avaliar rentabilidade.
5. Informar PF, número de operações, taxa de acerto, resultado em R e unidade monetária, expectativa líquida por trade, MDD de **equity intratrade**, MAE/MFE, duração e custos por trimestre e por faixa de horário. Se divergirem da simulação, **investigar a causa e não alterar premissas para forçar lucro**.
6. Congelar código, versão do broker e risco e realizar **forward em demo sem ajuste**, em dados genuinamente não vistos. Comprovar expectativa positiva após custos e drawdown aceitável no forward antes de qualquer avaliação real.
7. Rejeitar indicadores com repintura, lookahead de barras futuras, volume insuficiente, resultados concentrados em poucas operações ou dependência de otimização em 2025/26.

## Fontes e evidências

- [Registro imutável de referência dos dois candidatos](xau_two_priority_candidates_for_mt5_validation_20261112.json)
- [Resultado histórico M1–M30 Runner](xau_ema21_full_m1_m30_2025plus_20261112.md)
- [Resultado histórico EMA21 RSI MACD M30](xau_new_indicators_m1_m30_2025plus_20261112.md)
- [Laboratório dos sinais M30](https://github.com/lulualcides-sys/nexus-quant-paper/pull/75)

**Situação atual:** apenas candidatos em pesquisa, salvos no GitHub. A homologação com real ticks, spread broker e EA MQL5 compilado **ainda falta**. Nenhuma execução em conta real autorizada. Os outros modelos antigos continuam arquivados e intactos.
