# Nexus Quant XAU — arquivo mestre de resultados positivos

**Não é lucro real e não autoriza operar em conta real.** Nenhum resultado negativo foi apagado ou revertido.

## Arquivos preservados

- **52 cenários positivos antigos**, conforme `research/preserved/xau_all_positive_original_robots_20261110.json` (14 famílias de regras; alguns aliases duplicam as mesmas entradas). Arquivo não alterado.
- **30 cenários positivos da auditoria V8**, em `research/preserved/xau_v8_all_positive_h4_snapshots_20261110.json`: apenas **5 famílias H4**, cruzadas com 3 bancas virtuais (US$5 mil, 10 mil, 20 mil) e 2 hipóteses de slippage. 30 resultados positivos **não são 30 robôs independentes**.
- Outros modelos com P&L positivo pontual (V2/V4) continuam preservados em suas PRs, arquivos de pesquisa e relatórios; V6 negou a robustez da fusão M5. Não promovidos.

## Triagem para forward

**Único candidato V8 aprovado para monitoramento experimental em paper**: Channel 20 H4, US$10.000 virtuais, 40 encerradas, +US$844,56 (+8,45%) na hipótese US$0,15/oz/lado e +US$817,56 (+8,18%) em US$0,75/oz/lado, PF 1,688/1,659. Quatro trimestres isolados positivos. A reamostragem dos ganhos ainda admite prejuízo. Isto NÃO é aprovação para real.

A banca de US$5.000 com lote >=1oz reproduziu só cinco entradas Channel20 em um ano; não compará-la com o livro H4 original fracionário. Bancas maiores são sensibilidade de dimensionamento, não recomendação de aporte.

## Monitoramento real existente

`.github/workflows/monitor.yml` em `main` já está agendado para acompanhamento dos livros H4 e fechamento 19h30 America/Sao_Paulo, e `state/selected_gold_v2.json` registra somente operações virtuais do GC=F. Esses saldos **não** correspondem à execução BID/ASK da pesquisa V8 e não podem ser somados ao backtest nem anunciados como lucro da corretora.

## Fontes verificáveis

- [V8 12 meses — GitHub Actions](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42903579739)
- [Auditoria da incerteza](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42904719901)
- [PR de pesquisa, sem merge](https://github.com/lulualcides-sys/nexus-quant-paper/pull/68)
- [Monitor existente](https://github.com/lulualcides-sys/nexus-quant-paper/blob/main/.github/workflows/monitor.yml)

## Regra operacional permanente

Não desabilitar stops, não aumentar alavancagem para buscar lucro, não ativar corretora ou misturar resultados entre bancas, origens e períodos. Toda atualização de forward deve declarar timestamp, fonte, capital, custo, amostra, entradas, operações encerradas, P/L realizado e P/L aberto, DD e motivo de indisponibilidade. Zero trades deve ser reportado como zero; falta de feed, como indisponível. Nenhuma meta obrigatória de frequência.