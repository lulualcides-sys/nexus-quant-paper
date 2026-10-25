# Nexus Quant Paper — monitor gratuito

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
