# Resultado — Nexus Quant V5 GOLD (10 de novembro de 2026)

**Pesquisa retrospectiva, capital virtual de US$ 5.000 por cenário, sem ordens reais.** Dados do ouro GC=F Yahoo e XAUUSD spot Dukascopy arquivados no GitHub. Os mesmos sinais de V4, sem empilhar filtros. Parâmetros foram pesquisados em históricos já consultados no projeto: nenhuma amostra é um holdout independente intocado.

## 1. Ouro GC=F com histórico completo M5

| Política de saída | Operações fechadas | Frequência estimada/30 dias | P&L líquido (US$0,61/oz) | P&L líquido (US$1,81/oz) | P&L líquido (US$3,31/oz) |
|---|---:|---:|---:|---:|---:|
| V4 original, saída fixa | 202 | 208,4 | +US$286,60 | +US$43,00 | −US$261,50 |
| Stop protegido após fechamento +1,5R | 209 | 215,6 | +US$201,28 | −US$50,72 | −US$459,45 |
| Trailing após fechamento +2R | 207 | 213,5 | +US$188,53 | −US$61,07 | −US$398,51 |

**Resultado:** nenhuma saída nova melhorou a V4 no histórico integral; nenhuma passou em todos os 3 segmentos cronológicos. A V4 original perde dinheiro com estresse de US$3,31/oz, e seu lucro depende fortemente do terceiro segmento. A quantidade de operações por 30 dias é estimada, não é comprovação de 200 entradas em mês-calendário inteiro.

## 2. Fonte alternativa: Dukascopy XAUUSD spot, apenas 9 horas por sessão

Arquivo de 24 dias válidos, 12:00–20:55 UTC; não extrapolar para 24h.

| Política | Fechadas | P&L com US$0,61/oz | P&L com US$1,81/oz | P&L com spread máximo observado nos candles + US$0,15 de slippage/lado |
|---|---:|---:|---:|---:|
| V4 fixa | 87 | −US$124,56 | −US$228,96 | −US$168,46 |
| Breakeven 1,5R | 89 | −US$148,97 | −US$255,77 | −US$193,04 |
| Trailing 2R | 90 | −US$50,55 | −US$158,55 | −US$97,66 |

A redução de operações decorre do horário **incompleto** da fonte, não de filtros nem imposição de limite. O trailing diminui o prejuízo nesta amostra parcial, mas ainda falha no custo alto. Sem evidência de ganho robusto.

## 3. Comparação nos mesmos 2050 timestamps (19 sessões)

As duas fontes foram restringidas à mesma interseção de candles observados; sessões encerram às 20:55, impedindo posições atravessarem horas sem dados. Isso não transforma GC=F em XAUUSD nem reproduz fills de corretora.

| Fonte | Saída | Fechadas | P&L com US$0,61/oz | P&L com US$1,81/oz |
|---|---|---:|---:|---:|
| Yahoo GC=F | V4 fixa | 74 | −US$154,00 | −US$242,80 |
| Yahoo GC=F | Trailing 2R | 72 | −US$23,48 | −US$109,88 |
| Dukascopy XAUUSD | V4 fixa | 69 | −US$47,19 | −US$129,99 |
| Dukascopy XAUUSD | Trailing 2R | 71 | +US$25,86 | −US$59,34 |

**Conclusão:** na comparação de horário realmente comum, o desempenho não se reproduz de forma positiva nas duas origens com custo normal e estresse. O único saldo positivo (+US$25,86) é pequeno, já desaparece a US$1,81/oz e não confirma consistência.

## 4. Melhoria efetiva de engenharia

- Testes de causalidade dos stops com atualização apenas após fechamento, execução com gap e ausência de entrada retroativa na mesma vela.
- Comparação contra a V4 **original reproduzida integralmente** (paridade exata nos candles reais congelados GC=F, incluindo todas as entradas e saídas).
- Snapshot de preço com SHA256, 24 arquivos Dukascopy por dia com checksums; 06/11 em quarentena; 19 sessões pareadas em 2050 timestamps (sem interpolação).
- Custos dinâmicos de estudo baseados nos spreads máximos dos candles na Dukascopy. Isso é estresse conservador e **não** uma execução real bid/ask.
- Nenhum robô aprovado, nenhum motor anterior alterado, nenhuma ordem real, nenhum falso lucro declarado.

**Próxima ação com melhor custo-benefício:** congelar a V4 como controle e exigir novos dados bid/ask do mesmo instrumento/corretora para verificar se os sinais produzem vantagem líquida. Se não houver, investigar qualitativamente os 2 primeiros segmentos perdedores antes de mexer em saídas ou adicionar filtros. Não forçar 200 entradas negativas como meta de operação.