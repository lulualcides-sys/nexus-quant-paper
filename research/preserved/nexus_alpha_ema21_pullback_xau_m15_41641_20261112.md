# Preservação imutável de referência — NEXUS ALPHA EMA21 PULLBACK (XAUUSD M15)

Registro criado em 2026-11-12 para preservar o candidato identificado na pesquisa original. **Não é uma estratégia aprovada para negociação real**.

## Fonte e regra de sinal
- Símbolo exclusivo da pesquisa: **XAUUSD (ouro)**, período **M15**.
- Implementação de pesquisa original preservada em [points10k.py](../../robots/mt5/nexus_vector_retest/points10k.py), função `events(frame, "EMA21_PULLBACK")` e motor `simulate`, no commit ancestral da branch `research/alpha-points-10k-20261112`.
- EMA 21 e EMA 55, pullback à EMA 21 e recuperação/retomada em candle **fechado**; entrada na abertura do candle seguinte.
- Stop derivado do candle de sinal / EMA e ATR. Três saídas parciais (1R, 1,5R, 2R), 1/3 cada. Stop prevalece em candle com conflito stop/alvo. Máximo 48 candles M15 no replay original.
- Custo **hipotético fixo** de US$0,80/onça round-trip; `POINT=0.01` **suposto**, não calibrado ao broker.

## Resultado original de 10.000 candles (período exploratório, conforme captura do usuário)
| Métrica | Resultado |
|---|---:|
| Operações encerradas | 463 |
| Pontos brutos | +41.641 |
| Pontos líquidos **estimados** | +4.601 |
| Acerto | 41,68% |
| Profit Factor líquido | 1,019 |

**Não transformar +41.641 pontos brutos em lucro líquido nem projetar porcentagem da banca**: custo modelado consumiu aproximadamente 37.040 pontos (463 × 80 pontos). Dados não equivalem a execução com ticks reais/MT5, spreads variáveis ou corretora do usuário.

## Falha na generalização
Ao manter os parâmetros congelados, o modelo teve perdas em **duas janelas independentes de 2025**; portanto, não é robô homologado nem pode ser declarado consistentemente positivo. O replay adicional está em [points10k_2025.py](../../robots/mt5/nexus_vector_retest/points10k_2025.py).

## Continuar pesquisa (sem sobregravar o original)
- Somente XAUUSD; estudar **segurar operações por mais tempo** no M15 (48, 96, 192 e 384 candles), incluindo terceira parcela tipo runner.
- Comparar **direção original** versus **sinais invertidos**, recalculando corretamente o stop no lado da operação e mantendo custos equivalentes.
- Testar em janelas cronológicas independentes; não selecionar melhores parâmetros com base no conjunto reservado para teste.
- Aguardar spread/ticks reais do broker, comissionamento, walk-forward e compilação do EA antes de permitir uso fora da demonstração.
- Permanecer com o VWAP existente intocado. Não alterar bots aprovados, posição automática real nem monitoramento atual.

**Status:** snapshot de PESQUISA salvo; não há prova de que a versão EMA21 tenha produzido esse resultado em conta real, ou que a inversão/holding maior sejam lucrativos.
