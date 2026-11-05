# Tracker/ATLAS — validação de sinais por gravação contínua

**Data:** 2026-11-05. **Escopo:** investigação estatística independente; nenhuma operação nem lucratividade validada.

## Problema corrigido

A comparação anterior com as setas da Greenhouse avaliava **somente acertos sobre as setas conhecidas**. Isso não determina a *precision* nem permite saber quantas setas extras o ATLAS apresenta em momentos em que o indicador real não mostrou sinal.

Não é válido classificar como falso positivo um sinal de ATLAS apenas porque ele não apareceu num vídeo promocional editado: a câmera pode ter omitido esse candle. Tampouco é válido interpretar o tempo de reprodução do player como horário de mercado.

## Nova condição necessária para comparar qualidade das setas

O ATLAS aceita dois arquivos distintos:

1. `--tracker-labels`: CSV com **setas observadas** e campos `date,market_time,side,evidence_url,observed_after_close`, existentes no replay WINV26.
2. `--observed-windows`: CSV **declarando períodos com gráfico e indicador visíveis de forma contínua, com TODAS as setas daquele período anotadas**:

```csv
date,contract,timeframe,start_market_time,end_market_time_exclusive,evidence_url,recording_continuous,indicator_visible_throughout,all_tracker_signals_labeled
2026-10-13,WINV26,M1,10:25:00,10:35:00,https://URL-DA-GRAVACAO-REAL,yes,yes,yes
```

A linha acima é **um exemplo de estrutura**, NÃO uma gravação real auditada. O sistema não converte a declaração `yes` em prova: quem audita ainda precisa revisar o vídeo integral, o timeframe, o contrato, a transparência de setas, o fuso e a continuidade. Qualquer campo `no`, janela sobreposta, intervalo fora de sessão ou URL inválida gera erro.

Se houver lacunas no M1 de mercado dentro do período coberto, **não preencher velas fictícias nem calcular a métrica**. Cada candidato é avaliado somente após pelo menos 75 candles históricos disponíveis. Não usar candles futuros para detectar seta.

## Métricas calculadas APENAS para janelas de observabilidade integral

| Situação no mesmo candle e direção | Contabilização |
|---|---|
| Tracker compra, ATLAS compra | TP |
| Tracker compra, ATLAS venda | 1 FP e 1 FN (direção errada) |
| Tracker compra, ATLAS não sinaliza | 1 FN |
| Nenhuma seta do Tracker, ATLAS sinaliza em gravação comprovadamente contínua | 1 FP |
| Nenhuma seta de ambos | Não é uma operação; não inflar acurácia |

- Precisão = TP/(TP+FP): quantas setas do ATLAS correspondem a setas reais do Tracker, dentro das janelas.
- Recall = TP/(TP+FN): quantas setas reais do Tracker foram recuperadas pelo ATLAS, dentro das janelas.
- F1 = média harmônica de precisão e recall.
- Sem sinais ou sem denominador: valor `null` (não inventar 0%, 100% ou winrate).
- Sinais de ATLAS **fora** das gravações completas não são chamados de falsos positivos.

**Essas métricas NÃO medem lucratividade, execução de corretora nem equivalência de fórmula.** Mesmo o consenso de setas não reproduz eventuais regras de entrada, cancelamento, parcial ou stop.

## Execução com arquivos reais, se disponíveis

```bash
python -m research.atlas_b3_ticks_oct13 \
  --b3-file /dados/baixados-manualmente/NEGOCIOSAVISTA.zip \
  --tracker-labels /evidencias/tracker_setas_confirmadas.csv \
  --observed-windows /evidencias/gravacoes_continuas.csv

# Ou com série Profit genuína, contrato WINV26 M1:
python -m research.atlas_win_oct13 \
  --winv26-csv /dados/WINV26_M1_20261013.csv \
  --verified-labels /evidencias/tracker_setas_confirmadas.csv \
  --observed-windows /evidencias/gravacoes_continuas.csv
```

Nenhum dos arquivos de dados e gravações acima foi obtido nesta PR: são caminhos ilustrativos.

## Fonte primária e limitações

O [glossário oficial B3 — Negócios a negócio (PDF)](https://www.b3.com.br/data/files/14/42/28/31/FEC4A8103234E0A8AC094EA8/Glossario_NegociosListados_PT.pdf) informa `AcaoAtualizacao=0` como inclusão, `2` como cancelamento, `HoraFechamento` com milissegundos `HHMMSSNNN` e `TipoSessaoPregao=1` como sessão regular. O importador continua sem coleta automática da B3.

A afirmação comercial de 22 alvos e 5 stops em 13/10/2026 ainda não foi auditada; mesmo uma alta precisão entre setas pode produzir prejuízo após custos e não equivale à sua fórmula confidencial.

## Testes e aprovação

- `tests/test_atlas_tracker_observability.py`: sete testes sintéticos de precisão, recall, direção inversa, ausência de sinais, lacunas, pré-histórico insuficiente, janelas sobrepostas e rótulo fora da cobertura.
- Fluxos anteriores de importação e demais robôs permanecem preservados.
- **Não há promoção automática** para o ATLAS paper/operacional até termos dados reais, vídeo contínuo autenticado e validação prospectiva.
