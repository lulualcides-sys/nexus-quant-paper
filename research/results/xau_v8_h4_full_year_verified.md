# XAU V8 — ano completo de robôs H4 preservados, BID/ASK spot

**Pesquisa retrospectiva; não são fills da FBS e lucro real não é comprovado.**
Lotes mínimos de uma onça, risco-stop <=0.75%, posição nocional <=1x, sem alavancagem; cada candidato é conta virtual independente.
Sem adaptação de gatilhos/stop/alvo para o histórico. 2025-04 a 2025-09 aquece EMA200 H4. Avaliação 2025-10 a 2026-09.

| Modelo | Banca | Operações 0,15 | Resultado líquido 0,15 | PF 0,15 | Resultado líquido 0,75 | Q4/25 | Q1/26 | Q2/26 | Q3/26 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| channel20 | 5000 | 5 | +288.23 | None | +285.23 | +162.49 | +125.74 | +0.00 | +0.00 |
| channel20 | 10000 | 40 | +844.56 | 1.688 | +817.56 | +151.44 | +421.77 | +33.34 | +316.58 |
| channel20 | 20000 | 50 | +2652.35 | 1.881 | +2585.75 | +312.06 | +1592.16 | +225.41 | +697.09 |
| channel55 | 5000 | 8 | +448.15 | None | +443.35 | +324.96 | +123.20 | +0.00 | +0.00 |
| channel55 | 10000 | 34 | +1025.16 | 2.091 | +1001.16 | +548.28 | +406.60 | -187.39 | +67.14 |
| channel55 | 20000 | 37 | +2982.14 | 2.634 | +2928.14 | +1073.30 | +1314.60 | +162.55 | +326.06 |
| momentum100 | 5000 | 14 | +261.83 | 3.123 | +253.43 | +71.73 | +63.14 | +11.25 | +115.72 |
| momentum100 | 10000 | 33 | +309.68 | 1.29 | +285.68 | +26.35 | +289.93 | -38.37 | +40.10 |
| momentum100 | 20000 | 38 | +513.88 | 1.193 | +537.59 | +42.46 | +203.09 | +280.13 | +65.31 |
| rsi_trend | 5000 | 13 | +201.11 | 2.32 | +193.31 | +48.88 | +100.50 | +90.55 | +0.00 |
| rsi_trend | 10000 | 49 | +1028.14 | 1.717 | +955.83 | +261.71 | +446.68 | +488.01 | -138.05 |
| rsi_trend | 20000 | 57 | +2004.62 | 1.585 | +1723.31 | +807.27 | +576.01 | +593.26 | -236.93 |
| pullback20 | 5000 | 8 | +119.07 | 2.176 | +114.27 | +48.88 | +0.00 | +108.85 | +0.00 |
| pullback20 | 10000 | 32 | +689.40 | 1.68 | +632.09 | +377.82 | -1.28 | +372.53 | +91.32 |
| pullback20 | 20000 | 39 | +1601.35 | 1.656 | +1344.64 | +1030.78 | -72.84 | +871.49 | -196.83 |

**Ponto crítico:** resultados são baseados em histórico já estudado pelo projeto, não em forward. Sem swap/financiamento/FBS requote/impacto.
Não escolher o maior resultado entre capitais como otimização. Os grupos com banca de US$10 mil/20 mil são só teste de execução do lote mínimo; não recomendam aporte.
As janelas trimestrais reinicializam US$5 mil/10 mil/20 mil e não são somadas ao capital contínuo.
Todos os testes usam as mesmas regras de sinais H4 importadas do código existente, não recriações que permitiriam mudar os sinais.
Cenários positivos isolados com menos de 30 trades permanecem inconclusivos; prova de lucro não pode ser declarada.
