# WIN Price Action M1/M5 — auditoria de risco e validação econômica (09/11/2026)

**Estado: NÃO LUCRATIVO e NÃO APROVADO para capital real.** Corrigida a simulação histórica para sinalizar interrupções dos candles M1 enquanto uma posição está aberta; não converter intervalos sem negociação em supostos fills. Posições em aberto ao término agora exibem marcação a mercado separada do P&L fechado.

## Fonte e configuração

- Fonte histórica: contrato WINQ26 de dados de terceiros declarados como exportação Profit, Git blob SHA1 43c50f01882f1ac497a218549e0bff2964d94aa5.
- Base total 35.574 candles M1; análise junho (10.101) e julho (8.999), 2026. Não é base independente após pesquisas anteriores.
- 1 WIN por operação, capital R$2.000 por período, stop e take-profit técnicos, sem limite diário de perdas.
- Custo-base: R$4 por roundtrip mais 1 tick de slippage por lado, total R$6 assumidos. Custos reais da corretora não verificados.
- Execução verificada no GitHub Actions: https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42660835024

## Original versus filtro mínimo de R/R líquido igual a 1

| Mês | Baseline trades | Baseline líquido | Filtro trades | Filtro líquido | Veto de entradas por R/R líquido |
|---|---:|---:|---:|---:|---:|
| Junho/2026 | 7 | -R$49 | 2 | -R$38 | 6 |
| Julho/2026 | 21 | -R$43 | 5 | -R$16 | 17 |

Filtro pré-declarado como princípio econômico (alvo líquido >= stop líquido) e não como otimização por lucro de períodos históricos; a versão baseline continua disponível, sem alteração de trades. As rejeições podem incluir sinais em que outra posição estava aberta, por isso o número vetado não é necessariamente a diferença de fechamentos.

## Custo versus payoff realmente planejado

- Junho baseline: mediana do R/R líquido planejado 0,615; 6 das 7 operações tinham payoff líquido inferior a 1:1.
- Julho baseline: mediana 0,800; 16 das 21 operações inferiores a 1:1.
- Com risco máximo de R$20 e custo modelado de R$6 por ciclo, o stop bruto tem teto de R$14 ou 70 pontos WIN. Um alvo bruto de 2R implica no melhor caso aproximadamente R$22 de ganho líquido e R$20 de perda líquida, isto é, só ~1,1:1, não 2:1.

## Integridade e ressalvas

- Nenhum trade dos dois meses atravessou lacuna M1 na posição no cenário de um tick, mas o motor anterior não detectava esse risco. Agora detecta e reprova qualquer período com lacunas em posições, mesmo que o simulador calcule liquidação adversa hipotética.
- Testes sintéticos de falsa ausência de candle, exposição aberta, custeio de stop, vedação de reentradas simultâneas e veto econômico passaram no CI. Testes não demonstram lucro.
- O filtro reduziu prejuízos retrospectivos porque removeu entradas, mas ainda gerou prejuízo e amostra insuficiente. Dados já conhecidos não são OOS independente.
- Sem conexão com MT5 ou corretora, nem ordens reais. ATLAS e outros robôs permanecem intactos. A PR deve permanecer em rascunho.

## Decisão

**Reprovar para negociação real.** Próxima pesquisa apenas com histórico novo, verificado e datas pré-especificadas, sem mudar os filtros após observar o teste. Antes de integração MetaTrader 5, confirmar qualidade dos preços, custos, valor mínimo do stop viável, fluxo de execução, e simulação prospectiva.
