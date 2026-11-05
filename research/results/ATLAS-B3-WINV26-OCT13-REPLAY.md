# ATLAS — replay verificável do WINV26 em 13/10/2026 por negócios B3

**Status:** importador off-line de negócios, sem dados reais importados nesta PR. Não é o indicador Tracker e não comprova nenhuma de suas 27 setas promocionais.

## Fonte mais promissora

- Página de [Pesquisa por pregão — B3](https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/historico/boletins-diarios/pesquisa-por-pregao/pesquisa-por-pregao/).
- Prioridade: arquivo B3 de negócios individuais de derivativos/listados para **13/10/2026**, contrato **WINV26**, e não WINQ26 ou WINZ26.
- A página B3 informa **proibição de coleta automatizada, inclusive por IA**. Este repositório **não realiza downloads nem solicita URLs não divulgados de API da B3**. Obtenha o arquivo manualmente, quando disponível, ou por fonte licenciada com permissão. A disponibilização histórica depende da política atual da fonte.
- Alternativa permitida: exportação genuína M1 do Profit/MT5, processável pelo módulo `research/atlas_win_oct13.py`. Esse CSV agrega OHLCV e **não resolve** a sequência intraminuto das negociações.

## Como executar, se tiver o arquivo original

O arquivo fornecido deve conter, no mínimo, as colunas listadas:

```text
DataReferencia;CodigoInstrumento;AcaoAtualizacao;PrecoNegocio;QuantidadeNegociada;HoraFechamento;CodigoIdentificadorNegocio;TipoSessaoPregao;DataNegocio
```

O arquivo pode conter todos os contratos; somente negócios do **WINV26 em 13/10/2026, sessão regular**, são agregados. O módulo ignora períodos sem negócios (não inventa candles). Eventos de **cancelamento** são removidos com base no identificador oficial do negócio, mesmo se aparecerem em ordem distinta no arquivo; registros desconhecidos, duplicados ou cancelamentos sem negócio original geram erro e bloqueiam resultado.

```bash
python -m unittest discover -s tests -p 'test_atlas_b3_ticks_oct13.py' -v
python -m research.atlas_b3_ticks_oct13 --b3-file /caminho/manual/DRV_20261013.zip
```

Se, e **somente se**, existirem setas verificadas em gravação contínua do Tracker com horário **do mercado**, direção e evidência de formação após fechamento, fornecer um CSV separado (o tempo de reprodução do vídeo não é o horário de negociação):

```text
date,market_time,side,evidence_url,observed_after_close
2026-10-13,10:25:00,buy,https://url-publica-exemplo/registro,yes
```

```bash
python -m research.atlas_b3_ticks_oct13 --b3-file /caminho/manual/DRV_20261013.zip --tracker-labels /caminho/labels_verificadas.csv
```

O exemplo de linha acima é **apenas esquema ilustrativo**. Não é uma seta real e não deve ser inserida na execução do backtest.

## Critérios de integridade e rejeição

- As cotações de WIN precisam respeitar 5 pontos por tick. Unidade de `QuantidadeNegociada` = contratos, não `Volume` financeiro.
- Horário dos negócios `HoraFechamento` no formato `HHMMSSmmm`, interpretado em `America/Sao_Paulo`; ordenação por milissegundo e desempate pelo identificador do negócio.
- Padrão aceito: `AcaoAtualizacao=0` (negócio válido), `2` (cancelamento conforme fixture de documentação). Outros valores impedem calcular até serem interpretados por documentação oficial.
- Para toda a sessão-alvo é exigida cobertura de pelo menos 400 candles M1 **com negócios**; mínimo heurístico de qualidade, não prova de completude. É necessária auditoria adicional de sequência, leilões e operações faltantes.
- Em `research/atlas_b3_ticks_oct13.py` o resultado antes de haver setas verificáveis será `awaiting_verified_tracker_labels`, sem winrate nem P&L.
- O uso de negócios históricos corrigidos por eventos de cancelamento não informa **quando** um assinante em tempo real poderia ter percebido a correção; não afirmar equivalência entre replay e execução real.
- Tocar no preço não comprova execução de ordem limite na corretora; seriam necessários book/volume na fila, latency e logs de execução.

## Descobertas existentes

- PR #22: backtest em WINQ26 do 1º semestre, **0 de 25 cenários promovidos**; nenhum demonstrou edge robusta.
- PR #23: importador Profit do WINV26, dependente de dados M1 do pregão específico e das setas rotuladas do Tracker.
- Esta PR: importador adicional dos próprios negócios, com testes sintéticos de cancelamento/ordem/tick e prova de não preenchimento de candles fictícios.
- **Não foi obtida a fórmula fechada do Tracker nem a série real negociada de 13/10/2026**, e nenhum resultado promocional foi auditado.

## Integração e restrições

Esta PR deve alterar **apenas** arquivos em `research/`, `tests/` e um workflow de CI. Não modificar estados, motor paper prospectivo, 27 outros robôs, pagamentos, corretora ou automações.
