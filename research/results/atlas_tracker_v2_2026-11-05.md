# ATLAS #28 — Tracker v2: pesquisa e validação independente
**Executado:** 05/11/2026, GitHub Actions [run 42050233995](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42050233995).

## Evidências e limitações da reprodução
- O vídeo enviado (143,57 segundos) apresenta gráficos, setas, valores em pontos e depoimentos, mas **não revela a fórmula proprietária de detecção**.
- A [loja oficial](https://lojadagreenhouse.com.br/) apresenta o candle fechado, Fibonacci 0–100% espelhado, **entrada 50%**, **alvo 200%**, **stop −100%**. Sob essa geometria a relação distância-alvo/distância-stop é **1:1**, não 2:1.
- A [página do Tracker](https://lojadagreenhouse.com.br/ofertatracker/) divulga exemplos no mini-índice WIN M1; números do marketing não substituem comprovantes de fills de corretora, datas, custos e todas as operações.
- Não se pode provar absorção, agressão (delta) ou grandes participantes **a partir de OHLCV agregado**. Os novos filtros são hipóteses de exaustão de preço, não extração da regra interna do Tracker.

## Comparação retrospectiva GC=F, ouro, M5 a H1
**Base:** Yahoo 5m OHLCV, UTC 2026-10-05 13:55 – 2026-11-05 14:45. Banca virtual US$ 5.000, risco 0,75%, limite nocional 1x; execução OHLC conservadora; custo total ilustrativo de 7 bps ida+volta.

| TF | Detector | Fechamentos | Winrate | P&L US$ | PF | DD fechado | Trades nos últimos 30% | P&L últimos 30% |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| M5 | original | 112 | 45,54% | −524,27 | 0,403 | 10,56% | 28 | −239,86 |
| M5 | exaustão | 40 | 57,50% | −123,86 | 0,531 | 2,828% | 10 | −106,39 |
| M5 | exaustão + direção | 7 | 85,71% | +27,61 | 2,613 | 0,341% | **0** | **0,00** |
| M15 | original | 48 | 43,75% | −244,28 | 0,589 | 5,556% | 16 | −215,86 |
| M15 | exaustão | 24 | 29,17% | −295,24 | 0,207 | 5,905% | 6 | −148,98 |
| M15 | exaustão + direção | 6 | 16,67% | −74,69 | 0,196 | 1,499% | 0 | 0,00 |
| M30 | original | 23 | 56,52% | +1,96 | 1,007 | 1,786% | 4 | −59,48 |
| M30 | exaustão | 8 | 37,50% | −77,17 | 0,411 | 1,543% | 1 | −34,57 |
| M30 | exaustão + direção | 4 | 50,00% | −20,45 | 0,614 | 0,554% | 0 | 0,00 |
| H1 | original | 10 | 50,00% | −23,89 | 0,880 | 1,620% | 4 | −5,69 |
| H1 | exaustão | 2 | 0,00% | −76,46 | 0 | 1,529% | 1 | −35,51 |
| H1 | exaustão + direção | **0** | N/D | **0,00** | N/D | 0,000% | 0 | 0,00 |

**M5 exaustão+direção sob custos maiores:** 7bps +US$27,61; 14bps +US$3,04; 28bps **−US$45,77**. São 7 operações, e **0 no trecho cronológico final**. Isso NÃO justifica publicar o detector em paper-forward ou declarar lucro consistente.

## WIN B3 — ferramenta preparada, resultado ainda indisponível

O simulador `research/atlas_win_backtest.py` usa `research/win_price_data.py` para importar CSV genuíno do Profit/Nelogica e aplicar:
- WIN tick **5 pontos**, valor de cada ponto por minicontrato **R$ 0,20** ([especificação B3](https://www.b3.com.br/pt_br/produtos-e-servicos/negociacao/renda-variavel/futuro-mini-de-ibovespa.htm)).
- Entradas e stops na grade do WIN, contratos **inteiros**, risco de até **0,75%** da banca virtual R$5.000 por distância nominal do stop, até **3 contratos**.
- Janela conservadora de entrada 09:10 a 17:30 BRT, fechamento de sessão/posição, validade de ordem por até 3 candles e saída pessimista para ambiguidades OHLC.
- Cenários custo ilustrativo R$4,00 de taxas ida+volta por contrato + 0/1/2 ticks de slippage **por lado**. Isso não representa taxas executáveis verificadas.
- Comparação de M1, M5, M15, M30 e H1 com a mesma base real M1, respeitando lacunas e sem mudar de símbolo/vencimento silenciosamente.

**Estado da última CI:** `WIN_NOT_TESTED: no independently sourced WIN M1 CSV is present`. **Nenhum winrate ou P&L de WIN foi calculado.** Não substituir WIN por GC=F, IBOV ou dados fictícios.

### Como reproduzir quando existir uma exportação legítima M1
CSV com separador `;`, colunas `Ativo;Data;Hora;Open;High;Low;Close;Volume`, data `DD/MM/YYYY`, horário local America/Sao_Paulo, preço/volume reais, ticker consistente (WINFUT ou vencimento WIN...), ordenado por tempo, sem candle aberto.

```bash
python -m unittest discover -s tests -p 'test_atlas_tracker_v2.py' -v
python -m research.atlas_win_backtest --win-csv /caminho/para/WINFUT_M1.csv
# comparação do OURO, não do WIN:
python -m research.atlas_tracker_v2
```

### Decisão de promoção
- CI: 7 testes focados passaram, comparativo GC=F executado, workflows de regressão também verdes na PR.
- **NÃO alterar motor prospectivo do ATLAS #28**, nem os 27 outros, nem o relatório diário existente: vantagem não validada.
- Para aprovar um detector, exigir dados WIN específicos com origem e vencimentos auditáveis, profundidade temporal e validação walk-forward sem ajuste na mesma janela; reportar *expectancy* líquida, PF, DD, custos, quantidade de fechamentos, liquidez e períodos sem sinais.
- Comparar 3 hipóteses implica risco de seleção retrospectiva; os 7 trades vencedores não demonstram persistência.
