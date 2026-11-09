# WIN Price Action M1/M5 — protótipo isolado (09/11/2026)

**Situação: pesquisa offline PAPER-ONLY, não validada para dinheiro real.**
Não altera o ATLAS, os 27 robôs, o monitor diário ou estados existentes. Não envia ordens ou notificações.

## Regras implementadas

- Fonte: CSV real Profit M1, um contrato WIN por arquivo, validado pelo importador existente research/win_price_data.py.
- Contexto M5: apenas candles completos; classifica tendência de alta, baixa, lateralização ou mercado misto.
- Alta: identifica micro-LTD descendente com dois pivôs de máxima confirmados; exige fechamento M1 além da linha e rompimento da máxima estrutural recente, seguido de reteste em até 4 candles. Baixa: critérios inversos para micro-LTA.
- Lateralização: exige duas visitas a cada extremidade da faixa das últimas 12 velas M5 e rejeição no M1. Não opera no meio da faixa.
- Não compra/vende apenas porque tocou a linha, nem entra em rompimento sem reteste.
- Fibonacci é filtro automático opcional e experimental (38,2%, 50%, 61,8%) — **não é a marcação manual do usuário**.
- Entrada simulada na abertura da vela seguinte à confirmação. Não assume que um candle histórico proporcionou execução antes de existir sinal.
- **Somente uma posição por vez**: no máximo 1 contrato WIN em aberto. Após a saída, volta a avaliar oportunidades de entrada, sem empilhar ordens na mesma posição.
- Banca de referência R$2.000, orçamento de risco inicial **1% por operação (R$20), incluindo custos estimados**. **Sem limite de perda diária nem bloqueio por sequência de stops**, conforme solicitado. A cada nova oportunidade o risco técnico deve continuar cabendo no orçamento; sem margem/risco viável, não abre posição.
- **Stop Red** (stop-loss): stop técnico além do extremo do reteste; **Stop Win** (take-profit): alvo inicial 2R, limitado ao extremo oposto na lateralização e exigindo no mínimo 1,5R de espaço. Se stop e alvo forem tocados no mesmo candle, contabiliza o stop prioritariamente. Uma posição fechada permite procurar nova oportunidade.
- **Risco relevante:** sem trava diária, uma sequência de sinais perdedores pode consumir toda a banca. O stop não garante execução no preço e o risco realizado pode superar 1%. Essa configuração é somente para simulação até comprovar robustez.
- Custos de pesquisa **estimados**: R$4 ida e volta + slippage de um tick por lado = R$6 por negócio. Não são custos verificados junto à corretora.
- Se faltar dado real, não inventar operações, lucro, win rate ou resultado de backtest.

## Uso

Exportar um CSV nativo M1 do Profit com as colunas Ativo;Data;Hora;Open;High;Low;Close;Volume. Não concatenar vencimentos nem criar candles ausentes.

~~~bash
python -m unittest discover -s tests -p 'test_win_price_action.py' -v
python -m research.win_price_action --win-csv /caminho/WIN_M1.csv --out research/results/win_price_action_local.json
python -m research.win_price_action --win-csv /caminho/WIN_M1.csv --fibonacci --out research/results/win_price_action_fib_local.json
~~~

O arquivo de saída é um ledger de operações simuladas com custos e drawdown realizado, **não relatório de lucro garantido**.

## Antes de permitir paper prospectivo

1. Adquirir dados históricos genuínos e auditáveis, com contrato, horário, fonte e rolagem identificados.
2. Congelar parâmetros e comparar períodos de desenvolvimento e teste fora da amostra, sem reotimização no teste.
3. Avaliar rompimento/reteste e lateralização em separado; calcular expectancy líquida, PF, MDD e sensibilidade ao custo.
4. Recolher ao menos 100 operações por setup, múltiplos pregões e regimes, depois paper forward com logs de timestamps de sinal e execução.
5. Avaliar aderência das marcações automáticas às marcações humanas e reproduzir custos de corretora, spread e slippage. Somente depois avaliar integração com corretora.

## Limitações

LTA/LTD e zonas automáticas não reproduzem perfeitamente uma marcação humana; regime M5 é heurístico; OHLC M1 não prova fila ou ordem intrabar dos negócios; stops podem sofrer slippage maior e perdas além do orçamento. Código não utiliza dados futuros na identificação dos sinais.
