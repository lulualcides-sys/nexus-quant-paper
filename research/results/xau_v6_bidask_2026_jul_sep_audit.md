# Nexus Quant XAU V6 — validação negativa em 3 meses de BID/ASK

**Verificação:** [GitHub Actions run 42899394361](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42899394361), **75 testes unitários aprovados**, workflow concluído com sucesso; artefato imutável por execução `xau-v6-older-bidask-paper-research` (ID 13801608185). **Esta análise é retrospectiva, NÃO são ordens reais, e nenhuma estratégia nova foi aprovada.**

## Fonte e integridade

- XAUUSD spot MID para sinais derivado de cotações BID e ASK de M1 da Dukascopy, obtidas por espelho público `kevingtlin/Market-Data-Lab`, commit fixado **`b60bd71d0e34a42cb962daf688ff252e73f409ca`**. O repositório espelhado NÃO é uma corretora diferente, e as cotações NÃO são fills da FBS.
- 2026-06-25 até junho/2026: aquecimento; negociação virtual avaliada de **2026-07-01 a 2026-09-30**, três meses-calendário anteriores à janela de desenvolvimento V4 de outubro–novembro.
- **108,743 minutos sincronizados BID+ASK; 21,743 candles M5 completos;** 7 blocos M5 incompletos excluídos e 1 minuto com só um lado. Nenhuma interpolação; SHA256 de cada um dos oito CSV preservado no JSON.
- Spread mediano observado na abertura M5: **US$ 0.69/onça**. O spread está embutido nos fills via ASK/BID, sem dupla cobrança. Slippage adicional de ida e volta conforme indicado por lado abaixo. Não foram simulados swaps, comissões específicas da conta FBS, liquidez, requotes ou execução por ticks; os extremos da vela de 5min têm ordem desconhecida (adotado stop-first).
- Sinais **congelados da V4 pós-ablação**, sem novos filtros ou parâmetros ajustados ao histórico novo. Stop 3×ATR10, take-profit 3R, time exit 36 candles, risco-stop planejado 0,75%, máximo 1× exposição nocional, lote mínimo 1 onça, uma posição de cada vez.

## Banca virtual US$ 5.000 — mesmo portfólio, 3 meses sequenciais

| Slippage extra **por lado** em US$/onça | Operações fechadas | Líquido 3 meses | Retorno sobre banca inicial | Profit factor | Drawdown realizado máximo | Sinais barrados por lote mínimo/exposição |
|---|---:|---:|---:|---:|---:|---:|
| US$ 0.00 | 566 | US$ -744.08 | -14.882% | 0.814 | 19.358% | 1199 |
| US$ 0.15 | 531 | US$ -754.07 | -15.081% | 0.802 | 18.768% | 1470 |
| US$ 0.75 | 329 | US$ -863.17 | -17.263% | 0.655 | 19.745% | 3195 |
| US$ 1.50 | 263 | US$ -984.59 | -19.692% | 0.539 | 20.778% | 3752 |

A carteira principal com US$ 0,15/slippage por lado: **35.59% winrate**, 531 operações fechadas, **1470 entradas barradas** pelo lote mínimo de 1 onça e teto 1× quando o capital diminuiu. Não confundir "menos trades" por limitação de capital com vantagem estatística. Drawdown reportado de posições **fechadas**, pode subestimar perdas intratrade.

### Meses testados em carteiras virtuais separadas de US$ 5.000

| Mês | Fechadas | Líquido (US$0,15/slippage por lado) | Retorno do mês sobre US$5.000 | PF |
|---|---:|---:|---:|---:|
| 2026-07 | 250 | US$ -234.96 | -4.699% | 0.855 |
| 2026-08 | 234 | US$ -435.95 | -8.719% | 0.751 |
| 2026-09 | 216 | US$ -388.80 | -7.776% | 0.761 |

**Atenção:** os períodos acima são três simulações **reiniciadas** em US$5.000. Não somar seus lucros/perdas ou contagens como se fossem uma única carteira contínua. A carteira contínua teve 531 fechamentos; os folds têm mais entradas porque o capital reinicia, eliminando os bloqueios acumulados do lote mínimo.

### Sensibilidade ao tamanho da banca (apenas diagnóstico, US$ 10.000 virtuais)

| Slippage extra por lado | Fechadas | Líquido 3 meses | Retorno sobre US$10 mil | PF | Bloqueios de lote mínimo |
|---|---:|---:|---:|---:|---:|
| US$ 0.15 | 704 | US$ -1,789.05 | -17.891% | 0.785 | 0 |
| US$ 0.75 | 726 | US$ -2,702.01 | -27.020% | 0.669 | 0 |

Nenhum filtro ou regra alterado: banca maior reduz a impossibilidade mecânica de comprar a menor unidade negociável. O prejuízo persiste com mais operações. **Este segundo capital não substitui a simulação de US$5.000 nem é promessa de desempenho escalável.**

## Fragilidade estatística e decisão

- No cenário de US$ 5.000 e US$ 0,15/slippage por lado, o bootstrap por dias de negociação com fechamentos (3000 reamostragens IID, diagnóstico de fragilidade apenas) retornou **US$ -1,469.46 a US$ -69.03** para o lucro líquido fechado do período. Os dias não são necessariamente independentes; não interpretar isso como prova formal de ausência de edge.
- TODOS os três meses foram negativos na simulação mensal ao custo de US$0,15 por lado, e o estresse piora o resultado. A V4 com dados de novembro do futuro GC=F apresentava retorno positivo, mas **falhou na transferência temporal para XAUUSD spot**. Isso não prova que todas as estratégias de ouro são negativas, apenas **rejeita a evidência atual de robustez da V4**.
- `research_screen_pass`: **False**. `live_approved`: **False**. Nunca enviar ordens reais automaticamente, nem fazer merge desta pesquisa no motor de produção.

## Próximas prioridades sem sobreajustar

1. Não adicionar filtros ou otimizar stops usando estes mesmos três meses para inverter o resultado; preservar o resultado negativo como controle.
2. Validar os robôs anteriores com expectativa bruta historicamente positiva (ex.: Channel20 H4) **no mesmo BID/ASK spot e períodos distintos**, preservando o protocolo e sem comparar métricas incompatíveis de GC=F e XAU spot.
3. Obter novo período ainda não usado e bid/ask **da conta efetiva** para contabilizar swap, spread variável na execução, slippage e comissões. Apenas depois de validação temporal e prospectiva independente considerar homologação com posições fictícias contínuas.

**Transparência:** uma tentativa anterior de download diário direto da Dukascopy (Action #42897006513) falhou por conexão; a execução válida usou o espelho público PINNED de M1 e gerou todos os resultados com fontes SHA256. O workflow final [#42899394361](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42899394361) encerrou em sucesso.