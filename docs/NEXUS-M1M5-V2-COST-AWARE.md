# NEXUS QUANT — V2 pesquisa de rentabilidade líquida, não aprovação de trading

## Hipótese

Na primeira versão, o prejuízo se concentrou em custos: no período de validação dos livros BTC+ETH, Sweep produziu cerca de US$371 de P&L bruto contra US$2.381 de custos, e Trend cerca de US$689 bruto contra US$2.656 em taxas/desvio simulado. Não se deve confundir lucro bruto com lucro líquido. VWAP e Flow ficaram negativos até antes dos custos.

**V2 não assume sucesso.** Mantém os seis sinais independentes e o executor V1 original intacto no modo padrão; adiciona duas políticas de pesquisa `research_policy` opcionais e explícitas:

- `v2_cost_floor`: apenas autoriza um sinal quando o alvo geométrico teórico (4R) está a pelo menos **2× o custo de ida e volta (taxa + slippage)**, com base no último candle fechado. É uma condição necessária de amplitude, não estimativa de chance de alvo.
- `v2_cost_plus_regime`: a mesma exigência de custo mais EMA50 acima de EMA200, EMA50 crescente nas últimas 12 barras e preço acima da EMA50. Mantenha a identidade original de cada gatilho; a lógica apenas veta entradas.

Os dois modelos usam, por hipótese congelada, 4R e permanência máxima de 360 candles M1 ou 288 candles M5, em vez de alvos 1,6–2,3R e encerramento rápido. Tentar capturar movimentos maiores pode reduzir acertos e aumentar exposição; não é automaticamente melhor. Stops e regras de risco mantidos, incluindo 2% por dia, 10% de DD MTM, risco máximo planejado de 0,25% M1 e 0,50% M5, sem alavancagem.

## Custos e comparabilidade

Taxa Binance spot regular: **0,10% por lado** (<https://www.binance.com/en/fee/trading>). Cena base slippage 0,02%/lado; cenário custo dobrado 0,20% taxa + 0,04% slippage/ lado; cenário adverso 0,10% taxa + 0,11% execução (slippage + impacto) por lado. Sem espalhar um spread extra que duplicaria o desvio estimado.

**O filtro de entrada utiliza sempre o custo BASE pré-fixado**, mesmo no cenário de custo dobrado. Assim, a seleção de sinais não recebe informações do cenário de teste nem se torna diferente para aparentar resiliência. Stops executados antes de alvos em ambiguidade OHLC; gaps recebem preenchimento piorado, ordens são simuladas a partir do próximo open.

## Períodos e verdade estatística

- **Desenvolvimento:** quatro trimestres de 2025 em replay separado (recomeça US$10.000 por trimestre, para não esconder meses depois de atingir o breaker em janeiro).
- **Validação retrospectiva:** dois trimestres janeiro–junho de 2026, também livres de reotimização nesta versão. Esses preços **já foram examinados globalmente na V1**; logo, é avaliação retrospectiva, não holdout intocado.
- **Excluído:** julho–outubro de 2026, porque foi o teste final da V1, já revelado.
- **Exigência futura:** um período posterior realmente não inspecionado e paper forward contínuo se aparecer alguma hipótese que sobreviva aos custos. Positividade nesta análise nunca gera `APTO PARA PAPER FORWARD` automaticamente.
- O cron da GitHub Actions **não** captura candles M1 com precisão negociável. O replay é exclusivamente em lote, não agendamento live.

## Critérios de rejeição

Reprovar resultados líquidos não positivos em qualquer cenário na validação retrospectiva, drawdown >=10%, ou menos de 3 dos 4 trimestres de desenvolvimento com retorno positivo. Prejuízo líquido efetivamente observado em qualquer cenário de um trimestre de validação é **REPROVADO** mesmo com amostra pequena; ausência de operações e amostras com menos de 20 operações por trimestre **sem prejuízo observado** são **INCONCLUSIVAS**, não lucrativas. Mesmo resultados positivos são classificados INCONCLUSIVOS por falta de dados novos independentes.

Em caso de regressão do motor V1, falha de checksum, timestamps, dados ausentes ou erro de execução, **bloquear qualquer classificação financeira** e corrigir a simulação primeiro.

## Reproduzir

```bash
python -m unittest discover -s tests -p "test_nexus_m1m5_v2.py" -v
python -m unittest discover -s tests -p "test_nexus_m1m5_lab.py" -v
python -m research.nexus_m1m5.v2_run --out artifacts/nexus-m1m5-v2
```

Código: `research/nexus_m1m5/v2_policy.py`, `research/nexus_m1m5/v2_run.py`, mudanças opt-in em `engine.py`, testes em `tests/test_nexus_m1m5_v2.py`.

Saídas no artefato GitHub Actions: `results_v2.json` por trimestre/cenário com checksums originais, `trades_v2.csv` operações individuais, `REPORT_V2.md` ranking por robustez no pior cenário. **Sem alterações em src/, state/, relatórios operacionais, ATLAS, Telegram ou horários de fechamento.**
