# NEXUS QUANT — seis candidatos M1/M5 (somente laboratório)

## Estado e isolamento

Esta mudança existe exclusivamente em research/nexus_m1m5/, tests/test_nexus_m1m5_lab.py e .github/workflows/nexus-m1m5-lab.yml. Não importa nem executa src/crypto_runner.py, ATLAS, src/runner.py, Telegram ou futebol. Não altera arquivos state/, horários de 19h30 America/Sao_Paulo (financeiro e cripto), nem 00h00 (futebol). **Nenhum candidato recebe autorização automática de paper forward ou execução real.**

**M1:** sweep (varredura e rejeição de mínimo com sombra e volume); vwap (reversão à VWAP móvel de 48 minutos em lateralidade, com z-score aproximado por desvio do fechamento). **M5:** trend (pullback EMA20 M5, direção EMA50/200 de M15 estritamente fechado); breakout (Donchian 20, ATR, volume e distância; comparar confirmação imediata com reteste em até três candles); squeeze (Bollinger 20×2 dentro de Keltner EMA20/ATR14×1,5 seguido de expansão); flow (agressão compradora aproximada por taker-buy-base/candle-volume, **não** livro completo de ordens). Todos são independentes, de entrada long-only spot, com fechamento confirmado e entrada apenas a partir da abertura observada seguinte.

## Hipóteses e parâmetros congelados antes da inspeção do resultado

| Modelo | Mercado | Gatilho | Stop ATR mínimo | Alvo R | Prazo máximo |
|---|---|---|---:|---:|---:|
| Sweep | M1 | low < mínimo Donchian anterior, fechamento recupera nível, sombra >=1,5 corpo e >=0,3 ATR, volume >1,2× média | 1,25 | 2,0 | 90 candles |
| VWAP | M1 | fechamento anterior mais de 1,6 desvios abaixo VWAP48, recuperação parcial; regime EMA20/EMA50 próximo | 1,15 | 1,6 | 90 candles |
| Trend | M5 | EMA20/EMA50 + candle de retomada, EMA50/200 M15 fechado acima e crescente | 1,40 | 2,1 | 72 candles |
| Breakout | M5 | Donchian20, ATR>=1,10× ATR 5 barras atrás, volume>1,15×, extensão <=0,45 ATR; reteste alternativo | 1,65 | 2,3 | 72 candles |
| Squeeze | M5 | >=4 das 6 barras anteriores comprimidas e fechamento acima BB/Keltner | 1,40 | 2,0 | 72 candles |
| Flow | M5 | taker-buy>=59% e média 3 >=55%, volume >=1,35×, direção EMA20/EMA50 | 1,30 | 1,8 | 72 candles |

Stop estruturado é limitado a no máximo 2,5 ATR para evitar distâncias irreais; o stop nunca se afasta depois da abertura. Não há trailing stop. Setups foram escolhidos como hipóteses, **não como parâmetros otimizados ou comprovadamente rentáveis**. BTC/USDT e ETH/USDT são estudados em livros individuais com US$ 10 mil virtuais por combinação. Mercado spot sem margem: apenas compras, sem shorts ou alavancagem.

## Dados e integridade

Origem oficial: https://data.binance.vision/ e https://github.com/binance/binance-public-data. CSV Klines spot mensais Binance, intervalos 1m e 5m, pares BTCUSDT e ETHUSDT. Recorte predefinido **2025-01 a 2026-10 inclusive (22 meses)**. Cada ZIP é verificado com seu arquivo .CHECKSUM por SHA256. Doze campos oficiais, incluindo taker-buy base asset volume, são conferidos. Datas UTC em microssegundos (2025+) normalizadas a ms. Rejeição de OHLC inválido, volume negativo, taker-buy > volume, intervalo incorreto, duplicações, reordenações, gaps e arquivos mensais incompletos. Nenhum candle ausente é interpolado; falha de download significa **sem validação**, não resultado zero.

O M15 é derivado apenas de três candles M5 íntegros e alinhados; a decisão M5 não referencia um M15 ainda não fechado. A fonte não disponibiliza bid/ask de cada trade nem execução da ordem real: o preenchimento simulado é uma aproximação conservadora, não medição de slippage. Também não há histórico de latência WebSocket nem promessa de captura de cada candle por GitHub Actions.

## Execução conservadora e custos

- Taxa regular spot **0,10% por lado** e slippage modelado de **0,02% por lado** no cenário base. Cenário de custo dobrado: **0,20% de taxa + 0,04% de slippage por lado**. Cenário adverso: taxa 0,10%/lado e desvio de execução total **0,11% por lado** (0,08% slippage + 0,03% impacto). Como usamos OHLC de trades como referência, **não cobramos spread adicional** para não contar duas vezes a mesma aproximação de execução.
- Entradas à abertura do próximo candle realmente existente; candles faltantes bloqueiam dataset; gaps grandes de entrada (>1,5 ATR) cancelam entrada.
- Stop/alvo simultâneos no mesmo candle => stop primeiro. Gap abaixo do stop => execução pelo preço aberto piorado por slippage. Alvos e stops presumem preenchimento OHLC, sujeito a incerteza; não equivale a ticks ou cotações executáveis.
- Risco nominal por entrada M1 0,25% e M5 0,50% de capital corrente; quantidade dimensionada pelo prejuízo estimado completo até o stop (incluindo taxa nos dois lados e slippage), e limitada ao caixa disponível após comissão, sem exposição nocional acima de 1× no livro individual.
- Trava de novas entradas após perda diária MTM de 2% (data America/Sao_Paulo); circuit breaker cumulativo no DD MTM de 10%; os testes não garantem limite absoluto diante de gaps. PortfolioGate isolado bloqueia múltiplas posições no mesmo ativo, dados stale, sincronização defeituosa, mais de duas exposições e notional compartilhado >60% ou cluster BTC/ETH >40%: **não está conectado aos robôs operacionais**.
- Sem ordens reais, sem Telegram por operação, sem credenciais de corretora e sem mudanças em relatórios atuais.

## Validação estatística

Sem ajustar parâmetros ao P&L, particionamento cronológico por mês:
- 22 meses: desenvolvimento meses 1–12; validação 13–18 (três janelas walk-forward de dois meses); final intocado até primeiro replay meses 19–22.
- Cada fold opera em caixa novo, mas indicadores leem apenas prehistória (exclusivamente passada). Final usa a mesma política congelada. Repetir ou ajustar depois de observá-lo **desqualifica chamá-lo de holdout intocado**.
- Comparação com buy-and-hold spot com custos, caixa e crossover simples EMA20/50 na mesma janela. Comparação breakout imediato versus reteste.
- Relatórios: operações completas em CSV, fonte e SHA256 de cada ZIP, wins/losses, retorno líquido, PF, DD MTM, meses/regimes, custos, day-block bootstrap de 95% quando amostra permite, n efetivo aproximado com autocorrelação lag1 e proporção dos três maiores ganhos. Sharpe/Sortino somente com >=60 retornos diários.
- **APTO PARA PAPER FORWARD** apenas quando: lucro líquido positivo nas três estruturas de custos em final; PF>1,20; >=80 trades e n efetivo>=60; intervalo bootstrap com limite inferior positivo; DD<10%; sem circuit breaker; pelo menos duas janelas de três positivas; sem concentração >50% dos ganhos brutos positivos em apenas três operações. Qualquer perda líquida de final/stress => REPROVADO. Amostra insuficiente ou estatística fraca => INCONCLUSIVO.
- Regras de aprovação são gates **iniciais de pesquisa**, não inferência de lucratividade futura ou controle formal de multiplicidade dos seis modelos e dois mercados. Mesmo aprovados precisariam paper forward independente de 30–60 dias, validação de custos e latência antes de qualquer consideração de promoção.

## Reproduzir

Executar testes offline (somente standard library Python 3.11+):

    python -m unittest discover -s tests -p "test_nexus_m1m5_lab.py" -v

Para relatório longo real (rede necessária para baixar arquivos oficiais):

    python -m research.nexus_m1m5.run --end 2026-10 --months 22 --out artifacts/nexus-m1m5

A PR aciona workflow separado: testes offline e backtest real de 22 meses. Arquivo artifacts/nexus-m1m5/REPORT.md contém ranking **exclusivamente pela resistência líquida aos custos**, results.json os registros por cenário/fold e trades.csv cada trade fechado. Os resultados ficam no artifact GitHub Actions por 30 dias, não em state/ nem no Telegram. Se o servidor Binance ou checksum não responder, o job falha e nenhuma métrica será publicada.

## Limitações a resolver antes de forward paper

1. Confirmar execução verde CI e relatórios reais completos do download.
2. Investigar sensibilidade de parâmetros em janelas de desenvolvimento SEM repetir o teste final; para novas mudanças é necessário novo período futuro.
3. Execução prospectiva M1 requer serviço contínuo com WebSocket oficial, reconexão, logs de atraso, idempotência e persistência; cron de Actions não garante candle M1.
4. Monitorar correlação e exposição quando construir um motor paper compartilhado; atualmente os replays são livros independentes.
5. Ordem de evento intrabar e execução de ordens limitadas continuam aproximadas por OHLC e cenário adverso. Custos estimados não são fills.
