# XAUUSD — laboratório de mais entradas, validação cronológica e bloqueio operacional

Data da pesquisa: **10/11/2026**. Estado: **pesquisa isolada, não aprovada para operar**.

## Entrega verificável

- [Código das seis variantes](../research/xau_frequency_lab.py): referência inalterada, equilibrado e ativo, combinados com entradas Fibonacci 50% ou 75% e alvos 200%/250%. O experimento de 75% altera a geometria original: **não afirmar equivalência com Greenhouse**.
- [Motor que escolhe usando somente treinamento](../research/xau_frequency_scorecard.py): seleção congelada no artefato **antes** de ler os dados de validação e as duas janelas posteriores, sem autoajuste na análise.
- [Testes focados](../tests/test_xau_frequency_lab.py) e [testes cronológicos](../tests/test_xau_frequency_scorecard.py), além dos testes de execução sobre bid/ask e o motor anterior.
- [Experimento histórico completo](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42789286528): treino e validação processados, mas o primeiro holdout noturno tinha menos de 50 candles M5 e foi rejeitado. **Não foi um resultado financeiro** e não foi contornado artificialmente.
- [Recuperação auditada](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42789841878): reutilizou o arquivo de seleção e os 25 pregões já computados; alterou somente a janela incompatível por outra janela de 5 horas, com data/hora explícitas. **Sucesso técnico**, artefato `xau-frequency-v2-repaired-forward-preserved-selection`.
- [Indicador gráfico MT5 LAB independente](../indicators/mt5/NQ_XAU_Quote_Tracker_Lab_Research.mq5): lista Base / Equilibrado / Ativo; seleção **Base por padrão**; sinal em candle fechado; desenha as mesmas linhas 50/200/−100 da pesquisa; banner na tela avisa que o modo alternativo **não foi aprovado**. Não envia ordens.
- [Build binário LAB](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42790540637): MetaEditor Windows oficial, **0 erros e 0 avisos**, EX5 **30.688 bytes**; artefato `nq-xauusd-quote-tracker-LAB-experimental-EX5`, sujeito à expiração do Actions.

## Regras predefinidas, sem seleção posterior de lucros

Todos os seis modelos foram avaliados em **XAUUSD Dukascopy**. A atividade representa atualizações bid/ask da fonte, **não** delta agressor/volume negociado. Nenhum dado de corretora MT5 do usuário foi acessado.

- **Treinamento:** 15 sessões previstas entre 21/09 e 09/10/2026, 12–17 UTC. **02/10 foi quarentenado integralmente** porque um registro bid/ask não passou na validação. Nenhum tick isolado foi descartado.
- **Validação posterior:** 10 sessões previstas entre 12/10 e 23/10/2026, 12–17 UTC.
- **Janelas adicionais:** 09/11 07–12 UTC e 10/11 00–05 UTC. A janela original 09/11 18–23 UTC foi substituída **porque havia menos de 50 candles M5**, não por rentabilidade. O registro de seleção permaneceu intocado.
- **Execução hipotética:** ordens limitadas após candle fechado, vencimento de 3 candles, stop/alvo usando o lado correto do bid/ask e saída após 20 candles; não há execução retroativa, nem preenchimento garantido.
- **Cenário de atrito:** comissão hipotética de US$ 0,30 por onça e slippage de US$ 0,10 por onça somente para stops/saídas a mercado. **Cenário duplo:** US$ 0,60 e US$ 0,20 respectivamente. Não são taxas contratadas de uma corretora.
- **Critério do seletor:** ≥20 preenchimentos e ≥6 dias ativos no treinamento, lucro positivo e PF ≥1,20 **com custos duplos**, antes de observar validação. **Nenhum modelo cumpriu todos esses requisitos**.

## Comparação: sinais gerados, não trades preenchidos

| Variante M1 | Sinais treino | Preenchimentos treino | Lucro treino (US$/oz, custo duplo) | Sinais validação | Preenchimentos validação | Lucro validação (US$/oz, custo duplo) |
|---|---:|---:|---:|---:|---:|---:|
| Referência 50/200 | 18 | 11 | −24,145 | 16 | 8 | −17,551 |
| Equilibrado 50/200 | 22 | 15 | +4,160 | 28 | 17 | −37,171 |
| Ativo 50/200 | 37 | 21 | −30,535 | 45 | 25 | −21,202 |
| Equilibrado 75/200 | 22 | 16 | −5,135 | 28 | 20 | −48,677 |
| Ativo 75/250 | 37 | 24 | −42,075 | 45 | 30 | −51,574 |
| Equilibrado 75/250 | 22 | 16 | +4,690 | 28 | 20 | −69,427 |

**Mais sinais não equivalem a mais lucros:** referência 34 sinais vs Ativo 82 na soma das duas fases, aumento de ~141% em sinalizações, mas saldo negativo em validação. O lucro isolado do equilibrado no treino (15 ou 16 fills) não se repetiu no período posterior.

**M5:** poucos sinais e trades na amostra (por exemplo, 5 sinais no modelo referência na validação). Alguns resultados isolados são positivos, mas nenhum modelo M5 passou a regra de pré-seleção baseada em tamanho de amostra, PF e retorno após custos duplos. Não escolhemos o M5 por quatro operações favoráveis.

O histórico posterior foi coletado e auditado, mas **como nenhuma variante tinha sido selecionada previamente, nenhum resultado de holdout foi usado para trocar vencedor, ajustar limiares ou reivindicar lucro**. Os arquivos completos, inclusive perdas, permanecem no artifact.

## O que significaria “aprovado”

1. Demonstrar no mínimo 100 operações **futuras não usadas no desenvolvimento**, com retorno positivo após custos duplos e PF acima de 1,20; variações da amostra devem permanecer positivas sob bootstrap por pregão, sem escolher o período posteriormente.
2. Fazer teste real de indicadores em terminal MT5 **ligado a conta demo e histórico da corretora pretendida**, incluindo ponto, tamanho de lote, spread real, latência, horário servidor, swap e comissão. Resultado da Dukascopy **não substitui** backtest em corretora.
3. Se a meta for reproduzir exatamente o indicador original Greenhouse, obter uma série autorizada dos seus sinais em **XAUUSD, no mesmo feed e timeframe**. Não se encontrou código-fonte público confiável com a lógica interna; indicadores semelhantes do GitHub não são prova de equivalência.
4. Aprovação visual e autorização para operação são decisões distintas: a versão LAB é apenas para inspeção de setas e desenho; **a PR permanece DRAFT** e nenhum robô operacional é alterado.

## Como inspecionar no MT5

No [workflow do LAB](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42790540637), abra o artefato **`nq-xauusd-quote-tracker-LAB-experimental-EX5`**. Em um terminal MT5 conectado a servidor demo autorizado que ofereça `XAUUSD`, instale o arquivo EX5 em `MQL5/Indicators/`, depois atualize o Navegador. No gráfico XAUUSD M1 ou M5, abra `NQ_XAU_Quote_Tracker_Lab_Research`; o campo `InpLabPreset` permite Base, Balanced ou Active. O aviso na tela distingue as configurações experimentais. Não ativa AutoTrading. **Compilado não significa que já foi observado funcionando em conta demo externa.**

**Decisão:** manter separado da `main` e dos robôs existentes; nenhuma variante é apresentada como rentável.
