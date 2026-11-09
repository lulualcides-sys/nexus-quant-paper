# Auditoria REA do site público Greenhouse Tracker — 09/11/2026

**Escopo e limites:** análise somente das páginas comerciais públicas, do JavaScript entregue ao navegador e dos MP4 públicos apontados pelas páginas. Sem login, compra, área de membros, código proprietário do indicador ou operações financeiras. Não reproduzir materiais comerciais na distribuição do Nexus Quant.

## Conferência complementar dos vídeos incorporados do YouTube

- O HTML público faz referência a **cinco IDs** do YouTube: `g5Jo41A03yE`, `NiWQ5otSEIM`, `PH_j7Q0xu0U`, `WacleOhwv7Y`, `zqI2EgUgUzc`. A análise de quadros desses vídeos **não foi concluída**.
- [Workflow de verificação de YouTube](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42679480309): a tentativa de obter metadados e assistir às fontes públicas via `yt-dlp` foi recusada pelo YouTube com exigência de autenticação. O script não recebeu cookies e **não tentou contornar a restrição**. O workflow terminou sem erro técnico, mas a inspeção desses cinco vídeos tem status **bloqueado/indisponível**, e não `analisado`.
- A auditoria visual abaixo é restrita aos **seis vídeos MP4 efetivamente acessíveis** com 108 quadros amostrados, não ao conjunto completo das aulas do YouTube.
## O que foi executado (verificável)

- [REA static analysis (GitHub Actions 42676958276)](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42676958276): pacote oficial REA analisou **77 scripts/arquivos JavaScript públicos** extraídos de três páginas; saída JSON com 44,9 MB e digest imutável de Evidence. Esse material é código do **site e de seu painel demonstrativo**, não o código do Tracker de Profit/BlackArrow/MT5.
- [REA Chromium/browser runtime (GitHub Actions 42677601236)](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42677601236): o REA abriu a página pública em um Chromium 156 isolado, aguardou o carregamento e capturou DOM, acessibilidade e eventos de rede. Retornou exit code 0 e Evidence de `capture_browser_scenario`. Nenhum clique de compra, login, POST, ou acesso protegido.
- [Auditoria de vídeo e FFmpeg (GitHub Actions 42677523175)](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42677523175): os seis MP4 públicos foram baixados temporariamente e inspecionados por **18 quadros distribuídos ao longo de cada duração**, total **108 quadros**. Mídia e quadros foram removidos do runner; só metadados foram guardados. O áudio **não foi transcrito**, e a inspeção não cobre todos os quadros intermediários.
- [Decodificador do painel público (GitHub Actions 42678674974)](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42678674974): extraídos de forma estática os candles e os registros de operação embutidos no gráfico publicitário dos dias 3 e 4/11. Não se executou JavaScript não confiável e não se invocou API privada.

## Conteúdo visual realmente visto nos MP4

| Referência pública | Duração FFprobe | O que é visível nos 18 quadros amostrados | O que NÃO comprova |
|---|---:|---|---|
| `tracker-pregao-13-10.mp4` | 146,47 s | Vertical, editado, alterna gráficos desfocados, contadores numerados, anotações e tela final +8.819 pts | Não é fita contínua; não comprova as 27 entradas, fills ou ausência de repintura |
| `tracker-pregao-13-10-previa.mp4` | 10,30 s | Prévia vertical | Não valida condições pré-sinal nem operações |
| Antiga página `/tracker/`: `1.mp4` | 51,18 s | Elementos promocionais, logos, prints e gráficos estilizados | Não é código-fonte e não demonstra fórmula do sinal |
| Antiga página `/tracker/`: `2.mp4` | 77,39 s | Filmagem do monitor com gráfico e linhas horizontais; mostra regiões marcadas | O vídeo não revela parâmetros internos de detecção, nem backtest reproduzível |
| Antiga página `/tracker/`: `3.mp4` | 49,97 s | Vídeo editado com gráficos, marketing e setas | Sem exportação de entradas/sinais de máquina |
| Antiga página `/tracker/`: `0121-1.mp4` | 48,58 s | Rolagem de mensagens da comunidade e prints de operações | Depoimentos não são registros independentes da B3 |

**Atenção:** nomes de arquivos `1.mp4`, `2.mp4` e `3.mp4` são genéricos. Não foram assumidos como as aulas 01/02/05 divulgadas no player YouTube; essa equivalência NÃO foi confirmada. O vídeo do dia 13/10, rotulado como 'pregão completo' na publicidade, é uma montagem de 2m26s, não um replay integral de mercado em tempo real.

## Prova limitada e forte: o próprio painel público em JavaScript

O código visível do site embute arrays compactados `D.d` (candles **redesenhados**) e `D.s` (marcações) que alimentam um `canvas` interativo. O decoder público está em `research/greenhouse_public_gallery_decode.py`. Isso demonstra como a **página** plota os registros; **não contém nem demonstra o gerador proprietário de sinais**.

- 03/11/2026: **19 marcações** no array, com **16** rotuladas `w` (alvo) e **3** `l` (stop), e soma dos pontos listados de +2.835.
- 04/11/2026: **24 marcações**, **20** no alvo e **4** no stop, e soma dos pontos listados de +5.420.
- Total **43**, com **36** ganhos rotulados e **7** perdas rotuladas. Confere com as contagens publicitárias da página; não comprova fills.
- Em **43/43 marcações**, as distâncias brutas entrada→alvo e entrada→stop diferem por no máximo 5 pontos WIN. Isto reforça uma estrutura de payoff bruto **aproximadamente 1:1**, antes das taxas e slippage.
- Somente **9 das 43** marcações do painel coincidem, dentro de 5 pontos em todos os níveis, com a geometria 0/50/200/-100 aplicada à máxima e mínima do candle **redesenhado no mesmo minuto** da etiqueta. **0 das 43** coincidiram com a vela do minuto anterior sob essa regra estrita. Isso NÃO prova que o Tracker usa outra fórmula: o gráfico é uma reconstrução do vídeo, os timestamps podem não identificar a vela de sinal e existe arredondamento na grade de 5 pontos. Mas prova que não se pode chamar a equivalência matemática de 'confirmada pelo replay' com os dados disponíveis.
- Exemplo público: sinal 1 do dia 03/11 às 09:04 marcado como compra, entrada 167.645, alvo 168.150, stop 167.135, resultado `l`; a distância entrada-alvo é 505 pontos e a distância até stop é 510 pontos. O número de pontos exibidos é -505, ou seja, não se deve supor que seja igual a uma liquidação real com todos os custos.
- Exemplo público: sinal 43 do dia 04/11 às 18:04 marcado como venda, entrada 169.680, alvo 169.595, stop 169.765, resultado `w`, soma +85 pontos. São anotações da demonstração, não registros de ordens enviados à corretora.

## Evidências separadas de hipóteses

| Proposição | Status |
|---|---|
| Tracker anuncia versão MT5, Profit e BlackArrow | Confirmado como alegação vigente no site público; não validada na instalação |
| Setas são fixadas após candle fechado, 'não repinta' | Descrição comercial pública; vídeos amostrados não permitem teste causal independente |
| Geometria de cinco linhas / entrada 50%, alvo 200%, stop −100% | Confirmada na explicação pública e consistente com distâncias ~1:1 do painel |
| Sinal vem de um sweep de 20 candles, volume 1,30× e 35% wick | **Não comprovado:** é apenas hipótese do indicador **NQ** atual |
| Detector original do Tracker foi recuperado pelo REA | **Não**. Inspecionamos o JS da loja e do demonstrador, não o binário do indicador licenciado |
| A propaganda comprova 36 entradas reais e lucro líquido constante | **Não**. Não há fluxo de ordens, preço de preenchimento, comissões, risco e dados tick independentes |

## Próxima ação tecnicamente justificável

1. Usar os 43 horários da página pública como **conjunto de referência fraca** para investigar contextos de mercado, nunca como verdade absoluta nem como validação fora da amostra.
2. Obter histórico completo e não ajustado de WINZ26 para 03 e 04/11 via terminal MT5/Rico, com UTC, volume real e ticks. Não usar candles sintéticos reconstruídos do anúncio para validar vantagem financeira.
3. Comparar nossos timestamps com dados brutos. Separar precisão por sinal, cobertura, falsos positivos e se o gráfico original tem marcação pré- ou pós-fechamento. Não calibrar em ambos os dias e chamá-los de OOS.
4. Para replicar de forma mais próxima a leitura de fluxo, seria necessário um feed legítimo de negócios por preço/agressão e exemplos em tempo real, não só o site comercial.
5. **Não alterar os thresholds 20 / 1,30× / 35% da PR #51 apenas para ajustar os sinais de um replay publicitário**. Continuam como hipótese que precisa de dados e teste prospectivo.

## Referências públicas

- https://lojadagreenhouse.com.br/ofertatracker/
- https://lojadagreenhouse.com.br/ (explicação pública da Fibonacci do candle de sinal)
- https://rea.tools/ e https://rea.tools/guides/browser/

**Decisão:** REA foi utilizado de verdade e mostrou como funciona o front-end de demonstração. Nenhuma afirmação de acesso ao código original, de lucro consistente ou de implantação live foi feita. PR permanece draft, sem merge e sem alteração de robôs operacionais.