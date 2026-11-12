# ALPHA 65 — resultado verificável (12/11/2026)

**META NÃO ATINGIDA.** Critérios conjuntos: 65% de acerto líquido, pelo menos 159 operações encerradas em CADA mês completo de teste final, Profit Factor >=1,30, lucro líquido após custos, drawdown preferencial <=15%, no repaint, sem grid/martingale.

## Código e fontes
- [AUDIT.md](AUDIT.md): auditoria de ATLAS/Tracker, robôs preservados, estrutura/OB, Monster Arrows, indicadores e lacunas de dados.
- [run.py](run.py): 16 candidatos de três famílias independentes (sweep de liquidez, rompimento com reteste, EMA pullback) testados separadamente em M1/M5/M15/M30 e carteiras.
- [run_extended.py](run_extended.py): mesma lógica em arquivo OHLCV alternativo 2024–2025 para teste de transferência temporal.
- [test_alpha65.py](test_alpha65.py): testes sem ordens reais de não repintar sinais passados quando novas barras chegam, sinal confirmado, entrada posterior, stop-primeiro, uma posição, risco e critérios mensais.

## Replay inicial 2026
Base 179.662 barras XAUUSD M1, SHA256 verificado `a587597bbf88c2d868a00a4e0019cd705cee6ca4f20b0485d6b745f19fcc8225`. Separação treino abril/maio, validação junho e julho/agosto previamente examinados (não holdout virgem).

- **Sweep M5**, maior frequência no treino: 697 trades totais, 311 GREEN, 44,62% acerto, PF 0,538, **−US$ 7.007,20** no capital inicial virtual US$10.000, MDD 70,07%, expectativa −US$10,05/posição. Em abril 209 operações, maio 223, junho 227, julho 19 e agosto 0 porque a simulação parou após drawdown excessivo.
- Diagnóstico por saída: 366 SL, perdas agregadas −US$14.022,10; 2 stops por gap −US$921,87; 296 TP +US$7.987,63; 33 TIME −US$50,87. Os ganhos do TP não cobrem stops+custos.
- Outras estratégias: EMA_PULLBACK M30 PF 0,835 (a melhor relação PF geral na primeira bateria, **ainda negativo**); BOS_RETEST M30 PF 0,698. A soma de sinais múltiplos não corrigiu a expectativa.

## Transferência 2024–2025 — 12 meses de 2025 no arquivo
- Fonte pública alternativa: Git commit `b2cfdc571ffac9eff9f2132ea6946da559d29af2`, hash SHA256 composto `1e8dbce436af98cd06682535ca9ab278375e4a767e55ce6754c5a2c784917a16`, **711.477 candles M1** entre 2024 e 2025. Não é dado real de execução da corretora.
- Treino janeiro–junho 2024; validação julho–dezembro 2024; 12 meses de 2025 para transferência temporal, sem alterar regras durante a execução.
- Selecionado pelo treino: **EMA_PULLBACK M15**. Perdeu ~70% do capital até agosto de 2024 e, pela trava do simulador, **0 trades em 2025**. Zero atividade não prova lucro nem aprovação.
- Alternativas em 2025: EMA_PULLBACK M30, **376 trades no ano**, acerto 44,68%, PF 0,620; BOS_RETEST M30, **304 trades no ano**, acerto 43,75%, PF 0,593. Quantidades ANUAIS, não mensais. Nenhuma chegou aos requisitos.

## Verificação de realismo e limitações
- **Não foi executado Strategy Tester MT5 com ticks reais bid/ask.** Spread variável, slippage, comissão, volume mínimo, contrato, alavancagem e margem foram modelados com premissas explícitas, e não medidos de um broker. A fonte de 2024–2025 não foi auditada contra feed da corretora.
- Simulação com sinal no fechamento e execução na próxima abertura M1, stop-primeiro em vela que atinge alvo e stop, risco planejado de 0,75%, sem martingale/grid.
- A pesquisa original inclui stress de spread estimado e Monte Carlo simplificado; não equivale a robustez de mercado real. Falta validação MT5 do broker e novo período final genuinamente não utilizado.
- Os indicadores e robôs existentes **não foram alterados**; o trabalho está nesta branch isolada, sem merge na main e sem execução real.

## Execuções reprodutíveis
- [Primeira bateria 16 modelos](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/43196646713)
- [Teste ampliado 2024–2025](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/43197683400)
- [Verificações automatizadas](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/43198277370)

**Próxima prioridade técnica:** identificar novas hipóteses predefinidas que atuem na relação entre custo efetivo, stop e payoff, sem ajustar repetidamente o mesmo holdout. Só desenvolver EA de produção quando um teste MT5 real e uma janela OOS legítima sustentarem todas as metas.
