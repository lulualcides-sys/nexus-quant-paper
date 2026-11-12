# Nexus Quant | Indicator Fusion GOLD — V2 de investigação causal

Status: **experimental, paper-only, NÃO aprovado para negociação real**.

Motivação: backtests auditados na PR #68 mostraram que algumas entradas tinham resultado bruto pequeno ou positivo, mas custos estimados de 14bps transformavam os resultados em prejuízo; outras regras eram negativas mesmo sem custos. Implementar mais filtros sem comparação controlada poderia gerar sobreajuste.

## Código e método

- `research/indicator_fusion_v2.py`: cinco sinais novos e motor de comparação pareada.
- `research/run_indicator_fusion_v2.py`: executa no **mesmo** histórico de GC=F os quatro sinais originais V1 e os cinco sinais V2.
- `tests/test_indicator_fusion_v2.py`: causalidade, confirmação de reteste somente após rompimento, comparabilidade do motor e segurança de histórico.
- `CHANNEL55_CONTROL`: cruzamento confirmado do canal de 55 períodos, sem filtros; não é cópia exata de uma carteira/posição do robô Channel55 anterior.
- `CHANNEL55_IMPULSE`: canal55 + EMA50/200 + direção do impulso QKE e Z-score.
- `CHANNEL55_RETEST`: depois do rompimento do canal55, espera até 12 candles por toque e rejeição do nível anterior.
- `BOS_LEVEL_RETEST`: exige BOS confirmado antes de construir expectativa de reteste de nível, até 12 candles.
- `RANGE_LEVEL_RETEST`: rompimento de range comprimido de 20 candles, depois toque e rejeição, até 10 candles.

Os retestes exigem candle fechado, resposta coerente com a direção da tendência e limite de validade do nível. Não existe ordem na vela do sinal; entradas somente na abertura da próxima vela íntegra. A V2 **não altera** o código V1; importa as mesmas regras de simulação: risco de até 0,75% do patrimônio por stop, nocional <=1x, stop fixo 1,5 ATR(10), alvo fixo 1,8R, 48 candles limite. A avaliação usa os mesmos candles e três períodos cronológicos com custos 0, 7, 14 e 28 bps. Os custos de 14/28 bps são hipóteses, não spread/execução verificada da corretora. Stops podem exceder risco planejado por gaps.

Critério de triagem (não é autorização de capital real): >=30 fechamentos e os três períodos com resultado marcado positivo tanto com 14 quanto 28 bps, drawdown realizado <=10%. Mesmo se atender, verificar histórico prospectivo independente de novas datas, dados bid/ask e fills de corretora.

Riscos: (a) histórico Yahoo de apenas ~5 dias em M1, ~1 mês em M5, M15, M30; (b) GC=F é proxy de futuro, não XAUUSD spot negociado; (c) a amostra já foi estudada nas versões anteriores, portanto nenhuma melhora é prova de performance fora de amostra; (d) diferentes operações podem se sobrepor entre estratégias, logo retornos não podem ser somados diretamente; (e) fontes EX4/EX5 compiladas NÃO tiveram fórmulas extraídas.

Nenhum workflow de negociação, estado de carteira, credencial, notificação ou strategy engine original é modificado.