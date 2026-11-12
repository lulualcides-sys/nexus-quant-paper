# XAUUSD M1/M5 — inverter COMPRA e VENDA: experimento contrafactual (10/11/2026)

## Hipótese e procedimento

**Hipótese:** nos instantes de sinal já identificados pelo indicador independente, operar na direção OPOSTA. Para cada COMPRA, calcular uma VENDA; para cada VENDA, calcular uma COMPRA. **Não** se trocou artificialmente o sinal do lucro/prejuízo.

Foi criado [`research/xau_inverted_tracker_experiment.py`](../research/xau_inverted_tracker_experiment.py), com [7 testes](../tests/test_xau_inverted_tracker_experiment.py) e [workflow de 30 datas](../.github/workflows/xau-reverse-buy-sell-m1-m5.yml).

- Os **horários e quantidades de sinais são idênticos**, mas a entrada limite no outro sentido é recalculada a partir da **outra extremidade** do mesmo candle.
- Entrada Fibonacci 50% ou 75% conforme variante, alvo 200% ou 250%, stop em −100% — todos refletidos na nova direção. No F50, a entrada muitas vezes é o mesmo preço mediano da vela, mas o lado de execução é outro (*bid/ask*), e o preenchimento não é o mesmo.
- A execução percorre os ticks históricos bid/ask da **Dukascopy XAUUSD**. Para compras, entrada pela ask e saída por bid; para vendas, entrada por bid e saída por ask. Os stops podem escorregar em gaps; limites nunca recebem fill pior que o preço limite; expiração após três candles e saída por tempo.
- Custos simulados **dobrados**: US$ 0,60 por onça roundtrip + US$ 0,20 por onça de slippage para stops/saídas de mercado, além do spread da fonte. Não são custos de corretora validados.
- **Julho:** 06–17/07/2026, 10 pregões previstos, **9 válidos**. **Agosto:** 03–28/08/2026, 20 previstos, **18 válidos**. Três sessões são quarentenadas integralmente por inconsistências de dados; nenhuma operação é excluída por lucro ou prejuízo.
- Julho é uma **replicação histórica anterior ao desenvolvimento**, não um teste prospectivo futuro. Agosto já havia sido analisado na estratégia original. Selecionar a inversão porque a configuração original perdeu constitui exploração de hipótese orientada pelos resultados, e os lucros de julho não podem autorizar operações.
- **Evidência pública:** [GitHub Actions 42793507783](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42793507783), três jobs **SUCCESS**, artefatos `xau-inversion-july`, `xau-inversion-august` e `xau-buy-sell-inversion-30-date-scorecard`. A auditoria reencontrou os resultados originais já documentados em agosto antes de confiar nos contrafactuais: referência M1 −53,365, equilibrado M1 −44,065, ativo M1 −149,145 e referência M5 −20,405 US$/oz.

## Resultado integral por configuração

**Todos os valores abaixo são US$ por uma onça hipotética**, não US$ mil nem saldo de conta.

| Variante | TF | Julho original | Julho invertido | Fills inversos julho | Agosto original | Agosto invertido | Fills inversos agosto |
|---|---|---:|---:|---:|---:|---:|---:|
| Referência F50 | M1 | −28,340 | −8,680 | 12 | −53,365 | −78,505 | 30 |
| Equilibrado F50 | M1 | −14,625 | −76,000 | 25 | −44,065 | −234,270 | 67 |
| Ativo F50 | M1 | −23,810 | −86,845 | 35 | −149,145 | −211,355 | 98 |
| Equilibrado F75 | M1 | −12,523 | −97,004 | 25 | −37,618 | −297,435 | 67 |
| Ativo F75 / alvo 250 | M1 | −51,067 | −121,448 | 32 | −195,794 | −289,551 | 96 |
| Equilibrado F75 / alvo 250 | M1 | −14,618 | −100,414 | 24 | −66,066 | −297,957 | 65 |
| Referência F50 | M5 | −11,745 | −7,990 | 3 | −20,405 | +6,140 | 2 |
| Equilibrado F50 | M5 | −24,905 | +2,960 | 4 | −44,750 | −22,175 | 12 |
| Ativo F50 | M5 | −36,435 | +13,070 | 5 | −81,555 | −6,335 | 21 |
| Equilibrado F75 | M5 | −30,038 | −4,666 | 4 | −31,208 | −48,268 | 12 |
| Ativo F75 / alvo 250 | M5 | −43,353 | +21,627 | 4 | −82,100 | −15,133 | 21 |
| Equilibrado F75 / alvo 250 | M5 | −30,038 | +9,732 | 3 | −46,348 | −29,593 | 12 |

### Leitura quantitativa

- **M1:** todas as seis variantes invertidas tiveram P&L líquido negativo **em ambos os meses**. Uma parte apresenta mais limites preenchidos após inverter; mais operações não melhoraram os resultados.
- **M5:** algumas inversões ficaram positivas em julho, mas nenhuma foi positiva **tanto em julho quanto em agosto**.
- O M5 Ativo F50 invertido acumularia **+US$ 6,735/oz em 26 operações** dos dois meses, e o M5 Ativo F75/alvo250 invertido **+US$ 6,494/oz em 25 operações**, porém os resultados **mudaram de sinal entre os meses** e ficam próximos de zero comparados com a dispersão observada. Isto não demonstra vantagem robusta, e escolher os dois agora seria uma seleção retrospectiva enviesada.
- Por exemplo, no M5 ativo F50: **+13,070 em julho** seguido de **−6,335 em agosto**, com condições de custo hipotéticas fixas.
- Não somar os P&Ls de variantes concorrentes como se fossem uma única carteira independente.

## Riscos e bloqueios

**REPROVADO para negociação automática.** A estratégia continua experimental, sem conexão a um MT5 demo autorizado com feed/execução de corretora, sem custos reais, sem resultados futuros prospectivos, sem comparação completa com os sinais do Tracker proprietário da Greenhouse. Não colocar o modo inverso como default, não habilitar ordens, não publicar na `main` e não alterar os demais robôs.

Próxima pesquisa com mais valor: testar em datas **cronologicamente posteriores e realmente preservadas**, com os mesmos parâmetros congelados, e fazer análise de distribuição de resultados e execução em uma corretora. Uma hipótese nova baseada nesses resultados não pode reutilizar julho/agosto para aprovação.
