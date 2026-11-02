# Nexus Quant — notícias macroeconômicas e risco nos 27 robôs (01/11/2026)

## Objetivo e limites

Aplicar um filtro **temporal, sem sentimento especulativo**, ao nascimento de **novas posições virtuais** dos 27 robôs: 5 ouro H4, 5 ouro H4 alavancados, 15 H1, 1 USD/CAD H1/M15 e 1 Momentum60 H4. Não interromper operações existentes, stops, trailing stops, saídas de risco, limites de perda ou relatórios diários.

**Não há filtro capaz de garantir lucro nos 27 modelos.** Os testes H1 anteriores mostraram perdas agregadas mesmo após filtros de custo/tendência. Notícias podem reduzir a exposição em momentos de divulgação, mas também podem retirar oportunidades boas.

## Fontes verificadas — calendário de eventos de alto impacto em USD

Fontes **oficiais**, sem APIs pagas, corretoras, tokens ou LLMs:

- BLS emprego/NFP: https://www.bls.gov/schedule/news_release/empsit.htm
- BLS inflação/CPI: https://www.bls.gov/schedule/news_release/cpi.htm
- BLS PPI/JOLTS: https://www.bls.gov/schedule/2026/11_sched_list.htm e https://www.bls.gov/schedule/2026/12_sched_list.htm
- BEA PIB, renda e despesas pessoais/PCE: https://www.bea.gov/news/schedule
- Fed FOMC: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm

Snapshot *verificado em 01/11/2026 (horário de São Paulo)*, conservado em `research/news_calendar_2026_11.json`. O manifesto registra a data de verificação e a cobertura conhecida. Os calendários oficiais podem ser revisados; a aplicação **não presume que um snapshot de hoje estava disponível em 2025 ou antes de 01/11/2026**.

### Regra de bloqueio de novas entradas

- Evento de minuto confirmado: bloquear entrada a partir de **60 minutos antes** até **45 minutos depois** do horário oficial, em **America/New_York** com DST automático.
- Se a fonte só confirma a data de decisão do FOMC, bloquear **todo o dia local**, sem inventar horário de comunicado.
- Aplicar aos seis mercados associados a USD: EURUSD, USDJPY, XAUUSD, US500, XTIUSD e USDCAD. Essa classificação de escopo é uma **hipótese conservadora de risco**, não uma comprovação de ganho.
- O filtro é configurável via variável de repositório GitHub Actions `NEXUS_NEWS_GUARD_ENABLED=1`. Está **desligado por padrão** em testes e até a aprovação/integração da PR.
- Se ativado e não houver agenda confiável, o manifesto estiver vencido ou a data da decisão for anterior ao snapshot, **não abre uma nova posição**; **nunca** atrasa um stop/saída existente.
- Se a data de vigência de verificação expirar (16/11/2026 00:00 UTC no primeiro snapshot), a entrada fica bloqueada com `unknown` quando o filtro estiver ativado. Calendário deve ser renovado após conferência com fontes oficiais. Desligado, não interfere nos robôs originais.

## Verificação cronológica

Um calendário registrado em 02/11/2026 não pode ser aplicado retroativamente no backtest de maio/outubro de 2026. Isso geraria **lookahead** mesmo que os eventos tenham ocorrido no passado. Por isso, o filtro só admite simulação futura a partir do `observed_at_utc` verificável. Testes offline validam horários, horários de verão, duplicatas, fontes, mercados, expiração, ausência de dados, estado imutável e preservação de stops.

## Outras dimensões necessárias para buscar lucro

1. Custos: cenários normal e dobrado; resultado bruto, líquido e por operação; financiamento e slippage ainda não executável de corretora.
2. Validação prospectiva sem escolher parâmetros após observar o mesmo conjunto.
3. Robustez: diferentes regimes, walk-forward em períodos não utilizados para otimizar; custo real de bid/ask é obrigatório antes de capital real.
4. Controle de risco: exposição nominal, risco-stop, correlação de exposições ao USD e drawdown conjunto; não somar bancas virtuais de janelas desiguais como carteira executável.
5. Sem promessa de 27 robôs lucrativos: modelos sem vantagem líquida devem **ficar sem novas entradas ou seguir em investigação**, não ser forçados a operar.

**Integração:** PR dependente do trabalho anterior (#9–#12); não considerar implantado até CI aprovado e merge confirmado. Nenhum lucro ou ordem real foi gerado.
