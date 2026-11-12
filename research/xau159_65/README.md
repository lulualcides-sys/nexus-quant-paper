# Nexus Gold — meta 65% GREEN / 159 operações mensais
**Data:** 2026-11-12
**Status:** REPROVADO COMO ESTRATÉGIA; pesquisa preservada, NÃO integrar à execução real ou paper atual.

## Critério de aprovação (todas as condições no MESMO mês)
1. Pelo menos 159 posições encerradas e contabilizadas.
2. No mínimo 65% das posições com P&L líquido positivo.
3. Profit Factor superior a 1 e resultado líquido positivo.
4. Repetição consistente em meses fora da amostra e validação com custos/ticks MT5 do broker. Não usar "melhor mês" nem médias para esconder mês ruim.

## Pesquisa realizada
- Fonte XAUUSD M1: 179.662 OHLCV, março a setembro de 2026, hash SHA256 `a587597bbf88c2d868a00a4e0019cd705cee6ca4f20b0485d6b745f19fcc8225`.
- Modelo de custo: US$0,60/onça por round trip (hipotético). Stop antes do TP caso ambos sejam tocados na mesma vela. Entrada na abertura depois da confirmação.
- [screen.py](screen.py): 36 combinações iniciais, seguidas por 144 combinações com sessão/score/TP/SL. **0 de 180 combinações aprovadas.** A estratégia mais frequente gerou 2.903–3.074 operações/mês mas apenas 61,28%–63,31% de acerto, PF 0,435–0,490 no treino. OOS julho/agosto também negativo.
- [ml_screen.py](ml_screen.py): vetor matemático supervisionado com 19 características; treino abril–maio, limiar junho, OOS julho/agosto não usado na seleção. Junho 230 operações, 52,17%, PF 0,669; julho 285, 45,26%, PF 0,495; agosto 313, 52,08%, PF 0,624. **Reprovado.**
- [Teste clássico Actions](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/43193695880) e [Teste ML Actions](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/43194292289); artefatos JSON e relatórios com métricas verificáveis.

## Próxima decisão técnica
Não forçar resultados com TP minúsculo e stop enorme: acerto isolado não implica lucro. Para prosseguir, formular uma NOVA hipótese independente e usar novo período de validação, depois compilar/backtestar EA em MT5 com bid/ask de ticks e spread variável. **Nenhuma versão do EA atende atualmente à meta comprovadamente.** VWAP existente e robôs de produção permanecem intactos.

**Limitação:** métodos Python com OHLC, não Strategy Tester MT5; sem slippage dinâmico, swap, comissões, limites de margem ou detalhes de execução real.
