# Nexus Quant — auditoria de fluxo WIN e correspondência independente com o Tracker

**Estado: 09/11/2026. Pesquisa implementada; NENHUM acesso à conta Rico foi realizado. Código licenciado original Greenhouse não obtido.**

## Objetivo

Confrontar a hipótese independente `NQ_Win_Exaustao_Fluxo_Research.mq5` com negócios classificados (tape/volume/delta) de WIN, antes de reivindicar semelhança com as setas comerciais Greenhouse. O único parâmetro que pode ser transferido diretamente da publicidade é a geometria 0/50/100/200/-100. A decisão de sinal original é desconhecida.

## Código implementado

- `research/win_mt5_tick_provenance.py`: usa **somente** a instalação local aberta do MT5 (`terminal_info`, `symbol_info`, `symbol_select`, `copy_rates_range`, `copy_ticks_range`, `last_error`, `initialize`, `shutdown`). Lê datas específicas para vencimento explícito WINZ26 e M1 das 09:00 às 19:00 em horário de São Paulo; é uma janela de coleta, **não uma garantia dos horários oficiais do pregão**.
- Separa compras agressoras (`TICK_FLAG_BUY=32`) e vendas (`TICK_FLAG_SELL=64`) apenas em atualizações de negociação (`TICK_FLAG_LAST=8` ou `TICK_FLAG_VOLUME=16`), com `last` válido e `volume_real` positivo. **`TICK_FLAG_ASK=4` NÃO é TICK_FLAG_LAST**. A confirmação veio da [tabela oficial MetaQuotes](https://www.mql5.com/pt/book/applications/timeseries/timeseries_ticks_mqltick).
- Calcula por minuto delta, fração de volume com agressor identificado, delta dos últimos 15s, VWAP e nível de maior volume. Não inferimos agressão a partir de velas, preço Bid/Ask sem negócio ou `tick_volume`.
- Audita volume: compara soma de negócios com volume real do candle M1. Reprova candle quando a diferença relativa passa de 20%, se há menos de 25 negócios classificados, menos de 60% do volume com lado, histórico sem 15s de cobertura nas pontas ou lacuna M1. Esses parâmetros são **gates técnicos iniciais**, não parâmetros do Tracker.
- Coleta em blocos de 10 minutos, limita quantidade de ticks e falha explicitamente em erros de fonte. Não envia arquivos para GitHub nem o website da Greenhouse.
- `research/win_flow_public_label_comparison.py`: usa a política **congelada** de `research/win_flow_exhaustion_reference.py` (sweep/absorção, volume, delta e fechamento). Sinal só está disponível a partir do **próximo minuto**, com a janela das últimas 20 velas contígua e do mesmo dia. Compara com etiquetas públicas apenas dos dias efetivamente coletados e audita sinais por timestamp exato e tolerância de ±1 minuto. Não otimiza os thresholds.
- `executar_pesquisa_tracker_fluxo_MT5.cmd`: modo Windows de um clique. Cria um Python virtual isolado e instala os pacotes oficiais `MetaTrader5` e `tzdata` se faltarem. Coleta 03/11 e 04/11/2026 e salva na pasta local `private_mt5/`, excluída do Git. Depende de o usuário ter **MetaTrader 5/Rico instalado, aberto e conectado aos dados históricos**.

## Evidência de testes

- [GitHub Actions Linux — testes independentes e auditoria estática](https://github.com/lulualcides-sys/nexus-quant-paper/actions/workflows/win-mt5-tick-provenance.yml).
- [GitHub Actions Windows — inicializador CMD, Python isolado, pacote MetaTrader5 e tzdata](https://github.com/lulualcides-sys/nexus-quant-paper/actions/workflows/win-tick-provenance-windows.yml).
- Testes cobrem diferença `LAST=8` versus `ASK=4`, precisão do volume real, flags de compra/venda, dias UTC/São Paulo, lacunas M1, inconsistências entre candles e ticks, condições de falha, tempo de confirmação da seta e ausência de operações.
- Os testes utilizam **ticks sintéticos**. Não comprovam que a Rico fornece agressão, dados suficientes ou sinais originais; isso depende da execução no terminal Windows do usuário.

## Operação local (pesquisa sem dinheiro real)

1. Instalar e conectar o MetaTrader 5 da Rico em um computador Windows com Python 3.11 disponível. **O ChatGPT/GitHub Actions não pode controlar automaticamente essa instalação.**
2. Obter a branch da PR desta pesquisa no Windows. Na pasta do projeto, executar `executar_pesquisa_tracker_fluxo_MT5.cmd`.
3. O inicializador instala apenas pacotes gratuitos no seu ambiente Python isolado, sem tocar nos outros robôs. Ele tenta ler WINZ26 em 03/11 e 04/11. Caso a corretora não tenha histórico suficiente ou ofereça ticks sem as flags classificadas, sinaliza falta de evidência; não inventa resultados.
4. Dois arquivos `private_mt5/WINZ26_2026-11-03_flow_audit.json` e `private_mt5/WINZ26_2026-11-04_flow_audit.json` guardam **agregados locais**, não tick-by-tick em bruto. Uma terceira saída `private_mt5/nq_public_labels_comparison.json` informa sobreposição temporal dos sinais com o demonstrador comercial.
5. Para verificar um novo dia, chamar `py -3 -m research.win_mt5_tick_provenance --symbol WINZ26 --date AAAA-MM-DD`. Dependendo da configuração, a API Python pode exigir que o ambiente virtual do iniciador esteja ativado.
6. Para auditar com dados públicos mantendo os seus arquivos privados, repetir a comparação com `--fetch-public-html` ou com `--public-html` apontando para uma cópia pública previamente obtida. O coletor não faz POST nem upload de seus dados para a Greenhouse.

## Limites do que o resultado significará

- A página Greenhouse contém apenas **43 etiquetas comerciais de 03 e 04/11/2026** (19 e 24, segundo o próprio site), não logs completos e autenticados da ferramenta. Outras setas podem ter existido e não ter sido apresentadas. Logo, não marcamos horários não catalogados como 'falsos positivos reais'.
- A conta Rico não está conectada a este chat ou ao GitHub Actions. Até que os scripts rodem no computador, **não há valores reais de correspondência, taxa de acerto, agressão observada ou rentabilidade líquida**.
- Correspondência visual com labels comerciais não demonstra o gatilho original. Reproduzir 100% da amostra pública com parâmetros ajustados seria potencial sobreajuste.
- A entrada pública em 50%, alvo 200% e stop -100% resulta aproximadamente em relação bruta 1:1; com taxas e slippage, a necessidade de acerto é superior a 50%. Nenhum modelo está habilitado para envio de ordens.
- Não houve login em loja, download não autorizado, engenharia de DRM, uso de arquivos pagos ou alteração em produção. O projeto segue como pesquisa isolada.

## Referências verificáveis

- [Fonte MetaQuotes: ticks, atributos de trade e flags](https://www.mql5.com/pt/book/applications/timeseries/timeseries_ticks_mqltick)
- [Fonte MetaQuotes: API Python `copy_ticks_range` e interpretação de UTC](https://www.mql5.com/en/docs/python_metatrader5/mt5copyticksrange_py)
- [Greenhouse: método comercial e geometria do candle](https://lojadagreenhouse.com.br/)
- [Auditoria vetorial anterior: 63 hipóteses e 43 etiquetas](TRACKER_VEC_DISCOVERY_2026-11-09.md)

**Decisão:** o próximo marco comprovável é obter os agregados reais de uma instalação local autorizada. Até lá, os testes verificam somente correção e segurança do código. Nenhuma estratégia pode receber aprovação de dinheiro real com esta evidência.
