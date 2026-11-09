# Tracker: reconstrução vetorial aprofundada e investigação do gatilho — 09/11/2026

**Situação:** pesquisas executadas, hipóteses testadas e resultados preservados. O código-fonte do Tracker Greenhouse NÃO foi localizado publicamente, a regra original NÃO foi recuperada, e nenhuma vantagem financeira foi demonstrada.

## 1. Material e integridade

- Fonte: [oferta pública Greenhouse](https://lojadagreenhouse.com.br/ofertatracker/) e seu demonstrador JavaScript `D.d` (candles reconstruídos) e `D.s` (43 marcações dos dias 03 e 04 de novembro). Não é feed oficial B3 nem a lógica licenciada.
- Fonte HTML observada tem SHA256 `2bfa22a1d9b62237f92af539cffa07596189c14b5da3310f7a49002b32de1c83` e oferece 565 e 562 candles demonstrativos. Se o conteúdo mudar, rever a análise.
- O site público declara alvo em 200%, entrada em 50% e stop em -100% a partir do candle sinalizado e apenas após o fechamento. Matematicamente isso implica payoff bruto aproximado de **1:1**, com arredondamento ao tick de 5 pontos.
- Foram usadas **63 hipóteses geométricas fixadas no código**, três famílias (pavios, corpos, fechamentos) × 7 horizontes (1, 2, 3, 5, 8, 13, 20 candles) × 3 atrasos da etiqueta (0, 1, 2 minutos). Nunca foram usadas cotações posteriores à etiqueta para construir as âncoras.
- Código reproduzível em `research/tracker_vector_discovery_43.py` e `research/tracker_vector_anchor_families.py`; testes em `tests/test_tracker_vector_discovery.py` e `tests/test_tracker_vector_anchor_families.py`.

## 2. Resultado matemático dos níveis de preço

Para lado s=+1 (compra) ou s=-1 (venda), entrada E, alvo A e stop S:

- Distância do alvo `abs(A-E)` e distância do stop `abs(E-S)` diferem no máximo 5 pontos nas **43 marcações** do demonstrador.
- Amplitude de candle subjacente implicada pelo esquema público: `R = s*(A-S)/3`.
- Origem implícita: `O = E - s*R/2`. Para compra, mínimo implícito `O` e máximo `O+R`; para venda, máximo `O` e mínimo `O-R`.
- Amplitude implícita mediana: **143,333 pontos** (não arredondada; preços anunciados foram arredondados ao tick).
- Regra simples (pavio máximo/mínimo do candle rotulado): **9/43** correspondem com tolerância 5 pontos.
- Busca ampliada sobre as 63 hipóteses: **13/43** correspondem a alguma família, incluindo **4/43** cujo intervalo de referência termina pelo menos 1 minuto antes da etiqueta.
- **30/43 não são explicados** pelas 63 famílias e tolerância de 5 pontos. Isso demonstra a limitação dos candles redesenhados, e NÃO prova que a Greenhouse use âncoras ocultas ou outra fórmula.
- Controle exploratório: deslocar aleatoriamente a hora do vetor na sessão demonstrativa (100 iterações, semente fixa) encontrou **média 0,27** correspondência e máximo 1, contra 13 reais. Isso documenta que o alinhamento na página não é mero deslocamento horário aleatório. **Não é p-valor formal nem evidência independente do indicador**, pois o site pode ter reconstruído o gráfico ao redor dos sinais previamente selecionados.

## 3. Investigação sistemática do gatilho de entrada

- Com histórico anterior suficiente: **41 marcações** etiquetadas avaliáveis (18 do dia 03 e 23 do dia 04). Comparadas com **2.174 pares de minuto/direção**, que incluem 2.133 pares sem marcação publicitária. 'Não marcado' NÃO é uma operação verificada como ausente.
- Sete atributos causalmente mensuráveis no fechamento: fechamento relativo do candle, corpo direcional, pavio direcional, sweep de 20 velas normalizado, amplitude relativa, tendência contrária dos cinco minutos anteriores e pontuação manual de reversão (0 a 5).
- Para evitar calibrar e declarar sucesso no mesmo dia, limiares são obtidos só a partir da proporção de etiquetas do primeiro dia, depois aplicados ao segundo; também executamos a direção contrária, dias 04→03. Como ambos os dias foram vistos em pesquisas anteriores, **isso é transferência interna, não OOS genuíno**.
- Pontuação ampla de reversão: treino dia 03 → teste dia 04 classificou **167** pares como candidatos; **10** têm etiqueta no demonstrador, **157** estão sem etiqueta; `10/167 = 5,99%` precisão relativa às etiquetas e `10/23 = 43,48%` cobertura. No sentido inverso (04→03), **147 candidatos / 9 etiquetados / 138 não etiquetados**, precisão **6,12%**, cobertura **50%**. Isso é sinal demais para uma réplica exata.
- Tendência contrária dos 5 minutos anteriores: dia 03→04 **14 candidatos / 2 etiquetados** (14,29% relativa) e dia 04→03 **26 candidatos / 6 etiquetados** (23,08% relativa). São **apenas 8** etiquetas cobertas em 40 candidatos, e os outros 33/41 sinais não são explicados simultaneamente.
- O filtro de sweep recente relativamente extremo selecionou **19** pares no dia 04 e **26** no dia 03 nas respectivas transferências, com **zero** etiquetas em ambos. AUC interna aparentemente elevada não compensa a falha do limiar em ambos os dias; logo, **não temos detector do Tracker recuperado**.
- Volume real, agressão, book, bid/ask, filas e configuração de execução do fornecedor são **ausentes** do HTML; não podem ser inferidos com confiança a partir das linhas Fibonacci.

## 4. Auditoria de execução

- [Workflow dos sete atributos e nove testes](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42690566247): concluído com sucesso e JSON completo `tracker_vector_research_43.json` como artefato do Actions.
- [Workflow das 63 âncoras geométricas, oito testes e 100 deslocamentos](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42690999404): concluído com sucesso e JSON completo `tracker_vector_anchor_family_43.json` como artefato.
- Nem estes testes, nem o REA anterior, demonstram fórmula exclusiva ou que o indicador não repinta no terminal proprietário. A versão independente de fluxo da [PR #52](https://github.com/lulualcides-sys/nexus-quant-paper/pull/52) permanece separada, compilada em MetaEditor real e sem ordens.

## 5. Decisão operacional

- **Sem alteração automática do detector MQL5** para ajustar os 43 exemplos comerciais; alto risco de sobreajuste, vazamento de validação e falsa semelhança.
- A geometria pública está operacional no nosso indicador, mas o *gatilho* não pode ser identificado unicamente com essas duas sessões escolhidas. Muitos algoritmos distintos produzem as mesmas 43 etiquetas e divergem em dias futuros.
- Para avançar tecnicamente é necessária uma coleta legal de M1 + histórico de negócios classificado (`CopyTicksRange`/flags e volume real) de vários dias novos, junto de exemplos originais contínuos e datados dos sinais na plataforma com acesso autorizado.
- Executar teste prospectivo congelado comparando sinais por horário/direção, e validar execução com slippage e taxas reais da Rico. Zero ajustes após olhar período de avaliação.
- **Sem promessa de lucro, sem acesso à conta do usuário, sem cópia de arquivos privados Greenhouse, sem novas ordens live, sem merge em main.**
