# XAU V8 — diagnóstico de incerteza retrospectiva das operações H4

**CUIDADO:** bootstrap pós-hoc por dias com fechamento; não transforma amostra já selecionada em validação prospectiva nem implica probabilidade real de lucro.

| Robô | Custo adicional USD/onça/lado | Fechadas | Vencedoras | Líquido USD | Intervalo reamostrado 95% USD | Fração <=0 nas reamostragens |
|---|---:|---:|---:|---:|---:|---:|
| channel20 | 0.15 | 40 | 19 | +844.56 | -200.50 até +1918.54 | 0.0548 |
| channel20 | 0.75 | 40 | 19 | +817.56 | -226.20 até +1890.05 | 0.0612 |
| channel55 | 0.15 | 34 | 18 | +1025.16 | +45.34 até +1985.34 | 0.0198 |
| channel55 | 0.75 | 34 | 18 | +1001.16 | +20.19 até +1960.74 | 0.0222 |
| momentum100 | 0.15 | 33 | 15 | +309.68 | -555.22 até +1198.36 | 0.2452 |
| momentum100 | 0.75 | 33 | 15 | +285.68 | -578.63 até +1174.09 | 0.2608 |
| rsi_trend | 0.15 | 49 | 25 | +1028.14 | -94.48 até +2186.64 | 0.0362 |
| rsi_trend | 0.75 | 50 | 25 | +955.83 | -130.59 até +2057.24 | 0.044 |
| pullback20 | 0.15 | 32 | 16 | +689.40 | -256.70 até +1663.69 | 0.083 |
| pullback20 | 0.75 | 33 | 16 | +632.09 | -319.01 até +1589.06 | 0.1056 |

- Bancas: US$ 10.000 virtuais, uma posição por robô, risco-stop <=0,75%, spread bid/ask observado e custos por lado simulados.
- P&L reproduz integralmente o JSON do workflow V8; este script não modifica regras nem faz novas operações.
- Datas de fechamento são amostradas independentemente; isso ignora dependência temporal, regimes de volatilidade, múltiplos regimes e seleção retrospectiva entre estratégias e bancas.
- Intervalo que alcança prejuízo é sinal de incerteza; intervalo que exclui zero também não constitui aprovação de capital real.
- Apenas acompanhamento prospectivo e custos/executabilidade no corretor podem fundamentar uma decisão posterior.
