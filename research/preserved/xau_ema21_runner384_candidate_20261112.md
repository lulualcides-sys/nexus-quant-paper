# Snapshot verificado — XAUUSD EMA21 M15, Runner 384 (2026-11-12)

**Status: candidato EXPLORATÓRIO; não apto a conta real.** Esta variante foi selecionada entre 16 cenários por janela (direção original/invertida × 3 alvos/runner × 4 limites de permanência). Testar múltiplas alternativas no conjunto de 2025 significa que os períodos de 2025 **não** podem ser alegados como prova nova e incontaminada de vantagem após esta escolha.

## Regras exatas

- Somente XAUUSD M15, sinal fechado EMA21/55 de `points10k.py` congelado, direção ORIGINAL.
- Stop inicial vem da fórmula original: extremidade do candle de sinal / EMA21 menos/mais 0,12 ATR14; entrada na abertura seguinte.
- 1/3 em 1R, 1/3 em 1,5R, o 1/3 restante fica aberto até SL ou 384 candles M15, equivalente a 96 horas **de candles** (tempo cronológico pode incluir fins de semana e lacunas).
- Sem novos ajustes de stop e sem trailing automático. Uma posição por vez; cooldown de uma barra. Stop antes de alvo em ambiguidade intrabar.
- Excluídos os últimos 384 candles de cada janela para comparação controlada dos limites de permanência. Por isso o total de operações não coincide com o snapshot original +41.641 pontos brutos/463 trades.
- Ponto assumido XAUUSD=0,01, custo hipotético US$0,80/onça por trade (80 pontos), sem ticks Bid/Ask, spread dinâmico, corretagem real nem **swap/financiamento overnight**; custo por permanência prolongada pode eliminar o ganho.
- Implementação reproduzível: `robots/mt5/nexus_vector_retest/alpha_xau_longhold.py`.
- GitHub Actions: https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/43213774551 (run concluiu com sucesso, 7 testes sintéticos passaram).

## Resultado, pontos líquidos ESTIMADOS, não dinheiro real

| Janela de 10 mil candles M15 | Intervalo em UTC | Trades | Acerto | Bruto (pts) | Líquido estimado (pts) | PF | Máximo drawdown (pts) |
|---|---|---:|---:|---:|---:|---:|---:|
| 2026 exploratória | 30/03 a 01/09 | 149 | 41,61% | +16.862,2 | +4.942,2 | 1,064 | 20.908,0 |
| 2025 independente — bloco 1 | 06/01 a 09/06 | 119 | 40,34% | +15.079,7 | +5.559,7 | 1,132 | 10.593,1 |
| 2025 independente — bloco 2 | 09/06 a 10/11 | 145 | 47,59% | +28.596,6 | +16.996,6 | 1,421 | 8.431,2 |
| **Soma simples** | três janelas | **413** | — | **+60.538,5** | **+27.498,5** | **não agregado** | **não agregado** |

**Alerta de risco importante:** a primeira janela tem drawdown simulado de **20.908 pontos**, mais de **4 vezes** seu ganho líquido de 4.942 pontos. Não inferir segurança, rentabilidade consistente ou retorno sobre banca.

A inversão simples foi negativa em todas as três janelas e não deve ser considerada melhoria.

## Antes de aprovar
1. Congelar este perfil antes de qualquer novo teste; não otimizar usando os blocos já analisados.
2. Validar em **novo período/novo feed/forward test** não usado na seleção da variante.
3. Acrescentar swap de operações multi-dia, comissão, spread variável, slippage, gaps, Bid/Ask do broker e contrato real de XAUUSD.
4. Reproduzir em MetaTrader 5 ticks reais, verificar volume das parciais, compilação e stops/ordens; só depois conta demo, nunca habilitação automática de real.

**O candidato original EMA21 M15 de +41.641 brutos permanece intacto, bem como o robô VWAP.**
