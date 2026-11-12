# NEXUS QUANT — V4: novas entradas H1, execução M5, custo auditado

## Diagnóstico a partir do ledger anterior

A V3 gerou, somando contabilidades independentes do cenário BASE na validação
retrospectiva 2026-01..06, 507 operações: 347 saídas por stop (68,4%),
153 no alvo (30,2%) e 7 por tempo/fim. Resultado agregado **-US$4.285,54**
e taxas/desvio estimado **US$4.460,18**. Esses totais não equivalem a uma
carteira real; os candidatos frequentemente apostam nos mesmos momentos.

Tornar o stop mais largo por si só não criou edge. A hipótese V4 modifica o
ponto de ORIGEM da entrada, não apenas a distância de stop.

## Regras congeladas antes do replay

Não são otimizações de parâmetros obtidas pelo P&L. São quatro candidatos
totalmente pré-declarados: duas famílias de sinais H1 e dois métodos de saída.

1. **Canal H1 de 24h**: fechamento H1 acima da máxima das 24 H1 anteriores,
   fechamento anterior não acima da máxima anterior; EMA20 >= EMA50 > EMA200,
   inclinação EMA50 positiva em 12 horas, EMA200 não decrescente em 24h,
   fechamento na porção superior da vela, volume >= 1,10x média 20 horas,
   eficiência direcional >=0,23 e distância limitada da EMA20.
   Stop pelo maior entre 1,4 ATR H1, 1,2% do preço e estrutura técnica
   de 3 H1 (com limite 2,5 ATR de estrutura); alvo 2,8R; máximo 72 horas.
2. **Reentrada H1 na EMA20**: mesmas verificações de regime, candle H1 anterior
   toca proximidade da EMA20; candle fechado recupera EMA20 e rompe máxima
   anterior sem se esticar mais que 0,90 ATR; volume >=0,9x média 20h.
   Stop pelo maior entre 1,2 ATR H1, 1,0% do preço e suporte da estrutura;
   alvo 2,4R; máximo 72 horas.
3. Para ambas, **fixed**: stop/alvo fixos. **trail**: somente quando o fechamento
   M5 atinge +1,2R, próximo M5 terá stop >= preço líquido de equilíbrio,
   seguindo o maior fechamento com faixa de 1,15 ATR H1. Nada usa
   o máximo de um candle ainda aberto para apertar o stop dentro dele.

Em todos os casos: ATR H1 entre 0,4 e 2,8% do fechamento, exclusivamente long
spot BTCUSDT/ETHUSDT. A primeira M5 da hora seguinte à H1 fechada é o
primeiro preço de entrada permitido; não existe fill retroativo ao fechamento.
O stop vale também na M5 da entrada, com **stop antes de target** se ambos
são atingidos. Gap ruim preenche no preço pior, não no stop teórico.

### Gestão financeira preservada

- Saldo inicial: US$ 10.000 por candidato / trimestre / cenário.
- Exposição nominal por ordem: máximo 40% do saldo em spot, sem margem.
- Risco nominal planejado por ordem no stop: <=0,5% do saldo, já incluindo
  entrada/saída, comissão e desvio de execução modelado.
- Máximo uma entrada por dia local; cooldown entre entradas >=12h.
- Bloqueio de novas entradas por queda diária de 2% ou drawdown
  acumulado MTM de 10%; não abre novas operações nesses estados.
- Custo base: 0,10% corretagem por lado + 0,02% desvio cada lado.
  Cenário dobrado: 0,20% fee + 0,04% desvio por lado.
  Adverso: 0,10% fee + 0,11% desvio por lado.
  Desvio é proxy de spread/slippage/impacto e não é cobrado duas vezes.
- P&L verificado transação por transação:
  P&L bruto (referências open/stop/target) - taxas - execução = P&L líquido;
  soma do ledger reconcilia saldo final de cada período.
- Fills de backtest OHLC são simulações, não preços observados na exchange.

### Testes financeiros

Somente **2025-01 até 2026-06**, com fontes Binance spot oficiais zip
e checksum SHA256 mensal. Desenvolvimento 2025: quatro trimestres independentes.
Validação retrospectiva 2026-01..06: dois trimestres independentes.

Esse semestre já foi inspecionado nas V1/V2/V3. **Não é validação intocada.**
O suposto holdout 2026-07..10 também já foi inspecionado e não será usado.
Resultados positivos aqui não podem ser classificados como rentáveis
consistentes nem aprovados para paper-forward automático.

Há comparador 100% buy-and-hold por período e cenário (exposição
diferente, portanto comparação apenas informativa) e caixa sem risco.
Classificação automática: REPROVADO para perda líquida observada na validação
em qualquer cenário, falta de estabilidade ou risco; INCONCLUSIVO para
amostra inadequada, intervalo de confiança que cruza zero ou qualquer
resultado positivo em período anteriormente examinado. Não há estado APTO.

### Execução e auditoria

    python -m unittest discover -s tests -p "test_nexus_m1m5_lab.py" -v
    python -m unittest discover -s tests -p "test_nexus_m1m5_v2.py" -v
    python -m unittest discover -s tests -p "test_nexus_m1m5_v3.py" -v
    python -m unittest discover -s tests -p "test_nexus_m1m5_v4.py" -v
    python -m research.nexus_m1m5.v4_run --out artifacts/nexus-m1m5-v4

Arquivos: v4_system.py, v4_run.py, teste v4 e workflow independente.
O artefato produz results_v4.json, trades_v4.csv e REPORT_V4.md.

**Não modifica os robôs existentes, agendas das 19h30/00h, operações ATLAS,
Telegram, arquivos de estado, APIs privadas, deploy, limites de exposição em
produção, nem instala ordens de corretora.** Candidatos permanecem em PR draft.
