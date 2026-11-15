# AlphaXAU INDICADOR v1.06 — correção da compilação
**Defeito encontrado na imagem do MetaEditor:** nas linhas 340–343, a variável local foi nomeada `final`, palavra reservada da linguagem MQL5. Os 7 erros exibidos são compatíveis com erros encadeados de parsing. Corrigido para `requestPath` sem modificar a API `FileMove`.

## Instalação rápida
1. Baixe `AlphaXAU_Indicador_v1_06_CORRIGIDO.mq5` pelo ícone de download do GitHub.
2. No MetaEditor, abra a pasta do arquivo antigo `AlphaXAU_Indicador_v1_06.mq5`, substitua o arquivo pelo corrigido (se necessário, renomeie o novo com o mesmo nome do antigo).
3. Feche e reabra o arquivo **que está na pasta MQL5/Indicators**, então pressione **F7**.
4. Confira a saída do compilador. Se não constar `0 errors`, envie o painel completo de erros com número da linha.
5. O arquivo é INDICADOR, não EA. Não envia ordens; a consulta exige a bridge PowerShell v1.06 e Ollama `llama3.2` já ativos.

A correção foi submetida a 23 testes estáticos, incluindo regressões sobre não negociação, pivôs confirmados, timeframe atual, interface Ollama e ausência de palavra reservada `final` como identificador. **Ainda não foi possível compilar no MetaEditor do Windows a partir deste ambiente.**