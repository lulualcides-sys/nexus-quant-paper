# XAUUSD — Quinta pesquisa: regimes estatísticos M1, M5, M15 e M30

**Arquivado em 12/11/2026. Resultados de replay histórico OHLC, não de operações reais ou Strategy Tester MT5 com ticks reais.**

## Escopo e parâmetros sem mudanças posteriores aos testes

- Exclusivamente ouro **XAUUSD**, dados a partir de 01/01/2025 UTC; 2025 completo, 2026 parcial Q2/Q3 do feed disponível. Fontes 2025 e 2026 diferentes. Nenhum backtest antes de 2025.
- Só **M1, M5, M15, M30** conforme escopo exigido. Outras periodicidades foram bloqueadas pelo próprio código e testes.
- **ZSCORE80_REENTRY**: preço volta para dentro da banda normalizada de ±1,8 desvios padrão das últimas 80 barras, após fechamento confirmador.
- **VR5_REVERSION**: razão de variância de retornos 5 e 1 passo, estimada em 80 candles, inferior a 0,84; só considera retorno de Z-score a partir de ±1,45.
- **SHOCK_EXHAUSTION**: barra anterior tem range ≥1,8 ATR14 e corpo ≥55% do range, barra atual fecha cruzando midpoint contra o impulso, com corpo ≥22% do range.
- **CHOP14_EXPANSION**: Choppiness Index de 14 períodos sai de ≥58 para menor que 58, fechando além do canal das 14 barras anteriores, corpo ≥25%. O indicador usa máximas/mínimas passadas, sem pivôs futuros.
- **EMA21_BASE**: controle congelado, mantido idêntico às pesquisas anteriores.
- Execução simulada: candle de sinal completo e preenchimento no **open seguinte**, stop antes do alvo quando preço cruza ambos no mesmo candle OHLC, gap desfavorável; TP1=1R (1/3), TP2=1,5R (1/3), resto até stop inicial ou 96 horas de candles. Uma posição por vez.
- Custos *supostos* por round-trip US$0,80, US$1,20 e US$1,60 por onça; ponto de preço assumido 0,01. Não são preços/spreads/comissões de corretora.
- 20 combinações de modelo+timeframe, oito avaliações anual/TF e 24 janelas trimestrais. Os dois anos já foram examinados em muitas outras pesquisas; nenhuma amostra verdadeiramente intocada.

## Triagem congelada: nenhum novo candidato aprovado

Cortes: no mínimo 100 operações em 2025 e 50 em 2026 parcial; lucro líquido nos dois recortes sob custo US$1,20/oz; PF >1,10 em ambos; três trimestres positivos em 2025 e um em 2026. **Resultado: ZERO novas configurações cumprem tudo.**

## Melhor hipótese remanescente: Shock Exhaustion

| Timeframe / ano | Operações | Resultado estimado custo0,8 | PF custo0,8 | DD pontos encerrados | Net custo1,2 | PF custo1,2 | Net custo1,6 |
|---|---:|---:|---:|---:|---:|---:|---:|
| M5 2025 | 190 | 17.994,8 | 1,302 | 10.584,3 | 10.394,8 | 1,163 | 2.794,8 |
| M5 2026 parcial | 101 | 8.295,2 | 1,148 | 18.686,2 | 4.255,2 | 1,073 | 215,2 |
| M15 2025 | 90 | 27.240,8 | 1,505 | 21.373,7 | 23.640,8 | 1,424 | 20.040,8 |
| M15 2026 parcial | 45 | 14.913,5 | 1,374 | 10.915,6 | 13.113,5 | 1,321 | 11.313,5 |
| M30 2025 | 51 | 35.046 | 2,046 | 9.486,7 | 33.006 | 1,959 | 30.966 |
| M30 2026 parcial | 33 | -20.733,3 | 0,549 | 26.412,5 | -22.053,3 | 0,529 | -23.373,3 |

- **M5:** não satisfaz robustez sob custo 1,20: PF 2026 parcial de apenas **1,073**; sob custo 1,60 restam só **+215,2 pontos** em 2026, praticamente zerado.
- **M15:** lucro estimado nos dois recortes até custo 1,60, mas **90 e 45 operações**, abaixo do mínimo de 100 e 50; 2025Q2 e 2026Q3 negativos.
- **M30:** 2025 muito positivo, mas **2026 parcial negativo**, mostrando que um único ano positivo pode ser enganoso.

### Shock Exhaustion por trimestre, custo0,8

| Período | M5 | M15 | M30 |
|---|---:|---:|---:|
| 2025Q1 | -5.593,6 | 2.521,2 | 6.350 |
| 2025Q2 | 1.939,8 | -8.532,3 | 22.021,9 |
| 2025Q3 | 4.358,2 | 5.983,7 | 304,2 |
| 2025Q4 | 17.290,5 | 27.268,2 | 6.370 |
| 2026Q2 | 21.824,3 | 21.734,5 | 809,3 |
| 2026Q3 | -13.529,2 | -6.821 | -21.542,6 |

## Todas as combinações, custo 0,8 e stress custo 1,2

| TF | Estratégia | N2025 | Net2025 custo0,8 | PF2025 | Net2025 custo1,2 | N2026 parcial | Net2026 custo0,8 | PF2026 | Net2026 custo1,2 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| M1 | EMA21_BASE | 2055 | -181.351,3 | 0,370 | -263.551,3 | 630 | -34.015,1 | 0,717 | -59.215,1 |
| M1 | ZSCORE80_REENTRY | 844 | 21.831,2 | 1,153 | -11.928,8 | 552 | -58.199,4 | 0,629 | -80.279,4 |
| M1 | VR5_REVERSION | 868 | -24.635,8 | 0,836 | -59.355,8 | 533 | -46.053,5 | 0,663 | -67.373,5 |
| M1 | SHOCK_EXHAUSTION | 663 | -44.580,4 | 0,685 | -71.100,4 | 287 | -10.881,7 | 0,877 | -22.361,7 |
| M1 | CHOP14_EXPANSION | 1096 | -67.099,9 | 0,596 | -110.939,9 | 522 | -5.937,3 | 0,944 | -26.817,3 |
| M5 | EMA21_BASE | 695 | -45.316,6 | 0,729 | -73.116,6 | 257 | 1.666,6 | 1,018 | -8.613,4 |
| M5 | ZSCORE80_REENTRY | 519 | -66.741,5 | 0,632 | -87.501,5 | 212 | -8.763,5 | 0,932 | -17.243,5 |
| M5 | VR5_REVERSION | 328 | -35.650,5 | 0,653 | -48.770,5 | 211 | -32.997,2 | 0,696 | -41.437,2 |
| M5 | SHOCK_EXHAUSTION | 190 | 17.994,8 | 1,302 | 10.394,8 | 101 | 8.295,2 | 1,148 | 4.255,2 |
| M5 | CHOP14_EXPANSION | 437 | 12.937,2 | 1,126 | -4.542,8 | 252 | -43.864,6 | 0,619 | -53.944,6 |
| M15 | EMA21_BASE | 320 | 14.839,4 | 1,138 | 2.039,4 | 156 | 6.527,2 | 1,082 | 287,2 |
| M15 | ZSCORE80_REENTRY | 222 | 30.223,2 | 1,273 | 21.343,2 | 116 | 1.938,9 | 1,018 | -2.701,1 |
| M15 | VR5_REVERSION | 147 | 9.364,8 | 1,121 | 3.484,8 | 81 | -18.558,1 | 0,761 | -21.798,1 |
| M15 | SHOCK_EXHAUSTION | 90 | 27.240,8 | 1,505 | 23.640,8 | 45 | 14.913,5 | 1,374 | 13.113,5 |
| M15 | CHOP14_EXPANSION | 177 | 23.050 | 1,279 | 15.970 | 128 | -44.599,9 | 0,591 | -49.719,9 |
| M30 | EMA21_BASE | 214 | -9.214,4 | 0,917 | -17.774,4 | 105 | 21.289,6 | 1,290 | 17.089,6 |
| M30 | ZSCORE80_REENTRY | 197 | -59.371,4 | 0,633 | -67.251,4 | 85 | -1.091,5 | 0,990 | -4.491,5 |
| M30 | VR5_REVERSION | 95 | -10.454,1 | 0,856 | -14.254,1 | 40 | 10.017,2 | 1,248 | 8.417,2 |
| M30 | SHOCK_EXHAUSTION | 51 | 35.046 | 2,046 | 33.006 | 33 | -20.733,3 | 0,549 | -22.053,3 |
| M30 | CHOP14_EXPANSION | 122 | -26.407,5 | 0,720 | -31.287,5 | 54 | -23.820,5 | 0,696 | -25.980,5 |

## Limitações, decisão e próximos testes

**Nenhum candidato novo foi incluído na lista dos sete preservados.** O Shock Exhaustion M5 e M15 foram documentados para investigação, não para execução em conta real. Alterar limiares depois de observar estes números para fabricar um vencedor seria sobreajuste.

Melhor uso dos próximos recursos: reproduzir os três candidatos já existentes em timeframes válidos no MT5, com **every tick based on real ticks**, spread Bid/Ask da corretora, comissões, swap e slippage. Congelar código antes de forward demo genuinamente novo e avaliar MDD intratrade, expectativa líquida e PF trimestral. Em seguida só considerar reaplicar o Shock Exhaustion sem adaptação nos dados prospectivos.

Fontes conceituais: [Batten et al., 2017 — microestrutura intradiária de metais preciosos](https://pmc.ncbi.nlm.nih.gov/articles/PMC5407636/); [Gold regime shift (2026)](https://www.mdpi.com/2227-7390/14/20/3708). Estas fontes NÃO provam lucratividade desta estratégia.

### Evidências técnicas
- [GitHub Actions — execução completa com sucesso](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/43252710669)
- [PR draft #79 — código testado, não implantado](https://github.com/lulualcides-sys/nexus-quant-paper/pull/79)
- JSON integral: `research/preserved/xau_statistical_regimes_batch5_2025plus_20261112.json`
- [Escopo obrigatório M1/M5/M15/M30](xau_authoritative_timeframes_m1_m5_m15_m30_20261112.json)
- [Lista preservada de sete ideias](xau_selected_seven_candidates_20261112.json)
