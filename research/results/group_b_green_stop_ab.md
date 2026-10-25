# Nexus Quant: Grupo B — stop móvel de green versus stop fixo

**SOMENTE SIMULAÇÃO RETROSPECTIVA. Sem operações reais, sem FBS.**
Cinco robôs, cinco bancas de US$ 5.000, ouro GC=F, H4, exposição virtual 2× por entrada.
Identificação da série de preços usada neste teste (SHA-256): \`905ffc0508884ea1d6f05b0eff00acc053a4f81eeb3b91bb63c41113a37ae70d\`.
Período 24/10/2025–24/10/2026, 14 bps por operação ida e volta e 8% a.a. de financiamento virtual sobre excedente do saldo.

### Como funcionam os quatro modos
- **fixed:** stop inicial fixo + take profit 1,75R.
- **green_fixed:** mesmo alvo fixo; após atingir +1R favorável, só no candle seguinte começa a proteger lucro líquido estimado; a partir de +1,5R segue uma distância de 1R.
- **green_runner:** começa a proteger após +1R, trailing após +1,5R, **sem take-profit fixo** (deixa possíveis tendências correrem).
- **green_wide:** proteção após +1,25R, trailing após +2R com distância de 1,35R, **sem take-profit fixo**.
A ativação e ajuste são sempre **após o candle H4 fechar**, não dentro do candle do gatilho. Gaps podem produzir perdas mesmo com stop no green.

| Variante | P&L total 5 robôs | Diferença do fixo | Trades | Custos transacionais | Financiamento |
|---|---:|---:|---:|---:|---:|
| fixed | US$ +1,548.57 | US$ +0.00 | 147 | US$ 2,122.80 | US$ 109.09 |
| green_fixed | US$ +1,548.95 | US$ +0.38 | 147 | US$ 2,101.55 | US$ 94.66 |
| green_runner | US$ +2,790.99 | US$ +1,242.42 | 138 | US$ 2,004.34 | US$ 130.57 |
| green_wide | US$ +2,677.02 | US$ +1,128.45 | 136 | US$ 1,961.80 | US$ 151.32 |

### Lucro/prejuízo por robô e modo

| Robô | Fixo | Green + TP | Green runner | Green wide |
|---|---:|---:|---:|---:|
| Channel 20 L | US$ +136.26 | US$ +131.80 | US$ +166.48 | US$ +432.60 |
| Momentum 100 L | US$ +714.79 | US$ +512.15 | US$ +1,636.46 | US$ +1,366.80 |
| Channel 55 L | US$ +381.55 | US$ +582.76 | US$ +805.69 | US$ +813.55 |
| Momentum 40 L | US$ +181.44 | US$ +187.71 | US$ +52.75 | US$ +15.26 |
| Trend Long L | US$ +134.53 | US$ +134.53 | US$ +129.61 | US$ +48.81 |

### Limitações importantes

- Proteger green não garante saída positiva: slippage/gaps, custos ou distância ao preço podem prejudicar o resultado.
- Os candles OHLC não mostram a sequência intrabar; os stops só são atualizados depois do fechamento e os stops ativos têm prioridade sobre alvos simultâneos.
- Não usamos cotação real da FBS, margem real, ordem efetiva nem swap exato; os modelos simulam preços públicos de contratos futuros.
- Amostra já estudada anteriormente: diferenças de retorno não comprovam vantagem futura.
- As cinco estratégias operam ouro e têm risco concentrado e correlacionado.

Fonte e algoritmo: `research/green_stop_ab.py`, `src/leveraged_gold.py` e `src/green_stop.py`.
