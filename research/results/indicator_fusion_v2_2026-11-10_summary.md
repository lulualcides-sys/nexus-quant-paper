# Nexus Quant GOLD — V1 versus V2 pareados (2026-11-10)

**Fonte auditável:** [GitHub Actions run #42876232144](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42876232144), job 130040148612; arquivo íntegro em `indicator-fusion-v2-paper` artifact 13792660912. **21 testes unitários aprovados; workflow completo: success.**

**São backtests de pesquisa virtual**, não ordens de corretora e não resultados de FBS. GC=F do Yahoo (~5 dias M1 e ~1 mês M5, agregado integralmente para M15/M30). Capital reinicializado em US$ 5.000 a cada período para cada candidato; retornos não equivalem a capital composto e não podem ser somados numa carteira; cada timeframe utiliza janelas diferentes. Custos ida+volta simulados em bps (0/7/14/28); 14bps não é spread real verificado. Entrada na abertura seguinte, candle fechado, stop antes do alvo se ambiguidade dentro da vela, gap adverso preenchido na abertura. Mesmo motor de risco/saída para V1 e V2; M5/M15/M30 usam a MESMA série M5-base.

**Pré-definido antes da execução:** 5 hipóteses V2 (controle canal55, canal55+impulso, canal55+reteste, BOS+reteste, range+reteste). Critério de triagem retrospectiva: pelo menos 30 trades e 3 segmentos positivos nos dois cenários 14/28bps. **Nenhum candidato passou.** Essas amostras, e suas versões anteriores, já foram examinadas; não são holdout realmente novo. Não otimizar olhando o último segmento e depois chamar o segmento de validação independente.

## Placar completo (US$ virtuais)

### M1

| Modelo | Fechadas | Sem custo | 7 bps | 14 bps | 28 bps | 3 períodos positivos em 14/28? |
|---|---:|---:|---:|---:|---:|---|
| V1_BOS_DTC_QKE | 0 | 0.00 | 0.00 | 0.00 | 0.00 | Não |
| CHANNEL55_IMPULSE | 0 | 0.00 | 0.00 | 0.00 | 0.00 | Não |
| CHANNEL55_RETEST | 2 | 6.58 | -0.42 | -7.42 | -21.42 | Não |
| BOS_LEVEL_RETEST | 2 | 6.58 | -0.42 | -7.42 | -21.42 | Não |
| RANGE_LEVEL_RETEST | 2 | 6.58 | -0.42 | -7.42 | -21.42 | Não |
| V1_RANGE_DTC_QKE | 1 | -12.40 | -15.90 | -19.40 | -26.40 | Não |
| V1_OB_RETEST | 1 | -12.40 | -15.90 | -19.40 | -26.40 | Não |
| V1_SWEEP_REVERSAL | 1 | -12.40 | -15.90 | -19.40 | -26.40 | Não |
| CHANNEL55_CONTROL | 2 | -24.91 | -31.91 | -38.91 | -52.91 | Não |

### M5

| Modelo | Fechadas | Sem custo | 7 bps | 14 bps | 28 bps | 3 períodos positivos em 14/28? |
|---|---:|---:|---:|---:|---:|---|
| RANGE_LEVEL_RETEST | 7 | 97.51 | 72.87 | 48.26 | -0.88 | Não |
| CHANNEL55_IMPULSE | 15 | 132.27 | 79.30 | 26.54 | -78.37 | Não |
| CHANNEL55_RETEST | 12 | 97.86 | 55.51 | 13.29 | -70.76 | Não |
| BOS_LEVEL_RETEST | 8 | 27.39 | -0.68 | -28.71 | -84.64 | Não |
| V1_RANGE_DTC_QKE | 16 | 43.48 | -12.61 | -68.51 | -179.69 | Não |
| V1_BOS_DTC_QKE | 14 | 14.87 | -34.16 | -82.99 | -180.08 | Não |
| CHANNEL55_CONTROL | 20 | 47.07 | -26.60 | -99.83 | -244.99 | Não |
| V1_OB_RETEST | 15 | -53.81 | -106.19 | -158.42 | -262.36 | Não |
| V1_SWEEP_REVERSAL | 22 | -45.68 | -122.29 | -198.54 | -349.98 | Não |

### M15

| Modelo | Fechadas | Sem custo | 7 bps | 14 bps | 28 bps | 3 períodos positivos em 14/28? |
|---|---:|---:|---:|---:|---:|---|
| CHANNEL55_IMPULSE | 16 | 73.55 | 13.72 | -45.92 | -164.57 | Não |
| V1_BOS_DTC_QKE | 18 | 48.07 | -18.29 | -84.37 | -215.74 | Não |
| V1_RANGE_DTC_QKE | 15 | 17.85 | -38.18 | -94.04 | -205.26 | Não |
| CHANNEL55_RETEST | 16 | 9.92 | -49.54 | -108.77 | -226.57 | Não |
| CHANNEL55_CONTROL | 34 | 130.10 | 3.37 | -122.37 | -370.97 | Não |
| V1_OB_RETEST | 14 | -61.71 | -113.93 | -165.96 | -269.40 | Não |
| BOS_LEVEL_RETEST | 11 | -90.29 | -131.90 | -173.39 | -255.99 | Não |
| RANGE_LEVEL_RETEST | 11 | -106.31 | -147.89 | -189.38 | -272.04 | Não |
| V1_SWEEP_REVERSAL | 37 | 14.68 | -121.32 | -256.13 | -522.17 | Não |

### M30

| Modelo | Fechadas | Sem custo | 7 bps | 14 bps | 28 bps | 3 períodos positivos em 14/28? |
|---|---:|---:|---:|---:|---:|---|
| CHANNEL55_IMPULSE | 11 | 89.84 | 51.32 | 12.88 | -63.70 | Não |
| BOS_LEVEL_RETEST | 5 | 16.15 | -1.38 | -18.89 | -53.88 | Não |
| V1_RANGE_DTC_QKE | 13 | 64.14 | 18.64 | -26.75 | -117.20 | Não |
| CHANNEL55_CONTROL | 18 | 101.94 | 35.15 | -31.37 | -163.65 | Não |
| V1_OB_RETEST | 8 | 7.47 | -20.57 | -48.57 | -104.43 | Não |
| CHANNEL55_RETEST | 11 | -4.17 | -42.62 | -81.00 | -157.55 | Não |
| V1_SWEEP_REVERSAL | 19 | 28.50 | -37.94 | -104.10 | -235.61 | Não |
| V1_BOS_DTC_QKE | 14 | -21.65 | -70.48 | -119.19 | -216.22 | Não |
| RANGE_LEVEL_RETEST | 8 | -101.64 | -129.51 | -157.34 | -212.91 | Não |


## Diagnóstico prioritário

- M5 `RANGE_LEVEL_RETEST`: 7 negociações, +US$48.26 em 14bps, -US$0.88 em 28bps; 1ª janela negativa. **Inconclusivo e reprovado para real.**
- M5 `CHANNEL55_IMPULSE`: 15 negociações, +US$26.54 em 14bps, -US$78.37 com custo dobrado; 2ª janela negativa. **Não robusto.**
- M30 `CHANNEL55_IMPULSE`: 11 negociações, +US$12.88 em 14bps, -US$63.70 em 28bps; primeiro e terceiro segmentos negativos. **Não robusto.**
- M15: nenhum V2 positivo com 14 bps. Não insistir no mesmo backtest até gerar resultado positivo — risco alto de sobreajuste.
- M1: amostra ~5 dias, poucos negócios. Resultado zero não prova vantagem ou ausência de risco.
- Arquivos compilados EX4/EX5 não foram decompilados nem sua lógica replicada. Todas as regras V2 são hipóteses próprias baseadas nos indicadores abertos.

**Próximo passo prioritário:** obter spreads bid/ask observados em XAUUSD na corretora, ampliar histórico de candles/ticks da mesma fonte, congelar parâmetros, acompanhar novos dados com walk-forward; só aprovar se positivo líquido fora da amostra sob estresse de custos, sem mudança oportunista de regras. Resultados históricos positivos antigos no arquivo Dukascopy não são comparáveis diretamente a GC=F Yahoo sem recortar o mesmo período e executar regras na mesma base.
