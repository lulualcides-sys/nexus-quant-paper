# ATLAS V6 — filtro exploratório de horário, extraído de prejuízos anteriores

**Data:** 05/11/2026.

**Status:** melhora retrospectiva de amostra já estudada; **NÃO validado independentemente**, não representa resultado do Tracker comercial, não operar com dinheiro real ou substituir ATLAS paper. Versão de pesquisa testada com [GitHub Actions run 42082180250](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42082180250): cinco testes V6 e seis testes V5 passaram e backtest foi executado com sucesso.

## Por que este filtro?

No ranking anterior [V5](ATLAS-V5-DO-PIOR-AO-MELHOR-2026-11-05.md), a V1 perdeu −R$1.176 em sinais iniciados das 12h às 15h (34 trades) nos quatro meses completos analisados. A V3 perdeu −R$997 no mesmo intervalo (8 trades). Uma única modificação foi testada: **não emitir sinal se o horário LOCAL de abertura do candle fechado estiver entre 12:00:00 e 14:59:59 (America/Sao_Paulo)**. Fora desse horário a lógica original V1 ou V3 não muda.

**Viés fundamental:** o intervalo foi ESCOLHIDO após examinar o histórico. Reaplicá-lo aos mesmos meses é ajuste in-sample. Mesmo julho/2026 não é holdout virgem, porque o resultado mensal original já havia sido observado antes de escolher o novo filtro.

## Critérios invariáveis

- Mercado: contratos reais WINM26 M5 e WINQ26 M5 exportados por terceiro via Profit, arquivo pinado por Git hash, não auditado independentemente com a B3.
- Mesmos quatro meses completos **M26 março/abril e Q26 maio/junho**, mais **Q26 julho parcial (até 24/07) separado e excluído da soma**.
- Banca virtual de R$30.000 **reiniciada por período**, risco planejado 0,75%/operação e até 3 contratos inteiros; stop −100%, entrada limite 50%, alvo +200%, taxa simulada R$4/contrato ida+volta, slippage estressado de **2 ticks em cada lado**.
- Mesmo motor de backtest, tratamento pessimista intrabar, nenhuma otimização de alvo ou stop, mesmo leilão sem fills reais.

## Resultado por mês — líquido em R$, 2 ticks por lado

| Contrato e mês | V1 sem veto (trades) | V6 baseada V1 (trades) | V3 sem veto (trades) | V6 baseada V3 (trades) |
|---|---:|---:|---:|---:|
| WINM26 março completo | −37 (35) | **+771 (25)** | +126 (5) | **+336 (4)** |
| WINM26 abril completo | **+198 (25)** | +103 (21) | **+430 (9)** | +294 (8) |
| WINQ26 maio completo | −25 (31) | **+355 (19)** | −153 (5) | **+333 (3)** |
| WINQ26 junho completo | −40 (26) | **+166 (19)** | −167 (9) | **+270 (5)** |
| **Total dos quatro meses, sem composição** | **+96 (117)** | **+1.395 (84)** | **+236 (28)** | **+1.233 (20)** |
| WINQ26 julho **PARCIAL**, não somado | **−2.129 (27)** | −1.517 (20) | **−484 (4)** | −262 (3) |

Em abril o veto **piorou ambas as versões** em comparação com o modelo-base. Em julho parcial reduziu prejuízos, mas deixou resultados expressivamente negativos: V1 ainda perdeu R$1.517 e V3 R$262, mesmo com custos e risco invariáveis.

## Interpretação

A V6 baseada na V1 reduziu o número de operações (117 → 84) e transformou três meses antes negativos em positivos, mantendo abril positivo, mas com lucro menor. A V6 baseada na V3 teve apenas 20 operações nos quatro meses, o que não oferece tamanho amostral suficiente. A soma mensal (sem capital composto) foi expressivamente melhor, **mas seleção pós-análise pode explicar toda a diferença**.

**Decisão: manter somente para pesquisa / shadow test.** Não habilitar automaticamente no ATLAS paper, não modificar outros robôs, nem citar os R$1.395 como lucro replicável. Para aprovação futura são indispensáveis:
1. Novos meses e vencimentos nunca utilizados na seleção do horário.
2. Teste prospectivo (paper), com registro de **todas** as setas, ordens canceladas, risco, taxas e slippage, e sem alterar parâmetros depois de ver resultados.
3. Robustez sob 2 ticks por lado, meses positivos sem ganho concentrado em poucas operações e drawdown aceitável em amostra suficiente.
4. Correlação operacional com Tracker somente se houver gravação contínua das setas e candles equivalentes.

## Código

- `research/atlas_v6_noon_probe.py`: hipóteses congeladas V1/V3 com e sem veto 12h–15h, entradas e custos invariáveis, diagnóstico julho parcial.
- `tests/test_atlas_v6_noon_probe.py`: cinco testes determinísticos para bordas da janela, venda, ausência de lookahead, rejeição de configuração desconhecida e correspondência com o modelo pai.
- `research/results/atlas_v6_noon_exploratory.json`: gerado no artifact GitHub Actions com ledger de todas as operações; não promovido ao bot operacional.
