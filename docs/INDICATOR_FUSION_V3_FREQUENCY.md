# XAU GOLD — Indicator Fusion V3: frequência sem ordens artificiais

Objetivo do usuário: aproximadamente 200 **entradas realmente executadas** por mês no conjunto de estratégias do ouro. **Meta de pesquisa, não cota operacional.** A contagem deve vir de entradas simuladas observadas e depois prospectivas, nunca de sinais duplicados no mesmo candle nem de extrapolação de cinco dias como se fossem 30 dias de dados.

## Mudanças em relação a V2

- Cinquenta e cinco candles de canal e seis EMAs empilhadas eram requisitos muito restritivos para M1/M5; V3 testa cinco mecanismos distintos mais frequentes: cruzamento com retomada da EMA20; rompimento do canal de 12 candles; sweep do extremo dos oito candles anteriores; continuação de dois candles; rejeição de extremo do range de 16 candles.
- São hipóteses originais inspiradas nos conceitos dos indicadores abertos DTC/QKE/Market Structure/Auto Range/Monster Arrows. Não são transcrições exatas nem reproduzem códigos compilados EX4/EX5.
- Uma carteira virtual única, uma posição simultânea no ouro, prioridade de sinais congelada, abertura na vela seguinte, sem preenchimento de candles ausentes, sem reentrada retroativa no candle da saída e sem contar sinais coincidentes como múltiplas posições.
- Risco-stop planejado 0,35% do patrimônio, exposição nominal limitada a 1x; stop 1,25 ATR(10), alvo 1,8R, encerramento máximo de 12 candles. Todos fixados **antes** do backtest. Execução OHLC com gaps adversos e stop-first em trajetórias intrabar ambíguas.
- Custos sintéticos ida/volta 0, 7, 14 e 28 bps. Não substituem spreads, comissões e slippage do broker FBS/MT5. Dataset público Yahoo GC=F (futuro de ouro, não spot). Não operar dinheiro real com estes resultados.
- M5 é o período principal para avaliação de volume mensal; M15 comparador, M1 apenas diagnóstico com ~5 dias. Reporta operações fechadas, sinais detectados, sinais bloqueados por posição já aberta e por lacuna, normalização para 30 dias explicitamente **estimada** e número efetivo por mês UTC.
- Três cortes cronológicos para estabilidade diagnóstica; períodos já explorados anteriormente, **não** holdout independente. Backtest não implica expectativa positiva futura. Não usar os 200 trades como restrição de entrada na estratégia.

## Critérios

Volume e lucro são métricas SEPARADAS. Meta de ~200 fechamentos mensais só conta quando a mesma carteira de um único ativo realmente os registra, sem posições concorrentes. Aprovação exigiria retorno líquido positivo em amostra nova, custos reais, walk-forward e stress 2x sem drawdown excessivo; nenhum candidato deve ser classificado como aprovado apenas porque chegou ao volume.

Artefatos de pesquisa: `research/indicator_fusion_v3_frequency.py`, `research/run_indicator_fusion_v3_frequency.py`, `tests/test_indicator_fusion_v3_frequency.py`, workflow `indicator-fusion-v3.yml`. V1, V2 e todos os robôs preservados permanecem intocados.