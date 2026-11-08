# ATLAS V6 — nova amostra de 2025, validação limitada

## Razão e disciplina
Revisão prévia: issue #19, PR #23 e PRs #28–#31. O filtro V6 que exclui novos sinais 12:00–15:00 foi escolhido após as perdas de WINM26/WINQ26 de março–junho/2026. Julho parcial/2026 já havia sido inspecionado e foi negativo. Repetir esses meses não é validação independente.

## Nova fonte pública e limites
Repositório do terceiro: https://github.com/wesleyzilva/tradetech , auditoria https://github.com/wesleyzilva/tradetech/blob/main/docs/auditorias/AUDITORIA_DADOS.md . Série Profit pública WINFUT M5 2024–2025, **não** WINV26 nem rastreio de ordens Tracker:
- commit fixado: 0e6f28524cfcda661ad042f1cbacb2948db614f7
- arquivo: dados/candles/2024-2025/WINFUT_F_0_5min.csv
- Git blob SHA1 esperado: bc064fbc3d2b4ab22fe84561e19d46b9b1da6d1d
- pesquisa não republica os CSVs nem usa série ajustada alternativa
- a fonte informa que WINFUT **contém gaps de rolagem** e não identifica vencimento subjacente em cada candle. Logo o arquivo é uma falsificação quantitativa auxiliar, não prova de histórico de contrato único nem de fill real.

## Protocolo congelado
Executar setembro, outubro, novembro e dezembro de 2025 com V1/V3 originais versus V6 V1/V3; sem otimizar limiares ou remover meses ruins. Banca por mês R$30 mil, risco 0,75%, máximo 3 contratos, R$4/contrato/ida-volta e slippage 0/1/2 ticks **por lado**. O candle de sinal precisa fechar antes da colocação da ordem. Medir cobertura, sinais, ordens, operações encerradas, custos líquidos, ambiguidades intrabar, fatores de lucro e drawdown realizado. Fonte é **anterior** a 2026 (backward holdout), não um forward test.

## Critérios e bloqueios
Se fonte mudar, falhar em parse ou tiver dias insuficientes, não substituir candles. Mesmo que alguma coluna mostre resultado positivo, **rejeitar promoção** enquanto vencimentos de WINFUT, book/fills, WINV26 M1 de 13/10/2026 e as setas Tracker pós-fechamento não forem auditáveis. Resultados numéricos vêm do artifact/log do CI, nunca são preenchidos antecipadamente.

Sem alteração do motor ATLAS paper, demais robôs ou parâmetros de risco.
