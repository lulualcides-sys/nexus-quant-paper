# Entrada BB20 — comparação controlada, sem troca automática do robô

Mesmo histórico e mesmo risco/saída. Mudança apenas nos critérios de entrada.
Treino: 15 dias iniciais; validação retrospectiva: 15 dias finais.

| Filtro de entrada | 30d operações | 30d acerto | 30d P&L US$ | Treino P&L US$ | Validação operações | Validação acerto | Validação P&L US$ |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | 34 | 35.29% | +0.38 | -4.10 | 16 | 50.0% | +4.50 |
| touch | 14 | 28.57% | -6.37 | -4.34 | 7 | 42.86% | -2.04 |
| touch_slope | 11 | 18.18% | -7.19 | -4.50 | 5 | 40.0% | -2.70 |
| touch_wick | 9 | 33.33% | -1.13 | -0.29 | 2 | 50.0% | -0.83 |
| touch_wick_slope | 7 | 14.29% | -3.97 | -3.14 | 2 | 50.0% | -0.83 |
| touch_ema | 12 | 33.33% | -2.03 | -0.29 | 5 | 40.0% | -1.74 |
| touch_ema_wick | 9 | 33.33% | -1.13 | -0.29 | 2 | 50.0% | -0.83 |
| near_slope | 13 | 23.08% | -7.60 | -5.98 | 6 | 50.0% | -1.64 |
| near_ema | 14 | 35.71% | -1.62 | -0.95 | 6 | 50.0% | -0.67 |

**Validação não é prospectiva. Uma taxa de acerto alta com 1–3 trades não é prova de superioridade.**
