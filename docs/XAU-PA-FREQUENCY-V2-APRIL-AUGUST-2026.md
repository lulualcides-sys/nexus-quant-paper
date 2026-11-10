# XAUUSD Price Action v2 — aumento de frequência e diagnóstico de sobreoperação

**Pesquisa de 10/11/2026. Status: DRAFT, não aprovado para negociação.**

## Motivo da revisão

O sistema anterior de rompimento/reteste de microtendência exigia simultaneamente:
- contexto M5/M15 classificado com limites rigorosos;
- dois pivôs confirmados com inclinação compatível;
- rompimento muito específico e reteste apenas 1 a 4 candles depois;
- stop técnico, R:R líquido e regras de spread.

Mesmo com aquecimento correto do contexto, gerava poucas entradas, especialmente no M5. Isso é problema real de **cobertura de oportunidades**, mas não demonstra que mais sinais são lucrativos.

## Implementação auditável

- [Motor independente](../research/xau_pa_frequency_v2.py), [testes dos setups](../tests/test_xau_pa_frequency_v2.py), [consolidador](../research/xau_pa_frequency_v2_scorecard.py), [testes do consolidador](../tests/test_xau_pa_frequency_v2_scorecard.py).
- [GitHub Actions de execução — sucesso](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42803258837), **3 jobs aprovados**, artefato `xau-pa-frequency-v2-M1-M5-complete-report` mais relatórios individuais por dia com hashes SHA256 e ledger.
- Fonte XAUUSD spot: cotações BID/ASK Dukascopy, via `dukascopy-node@1.51.1`. Usa **09:00–12:00 UTC só para aquecimento** e **12:00–21:00 UTC** para ordens simuladas, idêntica fonte em cada configuração.
- Uma posição por vez, entrada a mercado no primeiro quote após fechamento do candle, filtro de spread, stop técnico limitado por ATR, stop com gaps, alvo 2R, saída por tempo e no último tick; sem preços futuros antecipados.
- Parâmetros pré-declarados e **não otimizados após ver abril/agosto**. Quatro hipóteses: `baseline` (inalterada); `structural` (rompimento/reteste de nível horizontal de 12 candles com candle de rejeição); `pullback` (EMA9/EMA21, toque e fechamento de recuperação); `combined` (união dos dois últimos, prioridade estrutural e intervalo mínimo de três candles entre sinais).
- Custos: cenário comum e cenário DOBRADO com comissão hipotética **US$0,60/oz por roundtrip** mais slippage adverso de **US$0,20/oz em cada ordem a mercado/stop**, ambos com spread BID/ASK observado. **Não** são tarifas verificadas de broker.
- Todos os valores representam **US$ por uma única onça teórica**, não lote/conta MT5, mil dólares ou capital do usuário. Sem swap, comissões reais, fila de execução, latência e rejeição de corretora.
- Teste fechado: abril 06–17 e agosto 03–14/2026, 10 pregões pré-selecionados por mês; **9 válidos em cada**. Excluídas integralmente **07/04/2026** (cotação inválida na linha 141.297) e **07/08/2026** (linha 35.282), independentemente de P&L. Abril/agosto são amostras históricas e agosto já foi consultado em outras pesquisas. **Não é forward/OOS prospectivo**.

## Resultado por janela — custos dobrados

| TF | Estratégia | Abril: sinais / fills | Abril líquido US$/oz | Agosto: sinais / fills | Agosto líquido US$/oz | Total fills | Total líquido |
|---|---|---|---:|---|---:|---:|---:|
| M1 | Controle original | 24 / 18 | −20,130 | 13 / 8 | −17,880 | 26 | **−38,010** |
| M1 | Reteste horizontal | 363 / 174 | −312,212 | 433 / 197 | −284,250 | 371 | **−596,462** |
| M1 | Pullback EMA | 276 / 163 | −339,376 | 265 / 168 | −227,440 | 331 | **−566,816** |
| M1 | Combinado | 439 / 252 | −523,225 | 480 / 284 | −441,192 | 536 | **−964,417** |
| M5 | Controle original | 5 / 4 | −8,707 | 0 / 0 | 0,000 | 4 | **−8,707** |
| M5 | Reteste horizontal | 73 / 40 | −41,605 | 68 / 35 | −36,352 | 75 | **−77,957** |
| M5 | Pullback EMA | 83 / 40 | +22,214 | 53 / 36 | −135,916 | 76 | **−113,702** |
| M5 | Combinado | 104 / 60 | −99,394 | 90 / 63 | −145,018 | 123 | **−244,412** |

### Diagnóstico

- **Frequência:** o M1 combinado executou **536 operações em 18 datas válidas**, aproximadamente 30 por sessão; o M5 combinado executou **123**, aproximadamente sete por sessão. Logo, a limitação de entradas pode ser superada sem inventar preço nem operações.
- **Qualidade:** o M1 combinado teve **123 vencedoras e 413 perdedoras**, taxa de acerto ~22,9%, muito baixa para compensar stops, spread e comissão. M1 reteste horizontal: 94 vitórias em 371 operações; EMA pullback: 73 em 331. M5 combinado: 31 vitórias em 123.
- **Falsos sinais/overtrading:** M1 combinado gerou 919 sinais antes de veto, mas 383 não viraram operações, incluindo posições já abertas e filtros econômicos. É incorreto considerar cada seta uma oportunidade executada.
- **Consistência:** todos os novos braços M1 registraram prejuízo **em ambos os meses**. M5 pullback ganhou em abril com 40 operações, mas perdeu mais em agosto com 36. Não houve evidência de vantagem estável, e a seleção do resultado isolado de abril seria sobreajuste.
- **Correção anterior mantida:** o histórico de pré-abertura para EMA e pivôs foi usado exclusivamente como contexto, e nenhum trade é contado antes de 12:00 UTC.

## Decisão e próxima hipótese científica

**REPROVADO PARA OPERAR.** Nenhum braço ganha direito a ser ativado no MT5. O avanço real foi descobrir que a frequência baixa era consequência da lógica excessivamente seletiva, enquanto maior frequência **agrava a expectativa negativa**.

O próximo teste de qualidade deve partir de uma hipótese estrutural nova e *pré-congelada*, em datas não observadas por esse novo modelo, registrando motivo de descarte de cada entrada e custos de uma corretora real. Não otimizar os 18 pregões e depois anunciar lucro como OOS. É recomendável também evitar múltiplas entradas correlacionadas no mesmo nível e condicionar a direção ao regime de tendência sem voltar a zerar a frequência.

**PR #61** isolada da `main`. Os robôs WIN, ATLAS e Tracker não foram modificados. Não há ordens enviadas.
