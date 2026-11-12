# XAUUSD M15 — auditoria da extensão de operações condicionada à tendência
**Data:** 2026-11-12  
**Situação:** PESQUISA CONCLUÍDA NESTA ITERAÇÃO — nova gestão REJEITADA; **nenhuma operação real liberada**.

## Solicitação
Manter posições mais tempo apenas enquanto houver microtendência em formação ou tendência forte. Operar exclusivamente XAUUSD (ouro). Preservar EMA21 Pullback e o snapshot bruto original de 41.641 pontos, bem como o candidato fixo Runner384.

## Experimentos implementados em Python (não MetaTrader)
- Entradas do `points10k.py` permanecem congeladas: sinal confirmado ao fechamento, abertura do candle seguinte, EMA21/EMA55, XAUUSD M15.
- `FIXED_RUNNER_384` (controle preservado): parcial 1/3 em 1R, parcial 1/3 em 1,5R, 1/3 até SL original ou 384 barras M15.
- `ADAPTIVE_TREND_REJECTED`: testa fechamento por perda de tendência, trailing EMA21/ATR e TP3 convencional na ausência de tendência. Reprovado por elevar número de entradas, custos e drawdown.
- `CONDITIONAL_RUNNER`: sem trailing e sem TP3, preserva SL original e parciais do Runner384. Após 48 barras M15, estende somente se a última barra **fechada** indicar microtendência ou tendência forte na direção da posição; encerra no próximo open caso contrário; máximo 384 barras. A lógica não usa candles futuros.
- A versão nova não é EA compilado, não interage com conta real e não altera arquivos de robôs anteriores.

## Replay histórico — pontos LÍQUIDOS ESTIMADOS
Cada linha é uma janela de 10.000 candles M15. Mesma população de sinais elegíveis por janela; número de negócios executados pode mudar porque as posições ficam abertas por tempos diferentes.

| Histórico (UTC) | Runner fixo 384 | Runner condicional | Resultado |
|---|---:|---:|---|
| 2026 (explorado anteriormente) | +4.942,2 (149 operações, PF 1,064) | +5.087,8 (333 operações, PF 1,031) | Ambos levemente positivos |
| 2025, janela 1 (explorada anteriormente) | +5.559,7 (119, PF 1,132) | **−13.799,7** (306, PF 0,866) | Condicional pior |
| 2025, janela 2 (explorada anteriormente) | +16.996,6 (145, PF 1,421) | **−9.368,1** (335, PF 0,916) | Condicional pior |
| 2024, janela 1 (inspecionada na iteração anterior) | −15.511,4 (161, PF 0,591) | **−24.714,8** (345, PF 0,650) | Ambas negativas |
| 2024, janela 2 (inspecionada na iteração anterior) | −13.267,5 (160, PF 0,655) | **−16.522,2** (309, PF 0,753) | Ambas negativas |
| 2023, janela 1 (**novo teste**) | −11.263,8 (153, PF 0,605) | **−19.819,8** (330, PF 0,663) | Ambas negativas |
| 2023, janela 2 (**novo teste**) | −2.298,3 (127, PF 0,879) | **−30.025,2** (332, PF 0,416) | Ambas negativas |

**Decisão técnica:** rejeitar a versão condicional como melhoria e não aprovar Runner384 para negociação real. O comportamento aparentemente positivo em 2025–26 NÃO se repetiu em 2023–24. O modelo condicional aumenta a quantidade de reentradas, o que eleva custos de transação.

## QA / proveniência
- Workflow GitHub Actions: https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/43217753852 (conclusão **success**).
- 7 testes originais do Runner384 e 16 testes sintéticos do adaptativo passaram, mais a suíte geral de segurança EA após corrigir dependências de CI.
- Dados 2026: CSV XAUUSD 1m com SHA256 fixo de `research_oos.py`.
- 2023, 2024 e 2025: mesma fonte secundária pública de arquivo diário, commit fixo `b2cfdc571ffac9eff9f2132ea6946da559d29af2`. 2023 foi novo holdout nesta iteração. 2024 já foi consultado na primeira tentativa.
- Custo hipotético: US$ 0,80/onça por ordem round-trip, `POINT=0.01` assumido.
- Não cobre swap, spread variável, slippage, ticks reais, volume real, diferenças de broker, comissões nem resiliência à execução. O drawdown foi calculado sobre P&L de trades encerrados, não risco intratrade.
- **Não** interpretar pontos simulados como lucro bancário ou backtest compilado MT5.

## Próxima linha de pesquisa priorizada
1. Diagnosticar **qualidade das entradas** por regime e ano, antes de mexer novamente no tempo de saída. O maior problema é ausência de expectativa líquida estável fora dos períodos escolhidos.
2. Investigar se prejuízo vem de stop inicial, custos ou reversões; manter todos os casos negativos no registro e evitar seleção só pelos melhores blocos.
3. Obter histórico Bid/Ask e custos/swap reais da corretora do usuário; calibrar XAUUSD SYMBOL_POINT/TICK_VALUE/contract size.
4. Congelar configuração nova antes de qualquer nova janela de teste e fazer walk-forward + demonstração MT5, jamais ativar conta real com esses dados.

**Originais preservados:** `research/preserved/nexus_alpha_ema21_pullback_xau_m15_41641_20261112.md`, `research/preserved/xau_ema21_runner384_candidate_20261112.md`, `robots/mt5/nexus_vector_retest/alpha_xau_longhold.py`; nenhum desses arquivos foi modificado nesta iteração.
