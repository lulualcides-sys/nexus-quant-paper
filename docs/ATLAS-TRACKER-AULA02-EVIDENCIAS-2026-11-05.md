# ATLAS — investigação do Tracker / Aula 02 e evidências visuais
**Data da análise:** 05/11/2026 (America/Sao_Paulo)  
**Status:** investigação técnica; nenhuma fórmula proprietária obtida; nenhuma alteração de trading aprovada.

## Fontes e escopo realmente analisados
1. [Aula 02 — Como funciona o Tracker?](https://www.youtube.com/watch?v=zqI2EgUgUzc), vídeo público de **05min37s**, canal GREENHOUSE — Mercado Financeiro. O navegador exibiu a transcrição automática, convertida de fala em português para texto inglês. **Os tempos abaixo são aproximados, e o texto é paráfrase da transcrição**, não auditação do código do indicador nem transcrição humana certificada.
2. [Página oficial de oferta](https://lojadagreenhouse.com.br/ofertatracker/): afirma seta após candle confirmado, não repintagem, compatibilidade com Profit/BlackArrow/MT5 e exemplos WIN M1. Alegações comerciais não são fatos auditados de execução.
3. [Página oficial principal da loja](https://lojadagreenhouse.com.br/): demonstra o Fibonacci sobre o candle do sinal, níveis 0 a 100%, entrada 50%, alvo 200%, stop -100%.
4. Vídeo vertical MP4 **fornecido pelo usuário**, duração medida por ffprobe de **143,572 s**, 720×1280, 30 fps. Análise visual de quadros em ~24, 32, 48, 64, 80, 96, 120, 136 s. Não constitui sequência contínua de ticks/prints independentes.
5. Foram **identificados mas NÃO analisados em sua íntegra** os vídeos públicos [Método 1M](https://www.youtube.com/watch?v=PH_j7Q0xu0U) e [Tempo real](https://www.youtube.com/watch?v=IFBP4wEHSIU). Não inventar seu conteúdo, preço, horário de operação ou resultado.

## Evidências diretamente atribuíveis à fala do apresentador — Aula 02
| Tempo aproximado no vídeo | Fala/afirmação parafraseada | Evidência e limite |
|---|---|---|
| 00:34–00:54 | Método comercial exige cenário, desenvolvimento e confirmação, não somente uma seta | Descrição verbal da metodologia; não define fórmula |
| 01:09–01:38 | O programa analisaria estrutura geral do preço, desequilíbrios, zonas de liquidez e rompimentos de estrutura | Alegação de funcionalidades, não prova independente de cálculo |
| 01:45 | Apresentador menciona centenas de linhas de código | Não confere acesso ao código; número não auditado |
| 01:59–02:20 | Diz que a aula não detalha os critérios e menciona uso próprio de Fibonacci | **Critérios proprietários permanecem desconhecidos** |
| 02:36–02:55 | Procura áreas de liquidez extrema; diz que sinais de M5 em diante seriam relativamente escassos | Não define a taxa de sinais nem a fronteira das zonas |
| 03:29–03:56 | Avaliaria manipulação dentro das zonas antes da decisão | Não foi definida detecção de manipulação |
| 04:05–04:16 | Exigiria confirmação acumulada dos critérios | Hipótese arquitetural de filtros em AND, sem enumerar condições matemáticas |
| 04:25 | Estrutura rompida sem confluência do Fibonacci: sem sinal | **Exemplo de veto**, não uma condição algorítmica implementável sem limiar |
| 04:31 | Correção com zona institucional contrária adiante: sem sinal | Exemplo de veto que depende de delimitação desconhecida da zona |
| 04:37 | Área de reversão com manipulação ainda acontecendo: sem sinal | Exemplo de veto; define comportamento qualitativo, não cálculo |
| 04:46–05:27 | Sem promessa de milagres; necessidade de conhecimento, gestão/saídas parciais | Não comprova rentabilidade, winrate nem R:R |

**Correção importante:** o relato secundário do navegador sugeriu "Pine Script/TradingView" como plataforma. A oferta oficial cita Profit, BlackArrow e MT5; **não há evidência na aula para atribuir a linguagem de programação ou a plataforma TradingView**. Não reproduzir essa inferência como fato.

## O que o vídeo vertical disponibilizado realmente mostra (amostra de quadros)
| Tempo do MP4 | Evidência visual verificável | O que NÃO demonstra |
|---|---|---|
| ~24s | Um gráfico de candles com áreas de suporte marcadas e trajetória anotada | Não revela a condição booleana que produziu seta |
| ~32s | Interface com indicador de pontos/sinais do dia, e candles | Não prova execução de uma ordem preenchida |
| ~48s | Marcadores 'COMPRA', anotação aproximada de +529 pontos e múltiplos gráficos | Número na apresentação não é registro auditado de corretora |
| ~64s | Painel +6.054 pontos e '100% no dia de hoje' | Não documenta taxa histórica independente |
| ~80s | Sinal 'VENDA' sobre gráfico identificado como 'Dólar Mini' | **Não é uma amostra pura de WIN**; há WDO/mini dólar no conteúdo |
| ~96s | Outro gráfico com várias linhas e marcações manuais de níveis | Não estabelece que linhas fazem parte do algoritmo interno |
| ~120s | Depoimentos exibidos na tela, sem candles com data/hora verificáveis para rotular | Não pode ser alinhado à série WIN M1 |
| ~136s | Frase promocional 'O SINAL NÃO REPINTA' | Não prova não repintagem sem observar candles ao vivo |

**Conclusão:** o material mescla trechos promocionais, diferentes ativos, anotações visuais e depoimentos. Sem contrato WIN, data/hora de mercado e preços íntegros de cada seta, não é possível extrair dataset de treino rotulado confiável. **Não somar movimentos favoráveis exibidos no vídeo como operações efetivamente executadas**.

## Especificação vetorial verificável (página e imagem fornecida)
Candle confirmado com `H > L`, amplitude `R = H-L`, direção `s=+1` (compra) ou `s=-1` (venda):
- Origem `O = L` para compra e `O = H` para venda.
- Preço no nível `p% = O + s * (p/100) * R`.
- Entrada `E=O+s*0.5R`, alvo `T=O+s*2R`, stop `S=O-s*R`.
- Distância a alvo `|T-E|=1.5R`; distância a stop `|E-S|=1.5R`; **R:R nominal = 1:1, não 1:2**.
- Definir geometria não resolve de onde veio o `s`, como é elegível o candle, regras de cancelamento, volume, contexto e execução.

## Hipóteses para ATLAS independente — não atribuir ao Tracker sem evidência
1. **Contexto ex ante:** swing highs/lows confirmados usando somente barras fechadas anteriores; localizar regiões de liquidez em máximas/mínimas repetidas.
2. **Desequilíbrio mensurável:** testar FVG de três candles fechados como proposta, NÃO presumir ser a definição Greenhouse.
3. **Quebra estrutural:** testar fechamento acima/abaixo de pivô já confirmado, sem lookahead; definição de pivô e tolerâncias pré-registradas.
4. **Rejeição/sweep:** preço ultrapassa extremo previamente identificado e fecha de volta, de acordo com direção definida antes do sinal.
5. **Confluência Fibonacci:** a aula confirma a existência de confluência, mas **seus níveis/âncoras exatos não são divulgados**; formular variantes independentes com parâmetros publicados.
6. **Veto por obstáculo:** se zona de liquidez/estrutura oposta estiver entre entrada e alvo, rejeitar a ordem — somente após delimitar objetivamente as zonas.
7. **Veto por manipulação não resolvida:** sem definição mensurável do conceito na aula, **não implementar uma regra arbitrária como se fosse oficial**.
8. **Crítico:** OHLCV agregado não mostra agressão/delta bid-ask ou manipulação institucional real. Para esses conceitos usar dados compatíveis; não inferir fluxo real a partir de cor do candle.
9. **Sinal somente após candle fechado**, ordem 50% só nos candles seguintes; distinguir momento da seta de momento do fill. Não presumir execução se o preço tocar vários níveis num candle de OHLC.

## Protocolo indispensável para validação contra os vídeos
Cada seta de vídeo só pode virar uma linha de dados se contiver **data do pregão, horário no eixo do gráfico, símbolo/contrato WIN/ WDO, timeframe, direção, preço/candle do sinal e instante em que a marcação aparece em relação ao fechamento**. Campo ausente = `unverifiable`, não preencher por suposição. O tempo do player (mm:ss) **não é o horário do mercado**.

1. Obter transcrição e sequências visuais do [Método 1M](https://www.youtube.com/watch?v=PH_j7Q0xu0U) e [Tempo real](https://www.youtube.com/watch?v=IFBP4wEHSIU); ainda pendentes nesta execução.
2. Rotular sinais positivos/negativos **em gravação contínua**, preservando todos os sinais e possíveis setas ausentes; snapshots promocionais não servem para medir sensibilidade ou precision.
3. Alinhar às velas M1 do **mesmo contrato WIN**, tick de 5 pontos e R$0,20 por ponto/contrato; verificar rolagem e timestamp local America/Sao_Paulo.
4. Comparar hipóteses com métricas para `TP`, `SL`, ordens não preenchidas, custos, slippage, drawdown e *expectancy* após custos, sempre separando vídeo, dado retrospectivo e paper-forward.
5. Só promover ao ATLAS prospectivo após número adequado de eventos rotulados e validação fora da amostra independente do desenvolvimento.

## Estado e decisão
- Aula 02 estudada por transcrição automática; MP4 do usuário amostrado visualmente.
- **Aulas de execução e gravação contínua ainda não estudadas integralmente.**
- Nenhuma fórmula exata/limiar interno encontrado.
- Nenhum histórico WIN M1 autenticado encontrado neste lote.
- **NÃO alterar o detector principal ou imputar lucro ao ATLAS**.
- Preservar resultados de GC=F M5–H1 como estudo de OUTRO mercado, nunca evidência do Tracker no WIN.
