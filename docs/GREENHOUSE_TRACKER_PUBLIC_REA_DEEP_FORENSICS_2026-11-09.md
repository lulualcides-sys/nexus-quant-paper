# Greenhouse Tracker — auditoria aprofundada do gatilho (REA + 43 marcações públicas)

**Data: 09/11/2026. Estado: EVIDÊNCIA PARCIAL. NENHUM CÓDIGO ORIGINAL DO TRACKER RECUPERADO.**

## Escopo executado e verificável

- REA 6.8.0 executado de verdade na inspeção estática dos 77 scripts públicos e na captura de página Chromium do site comercial. Auditorias anteriores: [REA código](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42676958276), [REA navegador](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42677601236).
- Seis vídeos MP4 públicos auditados em 108 quadros espaçados, não vistos integralmente frame a frame e sem transcrição de áudio: [auditoria de mídia](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42677523175). O vídeo de 13/10 tem 146,47 s e é editado. Os cinco vídeos do YouTube incorporados recusaram a coleta sem autenticação e não foram assistidos: [resultado](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42679480309).
- Painel público usa uma tabela estática `D.s` de 43 labels e candles 1 min redesenhados em `D.d`. Extraímos o formato de forma declarativa (sem executar Javascript de terceiros): [auditoria de 43 labels](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42678674974). Os arrays são **dados promocionais**, não o motor do indicador.
- [Nova auditoria de correspondência e seis testes unitários passaram](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42681234834). Scripts `research/greenhouse_deeper_signal_forensics.py` e `tests/test_greenhouse_public_price_forensics.py` guardados na PR #51, relatório JSON no artifact de GitHub Actions.
- REA foi direcionado a navegar dois botões públicos `Próximo` no demonstrador. [O job do REA executou](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42680648251), mas **o primeiro clique falhou** por timeout procurando o botão acessível; os cliques seguintes foram cancelados. O resultado registra o primeiro label do DOM, mas NÃO comprova paginação manual de outros sinais. Não confundir `conclusion: success` do workflow com sucesso da ação browser.

## O que a própria Greenhouse diz sobre a estratégia

- Na [loja oficial](https://lojadagreenhouse.com.br/), o Tracker é apresentado como **exaustão/reversão a partir do volume**, perto de topo ou fundo, e o Titan como **seguidor de tendência**. Alegação comercial, não código.
- O [Método DEC](https://metododec.com/) ensina **Direção, Estrutura e Confirmação**: detectar controle do preço, região técnica e candle de gatilho que fecha a favor. **Não há prova de que o Tracker implementa os três módulos literalmente nem seus períodos e limites.**
- A loja descreve a projeção visual do candle de sinal com 0% e 100%, entrada 50%, alvo 200%, stop -100%, espelhando para venda. Isso produz payoff bruto aproximadamente **1:1** (custos excluídos).

## Forense quantitativa dos sinais públicos de 03 e 04/11/2026

- A página oferece **565 e 562 candles M1 redesenhados** respectivamente, total 43 labels, dos quais **41** possuem 20 candles anteriores necessários ao nosso diagnóstico de preço.
- **31/41** labels têm candle alinhado com compra/venda no minuto rotulado.
- **12/41** possuem pavio direcional de ao menos 35% da amplitude do candle.
- **11/41** ultrapassam topo/fundo dos 20 candles anteriores em pelo menos 5 pontos WIN.
- **4/41** cumprem TODOS esses critérios de preço simultaneamente, incluindo fechar de volta no intervalo anterior. **Não reproduz a maioria dos sinais da publicidade.**
- Se aplicarmos a MESMA hipótese ao candle anterior ao minuto rotulado, **0/41** atendem a todos os critérios.
- Um único sorteio reprodutível de 43 candles dos mesmos dias com proporção de compra/venda preservada gerou 0 casos completos. **Esse sorteio é uma referência descritiva, não estimativa estatística de qualidade, p-valor ou confirmação de vantagem.**
- Dos 43 sinais, **9** coincidem dentro de 5 pontos com a geometria 0/50/200/-100 de candle redesenhado no próprio minuto. **0** coincidem com a vela imediatamente anterior. Na busca por deslocamentos de ±20 minutos, não surgiram outros matches dentro de 5 pontos. Isso aponta falta de alinhamento entre etiquetas e candle de origem no demonstrador, não prova de erro do algoritmo original.
- **43/43** têm distâncias entrada→alvo e entrada→stop praticamente 1:1, com diferença máxima de 5 pontos. Nenhum P&L declarado pode ser tratado como ganho líquido realmente executado.
- O demonstrador NÃO expõe `real_volume`, `tick_volume`, volume por preço, agressor comprador/vendedor ou feed bid/ask. Portanto **não é possível identificar o gatilho de fluxo/volume** a partir dessa tabela. Essas informações são mais importantes do que copiar as linhas.

## O que isso implica para nosso indicador MT5

- O atual detector `NQ_Vector_Exhaustion_Research.mq5` usa hipótese própria de rompimento falso, 20 barras, 1,30× volume real e pavio de 35%. É **um indicador novo de pesquisa, NÃO a réplica Tracker**. Não afirmar equivalência ou lucro.
- **Não alterar os thresholds** para ajustar a tabela de 43 exemplos escolhidos pela publicidade. Isso é overfitting. Manter PR #51 rascunho e nenhum Expert Advisor com ordens.
- Para construir versão aproximada sem licenças: usar dados originais WINZ26 M1 e, se possível, negócios/ticks de 03 e 04/11; construir detectores de reversão por exaustão, absorção e confirmação fechada, comparar timestamps/precisão com os labels públicos, separar treino e teste em dias novos e validar custos e slippage reais.
- Mesmo obtendo os dados de 03/04, aqueles dois dias já são amostras vistas/selecionadas e não são validação OOS. Precisamos de pregões inéditos e demonstrar ausência de repaint ao longo do tempo.
- **Limitação decisiva:** o site entrega o código do **apresentador** dos vídeos/canvas, não o código licenciado do indicador. Nem REA nem assistir a seis vídeos tornam o algoritmo interno identificável matematicamente.

## Próximos requisitos comprováveis

1. Exportação legal de volume de negócios/ticks de WINZ26 (ou vencimentos apropriados) e M1 íntegro, em datas específicas, via terminal e fontes autorizadas.
2. Registro independente da evolução temporal das setas do produto original, caso o usuário possua acesso válido ou vídeo contínuo público com resolução suficiente; não extrair código ou material protegido de área restrita.
3. Teste de concordância por timestamp **antes de ver resultado do trade**. Separar direção, sinal antecipado e níveis de preço. Analisar falso-positivo/falso-negativo, custo líquido e restrição de capital.
4. Compilação MQL5 em MetaEditor real e confirmação visual de que nossa nova hipótese não repinta.

**Não há autenticação da declaração de permissão dos proprietários para redistribuição do Tracker original. A investigação usou conteúdo publicamente disponível sem credenciais.**
