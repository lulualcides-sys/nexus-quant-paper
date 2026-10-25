# Nexus Quant Paper — cinco mercados, cinco estratégias

Monitor público de sinais com preços observados, **sem ordens na FBS e sem lucros fictícios**.

Mercados: EUR/USD, USD/JPY, ouro (futuro GC como referência), S&P 500 (futuro ES) e petróleo WTI (futuro CL).

Cinco estratégias: Trend Hunter, Breakout Pro, Reversal RSI, Momentum X, Pullback Master. Cada sinal é acompanhado por seis candles fechados posteriormente; o resultado é **direcional** e não equivale a uma operação executada.

### Telegram
1. Inicie a conversa privada com o bot usando `/start`.
2. Em **Settings → Secrets and variables → Actions**, crie `TELEGRAM_BOT_TOKEN` com o token do BotFather. Nunca publique o token.
3. Crie também `TELEGRAM_CHAT_ID` com seu ID numérico da conversa, quando conhecido. O programa pode tentar identificá-lo quando existe exatamente uma conversa privada iniciada com `/start`.
4. Execute o workflow manualmente pelo menu **Actions** no GitHub para testar; resumos são programados para dias úteis.

A publicação do código não confirma que o Telegram esteja autorizado nem que existam lucros realizados.
