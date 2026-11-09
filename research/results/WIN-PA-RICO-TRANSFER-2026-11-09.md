# WIN Price Action — custos Rico sem RLP e transferência para WINJ26

**09/11/2026 — testado em dados de terceiros com hash fixo; sem resultados robustos.**

## Evidência de execução

- [GitHub Actions — backtests e testes concluídos](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42664238865).
- Fonte WINQ26 35.574 M1 SHA Git 43c50f01882f1ac497a218549e0bff2964d94aa5 e WINJ26 5.129 M1 SHA Git 7fcc91ebde3e674f910ac82eef00b6bf19541151. Ambas são exportações Profit declaradas por terceiros, não atestadas pela B3.
- Estratégia original congelada: microtrendline rompimento/reteste e rejeição de faixa em M1 com regime M5. Um contrato, banca virtual R$2.000 por janela, stop individual, sem limite de perdas diárias, risco planejado até 1%.

## Hipóteses de custo

- [Rico – corretagem](https://www.rico.com.vc/custos/) anuncia R$0,45 por minicontrato day trade sem RLP; [B3](https://edu.b3.com.br/day-trade) indica teto educacional R$0,50 de custos B3 pelo WIN ida+volta. 1 tick em cada lado = R$2 de deslizamento. Estimativa total **R$3,40**; com 2 ticks por lado, **R$5,40**.
- Cenário anterior R$6; cenário RLP hipotético R$2,50. [MetaTrader na Rico](https://www.rico.com.vc/plataformas/metatrader/) tem plano promocional de corretagem R$0,26/contrato cujo enquadramento não está confirmado. Nenhum desses totais é a tarifa efetiva verificada da conta de usuário.

## Resultado líquido por contrato, R$3,40/roundtrip

| Contrato / período | Filtro econômico | Fechadas | P&L R$ | PF |
|---|---|---:|---:|---:|
| WINQ26 junho/2026 | Não | 9 | -75,60 | 0,224 |
| WINQ26 junho/2026 | R/R líquido >=1 | 7 | -86,80 | 0,109 |
| WINQ26 julho/2026 parcial | Não | 23 | -25,20 | 0,853 |
| WINQ26 julho/2026 parcial | R/R líquido >=1 | 20 | -18,00 | 0,884 |
| WINJ26 fragmentado em 2025 | Não | 2 | -28,80 | 0,000 |
| WINJ26 fragmentado em 2025 | R/R líquido >=1 | 2 | -28,80 | 0,000 |

**Crítico:** as duas entradas WINJ26 cruzaram intervalos sem candles M1 observáveis e foram encerradas com penalização adversa hipotética. Resultado negativo não é fill real e não pode ser usado para validar eficácia do setup. É outra expiração, mas base fragmentada e já consultada anteriormente em pesquisas.

## Stress de custos e filtro econômico

- Sob R$5,40 (2 ticks/lado), junho baseline perdeu R$64,20 (8 trades); julho baseline perdeu R$30,40 (21 trades).
- Mesmo com RLP hipotético a R$2,50, junho baseline perdeu R$36,00; julho teve +R$27,00 em apenas 24 trades. Ao colocar R/R mínimo de 1, junho perdeu R$41,50 e julho ganhou R$32,50. Essa vantagem pontual não sobrevive ao regime e aos cenários de custo.
- Sob custo anterior R$6, junho -R$49 e julho -R$43 sem filtro, já verificados anteriormente.
- No seu capital de referência, risco máximo planejado de R$20, podendo ser excedido por gaps. Reduzir a taxa não resolve um padrão de entradas com expectativa negativa.

## Decisão

Não autorizar conta real nem exportar Expert Advisor MT5 ainda. Relatório JSON com ledger completo no artifact da execução GitHub Actions. Dados futuros precisam ser de múltiplos contratos brutos completos nunca utilizados na escolha dos parâmetros, e execução simulada prospectiva com custos reais da Rico.

Para obter dados nativos do MT5 sem contas conectadas no GitHub, o importador estrito (com ticker, volume real, fuso e auditoria de lacunas) foi implementado na PR #50; não reutiliza preço sintético nem futuros contínuos como contratos negociáveis.
