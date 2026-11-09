# NEXUS CYCLES M5 — pesquisa isolada (CA/C1/C2)

**Status:** candidato experimental, apenas simulação. **Não integrado ao monitor,
Telegram, ATLAS, FBS, corretora ou execução de ordens.** Preserva todos os
estados dos robôs existentes.

## Origem e limitações

Uma descrição em vídeo cita canal de abertura (CA), C1, abertura de mercado,
stop/take e disciplina, mas **não fornece regras completas, dados, histórico de
operações ou demonstração estatística de lucratividade**. As regras abaixo são
uma hipótese quantitativa operacionalizada, **não uma reprodução comprovada**.

## Versão 1 congelada antes da primeira avaliação

- Ativo pretendido: XAUUSD spot/CFD, *se* houver histórico M5 confiável
  com origem e custos conhecidos. Fonte Yahoo `GC=F` é **futuro do ouro
  como proxy**, nunca equivalente a FBS spot nem prova de fills.
- Todas as barras: 5 minutos, timestamp UTC fechado, OHLC positivo e
  consistente; timestamps duplicados/incompletos são rejeitados.
- Sessão fixa: 08:00–16:00 America/New_York, com horário de verão real.
  Somente dias com as 96 barras M5 desse intervalo são avaliados.
- **CA:** máxima e mínima das primeiras quatro velas fechadas, 08:00–08:20.
- **C1:** primeiro fechamento para fora do CA; projeta-se uma altura de CA
  na direção do rompimento. Um rompimento C1 que ocorre na mesma vela
  que o rompimento inicial **não** pode gerar entrada.
- **C2:** fechamento *posterior* além do extremo projetado de C1,
  antes das 11:55 NY. Entrada virtual no open da próxima vela; nenhum
  cálculo usa a máxima/mínima da vela seguinte para escolher o sinal.
- Stop inicial em CA máximo (compra) ou CA mínimo (venda).
  Alvo fixo `1.5R`, risco por operação `0.25%` do patrimônio virtual,
  exposição nocional máxima `1x`, uma operação/dia por versão, flat
  até 16:00 NY, independentemente de resultado.
- Qualquer ambiguidade OHLC (stop e alvo tocados na mesma vela) é
  resolvida **a favor do stop**. Gap através do stop recebe preenchimento
  adverso na abertura, nunca um preenchimento impossível. Spread/taxas,
  slippage e alterações em stop/target não são ignorados.
- **A:** CA/C1/C2 sem confirmação extra.
- **B:** A mais EMA50>EMA200 H1, preço acima EMA50, inclinação EMA50
  positiva na compra (condições inversas para venda).
  Utiliza **apenas H1 fechada**; 205 H1 completas são exigidas.
- **C:** B mais altura CA entre 0.6 e 3.0 ATR14 M5, e custo estimado
  até 25% da distância ao stop. Os filtros não são otimizados depois
  de observar o holdout.

## Reprodução

Com arquivo próprio **CSV ou JSON** em UTC, campos
`time,open,high,low,close` (time epoch ou ISO-8601 com offset):

```bash
python -m research.nexus_cycles_m5_research --input dados_xauusd_m5.csv --source "fonte e período documentados" --fees-bps 8 --slippage-bps 2 --output reports/research/cycles_broker.json
```

Estudo preliminar com o **proxy público**:

```bash
python -m research.nexus_cycles_m5_research --yahoo-proxy --output reports/research/cycles_gc_proxy.json
```

Executar testes isolados:

```bash
python -m unittest discover -s tests -p 'test_nexus_cycles_m5.py' -v
```

O script recusa valores **zero** de custos; 8 bps ida e volta e 2 bps
de slippage por lado são **premissas ilustrativas**, não medidas
da corretora. O relatório faz divisão cronológica por dias (70/30)
e teste com custos dobrados. A sensibilidade não constitui walk-forward;
se o período/ativo já foi examinado, o holdout não é intocado.

## Controles adicionais de comparação

O relatório inclui um **benchmark SIMPLE**: compra/venda após o primeiro
fechamento além do CA (sem aguardar C1/C2), com exatamente a mesma lógica
de stop, alvo, custos e limite de risco. O resultado do modelo de ciclos
deve ser comparado a este controle, e não somente a zero.

Também são apresentados até três blocos `rolling_origin` de validação
cronológica (janelas 40–60%, 60–80%, 80–100%), sem ajustar parâmetros.
Eles são diagnósticos de estabilidade, **não** uma otimização walk-forward
com validação independente, e seus resultados são insatisfatórios em
amostras muito pequenas. Não existe promessa de vantagem.

## Critérios de avaliação para próxima fase

1. Obter dados independentes M5/M1 com corretora, especificação de
   sessão, ajustes de contrato, bid/ask, taxas, slippage e fuso.
2. Manter a hipótese A/B/C congelada e comparar com um breakout simples
   nas mesmas sessões; não escolher apenas meses lucrativos.
3. Rodar *walk-forward* purgado, forward paper e análise de estabilidade,
   custos x2, latência, gaps, spreads e correlação com as estratégias atuais.
4. Por padrão, **menos de 50 trades no holdout por versão = amostra
   insuficiente**. Mesmo 50 não comprova edge; requer meses/regimes
   adicionais, risco e desempenho pós-custos.
5. Somente depois considerar alertas em produção ou mudança de risco.
   Nenhuma ordem real autorizada.

## Segurança

- Nenhum código de corretora, ordens, chaves, tokens ou Telegram.
- Arquivos existentes e estados `state/*` não são alterados.
- Execução de pesquisa no CI é somente-leitura, sem conexão a contas.
- Se o Yahoo não responder, o workflow salva diagnóstico de
  indisponibilidade, **nunca lucro/zero inventado**.
