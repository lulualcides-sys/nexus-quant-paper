# ATLAS — importação de negócios B3 com RAM controlada

**Data:** 05/11/2026. Esta alteração substitui o agregador que acumulava todos os negócios WINV26 na RAM por um **replay local de duas passagens**.

## Motivação

O arquivo de negócios individuais de um pregão da B3 pode ter milhões de registros e centenas de MB descompactados. A implementação anterior construía um dicionário Python com todos os negócios e depois uma segunda lista contendo-os ordenados. Em dados reais esse crescimento pode consumir vários GB de RAM.

O código `research/atlas_b3_streaming.py` é agora invocado por `research/atlas_b3_ticks_oct13.parse_b3_trades` sem alterar a interface pública das funções de comparação de setas.

## Abordagem

- **Primeira passagem:** percorre o arquivo TXT/CSV ou o único TXT do ZIP local, filtra WINV26 em 13/10/2026, identifica ações `0`/negócio e `2`/cancelamento conforme [glossário oficial B3](https://www.b3.com.br/data/files/14/42/28/31/FEC4A8103234E0A8AC094EA8/Glossario_NegociosListados_PT.pdf). Armazena apenas os identificadores dos negócios cancelados.
- **Segunda passagem:** exclui os IDs cancelados mesmo quando foram corrigidos após o horário de sessão, valida preço/quantidade/tick e ordenação por horário + ID. Para evitar manter todos os identificadores de negócios na memória, verifica duplicatas em um **banco SQLite local temporário com chave primária**; não envia nada a servidores nem mantém a base ao concluir.
- **Agregação:** guarda uma linha acumulada por minuto negociado (abertura, máxima, mínima, fechamento, quantidade de contratos e número de negócios). Atualiza primeiro e último negócios com comparação de timestamp completo e ID. Não inventa negócios em minutos vazios.
- **Proveniência:** conserva hash SHA256 do arquivo de entrada, nome do membro ZIP e contadores. Marca que os cancelamentos são identificados retrospectivamente e que a origem ainda não foi auditada independentemente.
- **Falha fechada:** cabeçalho inválido, ação desconhecida, preços fora do tick, IDs repetidos ou cancelamentos sem origem causam erro.

## Custos e limitações

- O método reduz a memória de **O(número de negócios)** para **O(número de cancelamentos + minutos negociados)**, com índices de unicidade guardados **em disco**. Isso é uma característica de arquitetura do algoritmo, não um benchmark de performance verificado em B3 real.
- Há maior custo de E/S: hash do arquivo, duas leituras do arquivo de negociação, criação de índice temporário SQLite.
- Não foi obtido nem executado nesta PR um arquivo real do pregão WINV26 de 13/10/2026: **não afirmar throughput em milhões de trades, P&L, precisão do Tracker ou sucesso da replicação**.
- Um cancelamento conhecido somente depois do fechamento altera a reconstrução histórica corrigida; ela não é idêntica ao gráfico que o assinante viu ao vivo.
- A extração da B3 continua **manual ou licenciada**: o código não acessa o site B3 nem automatiza a coleta.
- Os resultados históricos dos 27 outros robôs e o motor ATLAS paper prospectivo não foram alterados.

## Testes reproduzíveis

```bash
python -m unittest discover -s tests -p 'test_atlas_b3_streaming.py' -v
python -m unittest discover -s tests -p 'test_atlas_b3_ticks_oct13.py' -v
python -m unittest discover -s tests -p 'test_atlas_tracker_observability.py' -v
```

Os cinco testes novos incluem lote sintético de 20.000 negócios, cancelamento após pregão, duplicatas com zeros à esquerda, ordenação em milissegundos e ZIP. O lote artificial **não** é evidência de um pregão real. A versão deve ser integrada apenas após verificar os testes e as regressões do repositório no GitHub Actions.
