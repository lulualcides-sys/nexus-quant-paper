# ALPHA65 — inventário e contrato de pesquisa

**Objetivo:** desenvolver EA novo de XAUUSD sem alterar VWAP, ATLAS, nem slots positivos.
**Status:** hipótese, não aprovado. Branch independente; nenhum comando de ordem real.

## Componentes auditados
1. **ATLAS** em src/atlas_vector.py: apenas proxy proprietário Tracker; usa sweep/wick/volume e H4, amostras esparsas; não duplicar como sinal independente.
2. **Preserved XAUUSD** research/preserved/xau_all_positive_original_robots_20261110.json: 52 slots de cenários positivos históricos, somente 14 famílias independentes, repetição de aliases H1; 0 robôs M5 originais positivos no snapshot. Nenhuma prova de 159 negociações por mês/65%/PF1,3 OOS.
3. **MS Dynamics & Order Blocks** Pine v6 na Library: pivôs 7 barras DIREITA, alertas sem confirmação final, OB zonas só podem ser confirmadas após BOS; proibido carimbar sinal no candle do pivô retrospectivamente. MPL-2.0: manter licença e atribuição se reutilizar código; aqui só ideias independentes.
4. **Monster Arrows** Pine v5 da Library: ZigZag/pivôs deslocam marcas ao passado; usar somente informação disponível após a confirmação; evitar importar marcadores de backfill para entradas.
5. **QKE MR Ultra Fast, DTC e Auto Range**: estudos de fonte fornecidos em Library; sinais rótulo WIN não equivalem a execução. BC Zones/Wyckoff EX5 compilados não fornecem lógica auditável; não usados como código.
6. **src/strategies.py**: cinco motores causais H1 com backtest anual negativo e proxies futuros GC=F; não chamar de comprovadamente vencedores.
7. **BB20**: snapshot XAUUSD M15 que piorou na validação; indicador isolado não é evidência de edge.
8. **Anterior pesquisa XAU159/65** na branch research/xau159-65-vector-scalper-20261112: 180 configurações negativas e ML 19D reprovado; não repetir esses parâmetros.

## Hipóteses NOVAS, pré-registradas
- SWEEP: varredura da máxima/mínima dos 12 candles ANTERIORES com rejeição (wick), confirmação no fechamento.
- BOS_RETEST: rompimento de estrutura 24 velas ANTERIORES, reteste em 1–7 candles posteriores, confirmação no fechamento.
- EMA_PULLBACK: EMA21/55/200 confirmadas no fechamento, rejeição da EMA21 e candle favorável.
- Composição no mesmo símbolo M1/M5/M15/M30 com prioridade por score e somente 1 posição aberta.

Cada score em [0,1] é vetor heurístico **não calibrado**, jamais probabilidade de 65% de vitória. Nenhum filtro é aprovado sem ablação no treino e OOS.

## Fonte e execução
- 179.662 M1 históricos públicos SHA fixa, 2026-03-26 a 2026-09-25: insuficiente para 12 meses de teste.
- Próxima abertura M1 é o primeiro preenchimento permitido para sinal fechado.
- Stop do candle de sinal e alvo 1,20R, stop-primeiro em caso de ambiguidade, gap para pior.
- Base: spread **variável ESTIMADO**, custo adicional de comissão/slippage hipotéticos (não observado em tick ou broker).
- Conta modelada US$10.000, 0,75% de risco por entrada, lote 0,01/100oz, step 0,01, alavancagem 100× **hipóteses**.
- Treino Apr–May, validação Jun, Jul–Aug reaproveitados de pesquisa prévia **não holdout final virgem**.
- Stress custos duplicados; 400 reamostragens Monte Carlo da sequência dos trades.
- Auditoria proíbe deploy automático. Aprovação real depende de nova janela OOS de pelo menos 12 meses e Strategy Tester MT5 com ticks reais de bid/ask e parâmetros corretos de corretora.

Referência pública de histórico bid-ask: https://www.dukascopy.com/api/data/get/historical-data-export
