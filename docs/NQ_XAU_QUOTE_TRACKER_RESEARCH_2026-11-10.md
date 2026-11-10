# Nexus Quant — Tracker independente para XAUUSD no MetaTrader 5

**Pesquisa de 10/11/2026 | experimental | nenhuma ordem ou lucro prometido**

## O que foi implementado

- **Indicador:** [`indicators/mt5/NQ_XAU_Quote_Tracker_Research.mq5`](../indicators/mt5/NQ_XAU_Quote_Tracker_Research.mq5). Apenas gráficos **XAUUSD**, inclusive sufixos de corretora (`XAUUSD.a`, por exemplo), em **M1 e M5**. Não habilita robô, EA, conta, compra ou venda automática.
- **Modelo Python auditável:** [`research/xau_quote_tracker_reference.py`](../research/xau_quote_tracker_reference.py), com decisão determinística sobre candle **já fechado**, comparação de atividade de ticks e validação de CSV de origem autorizada.
- **Testes:** [`tests/test_xau_quote_tracker_reference.py`](../tests/test_xau_quote_tracker_reference.py) e workflow de Linux/Windows + compilação **MetaEditor 5 oficial**. Não declarar EX5 compilado sem log de sucesso e artefato do workflow.

## Diferença fundamental para a pesquisa WIN

XAUUSD de uma corretora MT5 costuma representar preço spot/CFD negociado em mercado de balcão. O `tick_volume` de M1/M5 conta **atualizações de cotação no feed daquela corretora**, não lotes comprados, lotes vendidos, fluxo agressor, delta da B3/COMEX ou ordens institucionais. Não há fita consolidada para esse CFD. Um feed XAUUSD de outro servidor pode gerar sinais diferentes.

Portanto o projeto **NÃO** reaproveita o filtro de `TICK_FLAG_BUY/SELL` do WIN (nem converte variação do preço em agressão fictícia). Mantém apenas características visuais e hipóteses independentes de rejeição de extrema, não a fórmula original comercial da Greenhouse.

Referência de implementação dos campos e flags de tick na documentação MQL5:
- https://www.mql5.com/en/docs/series/copyticks
- https://www.mql5.com/en/book/applications/timeseries/timeseries_ticks_mqltick

## Método fixo antes de validação (hipóteses, NÃO parâmetros do Tracker original)

1. Em cada **candle M1/M5 confirmado**, avaliar os **20 candles anteriores**, todos fechados e cronologicamente contínuos (lacunas acima de 2 períodos bloqueiam).
2. Calcular **ATR 14 anterior** sem incluir o candle de sinal; exigir amplitude entre **0,60× e 2,50× ATR**.
3. Contagem de updates no candle `>=15` e `>=1,20×` a média da contagem dos 20 anteriores.
4. Exigir **spread histórico válido e positivo** e inferior a `0,35× ATR`; spread zero/ausente BLOQUEIA seta. Metadado histórico é uma estimativa, não garante spread na execução.
5. **Compra:** varrer mínima anterior em pelo menos `0,06× ATR`, fechar acima do nível varrido, corpo ascendente, pavio inferior `>=28%` da amplitude e fechamento nos `38%` superiores.
6. **Venda:** simétrico em máxima anterior, pavio superior `>=28%`, fechamento nos `38%` inferiores.
7. Marcar seta somente após candle fechado. Projetar guias por geometria pública: `0%`, `50%` (entrada), `100%`, `200%` (alvo), `-100%` (stop); linhas não implicam execução. Distâncias nominais alvo/stop desde a entrada são iguais: **R:R 1:1**, antes de spread, taxas e slippage.

**Atenção:** apenas uma seta de pesquisa, não sinal autorizado para operação. Não declarar win rate ou lucro antes de backtest *do mesmo XAUUSD broker*, com spreads reais, custos, split cronológico e walk-forward. Um backtest em GC=F (futuro do ouro) não valida necessariamente o XAUUSD OTC.

## Como verificar

1. Abra a workflow [XAU Quote Tracker](../.github/workflows/xau-quote-tracker-mt5.yml) no GitHub Actions da branch e confira `verify_reference` e `compile_official_mql5`. Um job verde de compilação deve produzir o artefato EX5.
2. No MT5 ligado a um **servidor demo autorizado que ofereça XAUUSD**, abra gráfico XAUUSD M1 ou M5 e instale o indicador compilado; não é necessário enviar nenhuma ordem. Sem terminal conectado a um feed não há sinais observáveis ao vivo.
3. Confira `Experts`/`Journal` se o broker registra **`tick_volume` e `spread` M1/M5 válidos**; feed sem spread histórico é bloqueado por desenho. Não substituir spread ausente por zero artificial.
4. Para sinais auditáveis sem conectar conta, use CSV autorizado com cabeçalho exato:
   `symbol,time_utc,open,high,low,close,tick_volume,spread_points`. Datas em ISO 8601 com fuso explícito, dados ordenados, uma vela por timeframe, mesmo símbolo/servidor/point/tick_size; o scanner Python **descarta a última vela como potencialmente aberta**.
5. Exemplo com export já disponível localmente: `python -m research.xau_quote_tracker_reference --csv /caminho/XAUUSD_M1.csv --timeframe M1`. Isso retorna apenas setas e hashes; **não** calcula P&L e não envia ordens.

## Portão para evoluir para um robô

- Conseguir histórico verificável de **XAUUSD da corretora pretendida**, incluindo spread histórico, informação de ponto/tick-size, horário servidor, custos/swap e uma janela fora da amostra.
- Modelar entrada limite no 50% **APÓS** o fechamento do candle, ordem não preenchida, prioridade conservadora se stop/alvo tocarem na mesma vela, spread variável, slippage e perda de conexão; não supor fill retroativo.
- Reportar amostra, lucro líquido, PF, DD, exposição e robustez no período de teste; não ajustar limiares para embelezar lucro.
- Manter WIN, ATLAS, ouro H4 e robôs aprovados inalterados. Integrar apenas após revisão e resultados independentes.

**Estado nesta branch:** pesquisa isolada; indicador não é a fórmula do Tracker, não é robô e não afirma acerto ou performance. 

## Refinamentos auditados — 10/11/2026

Comparação documental com https://lojadagreenhouse.com.br/ofertatracker/ e https://lojadagreenhouse.com.br/: são observáveis apenas a confirmação da vela, a geometria pública de Fibonacci, as setas, os exemplos de dados e os relatos comerciais. **Não há equações de sinal, parâmetros internos ou série oficial XAUUSD** para calcular uma taxa de coincidência.

Mudanças na mesma PR de pesquisa, sem alterar a `main`:

- Além das setas de compra/venda, o MT5 agora desenha etiquetas **COMPRA/VENDA** e preços com texto **ENTRADA 50%**, **ALVO 200%**, **STOP -100%** e, por padrão, guias de 0%/100%; são objetos visuais sem execução de ordens.
- Após desconexões ou pausas, a rotina percorre os candles novos que já fecharam, em vez de avaliar apenas a última vela M1/M5.
- Filtro **opcional** `InpRequireLiquidityZone=false` (padrão): exige múltiplos testes anteriores do extremo, com distância máxima `0,08× ATR` (`InpLiquidityToleranceATR`), no mínimo 2 toques. É uma **hipótese original** e fica desativada até haver dados para testar se reduz falsos positivos. O modelo Python espelha a mesma regra quando habilitada.
- Exportações CSV são verificadas com hash SHA256 por streaming (sem carregar o arquivo inteiro na memória); seleção equivocada de M1/M5 é rejeitada.
- Contrato da pesquisa permanece: **sem ordem automática, sem manipular WIN, sem agressão/delta fictícia, sem lucro alegado**.

**Evidência do último pipeline testado:** GitHub Actions
https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42758936261 —
20 testes unitários independentes aprovados em Linux e Windows, compilação MetaEditor 5 oficial com **0 erros/0 avisos**, saída EX5 **25.540 bytes**, artifact `nq-xauusd-quote-tracker-compiled-ex5`. Foram dados sintéticos de teste para os sinais; ainda não é prova de coincidência com o Tracker Greenhouse, nem backtest de ouro em corretora.

**Gate para declarar 'idêntico':** captura de funcionamento simultâneo do indicador original autorizado (mesmo broker, XAUUSD, timezone e timeframe) e nossa revisão durante intervalos completos, com **todos** os sinais e não-sinais, preços e horários. Sem o original acessível não é possível declarar identidade. Um visual aproximado, por si só, não comprova o mesmo algoritmo. Versão de pesquisa permanece DRAFT.


## Execução comprovada em cotações históricas reais do ouro — 10/11/2026

**Artefato de auditoria:** [GitHub Actions 42760267105](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42760267105). Execução aprovada, com **10 testes adicionais de integração + 20 testes do detector**. O EX5 foi compilado separadamente no [workflow 42759095890](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42759095890), usando MetaEditor oficial, **0 erros e 0 avisos**, com binário **26.168 bytes**. Os artefatos do Actions possuem prazo de expiração.

### Fonte aberta utilizada

- [dukascopy-node](https://www.dukascopy-node.app/instrument/xauusd), ferramenta de pesquisa open source, versão **1.51.1** fixada nos comandos de CI. Busca os dados de cotações bid/ask históricos para XAUUSD.
- **Não** usa o volume `askVolume/bidVolume` das cotações como agressão, lotes negociados ou volume transacionado. Faz a contagem **separada** de atualizações observadas de preço bid/ask e conserva o **maior spread registrado por candle** como filtro conservador.
- A fonte Dukascopy **não equivale ao feed XAUUSD de uma conta MT5 específica**, portanto essa validação prova apenas que a lógica reproduzível processa dados reais e gera seus próprios sinais.
- Não commitamos os ticks brutos da Dukascopy; ficam apenas os relatórios, período, contagem, hash SHA256 do arquivo de origem e amostra resumida das setas no artefato do Actions.

### Duas janelas fixas, sem recalibrar após os resultados

| Janela UTC | Cotações bid/ask | Candles M1 / M5 | Compras M1 | Vendas M1 | Sinais M5 |
|---|---:|---:|---:|---:|---:|
| 2026-10-29 12:00–17:00 | 150.767 | 300 / 60 | 1 | 1 | 0 |
| 2026-11-03 12:00–17:00 | 139.216 | 300 / 60 | 0 | 1 | 0 |
| **Total** | **289.983** | **600 / 120** | **1** | **2** | **0** |

**Esta contagem não é um backtest de lucro/prejuízo.** Nenhuma ordem foi enviada, nenhuma entrada de Fibonacci foi assumida preenchida, nenhum resultado de mercado foi convertido em trade. Foram testes históricos do indicador, sem avaliar operação executável ou custos totais. Apenas 10 horas totais de dados não demonstram vantagem estatística.

### Evidência reproduzível no repositório

- `research/xau_dukascopy_replay.py`: lê arquivos CSV do downloader `timestamp,askPrice,bidPrice,askVolume,bidVolume`, valida preço e horário, constrói OHLC de **bid**, tick_volume por contagem de **atualizações de cotação**, spread conservador por barra e passa os candles fechados para `research/xau_quote_tracker_reference.py`. Protege contra cotações cruzadas, dados desordenados, históricos curtos e candle final possivelmente aberto.
- `tests/test_xau_dukascopy_replay.py`: 10 testes offline independentes, inclusive rejeição de dados incorretos e distinção rigorosa entre contagem de updates e volume financeiro.
- `.github/workflows/xau-real-quote-replay.yml`: downloads gratuitos em janelas fixas, 2 timeframes, audit/proveniência e artifact `xauusd-real-dukascopy-quote-replay-research`. Reexecutar pelo GitHub Actions; nenhuma chave ou login de corretora é usada.
- `indicators/mt5/NQ_XAU_Quote_Tracker_Research.mq5`: o indicador para gráfico **XAUUSD M1 ou M5 no MT5**, compilado e preservado na PR. Precisa de terminal MT5 funcionando com um **feed da corretora** para exibir um gráfico ao vivo e atestar o sinal real da mesma conta.

**O que ainda NÃO foi comprovado:** funcionamento dentro do MT5 do usuário com sua corretora/servidor; coincidência exata de setas com o Tracker Greenhouse; taxas de acerto, retornos e lucro líquido. A Greenhouse não fornece públicamente uma série completa de setas *em XAUUSD* com o mesmo feed e instantes que permitiria testar equivalência. Não inferir a regra interna a partir de publicidade.

### Como usar o indicador na própria plataforma MT5

1. Acesse [o workflow compilado e aprovado](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42759095890) e seu artefato **`nq-xauusd-quote-tracker-compiled-ex5`**.
2. No terminal MT5 com conexão **demo** e símbolo **XAUUSD**, use **Arquivo > Abrir pasta de dados**. Coloque o arquivo `.ex5` em `MQL5/Indicators/`, reinicie o Navegador de indicadores e arraste `NQ_XAU_Quote_Tracker_Research` para o gráfico **M1/M5**. Nenhuma ordem é enviada.
3. Verifique **Journal/Experts** quanto a erros, candles, spread e histórico suficientes. O indicador não inventa setas quando faltam dados de cotação ou o spread está ausente. O terminal MetaQuotes demo que não apresenta XAUUSD ou não permite sessão não é suficiente para a confirmação de operação ao vivo.

**Decisão técnica:** manter a PR em DRAFT até existir teste realmente observável na plataforma MT5 específica e dados auditáveis para avaliar resultados de negociações hipotéticas; manter todos os demais robôs/estratégias intactos.
