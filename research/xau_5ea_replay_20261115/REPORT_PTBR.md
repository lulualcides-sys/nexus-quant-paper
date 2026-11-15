# Backtest exploratório dos cinco robôs Nexus XAUUSD

**Status: simulação Python com OHLC, NÃO Strategy Tester MT5 e NÃO validação para conta real.**

Fonte: 2025 (355.816 candles M1, 01/01/2025–31/12/2025) e 2026 parcial (179.662 candles M1, 26/03/2026–25/09/2026).
Depositado inicialmente: **US$ 10.000 simulados**. Risco aproximado: 0,35% do patrimônio por operação; lote mínimo 0,01 e contrato presumido 100 onças/1 lote.
Custos por operação por onça: **US$ 0,80, 1,20 e 1,60** hipotéticos. Stop primeiro em candles ambíguos.

| Robô | 2025 resultado (US$) | PF 2025 | Trades | 2026 parcial (US$) | PF 2026 | Trades | DD fechado 2025/2026 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Squeeze Breakout | 515.49 | 1.274 | 92 | 73.80 | 1.044 | 76 | 2.71% / 4.6% |
| Stoch Pullback | 239.78 | 1.058 | 219 | 357.41 | 1.193 | 108 | 4.67% / 3.26% |
| FVG Gold | -755.94 | 0.819 | 226 | 32.28 | 1.01 | 182 | 10.3% / 5.87% |
| Gold Breakout H4 | 270.64 | 3.691 | 9 | 0.00 | — | 0 | 0.99% / 0% |
| Sweep & Reclaim | -120.18 | 0.892 | 55 | -60.13 | 0.933 | 46 | 3.01% / 2.86% |

## Estresse de custos, US$ 1,60/onça

| Robô | 2025 US$ | 2026 parcial US$ | PF 2025 / 2026 |
|---|---:|---:|---:|
| Squeeze Breakout | 478.69 | 43.40 | 1.251 / 1.026 |
| Stoch Pullback | -56.32 | 376.43 | 0.984 / 1.214 |
| FVG Gold | -240.91 | 98.40 | 0.904 / 1.04 |
| Gold Breakout H4 | 267.04 | 0.00 | 3.623 / — |
| Sweep & Reclaim | -19.01 | -181.14 | 0.972 / 0.705 |

## Conclusões
- Squeeze M15 teve **+US$515,49 (PF 1,274)** 2025 e **+US$73,80 (PF 1,044)** 2026: PF 2026 excessivamente fraco para aprovação.
- Stoch M15 teve **+US$239,78 (PF 1,058)** 2025 e **+US$357,41 (PF 1,193)** 2026: PF 2025 fraco, e custo US$1,60 reverte 2025 para **−US$56,32**.
- FVG M15: −US$755,94 em 2025 e +US$32,28 em 2026 parcial: não consistente.
- Gold Breakout H4: apenas nove operações em 2025 e zero em 2026; sem amostra aceitável. Maioria dos sinais de 2026 foi rejeitada por risco/lote mínimo.
- Sweep & Reclaim M15: prejuízo nos dois períodos.
- **Nenhum dos cinco passou um critério básico de PF≥1,20 nos dois períodos, 100 negócios/ano, resultados positivos sob custos mais altos.**

## Limitações
- Dados de histórico público XAUUSD agregados em OHLC, NÃO ticks reais nem execução do EA .mq5 na corretora.
- As fórmulas foram espelhadas em Python e podem diferir em ATR/EMA/Estocástico, calendário e offset do servidor, VWAP ou sessões, stop mínimo e spread real.
- Custos hypotéticos sem comissão específica, slippage e swap. Tamanho de lote depende da corretora. Drawdown acima é de operações encerradas.
- Script Python compactado em quatro partes `chunk1..4.b64`; pipeline checou SHA256 do script reconstruído antes do backtest.

[GitHub Actions concluída](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/43667531262) · resultados detalhados e logs de operações estão no artifact da execução.
