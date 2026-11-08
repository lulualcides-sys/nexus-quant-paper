# NEXUS QUANT — V5: combater sinais sem vantagem, preservar ganho médio

## Dados reais e hipótese

Auditoria dos livros de operações V4, mercado spot BTCUSDT / ETHUSDT, taxas
e slippage incluídos. Em 2024 (livros virtuais independentes):

| Sinal | Vencedora média saída fixa | Vencedora média trailing |
|---|---:|---:|
| BTC recuo H1 | US$82,44 | US$49,18 |
| ETH recuo H1 | US$85,27 | US$50,12 |

Em 2025 o recuo BTC com saída fixa ganhou 15,8% das 19 operações;
a taxa histórica mínima para empatar segundo seus próprios payoffs era
34,4%. O trailing reduziu o payoff, mas o problema profundo continua
**sinais direcionais fracos, stops e custos**. Mais trades não resolvem.

### Configurações congeladas

Não criar 100 combinações até encontrar alguma verde. V5 contém exatamente
2 famílias H1 com saída fixa (canal 24h e EMA20 recuo), para BTC e ETH,
testadas com dois filtros H4 alternativos e o **controle V4 sem filtro**:

- H4_ALIGNMENT: EMA20 > EMA50 > EMA200, EMA50 crescente nas seis H4
  anteriores, candle H4 fechado e preço de referência acima da EMA50,
  ATR H4/preço de referência >=0,5%, eficiência direcional nos 12
  candles H4 anteriores >=0,16, extensão contra EMA20 <=2,5 ATR.
- H4_DIRECTIONAL: mesma tendência, EMA200 crescente nas últimas 12 H4,
  ATR H4/preço >=0,8%, eficiência direcional >=0,30,
  extensão no máximo 1,8 ATR.

Os filtros são **vetos** sobre a lógica de entrada V4, não sistemas
que se alimentam de seu próprio P&L. H4 é agregação de quatro H1 completas,
H1 de doze M5 completas. Na abertura de uma M5 após o fechamento H1,
a última H4 acessível deve ter fechamento <= horário dessa abertura.
Nunca usar fechamento, máxima ou mínima da M5 ainda em formação.

Preservado da V4: stop de 1%–1,2% ou ATR H1, alvo fixo 2,4R/2,8R,
fill conservador em open M5, gap stop e stop antes de target,
máximo 40% da banca alocada, risco modelado <=0,5% do saldo no stop
incluindo ida/volta de taxas/slippage, máximo uma entrada/dia,
cooldown 12h, limites MTM -2% diário e -10% acumulado.
Nenhuma ordem real, alavancagem ou credencial.

### Desenho de avaliação, sem mascarar sobreajuste

**2024–2025 desenvolvimento e 2026-01–06 avaliação retrospectiva.**
Estes períodos **já foram examinados nas V1–V4**, inclusive os
resultados agregados e a queda de payoff do trailing em 2024.
Portanto NENHUMA janela é um holdout intocado; não declarar APTO
mesmo se a V5 ganhar em uma janela.

Arquivos Binance spot mensais M5 oficiais: checksum SHA256 por ZIP,
integridade de timestamp, OHLCV e continuação dos meses. Intervalos
de 2024-01..2026-06 cobrem 30 meses, divididos em dez trimestres.
O defeito do arquivo BTCUSDT M5 março/2023 identificado em auditoria
anterior não é usado, nem corrigido silenciosamente.

Cenários de estresse permanecem: spot base 0,10% fee/lado +
0,02% slippage/lado, custo dobrado 0,20% + 0,04%, adverso
0,10% + 0,11% (impacto já embutido no desvio). Não assumir BNB desconto
sem evidência.

**Resultados necessários:** winrate observado, winrate mínimo de
equilíbrio no payoff bruto de cada livro, lucro líquido trimestral e
anual, pior cenário de execução, recusa por tipo H4, motivo de saída,
ledger com cada execução/custo/pnl, verificação do saldo. Todos os
12 candidatos (4 controles V4 + 8 gate V5) publicados, nunca apenas
o líder. Comparar reduções de stops contra número de bons sinais vetados,
e nunca confundir soma dos backtests com performance de uma carteira.

Qualquer ano com prejuízo após custos => REPROVADO. Menos de
50 trades/ano em 2024–25 ou 25 no semestre de 2026 => INCONCLUSIVO
caso não haja prejuízo observado. Mesmo resultado positivo nas três
janelas => INCONCLUSIVO até validação **futura** jamais inspecionada.

### Reproduzir

    python -m unittest discover -s tests -p "test_nexus_m1m5_lab.py" -v
    python -m unittest discover -s tests -p "test_nexus_m1m5_v2.py" -v
    python -m unittest discover -s tests -p "test_nexus_m1m5_v3.py" -v
    python -m unittest discover -s tests -p "test_nexus_m1m5_v4.py" -v
    python -m unittest discover -s tests -p "test_nexus_m1m5_v5.py" -v
    python -m research.nexus_m1m5.v5_run --out artifacts/nexus-v5

PR de pesquisa DRAFT. Preservar src/, state/, reports/, ATLAS,
Telegram, agenda futebol 00:00 e robôs 19:30 America/Sao_Paulo.
Publicação ou forward-paper requer evidência nova e autorização.
