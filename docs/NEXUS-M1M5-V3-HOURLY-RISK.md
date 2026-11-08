# NEXUS M1/M5 — V3: corrigindo a escala do stop e contexto do sinal

## Evidência do histórico V2 (não inferência)

O livro de operações V2 contém 10.175 lançamentos em todos cenários e trimestres.
No cenário base, 4.461 operações de desenvolvimento (2025), sendo 3.567 stops
e 843 targets; e 2.241 de validação retrospectiva (1º semestre/2026), com
1.783 stops e 426 targets. Win rate base: 19,9% em ambos.

Somatório fictício **de contas independentes**, não P&L de carteira:
primeiro semestre/2026, P&L bruto ~+213,9 USD contra comissão
~32.608 USD e execução estimada ~6.522 USD: resultado líquido
~-38.916 USD. A contagem total de taxas agrega diferentes hipóteses que
operam o mesmo candle, sem netting. Não representar esse agregado como
perda real da conta.

A V2 mostrou que elevar o alvo para 4R com stops muito próximos da cotação
não resgata edge. Frequência de stop próxima de 80% e taxas incidem mesmo
nas perdas. Classificar isso como simples problema de take profit seria falso.

## Hipóteses V3 congeladas

Apenas os **mesmos três tipos de entrada já existentes** (Sweep M1,
Trend M5, Breakout reteste M5), selecionados pelo diagnóstico V2. As
estratégias VWAP/Flow/Squeeze e a versão V2 continuam intactas.

- 1H derivada exclusivamente de **12 candles M5 completos, consecutivos**
  e alinhados. O signal bar de M1/M5 usa somente a última H1 cujo horário
  de fechamento seja <= fechamento do signal bar; não usa uma H1 em formação.
- Regime direcional: EMA20 >= EMA50 > EMA200 na H1, EMA50 crescente nas
  últimas 12 H1, fechamento H1 e fechamento do gatilho acima da EMA50.
  Sem perseguir preço excessivamente esticado contra EMA20 H1; ATR mínimo
  exclui volatilidade ínfima onde os custos consomem o movimento.
- Hipótese A (core): stop = máximo entre stop técnico da V1,
  0,60% do preço e 0,8 ATR de uma H1 fechada. Alvo 2R e 24h máximo.
- Hipótese B (strict): stop = máximo entre stop técnico da V1,
  0,90% e 1,2 ATR H1. Alvo 2,3R e 48h máximo. Exige EMA200 também
  crescente nas últimas 24 H1 e volatilidade H1 mais alta.
- Próxima barra como referência de execução. Sem mudar risco máximo de
  0,25% M1 ou 0,50% M5, capital $10.000 por simulação isolada,
  taxa spot base 0,10% por lado, cenários dobrado/adverso, stop antes do alvo
  em ambiguidade, gap adverso, trava -2% diário e -10% de drawdown MTM.
  Sem alavancagem, venda short, dados sintéticos ou rotinas de trading real.
- Aumento do stop muda a exposição temporal e pode piorar a perda de
  oportunidade. **Não afirmar que a mudança aumenta chance de lucrar.**

## Janelas e decisão

V3 usa desenvolvimento 2025-01..12 e validação **retrospectiva já vista**
2026-01..06; quatro e dois trimestres, respectivamente. Período 2026-07..10
*já examinado na V1* fica fora de todas as comparações.

Cada candidato tem resultado separado por trimestre e por cenário,
ledger CSV de entradas/saídas/taxas, SHA256 das fontes, ranking pelo
**pior custo líquido**. A mesma configuração de sinal se aplica em todos
os cenários para evitar artificialmente reduzir operações quando taxas mudam.

Candidatos com perda líquida observada na validação são REPROVADOS;
com pouco volume e sem perda observada são INCONCLUSIVOS. Histórico
positivo só seria **INCONCLUSIVO**, até nova amostra independente e
avaliação posterior fora da amostra. Não existe promoção automática.

## Rodar

    python -m unittest discover -s tests -p "test_nexus_m1m5_lab.py" -v
    python -m unittest discover -s tests -p "test_nexus_m1m5_v2.py" -v
    python -m unittest discover -s tests -p "test_nexus_m1m5_v3.py" -v
    python -m research.nexus_m1m5.v3_run --out artifacts/nexus-m1m5-v3

Saídas: results_v3.json, trades_v3.csv e REPORT_V3.md no artefato do CI.
Os arquivos de src/, state/, reports/ e workflows de fechamento já
existentes não são alterados. Zero ordens, Telegram ou conexão com corretora.
