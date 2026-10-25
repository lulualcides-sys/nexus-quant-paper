## NEXUS Futebol: resumo multimercado diário às 00h01 (25/10/2026)

- O mesmo bot [@NexusQuantAlertasBot](https://t.me/NexusQuantAlertasBot) passa a enviar **um relatório esportivo por dia**, agendado para **00h01 America/Sao_Paulo** (03h01 UTC). É o fechamento **do dia anterior**; GitHub Actions pode atrasar.
- Origem: arquivo bruto gratuito `market-history/AAAA-MM-DD.json` da branch `market-telegram-data` no [NEXUS SCORE](https://github.com/lulualcides-sys/nexus-score-gratis/tree/market-telegram-data/market-history). O monitor Quant lê somente a coleta, sem credenciais adicionais nem novos acessos a casas.
- Mostra total de jogos, odds verificadas, casas, diversidade de mercados, liquidez comprovada **≥ R$ 3 mil** e resultados separados em **amostra qualificada** e **amostra geral**. Liquidez sem valor, origem, tipo e moeda BRL é **desconhecida**, nunca aprovada por suposição.
- O código do Quant financeiro (10 robôs de ouro em simulação) e o respectivo relatório em dias úteis permanecem **separados e inalterados**; o horário 00h01 vale para o relatório *futebol*.
- Nenhuma coleta tenta contornar proteção anti-bot, autenticação, bloqueio regional, paywall ou cotas. Backtests e ganhos reais não são inferidos de placares.
- Código: [resumo](src/nexus_football_daily.py) · [auditoria de histórico](src/nexus_football_archive.py) · [workflow](.github/workflows/nexus-football-daily.yml).

---

# Nexus Quant Paper — monitor gratuito

## Stop móvel de green — Grupo B (25/10/2026)

**Ativado exclusivamente nas PRÓXIMAS posições VIRTUAIS dos cinco robôs alavancados.** As posições já abertas preservam a política na qual entraram; nenhuma operação real na FBS foi criada.

- Ao atingir **+1R de movimento favorável**, no fechamento do candle H4, o stop avança para acima do preço de entrada (ou abaixo nas vendas), incluindo uma margem estimada para custos e juros.
- A partir de **+1,5R**, o stop acompanha o melhor preço favorável a **1R de distância**. Nunca afrouxa.
- O take-profit fixo é retirado **somente das novas posições do Grupo B**, para permitir capturar tendências maiores. Há saída por stop ou tempo máximo (90 candles H4).
- O ajuste feito com o candle fechado **só vale para o próximo candle**. O algoritmo não inventa ordens executadas dentro do candle do gatilho. Continua usando o mesmo nível de risco-stop planejado (1,50%) e exposição virtual 2×.
- **Stop no green não garante lucro:** gaps, deslizamentos, aumento de custos, financiamento e indisponibilidade da fonte podem provocar prejuízo.

**Comparação A/B auditada no mesmo conjunto de preços** — 24/10/2025 a 24/10/2026, cinco robôs, US$ 25.000 virtuais: stop fixo **+US$ 1.548,57**, green mantendo o alvo **+US$ 1.548,95**, green runner **+US$ 2.790,99** e green mais folgado **+US$ 2.677,02**. Valores exclusivamente simulados; três robôs melhoraram e dois renderam menos com o runner. O período já havia sido analisado, portanto **não comprova vantagem futura**. Cotações públicas de futuros GC=F são mutáveis; o arquivo de auditoria inclui a impressão digital da série utilizada. O backtest de stop fixo anterior foi recalculado e convergiu para +US$ 1.548,57 na série mais recente.

[Relatório A/B completo](research/results/group_b_green_stop_ab.md) · [Todas as negociações e resultados](research/results/group_b_green_stop_ab.json) · [Implementação](src/green_stop.py).

---


## Copa de 10 robôs — dois grupos independentes (25/10/2026)

O monitor automático usa **dez bancas de pesquisa**, US$ 5.000 virtuais em cada uma (US$ 50.000 virtual no total), operando **apenas no ouro H4**. Os outros quatro mercados continuam observados para futuras pesquisas. Nenhuma ordem é enviada à FBS.

**Grupo A — 5 convencionais, sem empréstimo nocional:** RSI Trend, Channel 20, Pullback 20, Momentum 100, Channel 55. Risco-stop planejado de **0,75% por ordem**, exposição máxima de **1×** o capital da banca. Histórico original `state/selected_gold_v2.json` preservado e algoritmo de duração de posição corrigido para reinícios.

**Grupo B — 5 experimentais com maior risco e capacidade de alavancagem:** Channel 20 L, Momentum 100 L, Channel 55 L, Momentum 40 L, Trend Long L. Risco-stop planejado de **1,50% por ordem** (2× o grupo A), **exposição virtual efetiva de 2×** o patrimônio em cada nova entrada (com teto de segurança de 3×). Assim, para US$ 5.000, a exposição nocional será aproximadamente US$ 10.000. É uma dívida hipotética de aproximadamente US$ 5.000: não existe empréstimo real nem corretora conectada. O stop se ajusta para limitar a perda planejada antes de gaps, taxas e financiamento.

Proteções do grupo B: stop na menor distância entre 2 ATR e o risco planejado (aproximadamente 0,75% do preço quando a exposição é 2×), alvo de 1,75 vez essa distância, duração de até 90 candles H4, custos estimados de ida e volta de 14 pontos-base, financiamento teórico de **8% ao ano sobre o valor emprestado**, bloqueio de novas entradas no dia após **3%** de perda realizada e pausa permanente de novas entradas após **15%** de drawdown realizado. Essas travas **não garantem** perdas limitadas: gaps, custos ou mercados que se movem rapidamente podem ultrapassar o stop. Riscos são maiores que no grupo A e nenhuma estratégia está aprovada para dinheiro real.

Os cinco novos livros são persistidos em `state/leveraged_gold_v1.json`. **A primeira execução inicia as bancas no momento atual sem inventar operações antigas.** O relatório diário do [@NexusQuantAlertasBot](https://t.me/NexusQuantAlertasBot) compara **os 10 robôs**, separando resultados do dia (fechamentos), acumulados e operações abertas. Agendamento de segunda a sexta aproximadamente **19h15 (America/Sao_Paulo)**, sujeito a atrasos/ausência de execução do GitHub Actions.

A classificação é pelo **lucro líquido virtual realizado**, não por lucro real. Resultados positivos podem desaparecer na frente, e operar ouro com dez estratégias não equivale a diversificar em dez ativos.

[Workflow do monitor](.github/workflows/monitor.yml) · [Grupo A](src/gold_forward.py) · [Grupo B](src/leveraged_gold.py) · [Relatório](src/daily_digest.py).

---

## Pesquisa V3 — seleção tipo tipster esportivo (25/10/2026)

**Foco: lucro líquido verificado pelo preço observado, não só taxa de acerto.**

- Auditoria de **50 combinações**: 10 estratégias x cinco mercados, candles diários (D1), cerca de cinco anos de dados.
- Desenvolvimento (2022-07 a 2023-12), validação (2024), revisão retrospectiva (2025 a 2026-10-24).
- Custos incluídos, teste com taxas dobradas, drawdown, lucro por período, número de operações e perdas também publicados.
- A revisão mais recente **não é um holdout intocado**, pois esses anos já foram consultados anteriormente. Sem garantia futura.
- Ouro RSI Trend D1: desenvolvimento +1,26%, validação +4,32%, revisão 2025–26 +2,13%. US500 Momentum 120 D1 passou nos critérios iniciais, mas ficou -1,59% na revisão.
- Importante: **as simulações antigas de USD/JPY tinham P&L em JPY rotulado como USD**. A pesquisa V3 corrige a conversão. Resultados antigos de USD/JPY não devem orientar decisões.

Separadamente, um teste de sensibilidade **sem trocar as estratégias** avaliou o ouro H4 com risco de 0,5%, 0,75% e 1,0% por entrada. A modalidade prospectiva virtual opera agora com risco de **0,75%**, sem dinheiro real. Aumentar risco pode ampliar tanto ganhos quanto prejuízos e não corrige um modelo ruim.

Relatórios: [V3 50 combinações](research/results/regime_research_v3.md) · [Todos os dados V3](research/results/regime_research_v3.json) · [Sensibilidade de risco H4](research/results/gold_risk_sensitivity.md).

**Critério de investigação futura:** comparar resultados líquidos e custos, amplitude da perda, taxa de acerto, volume de sinais, tolerância ao dobro do custo e meses favoráveis/contrários. É permitida perda mensal. Nenhuma estratégia recebe aprovação para dinheiro real sem histórico prospectivo suficiente e exame da regulação aplicável. Os cinco mercados continuam sob observação; só os cinco modelos de ouro H4 têm livros virtuais de pesquisa separados.

---

## Pesquisa v2 — seleção por robustez (25/10/2026)

A primeira seleção de cinco estratégias H1 foi reprovada em backtest. Elas continuam identificadas como **LEGADOS NÃO APROVADOS** no diagnóstico.

A nova pesquisa testou **11 estratégias x cinco mercados = 55 combinações** em candles completos de 4h, com custos estimados, risco de 0,5% do saldo por sinal e limite nocional de 2x. Critério de seleção: apenas dados de 24/10/2024 a 23/10/2025; checagem em 24/10/2025 a 24/10/2026. A checagem posterior não é um holdout totalmente desconhecido, pois o período já havia sido examinado antes.

Os cinco escolhidos por desempenho no treino foram `rsi_trend`, `channel20`, `pullback20`, `momentum100` e `channel55`, todos para **ouro**, pois os quatro demais mercados não demonstraram robustez suficiente no conjunto selecionado. **Não implica que ouro nunca dará prejuízo: os cinco modelos são correlacionados e podem perder ao mesmo tempo.**

Resultados posteriores, cada um com US$ 5.000 independentes (backtest e não operações executadas na FBS):
- RSI Trend: +1,44%.
- Channel 20: +7,80%.
- Pullback 20: +1,31%.
- Momentum 100: +5,59%.
- Channel 55: +4,67%.

O sistema prospectivo `src/gold_forward.py` iniciou seus livros virtuais independentes do zero, **sem registrar operações históricas como se tivessem acontecido em produção**. Os demais quatro mercados permanecem em observação. Só sinais futuros e valores virtuais após custos aproximados aparecerão no relatório diário; nenhuma ordem real é enviada à FBS.

[Relatório integral das 55 combinações](research/results/strategy_screen_v2.md) · [Dados e operações de todos os candidatos](research/results/strategy_screen_v2.json) · [Política de seleção](research/config/paper_cohort.json)

---


Cinco robôs de sinais em cinco mercados, **sem conexão com FBS, sem operações executadas e sem resultados de lucro inventados**.

**Mercados:** EUR/USD e USD/JPY (câmbio indicativo), ouro GC=F, S&P 500 ES=F e petróleo WTI CL=F (três contratos futuros usados como proxies, não CFDs FBS).

**Robôs:** Trend Hunter (Donchian 55), Breakout Pro (Donchian 20), Reversal RSI, Momentum X e Pullback Master.

O sistema observa somente candles de uma hora já fechados e registra sinais prospectivos. Após seis candles posteriores, classifica cada sinal como favorável, contrário ou neutro. Esses números **não equivalem a lucro/RED em uma conta da corretora** e não incluem spread, taxas, liquidez ou execução.

## Ativar Telegram pelo celular

1. Abra o [@NexusQuantAlertasBot](https://t.me/NexusQuantAlertasBot) e envie **/start**. Se já iniciou, envie /start de novo antes do primeiro teste.
2. Abra [Settings > Secrets and variables > Actions](https://github.com/lulualcides-sys/nexus-quant-paper/settings/secrets/actions) neste repositório pelo navegador logado no GitHub.
3. Toque em **New repository secret**. Em **Name**, digite exatamente `TELEGRAM_BOT_TOKEN`; em **Secret**, cole o token recebido do @BotFather e salve. Não coloque o token em README, Issues, mensagens ou arquivos públicos.
4. **Não precisa cadastrar `TELEGRAM_CHAT_ID`.** O GitHub Actions procura uma conversa privada recente iniciada com o bot, envia uma confirmação e salva o ID criptografado em `state/telegram_chat.enc.json`. Se houver mais de uma conversa, será necessário definir `TELEGRAM_CHAT_ID` manualmente como Secret.
5. Abra [Actions](https://github.com/lulualcides-sys/nexus-quant-paper/actions), selecione **Nexus Quant | Five markets**, **Run workflow**, escolha `report` e execute. Consulte os logs da execução. O relatório pode inicialmente indicar que não há novos sinais; isso é normal.

Se o bot não encontrar sua conversa, **envie /start novamente no Telegram após salvar o token**. O GitHub Actions verifica a conexão automaticamente a cada hora e envia uma única confirmação quando encontra sua conversa. Uma mensagem antiga pode não estar disponível porque o Telegram retém updates por no máximo 24 horas, ou porque outro cliente já os confirmou. O arquivo de configuração no repositório armazena apenas a versão criptografada do ID; a chave deriva do token secreto.

## Funcionamento

- Scans periódicos aproximadamente a cada quatro horas em dias úteis (GitHub Actions pode atrasar).
- Verificação de autorização do Telegram a cada hora. Após a primeira confirmação, nenhuma nova mensagem de conexão será enviada.
- Um relatório agendado às 19h15 (horário de São Paulo), dias úteis. A mensagem só é enviada se as cinco fontes fornecerem dados válidos; caso contrário o workflow falha e não inventa números.
- Histórico prospectivo e relatórios são gravados em `state/` e `reports/`.
- Primeira execução apenas inicializa os pontos de partida. Histórico anterior nunca é rotulado como sinal produzido ao vivo.
- O endpoint Yahoo Finance utilizado é **não oficial** e pode ficar temporariamente indisponível.
- Não conectar contas reais nem usar esses sinais para investir sem verificação independente.

## Testes

```bash
python -m pip install cryptography
python -m unittest discover -s tests -v
python -m src.runner --mode scan
python -m src.runner --mode report
```

**Gratuidade:** GitHub Actions em repositórios públicos com runners padrão é gratuito dentro da política de uso do GitHub. Os alertas não exigem VPS, depósito na FBS ou computador ligado.

Fontes: [GitHub Actions](https://docs.github.com/en/actions/concepts/billing-and-usage) · [Telegram Bot API](https://core.telegram.org/bots/api).
