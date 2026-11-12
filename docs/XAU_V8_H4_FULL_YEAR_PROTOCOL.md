# V8 — verificar Channel20/55 H4 originais com um ano de BID/ASK observados

**Status exclusivamente pesquisa.** Alterar capital inicial em diagnóstico não produz vantagem matemática; não recomendar depósitos maiores. Não ativar live nem modificar motores antigos ou o estado das automações.

## Plano congelado antes de observar o ano completo

- Importar as cinco regras H4 originais de `research.screen_v2.sign`: Channel20, Channel55, Momentum100, RSI Trend e Pullback20. Nenhum gatilho novo nem filtro de aprovação por quantidade de trades. Máximo uma posição por robô.
- Abrir na ASK para compra/BID para venda na **abertura H4 imediatamente após** a vela completa que gerou sinal, somente quando não há lacuna. Fechar na BID/ASK oposta conforme lado. Stop 2 ATR14, alvo 3,5 ATR14, saída por tempo em 90 H4; gaps executados conservadoramente e stop primeiro na ambiguidade intrabar. Compras/vendas reais não são enviadas.
- Dados da Dukascopy BID e ASK M1 do mirror público `kevingtlin/Market-Data-Lab` com commit fixo `b60bd71d0e34a42cb962daf688ff252e73f409ca` (fonte não é FBS). Abr–Set/2025 para aquecimento EMA200; Out/2025–Set/2026 para teste anual, sempre sem candles falsos/interpolados.
- Regras de quantidade de posição congeladas: risco <=0,75%, notional <=1×, passo e mínimo de 1 onça, bancas virtuais de US$5000, US$10000 e US$20000 separadas; slippage extra de US$0,15 e US$0,75 **por onça e por lado**, além do BID/ASK já observado. Não somar retorno de contas virtuais nem comparar dólares absolutos sem normalizar pelo capital.
- Reportar ano contínuo com quatro trimestres separados (banca reinicializada), 30 ou mais trades como parâmetro de triagem estatística mínimo, fator de lucro, perdas e drawdown conservador intra-H4. Se os sinais não produzirem trades suficientes, resultado INCONCLUSIVO, não zero risco/lucro.
- **Triagem de pesquisa não é aprovação real:** para exame futuro, >=30 trades em banca virtual 10k, lucro líquido anual e em cada trimestre sob os dois custos e DD <=12%. Não mudar regra para passar, nem escolher a banca que deu positivo.
- Todos os períodos foram previamente usados noutros estudos do projeto. Não se trata de holdout intocado. Sem swap, comissão FBS real, news guard com histórico congelado ou execução tick-by-tick da corretora.

Workflow isolado `.github/workflows/xau-v8-h4-full-year.yml`; relatórios em `research/results/xau_v8_h4_full_year.{json,md}`.

## Auditoria estatística pós-hoc da V8

Depois da primeira execução anual, foi acrescentado o módulo `research/xau_v8_bootstrap_audit.py`, que só reamostra os resultados **já executados**, sem alterar sinais, lote ou regras de entrada/saída. Faz 5.000 reamostragens independentes dos dias com fechamento de operação (semente fixa 20261110), como diagnóstico da incerteza do resultado anual. Esse procedimento ignora a dependência entre trades, possíveis mudanças de regime e o viés de seleção entre cinco modelos; portanto não mede probabilidade real de lucro no próximo ano, mesmo quando o histórico passa na triagem retrospectiva.