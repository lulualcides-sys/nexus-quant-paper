# Nexus Quant Paper — monitor gratuito

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
