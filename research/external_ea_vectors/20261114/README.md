# Nexus Quant — extração vetorial de EAs públicos XAUUSD (2026-11-14)

**ESCOPO:** apenas XAUUSD. Sinais de origem em M15; novas frequências M1/M5/M30 requerem validação independente. Não foi realizado backtest MT5 nesta pesquisa. Todas as métricas abaixo são declarações dos autores, sem reexecução.

| Projeto | Resultado declarado | Código/licença | Decisão |
|---|---|---|---|
| [Quant Trading Squeeze Breakout](https://github.com/vrd07/Quant_Trading/blob/main/src/strategies/squeeze_breakout_strategy.py) | PF1,50 e 283 operações em relatório 2026 | MIT | Testar separado; relatório oficial reprova 3/6 critérios; PF1,15 em análise OOS longa, só 3/6 trimestres positivos |
| [Quant Trading Stoch Pullback](https://github.com/vrd07/Quant_Trading/blob/main/src/strategies/stoch_pullback_strategy.py) | PF1,22 e 658 operações | MIT | Testar separado; reprova 4/6 critérios, pior dia −8,3R |
| [FvgGold](https://github.com/foeed/FvgGold-EA/blob/main/FvgGold.mq5) | +48,7% em 64 operações Jan-Jul 2026 | MIT | Refatorar antes: lê EMA H1 em shift=0 (candle aberto); 6 meses otimizados sem OOS independente |
| [Gold Breakout H4](https://www.mql5.com/en/code/77691) | PF1,77 2020–26, 2025 +US$3761 e 2026 parcial +US$1398 | MQL5 CodeBase | Apenas referência contextual: H4 fora dos timeframes M1–M30, sem paridade comprovada |
| [GoldEA sweep/reclaim](https://github.com/eamonnkennedy93-blip/GoldEA) | PF1,30 OOS, 183 operações em vários símbolos | licença não localizada | Ideias somente; sem EA de produção público e XAUUSD não isolado |
| [EMA Gold](https://github.com/koichi055/ema-gold-trader-ea) | +US$11.042 e 650 trades divulgados | licença não localizada | Rejeitado para uso: arquivo .mq5 contém cercas Markdown e não foi comprovado compilável |

## Vetores operacionais extraídos

`SQUEEZE = [pct_ATR100=.20, |ΔKalman3|/ATR≤.50, coil_últimas6, ATR14/ATR14_prev≥1.05, penetração_Donchian20/ATR≥.10, alinhamento_EMA400, cooldown8, SL_USD33, TP2R]`

`STOCH = [inclinação_EMA50, distância_preço_EMA/ATR≥1.0, estocástico_K14/D3, pullback_K≤30 ou ≥70 em 10 barras, rompimento_range5, UTC07–21, SL_range±US$0.10, TP2R]`

`FVG = [largura_gap_ATR, corpo_impulso, EMA50/200_H1, frescor, premium_desconto, OB_confluência, sessão, score≥50, TP1.5R]`

`H4_TURTLE = [rompimento_máxima20, preço>EMA200, SL=2ATR20, TP2R, spread/SL≤.10, risco1%, apenas compra]` (apenas quadro referencial).

`SWEEP = [sweep_anterior_dia, sweep_Asia, sweep_Londres, close_reclaim, swing_HTF_confirmado, VWAP_ancorada, stop_pavio, TP_R_não_divulgado]`.

`EMA_DEMA = [close>EMA50, close>DEMA50, trailing_start200pts, trailing_step100pts, MaxTrades3, MaxSpread50pts, DailyLoss500USD]` (rejeitado).

## Auditoria dos resultados

- Fonte de PF1,50 e 283 negociações: `vrd07/Quant_Trading/reports/backtest_squeeze_breakout_2026-06-27/summary.md`, que marca FAIL em Sharpe, Daily Win Rate e Worst Day.
- Fonte de PF1,22 e 658 operações: `reports/backtest_stoch_pullback_2026-06-27/summary.md`, FAIL em 4 dos 6 gates.
- Auditoria de 2025/2026: `reports/squeeze_breakout_longoos.md`, PF1,15, 2025Q3 PF0,39, trimestre −US$2036.
- Código-fonte do Squeeze usa `sl_points=33.0` **preço do ouro**, não 33 pontos fracionários do MT5.
- FVG usa `CopyBuffer(...,0,0,...)` no EMA H1, sujeito a mudança durante o candle em formação.

## Estado da replicação

Um protótipo independente MQL5 com seleção SQUEEZE/STOCH e presets M15 está disponível no pacote entregue ao usuário no chat, com 9 testes **estáticos** PASS. **Não foi compilado no MetaEditor nem submetido ao Strategy Tester real.** Não é robô aprovado para operação ou promoção a produção. Conta real bloqueada por padrão. Não modificar os EAs já aprovados.

**Regras de aprovação futuras:** dados de 2025+, XAUUSD M1/M5/M15/M30, ticks reais na corretora, 100+ negócios, PF líquido≥1,20, DD≤15%, perda estressada e walk-forward, sem reotimizar após olhar validação.