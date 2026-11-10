# NQ WIN Exaustão de Fluxo — revisão final de execução e segurança

**Data da pesquisa: 09/11/2026 (America/Sao_Paulo).**

## Resultado verificável

- O indicador independente `indicators/mt5/NQ_Win_Exaustao_Fluxo_Research.mq5` foi atualizado para **ignorar atualizações simples de BID/ASK**, exigindo flags efetivas `TICK_FLAG_LAST`/`TICK_FLAG_VOLUME`, preço `last` válido e `volume_real` de contratos positivo antes de classificar agressão BUY/SELL.
- A cobertura de negócios classificados exige o mínimo definido nos inputs. Também há comparação de soma de volume do tape com volume real do candle M1; divergência acima de 20% (parâmetro experimental) **reprova o sinal**, em vez de inventar volume.
- O espelho Python `research/win_flow_exhaustion_reference.py` agora compartilha essas mesmas regras fundamentais; os testes incluem flags incorretas, falta de cobertura, inconsistência de volume, janela UTC/São Paulo, delta contrário e candle não fechado.
- O coletor `research/win_mt5_tick_provenance.py` passou a solicitar intervalos de 10 minutos terminando **1 milissegundo antes da próxima janela**, porque `copy_ticks_range` permite limite inclusivo. Os testes criam um negócio exatamente na fronteira e verificam ausência de dupla contagem.
- **52 testes passaram no Linux**, divididos em 15 do modelo de fluxo, 17 de integridade do tape MT5, 9 de comparação causal com etiquetas e 11 de reconstrução matemática. **41 testes repetidos passaram no Windows** para os três primeiros módulos.
- **Compilação MQL5 real em MetaEditor 5 no Windows: 0 erros e 0 avisos**, arquivo `.ex5` com 27.126 bytes arquivado no GitHub Actions. Não foi feita conexão a conta Rico, nem operação real.
- Pipeline verificado: https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42725495416
- Arquivo compilado: https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42725495416/artifacts/13722326355

## Componentes entregues

| Componente | Estado |
|---|---|
| Código do indicador independente MQL5 | Compilado, 0 erros/avisos |
| Detecção de absorção com delta por negócios com agressor identificado | Implementada, testada com dados sintéticos |
| Setas apenas após fechamento de candle M1 e vetores 50/200/-100 | Implementados, auditoria estática/testes de referência |
| Validação do volume `real_volume` dos negócios contra candle M1 | Implementada, teste de rejeição |
| Coleta local somente leitura dos ticks do MT5 | Implementada, testa API simulada; faltam ticks verdadeiros da Rico |
| Comparação dos sinais com os 43 horários promocionais públicos | Algoritmo implementado, faltam dados legítimos M1+ticks do período |
| Equivalência de sinais com o Tracker comercial | **NÃO comprovada** |
| Validação de lucro líquido/execução real | **NÃO realizada** |
| Liberação de ordens na corretora | **NÃO** (sem código de execução) |

## Por que não foi possível fechar o estudo de equivalência original

- A página pública do fornecedor mostra 43 etiquetas de dois pregões com candles redesenhados; não entrega o código interno que determina as setas, histórico de decisões não emitidas, nem delta de agressão.
- A própria matemática não permite recuperar a classificação da agressão somente de OHLCV: o mesmo volume total pode ter deltas positivos ou negativos, conforme o lado que iniciou os negócios. O modelo de risco dos 43 vetores de publicidade está documentado em `docs/TRACKER_INVERSE_MATHEMATICS_RISK_2026-11-09.md`.
- O [Hub de Dados Públicos da B3](https://www.b3.com.br/pt_br/dados/hub-de-dados-publicos/) **proíbe coleta automatizada**, inclusive por IA, nos termos publicados na página. Não foi realizada coleta por robô no Hub. Outras fontes públicas encontradas oferecem cotações agregadas, não os negócios classificados necessários para reconstruir o gatilho.
- O terminal MT5 da Rico roda no computador do usuário, não no GitHub Actions e não está acessível a este chat. A API oficial `copy_ticks_range` lê o terminal local e requer conta/servidor com histórico disponível: https://www.mql5.com/pt/docs/python_metatrader5/mt5copyticksrange_py .
- **Não afirmar reprodução exata do Tracker Greenhouse**. O arquivo produzido é um indicador independente com funcionamento análogo em linhas e hipóteses de fluxo; a correspondência real precisa ser medida com sinais autorizados e histórico inédito.

## Instruções de execução local

1. Pelo site do GitHub, na branch desta PR, obter o arquivo-fonte `indicators/mt5/NQ_Win_Exaustao_Fluxo_Research.mq5` ou o artefato `.ex5` compilado acima. Instalar em `MQL5/Indicators` do MetaTrader 5 da Rico e adicionar ao gráfico do contrato WIN vigente, em M1. **O indicador não faz operações.**
2. Com Python 3.11 e terminal MT5 instalado/conectado, executar `executar_pesquisa_tracker_fluxo_MT5.cmd` na pasta do repositório. O iniciador cria venv, instala bibliotecas oficiais de Python e tenta buscar os dias 03/11/2026 e 04/11/2026 do vencimento WINZ26.
3. A coleta grava agregados locais em `private_mt5`, ignorados pelo Git; sem upload automático dos dados da corretora. Se os ticks não tiverem volume real, flags de agressão ou histórico suficiente, os minutos são reprovados, e **não há taxa de coincidência confiável**.
4. A comparação, quando viável, informa coincidência de sinais por direção e horário, não lucro nem equivalência garantida. Para demonstrar desempenho, é indispensável histórico fora da amostra, logs em tempo real e execução simulada com custos confirmados.

**Controle:** mudanças apenas nesta branch de pesquisa; sem merge em main, sem alteração dos robôs operacionais, sem envio de ordens ou acesso a dados privados neste job. Nenhum resultado financeiro novo foi produzido.
