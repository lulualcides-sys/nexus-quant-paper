# Pesquisa XAUUSD — 200 entradas / 30 dias, V4 (10/11/2026)

**Execução verificável:** [GitHub Actions #42881115366](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42881115366); 40 testes unitários, workflow `success`. [PR #68](https://github.com/lulualcides-sys/nexus-quant-paper/pull/68) draft. Esses relatórios documentam **simulações retrospectivas paper-only** e **NÃO** demonstram lucro real/recorrente.

**Histórico de preços:** Yahoo GC=F futuro contínuo do ouro, não spot FBS. M5 observado de `2026-10-11T22:10:00+00:00` a `2026-11-10T18:50:00+00:00`, 6022 candles; SHA256 de serialização JSON canônica do OHLCV: `407a2117890d820148ca757283b785a8e8012f5fa948e8ca8b75120cf6fda697`. A seleção de parâmetros e da ablação ocorreram **depois de analisar esse período**, logo as janelas abaixo não são validação out-of-sample independente.

## Resultado

- **V4 completo:** 206 operações encerradas no recorte; taxa **estimada** 212.4 a cada 30 dias, não 200 confirmadas num mês calendário integral. Gatilhos de EMA20, Canal12, sweep de pivô e momentum; um único símbolo e uma posição por vez.
- **V4 ablação retrospectiva, sem MOMENTUM_2BAR:** 202 operações, taxa estimada 208.3 a cada 30 dias. REMOVER uma família de sinais não adiciona filtros redundantes, mas a decisão pós-hoc pode estar sobreajustada.
- As posições são arredondadas para baixo em **passos de 1 onça** equivalentes a 0,01 lote padrão FBS (contrato 100 onças por lote), com risco-stop planejado <=0,75% do patrimônio e exposição nocional <=1x.
- Stop = 3 ATR(10), alvo = 3R, máximo 36 candles M5. Regras selecionadas para atingir frequência na MESMA amostra. Não houve otimização prospectiva independente.

## Comparação de custo e lucro virtual em US$ (capital inicial de US$5.000)

| Custo hipotético da operação completa | Operações V4 | P&L V4 | P&L sem Momentum (operações) |
|---|---:|---:|---:|
| Sem custos | 206 | +282.67 | não rodado |
| Spread US$0,31/oz | 206 | +218.50 | não rodado |
| US$0,31 + US$0,15/slippage por lado | 206 | +156.40 | +284.40 (202) |
| US$0,31 + US$0,75/slippage por lado | 206 | -92.00 | +40.80 (202) |
| US$0,31 + US$1,50/slippage por lado | 206 | -383.52 | -263.70 (202) |
| Stress 7 bps | 207 | -350.03 | não rodado |
| Stress 14 bps | 196 | -911.74 | -710.67 (201) |
| Stress 28 bps | 91 | -1118.32 | não rodado |

O custo **US$0,61 por onça** significa spread fixo de US$0,31 + **US$0,15 de slippage por lado**, com *zero comissão adicional*. Os valores não reproduzem fill, spread intradiário, swap, rolagem, latência ou liquidez real. O ganho líquido marcado inclui eventual P&L flutuante estimado no último candle. Drawdown apresentado é apenas realizado, sem extremo intrabar.

## Repetibilidade nos três segmentos (mesmo histórico já explorado)

| Segmento | V4 operações | V4 com US$0,61/oz | V4 com US$1,81/oz | Sem Momentum operações | Sem Momentum com US$0,61/oz | Sem Momentum com US$1,81/oz |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 67 | -50.99 | -132.59 | 64 | -34.96 | -112.96 |
| 2 | 65 | +9.60 | -69.60 | 67 | -66.22 | -147.82 |
| 3 | 73 | +119.62 | +30.82 | 68 | +408.07 | +325.27 |

**Diagnóstico:** a ablação aumenta o resultado *neste histórico* mas continua negativa nos dois primeiros segmentos, positiva sobretudo no final. Não resistiu a cenários severos. Não é evidência para aprovar robô em conta real. Seleção repetida entre variantes dentro da mesma janela aumenta risco de sobreajuste.

## Onde os custos vêm

- Instrumento FBS XAUUSD: spread típico publicado ≈US$0,31 em unidade de cotação; spread flutuante: https://fbs.com/trading/specs/xauusd
- FBS condições comerciais: comissão de negociação anunciada como zero: https://fbs.com/trading/conditions
- Metais FBS: lote mínimo de 0,01 e contrato de 100 onças no XAUUSD: https://fbs.com/trading/specs/metals

**Importante:** FBS preço spot XAUUSD não equivale a Yahoo GC=F; não se pode aplicar custo de spot a futuro e chamar o P&L de backtest válido da FBS. Precisamos da série bid/ask do broker, spreads de momentos de execução, swaps e observações novas para testar de maneira honesta. As 200 entradas devem ser monitoradas como média de 30 dias, não impostas como cota com ordens aleatórias.

## Arquivos

- `research/indicator_fusion_v3_frequency.py` — gerador de cinco entradas e simulador causal de carteira única, suporte a lote e custo por onça.
- `research/indicator_fusion_v4_costaware.py` — V4, simulações de custo, ablação experimental e três segmentos.
- `tests/test_indicator_fusion_v4_costaware.py` — testes unitários e segurança, com regressão V1/V2/V3.
- [Artifact GitHub Actions](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42881115366) — JSON completo verificável do run final.

**Estado:** PR permanece em draft, sem integração a `main`, sem alterar ou apagar robôs positivos preservados, sem ordens/contas reais, sem aprovação de lucro recorrente.