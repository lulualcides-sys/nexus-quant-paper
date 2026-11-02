# Momentum60 H4 — acompanhamento prospectivo virtual (01/11/2026)

## Hipótese e evidência
Backtest revisitado e **não independente**: [comparação H4 de 2026-11-01](../research/results/entry_frequency_h4_2026-11-01.md). O Momentum60 terminou com 28 operações e resultado virtual líquido de US$ 482 versus 18 operações e US$ 297,42 do Momentum100. Com custo dobrado: US$ 454,60 versus US$ 281,76. Porém o novo modelo foi inferior ao Momentum100 no período de treinamento e apresentou drawdown maior na revisão (2,04% contra 1,24%).

**Conclusão:** hipótese exploratória; não é uma estratégia comprovada e não substitui nenhuma das 26 existentes.

## Implementação protegida
- `src/momentum60_shadow.py`: 27º observador **virtual experimental**, com `state/momentum60_shadow_v1.json` separado. Começa da observação atual, sem inventar entradas anteriores, e só cria novas posições simuladas no próximo H4 após sinal do candle fechado.
- Sinal `momentum60_lab` pré-cadastrado no laboratório. Risco-stop planejado 0,75% da banca virtual US$ 5.000, sem alavancagem nocional superior a 1×, stop 2 ATR, alvo 3,5 ATR, saída após até 90 candles. Conservador quando stop e alvo ocorrem no mesmo candle e quando o preço abre além do stop.
- Custos aproximados: 7 bps de ida e volta para GC=F. Não são preços de execução da FBS.
- `src/runner.py`: atualiza o estado experimental durante scans existentes; eventual falha não interrompe os outros robôs, nem reseta estado. Adiciona apenas **uma linha opcional ao resumo diário** existente, nunca alertas por entrada/saída.
- `tests/test_momentum60_shadow.py`: testes offline de bootstrap sem histórico fictício, replay sem duplicidade, sizing/risco, stop de gap, estado incompatível e relatório.
- Nenhuma conexão de carteira, corretora, execução de ordens ou dependência LLM. As bibliotecas Vibe-Trading/AutoHedge seguem como referências, não instalações.

## Portão para decisão futura
Exigir novas negociações simuladas suficientes, comparação cronológica com o Momentum100 na mesma amostra e custos, monitoramento de dados faltantes e drawdown; não promover por uma retrospectiva bem-sucedida. Nem um saldo virtual positivo garante lucro real.
