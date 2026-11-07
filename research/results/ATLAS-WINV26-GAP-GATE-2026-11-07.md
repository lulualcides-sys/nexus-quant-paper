# ATLAS — 07/11/2026: bloqueio WINV26 M1 e integridade do replay B3

## Verificação prévia
Lidos issue #19 e comentários até 06/11/2026, PR #23 e importadores atuais `research/atlas_win_oct13.py`, `research/atlas_b3_ticks_oct13.py`, `research/atlas_tracker_observability.py`. Não repetir a pesquisa Trader Gráfico, fontes de WIN diário, nem tratar publicidade como execução.

## Fonte adicional examinada
- [Backtester](https://backtester.com.br/) anuncia CSVs intradiários M1–D1 e séries contínuas WIN/WDO. **A própria página distingue o plano grátis Essencial do B3PRO para WIN/WDO** e diz que download depende de login; não foi feito login, cadastro ou pagamento. **Não há CSV WINV26 M1 do dia 13/10/2026 publicamente baixável e verificado na página examinada**. Uma série contínua ou ajustada, mesmo em M1, não substitui contrato WINV26 bruto sem metadados de rolagem.
- [NegocIA](https://negociab3.com.br/ticks/) anuncia dados tick a tick, mas acesso exige pagamento: não elegível.
- A evidência comercial [vídeo 13/10](https://www.youtube.com/watch?v=g5Jo41A03yE) já está catalogada na issue #19; não há extração independente confirmada de 27 setas com horário de mercado, candle fechado e sessão contínua. Não inferir preenchimentos da seta.

## Falha concreta de integridade corrigida
O importador de negócios B3 `match_signals()` aceitava **>=400 candles M1**, mas podia permitir comparação de setas com **até 100 minutos ausentes** entre 09:10 e 17:29, ao contrário do importador Profit que já exigia 500 minutos completos. Esse erro poderia distorcer janelas de sinais e o histórico prévio de indicadores.

A nova regra verifica **o dia 13/10/2026 e cada um dos 500 minutos esperados**, computa os ausentes e seus 20 primeiros horários e **bloqueia a comparação de sinais se houver qualquer lacuna**. Não preenche minutos artificiais, não converte uma seta em fill, não faz scrape e não modifica a estratégia. Este é um critério conservador de integridade para comparação de sinais: minutos sem negócio podem ser reais, mas sem comprovação de sessão contínua não serão classificados como observação completa.

Cinco testes com candles **SINTÉTICOS**: 500/500, 499/500 com lacuna interna, 420/500, 399/500 e 500 barras em data errada. Regressões de importação B3, Profit e observabilidade executadas no CI da PR. Testes sintéticos **não** são evidência de WINV26 real.

## Decisão
**Aceitar a correção de integridade apenas se CI verde. Rejeitar qualquer alegação de Tracker reproduzido ou rentabilidade.** Falta fonte gratuita e legal de WINV26 M1 de 13/10/2026 com proveniência, e gravação contínua das setas com horários de mercado e confirmação pós-fechamento. Depois de obter dados autênticos, reservar dias/contratos não usados no desenvolvimento, reconciliar setas versus ordens efetivamente executadas, custos e slippage. Sem dados, nenhum backtest financeiro novo.
