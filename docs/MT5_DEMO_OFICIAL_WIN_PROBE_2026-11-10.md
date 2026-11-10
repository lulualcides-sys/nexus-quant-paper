# MT5 demo oficial gratuito: verificação remota sem conta inventada — 10/11/2026

**Objetivo do usuário:** testar nosso indicador de fluxo para o contrato WIN sem recuperar o Windows local e sem vender/comprar nada nem usar dinheiro real.

## Procedimentos realmente executados

- Documentação oficial da MetaQuotes confirma [demo gratuito na plataforma web](https://www.metatrader5.com/pt/trading-platform/web-trading/how-to-connect) com [terminal trial](https://web.metatrader.app/terminal?lang=pt&mode=demo) diretamente no navegador. É um ambiente genérico de teste da plataforma, **não** necessariamente uma conta de corretora B3.
- [Execução Windows isolada no GitHub](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42750250629): instalado pacote Python Playwright, 7 testes de controle e navegador Chrome. A página oficial em `web.metatrader.app` carregou sem cadastro, e o texto da interface tinha indicadores de demo/trial. **Nenhum `WINZ26`, `WINV26` ou `WINQ26` foi encontrado no texto visível observado, e não foram identificadas flags de agressor de ticks.** Não foi verificada conexão a feed B3 nem lista integral de símbolos (parte pode depender de busca UI não feita).
- Na mesma execução foi instalado o **MetaTrader 5 oficial** em runner Windows descartável e o pacote Python `MetaTrader5`. A chamada sem autenticação a `initialize()` devolveu `False`; **não é possível concluir se a causa exclusiva foi conta ausente ou a restrição da sessão Windows headless de CI**. O diagnóstico não usa ou imprime `login`, senha, IDs pessoais ou dados da conta.
- O GitHub Actions não criou contas bancárias, cadastrou identidades fictícias ou enviou ordens de qualquer tipo, nem mesmo ordens demo. O `web` foi somente inspecionado; o terminal nativo foi apenas sondado.
- O programa `research/probe_public_mt5_demo.py` grava apenas sinais booleanos de presença da UI, sem conteúdo completo do terminal, tokens ou cookies. O `research/probe_mt5_native_without_login.py` relata estados redigidos sem credenciais.
- Os testes em `tests/test_mt5_free_demo_probe.py` cobrem segurança sem ordens e conservadorismo ao inferir dados de agressão/contrato WIN.

## Por que um número de conta fictício não resolve

- [API Python oficial `initialize()`](https://www.mql5.com/pt/docs/python_metatrader5/mt5initialize_py) conecta a um terminal e, opcionalmente, a uma conta **já emitida** pelo servidor do broker. Não existe parâmetro que gere um login válido apenas inventando um número.
- [Processo oficial de abertura de demo](https://www.metatrader5.com/pt/terminal/help/startworking/acc_open): selecionar um servidor e solicitar conta demonstrativa; a disponibilidade e formulários dependem do broker. O modo web gratuito é uma demo da plataforma, não comprova acesso à B3.
- O usuário não precisa de conta real para backtest de software, mas precisa de **dados reais de negócio com lado agressor** para validar a hipótese de absorção do WIN. Uma demo de EURUSD com 0.01 lote não representa a microestrutura, contratos, spread e fluxo de agressão do WIN.

## Limite demonstrado pela pesquisa

- O teste web confirmou abertura de página demo oficial, mas **NÃO confirmou um login de conta demo individual, WINZ26 ou histórico de negócios com flags BUY/SELL**.
- O teste nativo confirmou instalação do software, mas o `initialize` sem conta **não obteve conexão operacional**. Não foi criada sessão de corretora; não havia histórico utilizável para teste.
- O projeto já contém [indicador independente WIN em MQL5 compilado](https://github.com/lulualcides-sys/nexus-quant-paper/pull/56) e [importador de negócios CSV com agressor](https://github.com/lulualcides-sys/nexus-quant-paper/pull/58). Estes não foram alterados pelos testes demo.
- O projeto já tem importação de uma série **WINQ26 M1 de terceiro** para pesquisa de preços (`research/atlas_winq26_public.py`). Ela **não tem agressão classificada**, não é feed autenticado B3 e não é base válida para dizer que reproduzimos o Tracker. Não foi feita comparação nova de P&L nesta PR.

## Próxima fonte necessária

- Acesso autorizado à corretora B3 que disponibilize WINZ26 com negócios classificados, ou CSV de histórico Times & Trades/Profit/Nelogica legalmente obtido que contenha preço, tempo, quantidade e agressor. Um terminal demo genérico da MetaQuotes sem esses dados não resolve o problema.
- Sem esse feed, a decisão correta é preservar a PR de investigação e **não declarar replicação, ganho financeiro ou equivalência de setas**. Não usar dados falsos para ultrapassar bloqueios de onboarding/serviços financeiros.

**Estado:** os dois caminhos gratuitos foram executados como sondas em Windows GitHub Actions. O navegador abriu a demo oficial, mas o histórico real B3 necessário não foi obtido. Nenhuma conta foi falsificada, criada, cobrada ou usada para operações.
