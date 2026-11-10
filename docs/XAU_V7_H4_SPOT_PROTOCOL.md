# Nexus Quant V7 — auditoria dos cinco robôs originais H4 no ouro spot

**Status: exclusivamente pesquisa, sem ordens, sem promoção para main, sem mudanças nos robôs H4 originais e sem promessas de lucro.**

## Hipótese congelada

Comparar as **regras originais** `channel20`, `channel55`, `momentum100`, `rsi_trend`, `pullback20` (importadas de `research.screen_v2.sign`) nos mesmos dados históricos BID/ASK spot que reprovaram a V4 M5. Não acrescentar filtros nem otimizar parâmetros após inspecionar retornos. Backtest H4 executa uma posição por robô, contabilidades independentes.

- Dados: `kevingtlin/Market-Data-Lab`, fonte declarada Dukascopy BID/ASK M1, commit fixo `b60bd71d0e34a42cb962daf688ff252e73f409ca`, abril–setembro 2026. Abril–junho apenas aquecimento de indicadores, julho–setembro análise.
- As 12 fontes mensais CSV são baixadas sem previsão do futuro, com validação de candles, sincronização dos lados e hashes SHA256 por arquivo. Apenas H4 de 48 candles M5 consecutivos podem ser usados; nenhum preço ausente é preenchido.
- Sinal no fechamento do H4 anterior, entrada na próxima abertura H4 somente se horários adjacentes. Long compra ASK, vende BID; short vende BID, compra ASK. Slippage adicional de 0, 0.15 ou 0.75 USD/onça por lado. Nenhum spread cobrado duas vezes. Stop antes do alvo quando ordem intrabar desconhecida; gaps ao preço adverso de abertura.
- Saídas conforme pesquisa antiga: stop `2×ATR14`, alvo `3.5×ATR14`, timeout `90×H4`; risco 0,75%/entrada, notional <=1×, banca de US$5.000 por experimento.
- **Fracionário**: reproduce quantidade teórica permitida pelos antigos paper-books, como comparação não negociável abaixo de 1 oz. **Lote realista**: 1oz de mínimo e incrementos de 1oz. O robô não entra quando capital/notional/risco não permitem 1oz.
- Cinco famílias testadas em `fractional_slip_0p15`, `one_ounce_slip_0`, `one_ounce_slip_0p15`, `one_ounce_slip_0p75`. Não somar P&Ls de contas virtuais sem carteira compartilhada e correlações.
- A simulação reproduz sinais das regras originais, mas NÃO a execução exata de `src.gold_forward` (calendário histórico do `news_guard` não está congelado; prazos e correlação de ordens real FBS não são replicados). Swap/financiamento da corretora e comissão particular não modelados.
- Comparar Jul/Ago/Set independentes com capital virtual reinicializado, além do replay contínuo; número de trades, DD conservador intrabar H4, PF, retorno líquido sob slippage. Exigir pelo menos 30 negociações, P&L positivo contínuo e em cada mês tanto no custo normal como no estressado e DD <=12% para **triagem de pesquisa**; não implica live-approved.
- Não chamar julho–setembro de holdout intocado: outros testes do projeto já observaram essa janela, embora não essas regras H4 nesta exata base.

## Reprodução

```bash
python -m unittest tests.test_xau_v7_preserved_h4_bidask -v
python -m research.xau_v7_preserved_h4_bidask
```

Executar via workflow isolado `.github/workflows/xau-v7-preserved-h4-bidask.yml`. Publicar JSON íntegro e resumo, preservar fracassos, nunca alterar `state/` ou enviar ordens.