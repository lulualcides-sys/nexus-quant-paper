# Nexus Quant — reparo econômico dos 27 robôs (somente laboratório)

**Nenhuma ordem real e nenhuma estratégia de produção alterada.**

A comparação usa os mesmos candles para o original e candidato, e também refaz o P&L com custos dobrados. H1 testa filtros decididos antes de ler o resultado da nova execução; os dados históricos já foram examinados.

## Políticas testadas

- 15 H1: ATR/preço em bps ≥ 4× custo estimado de ida/volta, além de separação EMA50/EMA200 ≥ 1,5 ATR e alinhamento da tendência.
- 5 H4 alavancados: exposição nominal de 2× para 1× e risco-stop planejado de 1,5% para 0,75%.
- 7 controles: sem modificações (5 H4, Momentum60, USD/CAD M15).

| Robô | Política | Fech. original | Fech. candidato | Original US$ | Novo US$ | Custos×2 US$ | Status |
|---|---|---:|---:|---:|---:|---:|---|
| gold_h4:rsi_trend | unchanged_control | 10 | 10 | -12.13 | -12.13 | -26.87 | insufficient_sample |
| gold_h4:channel20 | unchanged_control | 6 | 6 | +179.76 | +179.76 | +170.54 | insufficient_sample |
| gold_h4:pullback20 | unchanged_control | 11 | 11 | -120.68 | -120.68 | -136.88 | insufficient_sample |
| gold_h4:momentum100 | unchanged_control | 4 | 4 | +48.81 | +48.81 | +42.22 | insufficient_sample |
| gold_h4:channel55 | unchanged_control | 4 | 4 | +228.03 | +228.03 | +222.27 | insufficient_sample |
| leveraged_h4:lev_channel20 | 1x_virtual_leverage_risk_075 | 8 | 8 | +21.16 | +16.51 | -25.44 | insufficient_sample |
| leveraged_h4:lev_momentum100 | 1x_virtual_leverage_risk_075 | 4 | 4 | +188.96 | +97.22 | -1.54 | insufficient_sample |
| leveraged_h4:lev_channel55 | 1x_virtual_leverage_risk_075 | 5 | 5 | +299.46 | +153.34 | +117.62 | insufficient_sample |
| leveraged_h4:lev_momentum40 | 1x_virtual_leverage_risk_075 | 7 | 7 | -191.05 | -93.20 | -134.38 | insufficient_sample |
| leveraged_h4:lev_trend_long | 1x_virtual_leverage_risk_075 | 3 | 3 | +87.44 | +48.03 | +26.87 | insufficient_sample |
| experimental_h1:EURUSD:ema20_retest | h1_cost_coverage_and_trend | 261 | 20 | -26.21 | -14.19 | -19.92 | insufficient_sample |
| experimental_h1:EURUSD:channel10 | h1_cost_coverage_and_trend | 230 | 24 | -78.60 | -7.60 | -14.62 | insufficient_sample |
| experimental_h1:EURUSD:rsi50 | h1_cost_coverage_and_trend | 249 | 21 | -55.15 | -12.48 | -18.36 | insufficient_sample |
| experimental_h1:USDJPY:ema20_retest | h1_cost_coverage_and_trend | 258 | 60 | -70.49 | -10.54 | -26.83 | rejected_no_stress_profit |
| experimental_h1:USDJPY:channel10 | h1_cost_coverage_and_trend | 215 | 46 | -71.57 | -33.87 | -45.48 | rejected_no_stress_profit |
| experimental_h1:USDJPY:rsi50 | h1_cost_coverage_and_trend | 246 | 62 | -62.33 | -28.34 | -44.31 | rejected_no_stress_profit |
| experimental_h1:XAUUSD:ema20_retest | h1_cost_coverage_and_trend | 111 | 63 | -37.21 | -26.82 | -43.87 | rejected_no_stress_profit |
| experimental_h1:XAUUSD:channel10 | h1_cost_coverage_and_trend | 97 | 50 | -32.78 | -25.10 | -38.03 | rejected_no_stress_profit |
| experimental_h1:XAUUSD:rsi50 | h1_cost_coverage_and_trend | 111 | 63 | -56.42 | -53.63 | -70.07 | rejected_no_stress_profit |
| experimental_h1:US500:ema20_retest | h1_cost_coverage_and_trend | 119 | 30 | -42.06 | -33.51 | -42.95 | rejected_no_stress_profit |
| experimental_h1:US500:channel10 | h1_cost_coverage_and_trend | 95 | 18 | -42.50 | -11.74 | -17.89 | insufficient_sample |
| experimental_h1:US500:rsi50 | h1_cost_coverage_and_trend | 106 | 24 | -36.51 | -23.76 | -31.06 | insufficient_sample |
| experimental_h1:XTIUSD:ema20_retest | h1_cost_coverage_and_trend | 129 | 82 | +32.87 | -16.63 | -33.50 | rejected_no_stress_profit |
| experimental_h1:XTIUSD:channel10 | h1_cost_coverage_and_trend | 108 | 58 | -9.98 | +13.61 | +1.17 | forward_test_only |
| experimental_h1:XTIUSD:rsi50 | h1_cost_coverage_and_trend | 119 | 73 | +12.16 | -16.04 | -30.76 | rejected_no_stress_profit |
| usdcad_m15:bb20 | unchanged_control | 27 | 27 | -2.61 | -2.61 | -5.47 | rejected_no_stress_profit |
| momentum60_h4:momentum60 | unchanged_control | 7 | 7 | +33.78 | +33.78 | +22.36 | insufficient_sample |

**Aprovação de dinheiro real: nenhuma.**
Mesmo um candidato historicamente melhor só pode entrar em experimento prospectivo após validação específica, controle de custos reais e sem seleção retrospectiva favorável.