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
