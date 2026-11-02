# Nexus Quant — triagem de rentabilidade (pesquisa virtual de 01/11/2026)

## Resultado objetivo, sem promessas de lucro

Comparação histórica em [GitHub Actions — PR #12](https://github.com/lulualcides-sys/nexus-quant-paper/pull/12), com **os mesmos candles indicativos Yahoo para original e candidato** e nova simulação de **custos dobrados**. As séries históricas já tinham sido examinadas em pesquisa anterior: **não é validação genuinamente fora da amostra**. Nenhum resultado corresponde a operações reais na FBS.

**Dos 27 robôs:**
- 15 H1 submetidos a filtro causal de volatilidade/custos/tendência; **nenhum grupo H1 foi corrigido para lucratividade agregada**.
- 5 H4 alavancados submetidos a cenário de exposição 1× e risco-stop planejado 0,75%; menos risco nominal, mas **continua negativo em stress agregado**.
- 7 controles (5 H4 convencionais, Momentum60 e USD/CAD M15) intactos.

## Métricas por grupo, mesmas séries históricas

| Grupo | Original líquido | Variante líquida | Variante custos ×2 | Operações fechadas na variante |
|---|---:|---:|---:|---:|
| 15 H1 | −US$ 576,78 | −US$ 300,64 | −US$ 476,48 | 694 |
| 5 alavancados H4 | +US$ 405,97 | +US$ 221,90 | −US$ 16,87 | 27 |
| 5 convencionais H4, controles | +US$ 323,79 | +US$ 323,79 | +US$ 271,28 | 35 |
| Momentum60, controle | +US$ 33,78 | +US$ 33,78 | +US$ 22,36 | 7 |
| USD/CAD M15, controle | −US$ 2,61 | −US$ 2,61 | −US$ 5,47 | 27 |

**Atenção:** os períodos e as bancas virtuais diferem entre grupos; somá-los não equivale ao retorno de uma carteira sincronizada.

## Candidato positivo que merece apenas forward-test

**XTIUSD Channel 10 H1** (petróleo WTI, preços indicativos CL=F), com filtro causal:
- Modelo atual: 108 operações fechadas, **−US$ 9,98**.
- Variante: 58 operações fechadas, **+US$ 13,61**.
- Variante com custos dobrados: **+US$ 1,17**.
- Drawdown fechado simulado: **2,766%**.
- Melhoria histórica em dólares: **+US$ 23,59**.

A vantagem sob stress é apenas **US$ 0,0202 por operação**, pequena demais para inferir robustez frente a diferenças de spread, deslizamento, financiamento ou regime de mercado. Resultado retrospectivo revisto = hipótese, **não aprovação**.

## Controles historicamente positivos, amostra insuficiente

- Channel 55 H4 sem alavancagem: **+US$ 228,03**; custos ×2 **+US$ 222,27**; apenas **4 fechamentos**.
- Channel 20 H4 sem alavancagem: **+US$ 179,76**; custos ×2 **+US$ 170,54**; apenas **6 fechamentos**.
- Momentum60 H4: **+US$ 33,78**; custos ×2 **+US$ 22,36**; apenas **7 fechamentos**.
- Channel 55 H4 em versão de exposição nominal 1×: **+US$ 153,34**; custos ×2 **+US$ 117,62**; apenas **5 fechamentos**.

Não é adequado promover os modelos acima para capital real com esse número de operações.

## Decisão financeira e técnica

1. **Não ativar dinheiro real.** Nenhuma estratégia demonstrou uma vantagem fora da amostra com custos verificáveis de corretora.
2. **Não aplicar o filtro H1 globalmente.** Ele reduz perdas absolutas, mas o grupo permanece negativo; retorno líquido por trade também pode piorar.
3. **Não afirmar que reduzir leverage produz lucro.** A versão 1× reduz o risco nominal e a perda no cenário de stress, mas não torna o grupo alavancado positivo nesse cenário.
4. Priorizar **observação prospectiva em paralelo**, com estados virtuais independentes, de XTIUSD Channel10 filtrado e dos controles Channel55/Channel20. O objetivo é obter novos resultados não utilizados para selecionar parâmetros.
5. Preservar os 27 robôs originais, limites de risco, saves e o Telegram **somente diário**. Este patch é apenas `research/`; nenhuma carteira, token, corretora, ordem ou operação real foi conectada.

O módulo `research/cost_repair_lab.py` e a suíte `tests/test_cost_repair_lab.py` possibilitam repetir a triagem com OHLC verificável. O JSON e Markdown detalhados também foram salvos como artefatos do workflow da PR #12.
