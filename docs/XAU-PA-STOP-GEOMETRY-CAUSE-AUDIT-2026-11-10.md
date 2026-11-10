# XAUUSD Price Action — auditoria da entrada original e dos stops (10/11/2026)

**Decisão: NÃO alterar a estratégia principal nem o Stop Red com base nesta hipótese.** Esta auditoria verifica o que gera prejuízo mantendo **os mesmos gatilhos de rompimento/reteste** e **sem criar filtros ou robôs novos**.

## 1. O que a estratégia do usuário exige de fato

As regras confirmadas na conversa são: LTA/LTD e outras regiões marcadas antes da execução; **rompimento da microtendência seguido por reteste** antes da entrada; compra/venda por rejeição de suporte/resistência **somente em lateralização**; apenas uma operação simultânea, sem limite diário arbitrário de perdas. As distâncias, ajustes e eventual condução do **Stop Red / Stop Win** não foram descritas suficientemente em pontos, preços ou R. O alvo **2R** e stop no extremo do candle ± **0,1 ATR** são **suposições do desenvolvimento**, NÃO regras comprovadamente feitas pelo usuário.

O código v6 e os relatórios usam marcações automáticas **proxy**; não existe comprovação de equivalência com os níveis que o usuário desenharia no gráfico.

## 2. A hipótese de falha no stop foi inspecionada SEM mudar uma entrada

- [Motor de diagnóstico](../research/xau_pa_stop_geometry_audit.py): reproduz exatamente os sinais v6 sem nenhuma alteração e confirma que os fills, horários de entrada e P&L são idênticos ao backtest v6 já verificado.
- [Testes de causalidade e preservação](../tests/test_xau_pa_stop_geometry_audit.py): só depois da verificação calcula se o stop do reteste ficou **antes de cruzar o nível invalidado** (compra de LTD: stop deveria estar abaixo da LTD, venda de LTA: acima da LTA). Isso é uma interpretação técnica a verificar com a forma de operar do usuário.
- Uma segunda simulação modifica **somente** o preço do Stop Red quando ele fica do lado de dentro da linha, reposicionando-o 0,1 ATR para além da linha. Não modifica compras/vendas, velas, sinais, custos, períodos, take-profit 2R, stop em outros casos nem tamanho da carteira.
- [GitHub Actions 42817270923](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42817270923): três jobs **SUCCESS**. **47 testes unitários aprovados por mês** (11 + 9 + 12 + 15). Dados Dukascopy spot BID/ASK XAUUSD, dez sessões previstas e **10/10 válidas**, junho 22–26 e julho 27–31 de 2026, 09–21 UTC, trades 12–21 UTC.

### Resultado verificado da geometria de stops

- **22 sinais de rompimento/reteste** no v6. Destes, **9 tinham stop do lado inadequado da linha rompida** pela hipótese de invalidação.
- **21 operações simuladas preenchidas**, sendo **9 efetivamente executadas com esse posicionamento**.
- Os nove stops foram reposicionados no estudo; os 22 sinais permaneceram inalterados e 21 operações continuaram sendo executadas.

| Cenário BID/ASK / custo dobrado | Junho 2026 | Julho 2026 | Total |
|---|---:|---:|---:|
| Stop original — fills | 8 | 13 | **21** |
| Stop original — líquido USD/oz | −28,164 | −29,112 | **−57,276** |
| Stop atrás da linha — fills | 8 | 13 | **21** |
| Stop atrás da linha — líquido USD/oz | −30,144 | −30,212 | **−60,356** |
| Stops atingidos (ambos) | 8 | 10 | **18** |
| Vitórias (ambos) | 0 | 2 | **2** |

**Resultado da hipótese: negativo.** Corrigir somente a posição do stop aumentou a perda em **US$ 3,080 por uma onça hipotética**. Por isso, **NÃO foi promovida** a alteração de stops.

### O que esse resultado NÃO prova

- Não prova que o trader desenha o mesmo nível ou escolheria a mesma operação.
- Não prova que o Stop Red real deva ser do outro lado da linha por 0,1 ATR. Tampouco prova que o stop original está certo.
- Não prova que a estratégia manual perde dinheiro. Ela foi substituída por proxies, parâmetros de stop e alvo sem confirmação, horários e dados de corretora diferentes.
- Não valida conta MT5, tamanho do contrato, custo do broker, swap, latência e execuções reais.
- Não autoriza procurar um nível de stop diferente que produza lucro retrospectivo e chamá-lo de validado.

## 3. O que devemos fazer agora, sem repetir os mesmos erros

A prioridade é **fidelidade de decisões**, e não mudança de indicadores ou geração de mais operações. Para qualquer trecho futuro, registrar antes dos trades: o preço e horário de cada marcação LTA/LTD/suporte/resistência; candle do rompimento; candle do reteste; entrada efetiva; Stop Red; Stop Win; e cancelamento de sinal. Construir uma auditoria operação por operação: `entrada humana × entrada do robô`, justificando falsos positivos, falsos negativos, duração e custos.

Depois congelar **os parâmetros efetivamente praticados**, reexecutar um histórico de corretora MT5 com preços bid/ask e custos reais, e medir consistência em datas **não utilizadas** no ajuste. Até lá, **nenhum resultado positivo pode ser anunciado como rentabilidade comprovada**.

**Estado:** pesquisa em PR #61 DRAFT, `main`, WIN e demais robôs operacionais preservados. Nenhuma ordem enviada.
