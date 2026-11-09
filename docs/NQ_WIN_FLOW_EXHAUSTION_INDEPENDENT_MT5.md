# NQ WIN Exaustão de Fluxo — alternativa funcional independente ao Tracker (pesquisa)

**Estado em 09/11/2026:** fonte MQL5 criada, modelo de referência Python testado, compilação real MetaEditor em CI separada. NÃO é o indicador proprietário Tracker, não utiliza fonte privada, não há negociação automática nem rentabilidade demonstrada.

## Fontes consultadas

- A [loja oficial Greenhouse](https://lojadagreenhouse.com.br/) anuncia que o Tracker procura reversões/exaustão e o Titan segue tendências; a [oferta atual](https://lojadagreenhouse.com.br/ofertatracker/) anuncia MT5, Profit e BlackArrow. Código-fonte e fórmula proprietária de entrada não estão disponíveis no HTML aberto.
- [Auditoria prévia com REA e 43 sinais públicos](../docs/GREENHOUSE_TRACKER_PUBLIC_REA_DEEP_FORENSICS_2026-11-09.md): apenas quatro de 41 marcas examináveis obedecem à hipótese anterior de sweep/preço; portanto os parâmetros antigos não são uma réplica demonstrada.
- [Referência oficial MQL5: CopyTicksRange](https://www.mql5.com/en/docs/series/copyticksrange) e [MqlTick + flags BUY/SELL](https://www.mql5.com/en/book/applications/timeseries/timeseries_ticks_mqltick). A API permite usar preços de negócios (`last`), volume real e classificação da iniciativa da negociação **quando a corretora fornece esses campos**. Tick volume ou cor do candle NÃO equivalem à agressão real.
- [Artigo público MetaQuotes de volume delta](https://www.mql5.com/en/articles/3708) como referência conceitual sobre `TICK_FLAG_BUY` e `TICK_FLAG_SELL`. Nenhum código do artigo copiado; implementação aqui é própria.
- A [B3 limita expressamente a coleta automatizada no Hub de Dados Públicos](https://www.b3.com.br/pt_br/dados/hub-de-dados-publicos/). Não fizemos scraping de suas páginas/dados protegidos por termos.

## Arquivos

- `indicators/mt5/NQ_Win_Exaustao_Fluxo_Research.mq5`: indicador próprio para o gráfico WIN M1 com setas e linhas de Fibonacci, classificador de pressão agressora em ticks executados, sem robô/ordens.
- `research/win_flow_exhaustion_reference.py`: espelho Python determinístico, sem ligação com corretora; calcula candidatos e audita a disponibilidade de fluxo classificado.
- `tests/test_win_flow_exhaustion_reference.py`: 12 testes sintéticos, incluindo cobertura, direção de agressão, não-repaint de candle fechado, volume real e custos.
- `.github/workflows/win-flow-exhaustion-mt5.yml`: testes Python no Actions sem pacote de corretora.
- `.github/workflows/win-flow-metaeditor-compile.yml`: tentativa de compilação de verdade em Windows com MetaEditor oficial, sem login em conta de negociação. Conferir **conclusão** antes de afirmar que o `.ex5` existe.

## Como esta versão gera um sinal

1. **Somente WIN de vencimento explícito e gráfico M1.** Exige grade de 5 pontos, volume real no candle e 20 candles fechados do mesmo dia do servidor. Não apresenta sinais em WINFUT/símbolos que não passaram na validação.
2. **Candidato por preço:** candle fechado de alta/baixa, próxima a extremo recente ou após sweep; pavio mínimo de 15%, fechamento na parte superior/inferior da amplitude e volume real do candle pelo menos 1,15× a média das 20 velas anteriores. São parâmetros iniciais próprios, NÃO os da Greenhouse.
3. **Confirmação por negócio real:** consulta `CopyTicksRange(_Symbol, ..., COPY_TICKS_TRADE, ...)` apenas no minuto do candle candidato. Exige no mínimo 25 eventos com agressor verdadeiro, participação classificada de pelo menos 60% do volume conhecido e cobertura aproximada do início/fim do minuto. Metadados indisponíveis → **não emitir sinal**.
4. **Exaustão/absorção:** para compra, vendedores agressivos precisam representar pelo menos 56% do volume classificado mas o candle recupera o preço e fecha em alta; para venda, regra espelhada com compradores agressivos e fechamento em baixa. Isso é hipótese de absorção contrária ao fluxo, não uma equivalência com o Tracker.
5. **Visualização:** seta no candle fechado, níveis 50% (entrada potencial), 200% (alvo visual) e -100% (stop visual); 0% e 100% opcionais. Linhas congeladas para cada sinal. **Não executa ordens**; a eventual posição ainda precisaria ser preenchida.

## Custo e risco da geometria pública

- Com entrada no 50% do candle, alvo 200% e stop -100%, a distância bruta até alvo e até stop é **1,5× a amplitude do candle**, ou aproximadamente 1:1 antes de custos. Arredondamento de 5 pontos pode produzir leve assimetria.
- Exemplo com 100 pontos de amplitude e 1 WIN: aproximadamente R$30 brutos em ganho/risco. Com custos hipotéticos R$6 por ciclo, recompensa líquida R$24 e risco líquido R$36 (60% de acerto mínimo de equilíbrio; sem spread/erros de preenchimento).
- Para banca de referência R$2.000 e risco de 1%, um sinal que arrisque R$36 é **incompatível** com limite de R$20 e não pode ser executado como se fosse uma operação autorizada.
- Sem dados reais de ticks/ordens/fee da Rico, nenhuma estatística de lucro pode ser emitida a partir dos testes sintéticos.

## Instalação no MetaTrader 5 — somente indicador

1. Instalar MT5 da Rico gratuitamente e conectar a conta demo ou uma conta com permissões de gráfico (não precisa ativar operação automática).
2. No MT5: **Arquivo → Abrir Pasta de Dados → MQL5 → Indicators**. Copiar apenas `NQ_Win_Exaustao_Fluxo_Research.mq5`.
3. Pressionar **F4** para abrir MetaEditor, depois **F7** para compilar. Se a compilação no CI gerar um `.ex5` original válido, usar somente esse arquivo se desejar, sem baixar executável de origem desconhecida.
4. Abrir gráfico M1 do contrato WIN de vencimento explícito disponível na Rico, aplicar o indicador e verificar, na aba Especialistas/Diário, se o servidor forneceu negociações classificadas com `TICK_FLAG_BUY/SELL`.
5. **Se não aparecer nenhuma seta**, isso NÃO prova ausência de reversões: pode significar que a corretora não fornece o histórico de negócios/volume exigido ou que os filtros são restritivos. Não desligar exigências de dados só para gerar resultados.

## Evidência e bloqueios

- Testes sintéticos não acessam a Rico, não comparam a imagem com o Tracker original e não medem rentabilidade. 12 testes de mecanismo e segurança executados em CI; o resultado deve ser conferido no workflow.
- O código do Tracker original ainda não foi obtido de fonte autorizada; o REA examinou apenas o **demonstrador público** e não trouxe o código de detecção de sinais.
- Versão nova NÃO substitui nem altera o protótipo anterior `NQ_Vector_Exhaustion_Research.mq5`, os robôs existentes, ou a branch `main`.
- Próximas validações: compilação real MetaEditor, teste visual em terminal MT5, dados de ticks legítimos de dias inéditos, congelamento dos parâmetros, comparação timestamp-a-timestamp com fontes que exibam o sinal original em tempo real, simulação com custo/deslizamento e exame fora da amostra. Não aprovar operação real sem isso.
