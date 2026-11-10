# NQ WIN — alternativa de fita histórica com agressor real (Nelogica/Profit)

**Escopo:** uma segunda via de pesquisa do indicador de fluxo, sem acesso obrigatório ao MetaTrader 5. Usa somente um CSV de negócios *tick by tick* que o usuário tenha obtido legalmente, de acordo com a licença do fornecedor. Nenhum dado é adquirido ou baixado automaticamente da Nelogica/B3 e nenhuma ordem é enviada.

## Descoberta documental

- [Nelogica — tipos de arquivos de base histórica](https://ajuda.nelogica.com.br/hc/pt-br/articles/11169423343515-Tipos-de-Arquivos-e-Exemplos-de-Layout-Base-Hist%C3%B3rica-de-Dados): o layout **Tick by Tick** contém Ativo, data, tempo, número do negócio, preço, quantidade, volume financeiro, agente comprador, agente vendedor, agressor e after. A fornecedora diz expressamente que o arquivo **não pode ser redistribuído**. É proibido publicar no GitHub os arquivos de origem sem permissão contratual.
- [Nelogica — TradeType oficial ProfitDLL](https://ajuda.nelogica.com.br/hc/pt-br/articles/11973319153563-Como-requisitar-trades-hist%C3%B3ricos-com-a-ProfitDLL): **2 = agressão de compra, 3 = agressão de venda**; 13 = RLP e 32 = desconhecido. Nosso importador trata tipos não identificados como **não classificados**, nunca como compra/venda.
- [Nelogica — disponibilização dos históricos](https://ajuda.nelogica.com.br/hc/pt-br/articles/11169188636443-Disponibilidade-de-Dados-Hist%C3%B3ricos-para-exporta%C3%A7%C3%A3o-em-CSV): exportações tick-by-tick do WINFUT constam desde 01/05/2012, mas a entrega pode exigir serviço contratado e acesso sFTP; não há evidência de arquivo completo gratuitamente disponível para nós.
- [Nelogica — exportação comum de histórico no Profit](https://ajuda.nelogica.com.br/hc/pt-br/articles/360044287672-Como-exportar-dados-hist%C3%B3ricos-de-ativos-para-o-Excel): uma exportação de **candles** traz OHLCV e **não** os agressores individuais. Essa exportação não é substituta do histórico Tick by Tick.

## Implementação no Nexus Quant

- `research/win_licensed_tape_csv.py` aceita o layout do fornecedor, com cabeçalho português/acentos, separador de ponto e vírgula (ou tabulação/vírgula), preços na notação brasileira e horário local `America/Sao_Paulo`. Não assume que data/hora do servidor de outro provedor esteja em BRT.
- Detecta automaticamente **vencimento explícito WIN** (ex.: WINZ26) e a data do primeiro registro. Exige que **todos** os negócios do arquivo pertençam ao mesmo vencimento e dia; misturar série contínua WINFUT, mudança de vencimento ou horário desordenado gera erro.
- Recusa preço fora da grade de 5 pontos WIN, quantidade inválida, identificadores de negócios duplicados, ausência do campo agressor e arquivo muito grande para as salvaguardas definidas.
- Reconstrói candles por minuto somente de negócios efetivos: abertura = primeiro preço, fechamento = último preço, máxima/mínima observadas e `real_volume` = soma das **quantidades de contratos**. O campo `Volume` do fornecedor pode ser financeiro; o importador não o confunde com quantidade.
- Calcula volume de agressão compradora/vendedora, `delta = buy - sell`, fluxo nos últimos 15 segundos, VWAP e preço de maior volume. Transações com `agressor` desconhecido entram no volume total mas **não** no delta classificado.
- Exige no mínimo 25 transações com agressor identificado no minuto, participação classificada de pelo menos 60%, registro no começo e no final do minuto; lacunas são marcadas. Esses são **parâmetros de pesquisa próprios**, não a fórmula do Greenhouse Tracker.
- Reaproveita a política congelada do indicador independente (`independent_signals`) e coloca o instante de disponibilidade **após o fechamento** do candle. Opcionalmente compara com as etiquetas comerciais públicas 03–04/11, deixando explícito que são exemplos escolhidos e não a saída completa do indicador original.
- Exporta apenas **agregados locais** em `private_mt5/`, pasta já excluída do Git. Não guarda códigos dos agentes compradores/vendedores ou os negócios individuais no JSON resultante, não envia arquivos à Greenhouse, Nelogica, GitHub ou terceiros.
- *Importante:* a reconstrução do candle é feita **do mesmo arquivo** que fornece o volume; portanto a concordância de volume é interna. **Não** afirmamos ter feito confronto independente com candles de outra corretora. Para validar integridade externa, usar uma segunda fonte autorizada e ajustar os gates por política de licença.

## Instalação e execução sem ProfitDLL

No Windows, com Python 3.11 instalado, **arrastar um arquivo CSV tick-by-tick licenciado** até `iniciar_pesquisa_WIN_csv_licenciado.cmd` na pasta do projeto. O script cria seu ambiente virtual e instala apenas `tzdata`, se preciso. Ele identifica a data e o vencimento automaticamente; não pede senha nem conta.

Alternativa via terminal, na branch de pesquisa:

```bat
py -3 -m research.win_licensed_tape_csv --csv "C:\dados\WINZ26_2026-11-03.csv" --output "private_mt5\analise_03_nov.json"
```

A comparação opcional com a página pública é: `--compare-public`, somente para os dias em que a Greenhouse divulgou sinais (03 e 04/11/2026). É uma análise exploratória, não um teste de eficácia fora da amostra. O operador deve respeitar as condições de acesso e uso de dados.

## Validação e bloqueios

- Pipeline multiplataforma: [GitHub Actions — importação de CSV licenciado](https://github.com/lulualcides-sys/nexus-quant-paper/actions/workflows/win-licensed-tape-import.yml).
- Testes criam 525 negócios **sintéticos**, reconstruindo 21 candles M1 e um sinal de absorção programado apenas para verificar a cadeia, não a lucratividade. Casos negativos rejeitam dia/contrato misturado, código de agressão desconhecido, trade repetido e preço fora da grade.
- Não possuímos qualquer CSV licenciado de WIN dos dias 03–04/11 na sessão atual. Portanto **não existe correspondência real calculada com o Tracker, nenhuma taxa de acerto confiável e nenhum lucro comprovado**.
- O fabricante não publicou o código original do Tracker. Nenhuma cópia exata foi obtida ou alegada. O indicador MQL5 independente da [PR #56](https://github.com/lulualcides-sys/nexus-quant-paper/pull/56) permanece intacto; a nova via de dados é apenas um recurso complementar de pesquisa.
- Nenhum arquivo privado é enviado a repositório, nenhuma PR é integrada à `main`, nenhuma ordem pode ser executada por este importador.

**Próxima condição externa necessária:** acesso legítimo a negócios históricos do vencimento WINZ26 para as datas alvo, com agressor identificado. Sem isso, atribuir números de desempenho seria fabricar evidência.
