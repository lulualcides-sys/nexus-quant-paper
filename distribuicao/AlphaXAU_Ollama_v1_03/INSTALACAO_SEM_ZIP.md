# AlphaXAU + Ollama v1.03 — instalação sem ZIP

Esta pasta contém o arquivo **Nexus_AlphaXAU_Ollama_Decisoes_v1_03.mq5** do pacote já entregue no ChatGPT. É o EA completo para conectar a interface do gráfico ao modelo Ollama já instalado no computador.

1. Abra o arquivo .mq5 no GitHub e clique no ícone **Download raw file** (canto superior direito do arquivo).
2. No MetaTrader 5: **Arquivo > Abrir Pasta de Dados**.
3. Na pasta aberta, crie `MQL5/Experts/NexusAlphaXAU_Decisoes_v103/` e mova o arquivo .mq5 para dentro.
4. Abra MetaEditor (`F4`), localize o arquivo no Navegador, abra-o e compile com **F7**, confirmando zero erros. Se falhar, envie a lista completa dos erros.
5. Em MT5: **Ferramentas > Opções > Expert Advisors**, marque *Permitir WebRequest para URLs listadas* e adicione `http://127.0.0.1:11434`.
6. Abra o gráfico XAUUSD M15, em Navegador > Experts, adicione `Nexus_AlphaXAU_Ollama_Decisoes_v1_03`.
7. Confira `InpOllamaModel=llama3.2`, `InpEnableIA=true`, `InpRecordEveryM15=true`, `InpTradingEnabled=false` e `InpAllowReal=false`.
8. O Ollama deve estar em execução no Windows; ele já foi instalado/testado pelo usuário. A cada novo candle M15 fechado o EA deverá consultar o modelo e registrar a decisão em `Terminal/Common/Files/NexusAlphaXAU/` (no Windows, em `%APPDATA%/MetaQuotes/Terminal/Common/Files/NexusAlphaXAU/`).

**Segurança:** as decisões da IA não enviam ordens; negociação real continua bloqueada. O arquivo .mq5 dispensa o ZIP para uso do painel e registro ao vivo; a validação histórica por Python depende dos scripts adicionais contidos no pacote ZIP separado.

**Verificação:** o código foi comparado com o arquivo fonte do pacote do ChatGPT; código MQL5 ainda não compilado nem testado na instalação do usuário.
