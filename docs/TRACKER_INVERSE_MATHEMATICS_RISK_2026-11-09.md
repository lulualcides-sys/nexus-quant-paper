# Tracker — inversão matemática dos 43 vetores públicos e limite de identificação

**09/11/2026 — código executado, cálculo independente testado; não é o indicador original da Greenhouse.**

## Escopo e dados

- A [página pública de oferta](https://lojadagreenhouse.com.br/ofertatracker/) entrega 43 etiquetas de entradas, alvos, stops e resultados comerciais selecionados de 03 e 04/11/2026. Arquivo extraído pela rotina já auditada `research/greenhouse_public_gallery_decode.py`. Não se acessou área paga ou login.
- Conteúdo do HTML verificado por SHA256: `2bfa22a1d9b62237f92af539cffa07596189c14b5da3310f7a49002b32de1c83`.
- Os 43 registros e candles do painel são uma reconstrução comercial, não feed de ticks da B3, lista completa de sinais, fills de corretora ou código-fonte do Tracker.
- [GitHub Actions — auditoria matemática final, 11 testes unitários](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42722761735). Fonte em `research/tracker_mathematical_inverse_43.py`, testes em `tests/test_tracker_mathematical_inverse_43.py`, JSON completo disponível nos artifacts da execução.

## O que a matemática recuperou de forma exata (até arredondamento)

Se o candle base tem máxima `H`, mínima `L`, amplitude `R=H−L`, seu ponto médio `E=(H+L)/2`. O sentido é `s=+1` na compra e `s=−1` na venda. Sob a construção pública 50% / 200% / −100%:

```text
Entry:        E = (H + L) / 2
Target:       A = E + s * 1.5 * R
Stop:         S = E - s * 1.5 * R
Inverse:      R = |A - S| / 3
Center:       C = (A + S) / 2   (≈ E)
Implied high:  H = C + R / 2
Implied low:   L = C - R / 2
Symmetry:     |2E - A - S| <= 5 pts in ALL 43 observed labels
```

- `43/43` etiquetas têm distância bruta de ganho/stop simétrica até 5 pontos, coerente com arredondamento na grade WIN.
- Amplitude implícita dos 43 vetores: mínimo **56,67 pontos**, mediana **143,33 pontos**, máximo **535 pontos**.
- Essas equações permitem recuperar o **vetor numérico representado**, mas **não determinam unicamente o candle que originou o vetor**: na auditoria anterior, apenas 13/43 valores combinaram com alguma das 63 hipóteses de âncora avaliadas sobre os candles redesenhados.

## Restrição econômica para a banca de referência

Para **um contrato WIN**, assumimos R$0,20 por ponto, custo por operação completa de **R$3,40** (hipótese, não tarifa efetiva confirmada da Rico), banca **R$2.000** e limite planejado de **1% (R$20) por operação**.

```text
Gross stop risk (BRL) = 0.20 * 1.5 * R = 0.30 * R
Planned net stop risk = 0.30 * R + modeled roundtrip cost
Admissible R <= (20 - cost)/0.30
With cost R$3.40:  R <= 55.33 index points
```

| Métrica calculada | R$3,40 (base) | R$5,40 (estresse) | R$6,00 (anterior) |
|---|---:|---:|---:|
| Máxima amplitude cabível no risco de R$20 | 55,33 pts | 48,67 pts | 46,67 pts |
| Etiquetas comerciais cabíveis | **0/43** | **0/43** | **0/43** |
| Menor capital teórico para o menor stop a 1% | R$2.040 | R$2.240 | R$2.300 |
| Capital mediano teórico para o stop divulgado a 1% | R$4.640 | R$4.840 | R$4.900 |
| Maior capital teórico exigido a 1% | R$16.340 | R$16.540 | R$16.600 |

**Interpretar corretamente:** isso não diz quanto dinheiro você deve depositar, nem a margem exigida pela Rico, nem que os 43 sinais seriam executáveis com essa quantia. Indica somente que reproduzir seus níveis publicitários com um contrato viola a regra de risco planejado adotada na nossa banca R$2.000. Slippage real e gaps podem exceder o stop planejado.

O menor sinal tinha perda bruta anunciada de R$17; com R$3,40 estimados de custo, risco líquido **R$20,40**, maior que o nosso limite R$20. A operação tem custo de oportunidade: aumentar risco para reproduzir a publicidade alteraria o projeto de gestão de risco.

## Por que não conseguimos obter o gatilho exato só por matemática dos candles

Há uma impossibilidade de identificação com os dados fornecidos, não uma questão de capacidade de cálculo:

1. A lista contém **43 marcas positivas** e não contém um log completo de todas as vezes que o Tracker ficou em silêncio. O script construiu dois algoritmos matematicamente distintos que produzem todos os 43 horários publicados e discordam sobre ao menos um minuto não catalogado. Ambos são compatíveis com toda a evidência observável, logo nenhuma regra única pode ser deduzida apenas desses exemplos.
2. Mesmo se a página fornecesse OHLC e volume negociado `V`, isso não revelaria o delta de agressão `Δ = V_comprador − V_vendedor`. Com `V=100`, **80 compras/20 vendas geram Δ=+60**, ao passo que **20 compras/80 vendas geram Δ=−60**, ambos com o mesmo volume total. OHLC não fornece flags de agressor suficientes para resolver essa ambiguidade. São exemplos matemáticos, não transações recuperadas.
3. O frontend contém vetores marcados **depois** dos eventos apresentados na publicidade. Sem instantes de formação das setas, feed bid/ask/ticks e histórico original, infinitos geradores de sinais podem reproduzir os mesmos 43 exemplos e divergir em pregões novos.

Portanto, não existe dedução honesta do código fechado apenas a partir desses dados. A implementação possível é **independente e funcionalmente análoga**, validada prospectivamente.

## O que fazer com o conhecimento extraído

- Preservar a geometria 50/200/−100 na PR #52 como ferramenta visual, não como promessa de fill.
- Manter a coleta real de ticks da [PR #54](https://github.com/lulualcides-sys/nexus-quant-paper/pull/54) apenas no PC com MT5 Rico conectado; o algoritmo exige `TICK_FLAG_BUY/SELL`, `volume_real` e histórico íntegro.
- Testar absorção por agressão contrária e confirmação fechada em **novos pregões**, sem ajustar parâmetros nos dias de teste ou nos 43 sinais vistos.
- Bloquear operações reais que ultrapassarem 1% de risco modelado com 1 WIN e custos; considerar apenas pesquisa ou estratégias com distância de stop compatível e risco preservado.
- Não implementar entradas reais nem substituir indicadores aprovados sem validação independente.

**Conclusão:** a reconstrução matemática dos vetores está concluída e reproduzível. A identificação unívoca do gatilho proprietário **não foi obtida** e não é possível com este conjunto limitado de informações. A PR permanece em rascunho, sem alterar a main nem contas reais.
