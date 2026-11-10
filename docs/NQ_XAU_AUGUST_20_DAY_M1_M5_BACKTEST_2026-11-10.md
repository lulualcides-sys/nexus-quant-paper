# XAUUSD — backtest adicional M1/M5, 20 sessões de agosto de 2026

## Evidências reproduzíveis

- **GitHub Actions:** [run 42792034634](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42792034634), status **SUCCESS**, artefato `xauusd-august-20-session-M1-M5-full-scorecard` (ID 13753295231; expira conforme política do GitHub Actions).
- **Código de comparação:** [research/xau_august_frozen_replication.py](../research/xau_august_frozen_replication.py), [testes](../tests/test_xau_august_frozen_replication.py), [workflow](../.github/workflows/xau-august-20-session-m1-m5.yml).
- **Origem:** Dukascopy XAUUSD spot `bidPrice` e `askPrice` históricos, captados com `dukascopy-node@1.51.1`, 12:00–17:00 UTC em 20 pregões previstos de 03/08 a 28/08/2026; 18 janelas válidas.
- **Integridade:** dias 2026-08-07 (cotação inválida no registro 6.900) e 2026-08-28 (cotação inválida no registro 36.271) foram **quarentenados integralmente** antes de calcular P&L. Nenhum tick individual foi apagado seletivamente para melhorar o resultado. O artefato contém os hashes SHA256 por sessão, contagem de cotações e livro de operações simuladas; não redistribui os ticks brutos.
- **Execução:** regras das seis variantes em [research/xau_frequency_lab.py](../research/xau_frequency_lab.py) **congeladas** antes deste experimento. M1 e M5, mesmo modelo de entrada limite após fechamento do candle, expiração de 3 candles, stop/alvo por quotes bid/ask, saída por tempo, apenas uma posição por vez; sem trades ao vivo.
- **Custos:** resultados abaixo são do cenário *double_friction*, comissão hipotética round-trip US$ 0,60/oz + slippage hipotético US$ 0,20/oz apenas em stop e saída a mercado, além do spread bid/ask registrado. Não são preços contratados de nenhuma corretora; não incluem swap/latência/impacto de mercado. **USD por onça teórica ≠ saldo ou lucro de conta em USD, BRL ou milhares.**
- **Natureza do conjunto:** agosto precede setembro/outubro, quando as estratégias foram desenvolvidas e avaliadas. Portanto a replicação é **histórica e não prospectiva**. Não chamar o período de *future holdout*.

## Resultado integral — nenhuma variante positiva

| Variante | TF | Sinais | Limites preenchidos | Vitórias/Derrotas | Líquido US$/oz | Profit Factor | Primeira metade | Segunda metade |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| referência F50/alvo200 | M1 | 33 | 23 | 9/14 | **−53,365** | 0,400 | −33,940 | −19,425 |
| equilibrado F50/alvo200 | M1 | 70 | 44 | 21/23 | **−44,065** | 0,665 | −11,500 | −32,565 |
| ativo F50/alvo200 | M1 | 109 | 70 | 28/42 | **−149,145** | 0,443 | −52,705 | −96,440 |
| equilibrado F75/alvo200 | M1 | 70 | 53 | 31/22 | **−37,618** | 0,750 | −16,516 | −21,102 |
| ativo F75/alvo250 | M1 | 109 | 80 | 33/47 | **−195,794** | 0,439 | −65,987 | −129,807 |
| equilibrado F75/alvo250 | M1 | 70 | 52 | 25/27 | **−66,066** | 0,641 | −5,691 | −60,375 |
| referência F50/alvo200 | M5 | 2 | 1 | 0/1 | **−20,405** | 0,000 | −20,405 | 0,000 |
| equilibrado F50/alvo200 | M5 | 12 | 8 | 3/5 | **−44,750** | 0,398 | −12,140 | −32,610 |
| ativo F50/alvo200 | M5 | 23 | 17 | 5/12 | **−81,555** | 0,366 | −25,150 | −56,405 |
| equilibrado F75/alvo200 | M5 | 12 | 11 | 6/5 | **−31,208** | 0,637 | −11,937 | −19,271 |
| ativo F75/alvo250 | M5 | 23 | 19 | 6/13 | **−82,100** | 0,423 | −26,534 | −55,566 |
| equilibrado F75/alvo250 | M5 | 12 | 11 | 5/6 | **−46,348** | 0,464 | −19,947 | −26,401 |

**Primeira metade:** 03–14 agosto (nove sessões válidas); **segunda metade:** 17–28 agosto (nove sessões válidas). A separação está fixada por data. Cada variante apresentou P&L líquido **negativo em ambas as metades**, mesmo sem selecionar um vencedor pela amostra.

Contagens de sinais, preenchimentos e lucro são de **cada configuração concorrente**, e **não devem ser somadas entre variantes como se fossem operações independentes de uma única conta**.

## Decisão de pesquisa

**BLOCKED / DRAFT.** Não há evidência de vantagem estatística líquida nas políticas atuais de M1 ou M5 com custos duplos. O modelo M1 equilibrado 75% foi o menos negativo da amostra, mas isso **não autoriza elegê-lo como vencedor**: escolher retrospectivamente pelo menor prejuízo seria sobreajuste.

Próximas barreiras de aceitação: separar previamente qualquer hipótese nova do período visto, obter histórico e execução em feed de corretora MT5 compatível, despesas reais/contrato e período efetivamente futuro com quantidade suficiente de operações. O método não fornece a lógica proprietária da Greenhouse, só uma pesquisa independente de cotações com geometria pública de Fibonacci.

**Status verificado:** GitHub Actions concluído com sucesso; nenhum arquivo de estratégia/robô de produção foi alterado; [PR #60](https://github.com/lulualcides-sys/nexus-quant-paper/pull/60) permanece em rascunho e sem merge.
