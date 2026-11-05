# ATLAS V5 — extração do pior ao melhor, custo/risco uniforme

**Data de verificação:** 05/11/2026.

**Execução reprodutível:** [GitHub Actions run #42080630576](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42080630576), com **17 testes focados e de regressão aprovados** (6 V5, 8 V4 e 3 WINM26), e backtest real de preços históricos Profit/terceiro em dois contratos. Os quatro períodos mensais foram executados com banca virtual R$30 mil **reiniciada em cada mês**, risco 0,75%, máximo 3 minicontratos, taxa estimada R$4/contrato ida+volta e **2 ticks de slippage por lado**, sem ordens reais.

Os datasets usados foram fixados por hashes de Git: WINM26 M5 `6ee0eebd10e24ac40c073efe73883c313e6c27b1`; WINQ26 M5 `fe06f08f87183db468bc2a05ec080cda661660e9`. Nenhum é auditado independentemente pela B3. O último mês de julho é **PARCIAL** e fica fora do ranking, mas aparece nos resultados adicionais.

## Ranking do pior ao melhor — quatro meses completos

| Ordem | Versão | Trades | Meses positivos | Líquido 1 tick R$ | Líquido 2 ticks R$ | Amostra mínima para classificação? |
|---:|---|---:|---:|---:|---:|---|
| 1 (pior) | V5 custo + ruído | 44 | 1/4 | −1.130 | **−1.262** | Sim (só descritiva) |
| 2 | V5 custo | 90 | 1/4 | −770 | **−1.064** | Sim (só descritiva) |
| 3 | V4 rompimento + reteste | 85 | 2/4 | −725 | **−1.019** | Sim (só descritiva) |
| 4 | V4 rejeição / volume | 36 | 1/4 | −137 | **−289** | Não |
| 5 | V4 VWAP | 5 | 1/4 | +112 | **+90** | Não |
| 6 | V1 original | 117 | 1/4 | +552 | **+96** | Sim (só descritiva) |
| 7 | V4 tendência | 12 | 3/4 | +279 | **+231** | Não |
| 8 (maior saldo) | V3 confluência | 28 | 2/4 | +354 | **+236** | Não |

**Atenção:** o ranking ordena por soma dos saldos mensais, mas cada mês é uma simulação independente com banca reiniciada. Não representa retorno composto ou estratégia operacional selecionada. A elegibilidade para classificar é apenas um piso de tamanho amostral (>=40 trades, >=8 por mês em ao menos três meses). Nem mesmo as versões elegíveis estão aprovadas para operar. A V3 tem o maior saldo, mas apenas 28 trades; a V1 teve 117 trades e lucro marginal, distribuído de modo altamente desigual.

### V1 mês a mês (2 ticks em cada lado)

| Contrato e período | Operações | Saldo líquido R$ |
|---|---:|---:|
| WINM26 março completo | 35 | −37 |
| WINM26 abril completo | 25 | +198 |
| WINQ26 maio completo | 31 | −25 |
| WINQ26 junho completo | 26 | −40 |
| **Total descritivo** | **117** | **+96** |

O único mês positivo gerou resultado suficiente para compensar perdas pequenas dos demais, mas não demonstra estabilidade.

## Identificação das causas de perda

**V1, quatro meses completos, 117 trades, estresse 2 ticks:**

- 60 saídas em **TARGET**, líquido agregado +R$9.020; 45 em **STOP**, −R$8.357; três **STOP_SAME_BAR**, −R$611; oito **SESSION_CLOSE**, +R$99; uma **TIME**, −R$55.
- **Bruto antes dos custos simulados: +R$1.920. Custos de taxa + slippage: R$1.824. Líquido: +R$96.** Assim, 95% do lucro bruto foi absorvido por custos, sob as hipóteses de execução.
- Por horário **do sinal**, antes de 12h: 61 operações, **+R$517**; das 12h às 15h: 34 operações, **−R$1.176**; após as 15h: 22 operações, **+R$755**.

**V3**, 28 trades nos quatro meses, bruto R$708; custo R$472; líquido R$236; das 12h às 15h perdeu R$997 em oito trades. O efeito da hora aparece tanto na V1 quanto na V3, mas **foi descoberto retrospectivamente nos próprios dados**, portanto não pode ser tratado como filtro validado.

**V5 foi falsificada nos próprios parâmetros registrados:** custo mínimo relativo ao alvo e rejeição de volatilidade reduziram ou alteraram operações e pioraram o resultado agregado. **Não promover V5 nem ajustá-la para forçar lucro nos mesmos meses.**

## Mês fora do ranking: julho/2026 INCOMPLETO (WINQ26, até 24/07)

| Versão | Trades | Resultado líquido 2 ticks R$ |
|---|---:|---:|
| V1 | 27 | **−2.129** |
| V3 | 4 | −484 |
| V4 rejeição | 6 | −714 |
| V4 tendência | 0 | 0 (não é vitória) |
| V4 VWAP | 0 | 0 (não é vitória) |
| V4 rompimento | 14 | −182 |
| V5 custo | 21 | −1.610 |
| V5 custo + ruído | 12 | −959 |

**Alerta:** ignorar julho simplesmente porque o mês está incompleto seria selecionar o resultado retrospectivo mais favorável. Julho fica fora da *classificação de meses completos*, não fica fora da avaliação de risco. A forte perda V1 é evidência adversa relevante, e exige bloqueio de qualquer promoção.

## Próximo experimento controlado

Os dados mostraram perdas concentradas em sinais das 12h às 15h. A única hipótese justificável **para pesquisa exploratória** é testar uma regra explícita de veto de sinais nesse intervalo, mantendo todas as demais regras, e relatar se ela reduz prejuízo ou somente retira operações. Como o padrão foi observado nos mesmos dados, é **treino retrospectivo**, nunca validação fora da amostra. O período julho parcial, cujo prejuízo agregado foi observado, pode servir como diagnóstico de transferibilidade, mas também não é holdout inteiramente virgem.

Após isso, novos meses e vencimentos com execução prospectiva devem validar a hipótese. A regra de risco e os robôs paper/real **não foram alterados**.

## Arquivos técnicos

- `research/atlas_v5_cost_aware.py`: regras V5 pré-registradas de custo e volatilidade, não promovidas.
- `research/atlas_v5_loss_ranking.py`: consulta bases com SHA fixo, simulador de custo, ranking, lotes de saída por horário e motivo de encerramento, e exporta dados detalhados JSON.
- `tests/test_atlas_v5_loss_ranking.py`: testes sem rede de ausência de lookahead, importação de candle, controle de custo, agrupamento de perda e ranking.
- [Ledger completo da execução](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42080630576): artefato ZIP temporário com negócios encerrados, custos, stops e resultados de todos os cenários.
