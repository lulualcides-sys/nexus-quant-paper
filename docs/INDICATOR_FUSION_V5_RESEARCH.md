# Nexus Quant — GOLD V5: saídas causais, 200 entradas/30 dias sem filtros adicionais

**Status: pesquisa isolada; NÃO ativada na corretora, NÃO fundida à main.**

## Problema corrigido

A V4 tinha resultado positivo nos candles Yahoo GC=F M5 com custo teórico de US$0,61/onça, mas não possuía confirmação entre fontes independentes de cotações. A biblioteca já tinha um artefato Dukascopy XAUUSD com 24 sessões de bid/ask (MID OHLC) de 05/10 a 05/11/2026. Esses arquivos cobrem só parte do dia (12:00–20:55 UTC de forma comum). Não é válido projetar automaticamente o desempenho de 24h a partir de uma fonte de 9h/dia. O dia 06/11 foi anteriormente colocado em quarentena e permanece excluído.

## Implementação

- Três políticas explicitadas e comparadas, sem adicionar filtros de sinais: `fixed_v4` (mesma saída da V4), `breakeven_1p5R` (stop acima do preço de entrada após fechar +1,5R), `close_trail_2R` (trail de 1,25 ATR/10 após fechamento +2R). Stops só são atualizados **após a vela fechar**, válidos para a vela seguinte. Sem movimentar stop retroativamente e sem reaproveitar a abertura após saída intrabar.
- Sinais mantidos da V3 e ablação sem `MOMENTUM_2BAR` feita na V4. Esta ablação foi escolhida **após ver lucros e perdas** e não se torna validada com novos testes no mesmo histórico.
- Risco-stop planejado <=0,75%, exposição nocional <=1x, contratos de pelo menos 1 onça em passos de 1 onça, stop inicial 3 ATR(10), alvo 3R, limite 36 velas. Mantém carteira única com uma posição por vez no ouro.
- Entrada no próximo candle M5 observado após sinal fechado. Abertura por gap é analisada antes dos toques intrabar; stop antes de alvo quando a mesma vela tem ambos os toques e a trajetória é desconhecida. Contabilizar marcação a mercado de posições finais, porém drawdown divulgado apenas das posições fechadas.
- Paridade obrigatória da V5 com V4 fixa no arquivo **real** Yahoo congelado (todas as entradas/saídas idênticas), além de testes unitários sintéticos.

## Fonte e custos

- Yahoo GC=F futuro contínuo é proxy, não spot XAUUSD FBS. Source: ZIP/artifact `indicator-fusion-v3-frequency-paper` da GitHub Actions run **42879014930**, contém `xau_gc_f_observed_m5_20261110.json.gz`, SHA256 `e108c0b2aea67a913148c1922fe7568f7e464c5720360e1006547caf874fa79f`.
- Dukascopy XAUUSD OHLC MID agregado a partir de ticks bid/ask, dias de 05/10 a 05/11, 24 sessões válidas, 06/11 em quarentena. Arquivo `xau-candles/*.json` no artefato `XAU-all-original-27-plus-ATLAS-M1-M5-M15-84-scorecards` da GitHub Actions run **42847239203**. Checksum de arquivos de dias válidos (bytes com nome e delimitador): `0fd2f4111bae5b71410deaa8e623f84f35a35f6d1ca4964950c45c6e65a95b2a`.
- Três coortes: Yahoo completo (~30 dias), Dukascopy 12:00–20:55 UTC (24 sessões) e duas coortes **mesmos timestamps** em Yahoo e Dukascopy (19 sessões, 2050 candles). Uma única posição e fechamento obrigatório às 20:55 nas coortes parciais; não executar posição na parte do dia sem observações.
- Cenários hipotéticos de custo completo US$0,61, US$1,81 e US$3,31 por onça; estresse adicional 14bps. Para Dukascopy, cenário conservador calculado como média dos **spreads máximos dos candles** de entrada/saída + slippage US$0,15 por lado. Este último usa o spread máximo de cada candle apenas como **diagnóstico retrospectivo de custo**, e **não é spread realmente executado no momento da ordem**. Nenhum cenário equivale aos spreads/slippage históricos da conta FBS.
- Sem custos reais de swap, comissão da conta, gaps entre ticks e execução real. Não somar as contas virtuais, não considerar saldos de diferentes fontes como carteira conjunta.

## Critério de avaliação

No Yahoo full-session, manter ~200 trades/30 dias como meta de frequência, nunca cotas artificiais. Nas coortes parciais, a frequência é menor por limitação dos horários observados, portanto **não comprova nem refuta** 200 entradas em 24h. Exigir consistência por 3 períodos cronológicos e por custo normal/estresse, amostra suficiente, e depois dados **novos e ainda não vistos** para confirmar.

O histórico foi analisado diversas vezes no Nexus Quant: **qualquer seleção de política a partir destes resultados sofre risco de sobreajuste**. Os testes históricos de outra fonte são verificação de sensibilidade, não forward test verdadeiramente novo. Nenhum candidato é aprovado automaticamente para dinheiro real, mesmo com P&L histórico positivo.

## Reprodução

```bash
python -m unittest tests.test_indicator_fusion_bots tests.test_indicator_fusion_v2 tests.test_indicator_fusion_v3_frequency tests.test_indicator_fusion_v4_costaware tests.test_indicator_fusion_v5_exits -v
python -m research.run_indicator_fusion_v5_exits \
  --yahoo-gzip /caminho/xau_gc_f_observed_m5_20261110.json.gz \
  --dukascopy-dir /caminho/artefato_dukascopy_extraido
```

A workflow independente `.github/workflows/indicator-fusion-v5.yml` descarrega somente os artefatos congelados, verifica hashes e publica JSON e Markdown. **Não existe envio de ordens ou modificação de `state/`.**