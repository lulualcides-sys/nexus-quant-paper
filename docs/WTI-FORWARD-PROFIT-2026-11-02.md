# Nexus Quant — evidência prospectiva de lucro (02/11/2026)

## Resultado anterior não aprovado para capital real
O teste de 27 robôs em três segmentos cronológicos detectou **0/27 que passaram todos os critérios**. Os preços e resultados foram inspecionados em pesquisas anteriores: *não* constituem novo out-of-sample. Os três candidatos escolhidos para acompanhamento após isso são:

- `gold_h4:channel20` e `gold_h4:channel55` — manter exatamente os livros virtuais pré-existentes de ouro, sem reconfigurar ordens/entradas.
- `wti_filtered:channel10` — uma **carteira virtual adicional, experimental** de WTI H1 (CL=F) com filtro de custo/ATR e EMA, em estado próprio. **Não altera os 27**, não duplica nem substitui o H1 XTIUSD Channel10 original.

## Protocolos de prova
1. **Zero backfill**: WTI começa após o primeiro H1 fechado observado; saldo inicial virtual US$ 1.000 e 0 operações. Nenhum resultado retroativo é criado. Se um watermark desaparecer, recusa novas operações.
2. **Filtro fixo e compartilhado**: o módulo `src/cost_aware_gate.py` aplica `ATR/close × 10.000 ≥ 4× custo estimado em bps`, `|EMA50−EMA200|/ATR ≥ 1,5` e alinhamento da direção, usando **apenas o candle anterior fechado**. A pesquisa histórica e o novo shadow usam a mesma função.
3. **As operações são virtuais**; execução e corretagem reais da FBS **não** são usadas. As entradas são geradas na próxima abertura de vela horária, e saídas/stop seguem o motor H1 já testado.
4. **Evidência nova somente**: a watchlist inclui negociações abertas **e encerradas** depois de **02/11/2026, 06:30 UTC**, e exclui negociações antigas encerradas depois. Se faltar registro, **indisponível ≠ lucro zero**.
5. **Robustez e custos**: separação de bruto, transação, líquido, retorno por trade e drawdown fechado. A coluna de custo dobrado da watchlist é uma **sensibilidade aritmética de fills fixos** (não um novo replay de backtest). A pesquisa separada continua calculando cenários completos com dois custos.
6. **Quantidade de operações**: ouro H4 mínimo 20 fechamentos novos; WTI H1 mínimo 60. Mesmo que haja retorno positivo, resultado é marcado **somente para revisão**, sem promoção automática.
7. **Telegram**: apenas uma linha na mensagem diária já existente, **nunca** alertas por entrada/saída. JSON detalhado em `reports/profit_watchlist/YYYY-MM-DD.json`.
8. **Notícias**: o filtro oficial do PR anterior fica **desativado por padrão**; se ativado, impede somente novas entradas sobre eventos oficiais ou calendário vencido; nenhum stop existente é bloqueado.

## Como foi protegido
- As alterações no motor `src/experimental_h1.py` adicionam apenas o argumento opcional `signal_fn=None` para o novo shadow. Os 15 livros originais continuam usando `setup` anterior sem alterações.
- O arquivo `state/wti_channel10_filtered_shadow_v1.json` é independente, sem edição de `state/experimental_h1_v1.json`, `state/selected_gold_v2.json` ou saves legados.
- Testes verificam que reprocessar o mesmo candle não cria entradas duplicadas, que o inicial não inventa trades, que o stop funciona e que dados ou estado inválidos interrompem a simulação.
- Execução prospectiva ocorrerá **somente após integração da PR** na branch principal e execução programada; nenhuma execução futura é presumida.

## Critério decisório
Não é tecnicamente correto prometer lucro nos 27 ou anunciar robô vencedor agora. Aguardar resultados **realmente novos**, custos executáveis de corretora e múltiplos regimes antes de aumentar o risco ou executar ordens reais.
