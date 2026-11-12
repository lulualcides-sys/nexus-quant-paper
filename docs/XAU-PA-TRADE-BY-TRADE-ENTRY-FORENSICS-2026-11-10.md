# Ouro XAUUSD Price Action — auditoria dos 21 trades e falha de antecipação (10/11/2026)

**Conclusão:** a estratégia manual não foi validada nem refutada. As regras de desenho das linhas e a política exata de Stop Red/Win não foram fornecidas. Esta auditoria isola **o que foi realmente executado pelo robô**, com preços da Dukascopy BID/ASK, e evita atribuir-lhe os critérios subjetivos do trader.

## 1. Fato observado: muitas entradas já longe da LTA/LTD rompida

Fonte: [GitHub Actions 42823954933](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42823954933), artefatos `xau-pa-original-vs-stop-win-red-june-ledgers` e `xau-pa-original-vs-stop-win-red-july-ledgers`, código `research/xau_pa_m5_context_m1_v6.py`. Todos os 21 negócios do braço `existing_20_bar_time_exit`, cenário de custos dobrados, sem ocultar perdedores. Todas as linhas são **proxies automáticas**.

A distância à linha é calculada como **|preço de entrada − valor da linha no reteste| / |preço de entrada − stop inicial|**. Logo 1,00R é uma distância inicial **igual ao risco técnico definido no simulador**, não o lucro possível.

| Entrada UTC (2026) | Lado | Entrada | Linha | Stop | Distância/risco | Motivo de saída | Min até saída | Líquido US$/oz |
|---|---|---:|---:|---:|---:|---|---:|---:|
| 23/06 12:39 | Compra | 4121,405 | 4119,005 | 4118,629 | 0,86R | STOP | 5,3 | −3,597 |
| 23/06 16:01 | Compra | 4140,045 | 4137,114 | 4137,349 | 1,09R | STOP | 1,3 | −3,630 |
| 24/06 12:11 | Venda | 4039,635 | 4044,302 | 4044,329 | 0,99R | STOP | 0,8 | −5,600 |
| 24/06 15:37 | Venda | 4007,868 | 4008,760 | 4010,670 | 0,32R | STOP | 1,0 | −3,637 |
| 25/06 12:22 | Venda | 3979,175 | 3981,235 | 3980,977 | 1,14R | STOP | 0,4 | −2,640 |
| 25/06 17:45 | Compra | 4034,845 | 4032,745 | 4032,840 | 1,05R | STOP | 0,2 | −2,810 |
| 26/06 12:09 | Compra | 4047,765 | 4045,245 | 4045,409 | 1,07R | STOP | 10,1 | −3,180 |
| 26/06 18:02 | Venda | 4072,275 | 4074,581 | 4074,521 | 1,03R | STOP | 1,4 | −3,070 |
| 27/07 13:32 | Venda | 4078,555 | 4081,633 | 4082,049 | 0,88R | STOP | 3,1 | −4,450 |
| 27/07 14:12 | Compra | 4075,385 | 4072,270 | 4071,887 | 0,89R | STOP | 14,3 | −4,370 |
| 27/07 14:38 | Compra | 4068,745 | 4066,000 | 4065,685 | 0,90R | STOP | 3,3 | −3,900 |
| 28/07 17:58 | Compra | 4028,175 | 4026,544 | 4026,615 | 1,05R | TIME | 20,0 | −0,480 |
| 29/07 18:30 | Compra | 4068,225 | 4063,613 | 4063,822 | 1,05R | STOP | 1,5 | −5,350 |
| 30/07 16:37 | Venda | 4112,275 | 4114,395 | 4114,501 | 0,95R | TARGET | 9,9 | +3,852 |
| 30/07 16:51 | Compra | 4110,175 | 4108,575 | 4108,443 | 0,92R | STOP | 0,9 | −2,580 |
| 30/07 18:32 | Compra | 4106,235 | 4103,827 | 4103,918 | 1,04R | STOP | 10,2 | −3,180 |
| 30/07 19:51 | Compra | 4113,085 | 4111,365 | 4111,482 | 1,07R | STOP | 0,5 | −2,450 |
| 31/07 12:18 | Venda | 4055,535 | 4056,342 | 4056,833 | 0,62R | STOP | 0,8 | −2,570 |
| 31/07 14:11 | Venda | 4025,935 | 4027,731 | 4028,211 | 0,79R | STOP | 0,4 | −3,130 |
| 31/07 17:46 | Venda | 4050,765 | 4052,255 | 4052,955 | 0,68R | STOP | 0,2 | −2,990 |
| 31/07 19:41 | Compra | 4050,845 | 4049,375 | 4049,302 | 0,95R | TARGET | 3,2 | +2,486 |

**Resumo reproduzido:** 21 execuções, 2 alvos, 18 stops e 1 TIME; **9 entradas além de 1R** de distância à linha; **mediana 0,953R**; **mediana até STOP 1,195 minuto**. Líquido **−US$57,276 por uma onça teórica** após custos duplicados. Não confundir com saldo ou lote de corretora.

## 2. Investigação da causa: entrar cedo demais também é ruim

Uma hipótese operacional, **não um novo indicador**, foi implementar `research/xau_pa_intrabar_retest_execution.py`: aguardar rompimento CONFIRMADO de LTA/LTD em candle fechado, depois toque na linha e reação detectada por dois ticks cronológicos, abrir apenas no **tick seguinte**; manter sinais de lateralização da v6 intactos, os mesmos stops/alvos hipotéticos e custos.

**[Execução 42825468629](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42825468629)** com 3 jobs SUCCESS: 47 testes unitários em cada um dos dois blocos; datas pré-fixadas maio 18–22 e setembro 28–outubro 02, **9/10 válidas**; 02/10 excluído inteiramente por cotação bid/ask inválida no registro 48.102. Resultado:

| Entrada | Maio: fills, líquido US$/oz | Setembro/outubro: fills, líquido US$/oz | Total fills | Total líquido |
|---|---:|---:|---:|---:|
| v6: aguarda fechar reteste | 23, −20,777 | 13, −18,496 | **36** | **−39,273** |
| Reação intrabar no reteste | 68, −121,374 | 51, −105,608 | **119** | **−226,982** |

Original v6: 9 vitórias/27 perdas. Reação intrabar: 13 vitórias/106 perdas. Mais sinais não provam vantagem: o detector tratou repiques muito pequenos (hipótese `0,08 ATR`) como entrada e multiplicou falsos positivos. Os gatilhos de rompimento observados passam de 39 para 180 por conta da nova cronologia, portanto **não são conjuntos de trades idênticos**; comparar P&L é correto entre braços completos, mas não atribuir a diferença só ao preço de execução.

**Decisão inequívoca: NÃO adotar a entrada intrabar.** Não alterar `main`, não publicar EA, não declarar lucro. Código e backtest permanecem isolados na PR #61 como pesquisa reprovada.

## 3. Limites que impedem equiparar bot e estratégia humana

- As LTA/LTD foram inferidas de dois pivôs confirmados e não representam desenhos próprios do usuário. A duração do reteste, a força da reação, a proximidade real e os rompimentos falsos que o trader rejeita não estão documentados.
- O stop no extremo do candle com margem de ATR, alvo nominal 2R e saída automática após 20 candles são **suposições de código**, não parâmetros pessoais comprovados.
- A [auditoria anterior do stop](XAU-PA-STOP-GEOMETRY-CAUSE-AUDIT-2026-11-10.md) mostrou que mover 9 stops para além da linha **piorou** de −US$57,276 para −US$60,356/oz.
- A [auditoria de saída por tempo](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42823954933) mostrou que eliminá-la **piorou** de −US$57,276 para −US$59,196/oz.
- 20 dias preselecionados ao longo dos experimentos não viram um verdadeiro teste futuro. Os resultados não reproduzem feed/custos/latência/lotes reais de MT5.

## 4. Direção de melhoria que NÃO exige mais filtros aleatórios

O próximo produto útil é um **replay visual da entrada** que mostre, para cada trade executado, LTA/LTD e seus pivôs, candle rompido, reteste, preço/horário efetivo, risco, Stop Red/Win e saída. A partir dessa evidência, classificar entrada como `aceitaria manualmente / rejeitaria / dúvida` sem otimizar retroativamente o histórico. A versão `manual` que já exige marcas datadas deve ser o único caminho para declarar fidelidade.

**Status final desta rodada:** causalidade das entradas intrabar testada e reprovada, nenhum filtro novo aprovado, nenhum lucro anunciado, main e robôs antigos intactos.
