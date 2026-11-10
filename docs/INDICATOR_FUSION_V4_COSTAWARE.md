# XAUUSD / GC=F — V4: meta ~200 entradas por 30 dias, com custo e lote reais por contrato

**EXCLUSIVAMENTE PESQUISA / PAPER. NÃO HABILITAR ORDENS REAIS.**

## Objetivo
Manter aproximadamente 200 entradas/30 dias em uma única carteira de ouro, sem exigir 6 EMAs ou várias confirmações de tendência, e medir se o resultado líquido paga custos plausíveis. Meta de frequência não é uma ordem para entrar artificialmente.

## Dados e fontes de custo
- Histórico de referência: Yahoo Finance GC=F (futuro contínuo do ouro), candles fechados M5; **não é o bid/ask histórico do XAUUSD spot na FBS**. Proveniência do arquivo registrada com SHA-256.
- FBS publica spread típico de XAUUSD ≈ US$ 0,31 por onça (pode variar): https://fbs.com/trading/specs/xauusd ; condições indicam ausência de comissão de negociação: https://fbs.com/trading/conditions . **Não são custos confirmados de cada operação histórica.**
- Lote mínimo listado para metais: 0,01 lote, contrato 100 onças por lote → 1 onça mínima; posições arredondadas para baixo em passos de 1 onça. Não se criam posições fracionárias abaixo do mínimo.
- Testes independentes de custo all-in: spread típico US$0,31 por onça; spread + slippage de US$0,15 por lado = US$0,61 por onça; spread + US$0,75/lado = US$1,81; spread + US$1,50/lado = US$3,31. Em paralelo, estresses genéricos legados de 7, 14 e 28 pontos-base de nocional.
- Sem comissão específica além do spread publicada para o instrumento; swaps, gaps, rolagem, fill real, variação intradiária do spread, financiamento, requotes e ordens limitadas não estão reproduzidos. Nenhum retorno deve ser considerado resultado líquido real da FBS.

## Execução
- Mantém os cinco sinais experimentais da V3; **sem filtro técnico adicional**. Uma única posição sobre o mesmo ativo por vez, prioridade imutável, candle fechado, entrada na próxima abertura completa.
- Política de holding escolhida **após o diagnóstico retrospectivo da frequência**: stop=3 ATR(10), alvo=3R e duração máxima=36 candles M5 (até 3h); risco-stop planejado de 0,75% do saldo e exposição nocional máxima 1x. Não representam parâmetros fora da amostra.
- Sem operação sobre intervalo ausente, sem lookahead, sem retorno a preço de abertura depois de saída intrabar. Gaps adversos executados na abertura; stop-first somente quando trajetória intrabar é desconhecida.
- Comparar 3 janelas cronológicas; por já terem servido ao diagnóstico, **não são holdout intocado**. Resultados positivos em partes da amostra não liberam dinheiro real.
- Contagem de operações por mês em calendários parciais não autoriza afirmar **200 operações em mês completo**. Usar estimativa explicitamente rotulada de 30 dias, e acompanhar meses futuros inteiros.

## Estado e critérios de promoção
- 39 testes unitários agregados V1–V4 aprovados antes da publicação da branch; o workflow executa 39 testes novamente.
- Só promover após avaliação em dados prospectivos novos do mesmo ativo, simulação da execução real do broker, slippage, spread variável, lote mínimo e regime de notícias, drawdown com P&L aberto, comparando custos normal e estresse.
- Nenhuma fonte compilada EX4/EX5 foi decompilada; nenhum robô anterior substituído, nenhum estado ou ordem real alterado.

## Execução
`python -m unittest tests.test_indicator_fusion_bots tests.test_indicator_fusion_v2 tests.test_indicator_fusion_v3_frequency tests.test_indicator_fusion_v4_costaware -v`

`python -m research.run_indicator_fusion_v4_costaware`

Arquivo auditável de saída: `research/results/indicator_fusion_v4_costaware_latest.json` no artifact GitHub Actions do workflow.