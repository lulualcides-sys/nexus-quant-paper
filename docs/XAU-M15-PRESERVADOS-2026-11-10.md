# M15 XAUUSD — versões positivas preservadas (10/11/2026)

Arquivo mestre: [research/preserved/xau_m15_positive_20261110.json](../research/preserved/xau_m15_positive_20261110.json).

A seleção de 24 sessões históricas válidas foi **congelada**, com checksum do relatório fonte. Este commit preserva **as referências das regras originais, identidade, resultados e custos**, sem modificar os motores de produção, ordens, capital, estados, parâmetros ou o ATLAS.

Amostra: 05/10–05/11/2026, Dukascopy BID/ASK convertido a candle MID; custo convencional de 7bps, alavancado 14bps, ambos estimados. Não são cotações de execução MT5 nem lucros reais. O dia 06/11 foi integralmente quarentenado por cotação inválida.

- **20 entradas positivas na tabela M15**, mas representam somente **8 regras distintas**.
- **4 regras continuam positivas com custos dobrados**: Channel55 convencional (+US$ 6,27), Channel55 alavancado (+US$ 29,69), EMA20 Retest (+US$ 8,34) e RSI50 (+US$ 24,57).
- As outras 4 regras preservadas — Channel20 convencional, Channel20 alavancado, Trend Long alavancado e Channel10 experimental — não passaram o stress de custos.
- As 15 entradas da família H1 representam **3 regras repetidas em 5 antigos mercados**. No ouro são cópias idênticas e NÃO formam um portfólio de quinze sinais independentes.

Fonte de evidência: [GitHub Actions 42847239203](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42847239203). Código da pesquisa original: commit `12ce73ce491b5c20333fd36ca494b34d949b399d` (PR #65).

**Estado:** snapshot preservado. Nenhum robô habilitado para negociação, nenhum lucro garantido, nenhum código original substituído.
