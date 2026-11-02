# Nexus Quant — lucro líquido em 3 períodos para 27 robôs

**Pesquisa virtual. Nada foi operado na FBS.** Três janelas cronológicas disjuntas por mercado, bancos reinicializados a cada segmento; nenhum resultado é lucro futuro garantido ou conta real composta.

Os períodos históricos já foram examinados em pesquisas anteriores. **Isto NÃO é out-of-sample independente.**
Custos normais vs custos ×2, regras atuais dos 27 robôs e duas variantes experimentais (H1 filtrado / alavancados 1×).
Notícias NÃO retroaplicadas, pois o calendário não estava disponível nas datas antigas e usar dados posteriores geraria look-ahead.

| Robô | Fech. | P&L original soma | P&L candidato soma | Custo×2 soma | Períodos + | Períodos + custo×2 | Revisão |
|---|---:|---:|---:|---:|---:|---:|---|
| gold_h4:rsi_trend | 10 | -7.69 | -7.69 | -22.20 | 1/3 | 1/3 | rejeitado/amostra insuficiente |
| gold_h4:channel20 | 4 | +121.02 | +121.02 | +115.35 | 2/3 | 2/3 | rejeitado/amostra insuficiente |
| gold_h4:pullback20 | 10 | -78.37 | -78.37 | -93.88 | 1/3 | 1/3 | rejeitado/amostra insuficiente |
| gold_h4:momentum100 | 4 | +50.51 | +50.51 | +43.91 | 1/3 | 1/3 | rejeitado/amostra insuficiente |
| gold_h4:channel55 | 3 | +160.42 | +160.42 | +156.16 | 2/3 | 2/3 | rejeitado/amostra insuficiente |
| leveraged_h4:lev_channel20 | 8 | +24.10 | +17.23 | -24.56 | 2/3 | 1/3 | rejeitado/amostra insuficiente |
| leveraged_h4:lev_momentum100 | 4 | +192.50 | +98.10 | -1.08 | 2/3 | 2/3 | rejeitado/amostra insuficiente |
| leveraged_h4:lev_channel55 | 5 | +296.63 | +152.52 | +117.46 | 2/3 | 2/3 | rejeitado/amostra insuficiente |
| leveraged_h4:lev_momentum40 | 7 | -190.23 | -92.95 | -134.85 | 1/3 | 1/3 | rejeitado/amostra insuficiente |
| leveraged_h4:lev_trend_long | 3 | +88.25 | +48.21 | +27.20 | 1/3 | 1/3 | rejeitado/amostra insuficiente |
| experimental_h1:EURUSD:ema20_retest | 20 | -26.24 | -14.25 | -20.05 | 0/3 | 0/3 | rejeitado/amostra insuficiente |
| experimental_h1:EURUSD:channel10 | 24 | -80.65 | -7.55 | -14.62 | 1/3 | 1/3 | rejeitado/amostra insuficiente |
| experimental_h1:EURUSD:rsi50 | 21 | -55.83 | -12.48 | -18.42 | 1/3 | 0/3 | rejeitado/amostra insuficiente |
| experimental_h1:USDJPY:ema20_retest | 60 | -71.80 | -10.07 | -26.47 | 1/3 | 1/3 | rejeitado/amostra insuficiente |
| experimental_h1:USDJPY:channel10 | 46 | -73.76 | -34.17 | -46.08 | 0/3 | 0/3 | rejeitado/amostra insuficiente |
| experimental_h1:USDJPY:rsi50 | 62 | -63.20 | -28.24 | -44.52 | 1/3 | 1/3 | rejeitado/amostra insuficiente |
| experimental_h1:XAUUSD:ema20_retest | 63 | -36.70 | -26.78 | -44.25 | 1/3 | 0/3 | rejeitado/amostra insuficiente |
| experimental_h1:XAUUSD:channel10 | 50 | -32.99 | -25.06 | -38.27 | 1/3 | 1/3 | rejeitado/amostra insuficiente |
| experimental_h1:XAUUSD:rsi50 | 63 | -56.45 | -54.39 | -71.56 | 0/3 | 0/3 | rejeitado/amostra insuficiente |
| experimental_h1:US500:ema20_retest | 30 | -41.35 | -33.68 | -43.40 | 1/3 | 0/3 | rejeitado/amostra insuficiente |
| experimental_h1:US500:channel10 | 18 | -43.07 | -11.76 | -17.94 | 1/3 | 0/3 | rejeitado/amostra insuficiente |
| experimental_h1:US500:rsi50 | 24 | -36.11 | -23.86 | -31.31 | 0/3 | 0/3 | rejeitado/amostra insuficiente |
| experimental_h1:XTIUSD:ema20_retest | 82 | +22.98 | -15.96 | -33.18 | 1/3 | 0/3 | rejeitado/amostra insuficiente |
| experimental_h1:XTIUSD:channel10 | 58 | -19.47 | +13.84 | +1.53 | 2/3 | 2/3 | rejeitado/amostra insuficiente |
| experimental_h1:XTIUSD:rsi50 | 73 | +2.17 | -15.38 | -30.41 | 0/3 | 0/3 | rejeitado/amostra insuficiente |
| usdcad_m15:bb20 | 26 | -3.10 | -3.10 | -5.85 | 1/3 | 1/3 | rejeitado/amostra insuficiente |
| momentum60_h4:momentum60 | 7 | +36.75 | +36.75 | +25.26 | 1/3 | 1/3 | rejeitado/amostra insuficiente |

## Janelas por mercado (UTC, finais exclusivos)
- XAUUSD_H4: 2026-07-14 a 2026-08-19 (130 candles), 2026-08-19 a 2026-09-25 (130 candles), 2026-09-25 a 2026-10-30 (130 candles)
- USDCAD_M15: 2026-10-06 a 2026-10-14 (576 candles), 2026-10-14 a 2026-10-22 (576 candles), 2026-10-22 a 2026-10-30 (576 candles)
- EURUSD_H1: 2025-10-24 a 2026-02-27 (2086 candles), 2026-02-27 a 2026-07-01 (2086 candles), 2026-07-01 a 2026-10-30 (2086 candles)
- USDJPY_H1: 2025-10-24 a 2026-02-27 (2075 candles), 2026-02-27 a 2026-07-01 (2075 candles), 2026-07-01 a 2026-10-30 (2075 candles)
- XAUUSD_H1: 2026-05-07 a 2026-07-07 (942 candles), 2026-07-07 a 2026-09-02 (942 candles), 2026-09-02 a 2026-11-02 (941 candles)
- US500_H1: 2026-05-07 a 2026-07-08 (940 candles), 2026-07-08 a 2026-09-03 (940 candles), 2026-09-03 a 2026-11-02 (939 candles)
- XTIUSD_H1: 2026-05-07 a 2026-07-07 (942 candles), 2026-07-07 a 2026-09-02 (941 candles), 2026-09-02 a 2026-11-02 (941 candles)

## Principais salvaguardas
- 27 robôs, 3 janelas por robô = 81 linhas auditáveis; nenhum período sobreposto.
- Sinais no candle anterior completo; próxima abertura para entradas; stops conservadores.
- Fonte: Yahoo indicativo GC=F, ES=F, CL=F e FX, não bid/ask executável da FBS.
- Encerramentos já registrados; operações em aberto não incluem marcação a mercado; DD apenas de fechamento.
- Mínimos de revisão: 60 operações H1/M15 e 20 H4, resultado positivo em todos os 3 períodos nos custos normal e ×2, drawdown fechado ≤10%.
- Os critérios acima são triagem histórica, não licença para capital real.
- Se uma estratégia não tem vantagem positiva, é correto ficar sem operar; nunca forçar 27 robôs a lucrar.
- Vários testes/candidatos geram risco de seleção retrospectiva e multiplicidade. Somente observações prospectivas novas podem confirmar vantagem.