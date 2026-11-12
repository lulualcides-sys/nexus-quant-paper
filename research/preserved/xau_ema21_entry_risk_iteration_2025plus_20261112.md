# XAUUSD EMA21 M15 — avaliação de qualidade de entrada e proteção do runner (2025+)

**Data:** 12/11/2026. **Situação:** pesquisa experimental, nenhum novo robô homologado.

## Escopo e segurança

O usuário autorizou **somente XAUUSD** e testes com candles a partir de **2025-01-01 UTC**. Fonte diária de 2025 (commit fixo `b2cfdc571ffac9eff9f2132ea6946da559d29af2`) e fonte 2026 com SHA256 verificado. Nunca carrega ou baixa 2024 ou anteriores nesta rotina.

Códigos anteriores, sinal EMA21/55 original, snapshot +41.641 pontos brutos e Runner 384 **não foram alterados**. A nova engine `alpha_xau_entry_risk_2025plus.py` reproduz o Runner 384 operação por operação antes de comparar qualquer variante. A estratégia não envia ordens.

## Variantes testadas

1. **RUNNER384_ORIGINAL:** sinal de entrada fixo, 1/3 a 1R, 1/3 a 1,5R, restante a SL ou 384 candles M15.
2. **ENTRY_QUALITY:** requisito de alinhamento EMA21/55 e inclinação da EMA21, risco inicial e range do candle normalizados por ATR. Verificação de sinal com candle fechado; risco do próximo `open` somente quando ordem poderia ser enviada.
3. **BREAKEVEN_AFTER_TP2:** proteção de stop no preço de entrada apenas **no candle seguinte** à execução de TP2.
4. **ENTRY_QUALITY_BE:** combinação de (2) e (3).
5. **REVERSAL_GATED_BE:** após TP2, proteção ao preço de entrada apenas quando dois candles fechados confirmam reversão desfavorável em torno da EMA21. Não estreita stop em tendência sem reversão.

A prioridade do SL em conflitos OHLC é preservada. Gaps preenchem pelo `open` se piores que SL. Uma posição de cada vez, intervalo de uma barra, cauda de 384 candles excluída igualmente de cada janela. Custos assumidos iguais para todos os cenários, US$ 0,8 / 1,2 / 1,6 por onça por round-trip.

## Resultados verificados (pontos líquidos **estimados**, custo = US$0,80/onça)

Cada janela contém 10.000 candles M15. Comparar dentro da mesma janela; variantes podem encerrar posições em horários diferentes, mudando a quantidade de novas entradas.

| Modelo | 2025 bloco 1 | 2025 bloco 2 | 2026 bloco 1 | Interpretação |
|---|---:|---:|---:|---|
| Runner384 original | **+5.559,7 (119)** | **+16.996,6 (145)** | +4.942,2 (149) | Único positivo nos três blocos, já era candidato conhecido |
| ENTRY_QUALITY | −3.258,1 (97) | +19.344,5 (91) | −1.030,6 (125) | Mistura ganhos/perdas |
| BREAKEVEN_AFTER_TP2 | −3.006,2 (172) | +8.517,1 (201) | −3.069,1 (222) | Reprovado |
| ENTRY_QUALITY_BE | +3.067,1 (111) | +3.760,1 (114) | **+12.702,6 (149)** | Melhor em 2026, inferior ao original em ambos blocos 2025 |
| REVERSAL_GATED_BE | −4.450,9 (160) | +9.939,3 (185) | +7.683,7 (197) | Melhor em 2026, mas perde na primeira janela de 2025 |

Números entre parênteses representam operações. As cinco configurações foram comparadas com regras explícitas. A política de promoção exigia superar o original em **todas** as janelas simultaneamente em pontos líquidos e MDD, mantendo mínimo de 80 operações e positivo com custo 1,2. **Nenhuma passou**.

### Risco e custos

- 2026 Runner384: +4.942,2 pts, PF 1,064, MDD 20.908 pts. Com custo 1,2: **−1.017,8 pts**.
- 2026 ENTRY_QUALITY_BE: +12.702,6 pts, PF 1,181, MDD 11.414,6 pts. Com custo 1,2: +6.742,6 pts. Entretanto, 2025-1 e 2025-2 ficam abaixo do Runner384 e **ambas ficam negativas** quando o custo sobe para 1,2.
- 2026 REVERSAL_GATED_BE: +7.683,7 pts, PF 1,081, MDD 20.908 pts. Com custo 1,2: **−196,3 pts**. 2025-1 já é negativo ao custo 0,8.
- O uso de `POINT=0,01` é uma suposição; custos, swap overnight, slippage, taxas e Bid/Ask reais do broker não foram calibrados.
- Drawdown calculado apenas no fechamento dos trades; o risco intratrade pode ser maior.

## Validação de software

CI + replay: https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/43221061662

- 15 testes sintéticos iniciais + 4 novos da reversão, mais testes legados da EMA21, executados na Action.
- A comparação verifica equivalência **trade a trade** entre cópia experimental e `simulate_xau(...,384,runner=True)`. Divergência gera falha.
- Não houve uso de histórico anterior a 2025 nem modificação de bots existentes, conta real, sinais Telegram ou main.

## Decisão e próxima prioridade

**Preservar Runner384 original como candidato histórico, sem aprovação para trading real.** Rejeitar nova substituição automática: o aumento em 2026 não se generalizou para 2025.

Em vez de repetir otimizações no mesmo conjunto de dados, a próxima melhoria confiável é adquirir **preços Bid/Ask e custos reais** da corretora e seguir com **forward test** da configuração congelada. A métrica prioritária é expectativa líquida estável **depois** dos custos e drawdown, não apenas pontos brutos.
