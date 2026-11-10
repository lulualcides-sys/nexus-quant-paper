# Pesquisa de ferramentas GitHub e fontes de negócios WIN — 09/11/2026

**Objetivo:** melhorar a detecção independente de exaustão/absorção no WIN sem confundir publicidade do Tracker com dados reais, sem copiar código fechado e sem alterar robôs aprovados.

## 1. Descoberta urgente: exportação nativa Profit pode atender aos dias 03 e 04/11

- [Nelogica — como exportar dados históricos](https://ajuda.nelogica.com.br/hc/pt-br/articles/360044287672-Como-exportar-dados-hist%C3%B3ricos-de-ativos-para-o-Excel) informa limite de **8 dias para intervalo de Trades do mini-índice WIN**. Na data de 09/11/2026, os dias 03 e 04/11 são recentes e devem ser verificados imediatamente no Profit, sujeito à janela efetiva, limite exibido e versão contratada. Não pressupor que o usuário tenha Profit.
- [Nelogica — Times & Trades](https://ajuda.nelogica.com.br/hc/pt-br/articles/360054569632-Times-Trades): a aba Negócios apresenta negócios com data/preço/quantidade e agressor, nativa na versão Pro/Ultra. A disponibilidade de dias depende da atividade de cada instrumento e pode variar.
- [Nelogica — produtos](https://www.nelogica.com.br/produtos/): lista exportações CSV Times & Trades e CSV Agressor em sua matriz de recursos. **Não foi confirmada a estrutura exata de um CSV emitido por uma instalação Profit Pro específica.**
- **Distinção crítica:** a exportação padrão de candles OHLCV não contém necessariamente o lado agressor. Mesmo que a tela Times & Trades o exiba, só é utilizável para delta se o arquivo local de negócios fornecer explicitamente uma coluna Agressor e registros individuais. Nosso importador rejeita a ausência, sem deduzir direção pelo candle ou por cores de tela.
- Nem REA nem GitHub podem operar a instalação Windows particular do usuário neste chat; não existe acesso remoto autorizado à conta de Profit/Rico, nem foi encontrado CSV real disponível aos conectores. O passo de exportar ou habilitar o feed é uma dependência externa genuína.

## 2. GitHub avaliado, critérios de custo e licença

| Projeto | Evidência | Valor imediato | Restrição / decisão |
|---|---|---|---|
| [milocaetano/quantick](https://github.com/milocaetano/quantick) | Repositório MIT (confirmado via API GitHub); engine Rust de volume/tick/imbalance bars, CVD, replay e bridge MT5 | **Alta**: referência técnica para barras de volume e divergência de agressão | Não instalar sem testes; implementação independente NQ em Python para evitar novo runtime e cópia de arquitetura |
| [diogojrdev/profitdll-wrapper](https://github.com/diogojrdev/profitdll-wrapper) | Repositório MIT (confirmado via API); wrapper Python para dados e históricos ProfitDLL | **Alta** se houver licença válida | ProfitDLL nativa e credenciais Nelogica continuam necessárias. Wrapper também expõe envio de ordens: **não conectar automaticamente** |
| [nicksauro/data-downloader](https://github.com/nicksauro/data-downloader) | Pesquisa mostra downloader ProfitDLL com Parquet e modo local | Médio: alternativa futura para coleta histórica e DuckDB | Sem licença de uso clara nos metadados consultados; não copiar fonte ou distribuir binário; acesso ProfitDLL ainda é obrigatório |
| [klaubeer/trade-scan](https://github.com/klaubeer/trade-scan) | Backtester WIN com slippage, walk-forward e Monte Carlo | Médio para avaliação posterior | O motor candle a candle não recupera agressor de negócios; não usar como verdade para equivalência com Tracker |

**Dados encontrados no GitHub:** a busca por CSV autorizado de WINZ26 dos pregões 03–04/11 com histórico real de negócio/agressor não retornou um arquivo verificável com licença de reutilização. Não usar séries sintéticas, resultados de modelos de terceiros ou prints como se fossem fita de negócios.

## 3. Implementado nesta branch (sem instalar dependências de terceiros)

- `research/win_volume_bars_cvd.py`: engine independente de **barras fechadas por volume executado**, CVD (delta acumulado), fração de contratos com agressor identificável, detecção experimental de exaustão por agressão contrária ao fechamento e divergência de CVD.
- **Não divide transações grandes** em eventos imaginários: se um negócio ultrapassar o limite de volume da barra, a barra encerra com volume excedente real. Última barra incompleta não produz sinal. Barras rejeitam dados sem agressor/classificação mínima.
- O detector exige, por padrão, 500 contratos por barra, 25 prints identificados, fração de volume classificado ≥80%, referência de 8 barras, agressão oposta ≥55% e rompimento/rejeição do extremo recente. São **parâmetros de pesquisa arbitrados**, não os do Tracker e não foram otimizados nos 43 exemplos de publicidade.
- `research/win_profit_timestrades_export.py`: lê CSV local de trades de formato compatível, reconhecendo campos explícitos de data/hora, preço (ou valor negociado por unidade), quantidade e **agressor**; símbolo precisa estar presente ou ser informado explicitamente; numeração de negócios é opcional, mas a falta dela é marcada como **impossibilidade de verificar duplicidades**, nunca tratada silenciosamente como dado íntegro.
- Aceita decimais brasileiros e nomes de colunas usuais, mas não afirma ser compatível com TODOS os layouts de exportação Profit. Um CSV real específico ainda precisará ser validado antes de declarar compatibilidade em produção.
- Usa duas passagens sequenciais pelo CSV para controlar RAM, exige SHA256 idêntico antes/depois da análise, verifica contagem entre passes, recusa vencimentos misturados, ordem cronológica violada, preços fora da grade WIN de 5 pontos, volume inválido ou ausência da coluna agressor.
- `analisar_WIN_fluxo_Profit_timestrades.cmd`: iniciador Windows para arrastar e soltar um CSV local, cria ambiente Python isolado e instala apenas `tzdata` se necessário. Armazena agregados e sinais **somente** em `private_mt5/`, pasta ignorada pelo Git.
- `tests/test_win_volume_bars_cvd.py` e `tests/test_win_profit_timestrades_export.py`: testes focados com dados inventados identificados, incluindo divergência volume/candle, ausência de flags, ausência de trade ID, no-lookahead, volume classificado e risco de duplicar trades.
- `.github/workflows/win-volume-bars-cvd.yml`: suítes separadas Linux/Windows e teste do iniciador CMD. **Somente a conclusão da execução final do CI comprova o estado atual dos testes.**

## 4. Sem atalho artificial para réplica do Tracker

- A investigação anterior com REA demonstrou geometria comercial 50/200/−100 e ausência da fórmula de disparo no site aberto; os 43 exemplos publicados são selecionados retrospectivamente, sem os trades completos do feed.
- Barras por volume podem separar volatilidade de atividade, e CVD/absorção adicionam sinais fisiológicos de microestrutura. Mas são hipóteses próprias a validar com datas futuras e fontes de negócios consistentes; **não são cópia nem prova de identidade de sinais do Tracker**.
- A [B3 veta coleta automatizada no Hub de Dados Públicos](https://www.b3.com.br/pt_br/dados/hub-de-dados-publicos/); portanto não tentar raspar esse portal, nem reutilizar redistribuições de histórico sem verificar licença.
- Com o indicador original privado, só seria possível medir concordância num feed autorizado com timestamps reais de setas, incluindo eventos não selecionados pela propaganda; sem isso, aumentar o número de filtros não resolve a ausência de evidência.

## 5. Próximas ações praticáveis

1. **Primeira prioridade (janela curta):** conferir exportação do WINZ26 nos dias **03 e 04/11/2026** via Profit, se houver versão compatível, ou dados legitimamente contratados. Para obter agressão real, priorizar Times & Trades/CSV com lado Agressor explícito. A exportação comum de candles não serve.
2. Se tiver um CSV com colunas `Ativo,Data,Hora,Valor,Quantidade,Agressor`, arrastá-lo para `analisar_WIN_fluxo_Profit_timestrades.cmd` na pasta de projeto. Se faltar contrato/dia no arquivo, utilizar os argumentos `--symbol WINZ26 --date 2026-11-03` do módulo Python, sem edição dos dados.
3. Conferir no relatório privado `private_mt5/nq_profit_tape_analysis.json` dados válidos, CVD e sinais independentes. Não publicar CSV real licenciado no GitHub. O histórico real permanece local.
4. Só depois comparar as setas inéditas em horários e direções com capturas autorizadas do Tracker, mantendo uma amostra não vista para teste. Fazer replay conservador, custos reais da Rico, MDD, slippage e risco de 1 contrato WIN antes de considerar qualquer trade simulado, e nunca autorizar operação real automaticamente.

**Estado:** implementação de pesquisa isolada. Sem cópia proprietária, sem compra de licença, sem dados reais de Rico/Nelogica, sem execução de ordens e sem mudança na main.
