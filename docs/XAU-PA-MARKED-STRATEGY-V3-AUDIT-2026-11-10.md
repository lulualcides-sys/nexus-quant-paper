# XAUUSD Price Action v3 — regras confirmadas, lacunas e testes, 10/11/2026

## O que o usuário realmente descreveu

- Antes das operações, desenha **suportes, resistências, LTA e LTD**.
- Quando há **microtendência**, aguarda **romper a linha e depois fazer o reteste**, tanto para compra quanto para venda.
- Só aceita operar **diretamente no toque/rejeição da linha** quando o mercado está **lateralizado**.
- Quer **uma posição por vez**, com **Stop Win e Stop Red**; não quer travamento por limite diário de perda.
- **Não declarou** valores exatos de stop e alvo no ouro, largura das regiões, método matemático exato para escolher pivôs, quantidade exata de candles de confirmação, como identifica lateralização ou quando atualiza uma linha. Estes pontos NÃO podem ser anunciados como reprodução exata da discricionariedade.

## 1. Nova máquina de estados para LTA/LTD

[Motor v3](../research/xau_pa_manual_rules_v3.py), [12 testes unitários causais](../tests/test_xau_pa_manual_rules_v3.py), [scorecard de proveniência](../research/xau_pa_manual_rules_v3_scorecard.py) e [5 testes de auditoria](../tests/test_xau_pa_manual_rules_v3_scorecard.py).

Em comparação com os experimentos v2, **não usa EMA9/EMA21 nem rompe nível horizontal de 12 candles como substituto da microtendência**:

1. **LTD** (linha de topos descendentes) previamente marcada: primeiro candle **fecha acima da linha**, caracterizando rompimento **para compra**.
2. O robô **aguarda pelo menos um candle posterior**. Se fechar de novo abaixo da linha de forma significativa, considera *falso rompimento* e não entra.
3. Se houver **toque da antiga linha de resistência e fechamento de recuperação acima dela**, gera COMPRA **após o fechamento do candle de reteste**.
4. **LTA** (linha de fundos ascendentes) segue lógica espelhada: romper **para baixo**, retestar por baixo e confirmar **VENDA**.
5. Rompimento sem reteste válido expira após **8 candles M1 ou 5 candles M5** (hipóteses de implementação, NÃO uma regra explicitamente fornecida).
6. Cooldown mínimo de 3 candles após operação sinalizada impede múltiplas setas na mesma sequência.

A tendência, por si só, não cria entradas; o preço precisa cruzar a LTA/LTD e passar pelo estado de reteste.

## 2. Toques nas marcações apenas em lateralização

A entrada de reversão perto do suporte ou resistência pre-marcado só é aceita se os **18 candles anteriores** (não o candle de sinal) apresentarem deslocamento direcional pequeno, oscilação de um lado ao outro da faixa e amplitude compatível com ATR. Depois, o candle precisa tocar a zona e fechar de volta para o interior com rejeição.

- Suporte tocado/rejeitado na lateralização: **COMPRA**.
- Resistência tocada/rejeitada na lateralização: **VENDA**.
- Mercado direcional: **PROIBIDO** operar toque contrário à tendência; só podem ser usados os estados de rompimento/reteste.
- Stop usa extremo do reteste ou rejeição e um colchão de ATR. Alvo nominal de 2R, limitado pela largura disponível do range. São hipóteses ajustáveis, não parâmetros pessoais confirmados.

## 3. Marcações MANUAIS vs. aproximações automáticas

**`manual`:** sem arquivo de marcações, **nenhuma entrada é autorizada**. Um arquivo cronologicamente válido precisa especificar data, símbolo, horários de desenho anteriores à negociação, e linhas/zonas marcadas para **M1 e/ou M5**. O motor não inventa suporte, resistência, LTA ou LTD atribuídos ao usuário.

**`proxy`:** permite auditoria técnica com cotações históricas, mas os dois últimos pivôs confirmados geram uma **linha causal aproximada**, e os máximos/mínimos de 09h–12h UTC geram zonas automáticas. **É um modelo experimental, NÃO as marcações reais do usuário.**

Exemplo de formato de arquivo manual; **valores sintéticos ilustrativos**, não níveis reais do ouro e não destinados a executar ordens:

```json
{
  "symbol": "XAUUSD",
  "day": "20261102",
  "created_ms": 1793619000000,
  "by_timeframe": {
    "M1": {
      "trendlines": [
        {
          "kind": "LTD",
          "x1_ms": 1793611200000,
          "y1": 4000.0,
          "x2_ms": 1793614500000,
          "y2": 3995.0
        }
      ],
      "range": {
        "support_low": 3960.0,
        "support_high": 3962.0,
        "resistance_low": 4020.0,
        "resistance_high": 4022.0
      }
    }
  }
}
```

Observações: todos os timestamps são Unix em **milissegundos UTC**; início das velas dos pontos de ancoragem deve existir na fonte e estar concluído antes de `created_ms`; o arquivo precisa ter `created_ms` anterior ao início da negociação. Caso não existam marcações reais M5, remova a seção M5: ele ficará bloqueado em modo manual. A foto de uma linha **não** pode ser convertida automaticamente com precisão sem identificar os respectivos preços/horários.

Não utilizar o exemplo acima como marcação factual. Ele serve para o formato. O sistema rejeita marcações posteriores ou pontos de ancoragem futuros.

## 4. Backtest adicional real de cotações — 26/10 a 06/11

**[GitHub Actions SUCCESS, três jobs](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42806092691)**: 12 testes do novo detector, cinco testes do scorecard, 15 testes do motor de preços; repetidos para as duas janelas. Outubro 26–30: **5/5 datas válidas**. Novembro 02–06: **4/5**; **06/11** excluído integralmente por registro BID/ASK inválido na linha 79.637. Artefatos `xau-pa-v3-marked-rules-M1-M5-scorecard`, `xau-pa-v3-proxy-october-ledgers`, `xau-pa-v3-proxy-november-ledgers`. Os hashes SHA256 e os negócios simulados constam nos artefatos.

**AVISO CRÍTICO: estes backtests v3 usam `proxy` automático, porque ainda NÃO existem as linhas reais do usuário nessas datas. Assim não constituem backtest da discricionariedade manual.**

| Tempo | Modelo | Outubro sinais/fills | Outubro US$/oz | Novembro sinais/fills | Novembro US$/oz | Total fills | Total US$/oz |
|---|---|---:|---:|---:|---:|---:|---:|
| M1 | Original | 10/8 | −6,545 | 13/8 | −27,502 | 16 | −34,047 |
| M1 | Marcações proxy + regras v3 | 60/40 | −56,442 | 43/32 | −48,805 | 72 | **−105,247** |
| M5 | Original | 1/1 | +11,392 | 2/1 | +10,914 | 2 | +22,306 |
| M5 | Marcações proxy + regras v3 | 17/12 | −41,056 | 13/10 | +12,052 | 22 | **−29,004** |

**Composição da v3 M1**: outubro 27 fills de rompimento/reteste (−38,872) e 13 de lateralização (−17,570); novembro 26 de rompimento/reteste (−36,457) e seis de lateralização (−12,348).

**Composição da v3 M5**: outubro seis fills de rompimento/reteste (−35,387) e seis de lateralização (−5,669); novembro seis rompimento/reteste (−5,398) e quatro lateralização (+17,450).

**Custos de stress:** comissão assumida de US$ 0,60 por onça em ida e volta, slippage adverso de US$ 0,20 por onça nas saídas a mercado/stops e entradas, mais BID/ASK da fonte. Todos os valores representam **uma onça hipotética**, não conta de corretora, reais, nem milhares de dólares. Não inclui custos reais, swap, liquidez do broker, rejeições, margens ou lotes.

## 5. Limitações bloqueantes antes de aprovação

- **Fidelidade ao trader: PENDENTE.** Necessário comparar marcações e entradas realmente efetuadas/anotadas pelo usuário, com horários/níveis e exemplos de sinais rejeitados, contra o motor; não basta melhorar P&L de um proxy.
- **Parâmetros de risco: HIPÓTESES.** Stop Red/Stop Win sem valores monetários, localização exata e tratamento de saída não podem ser reproduzidos perfeitamente.
- **M1 e M5 foram reportados separadamente para diagnóstico**, mas também executados no braço **SHARED** do [novo executor de trava global](../research/xau_pa_shared_execution.py): **uma única posição por XAUUSD** entre ambos os timeframes, respeitando prazo individual de cada timeframe. Caso dois sinais ocorram exatamente juntos, nenhum é escolhido até haver uma regra de prioridade fornecida pelo usuário. O resultado SHARED não é a soma das duas contas separadas.
- **Nenhuma conta MT5 autorizada conectada**, nenhuma comprovação de desempenho em feed do broker, nenhuma ordem enviada.
- **Fonte e horários:** XAUUSD spot bid/ask Dukascopy 09h–21h UTC, aquecimento 09h–12h e ordens de 12h–21h, regras históricas pré-definidas mas não validada uma amostra prospectiva.

**DECISÃO: PR #61 em DRAFT, não mesclar, não operar com dinheiro real.** A v3 corrigiu a sequência causal e tornou possível aceitar marcações explícitas; nenhum benefício financeiro robusto foi demonstrado.


## 6. Trava global de posição: M1 e M5 simultâneos (mesmas datas)

A v3 inicialmente testava a posição única **dentro de cada timeframe**, o que não bastava para cumprir a preferência do usuário de uma posição por vez no instrumento. Foi acrescentado o [executor compartilhado](../research/xau_pa_shared_execution.py), com [sete testes de borda](../tests/test_xau_pa_shared_execution.py) que verificam tempo de vida de 20 barras M1 versus 20 barras M5, ausência de posições sobrepostas, colisões simultâneas bloqueadas e coincidência com o motor anterior em uma operação isolada.

**Reexecução GitHub Actions concluída:** [run 42807389157](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42807389157), três jobs **SUCCESS**; 12 testes do motor v3 + 5 de auditoria + 7 da trava compartilhada + 15 do simulador original, repetidos por período. Mesmas 9 sessões válidas, mesma fonte BID/ASK e custos de stress.

| Operação no XAUUSD | Outubro sinais / fills | Outubro líquido US$/oz | Novembro sinais / fills | Novembro líquido US$/oz | Total fills | Total US$/oz |
|---|---:|---:|---:|---:|---:|---:|
| Legado com posição global | 11 / 9 | +4,847 | 15 / 9 | −16,588 | 18 | **−11,741** |
| Regras v3 + **posição global M1/M5** | 77 / 43 | −77,429 | 56 / 37 | −27,982 | 80 | **−105,411** |

A versão v3 global acertou **19 de 80 operações** (23,75%) e perdeu em **61**, por isso não apresenta vantagem líquida. Os dois blocos foram negativos. São resultados com **marcações proxy automáticas**, não com linhas reais do usuário.

**Decisão:** trava por símbolo implementada e testada; nenhum resultado autoriza negociação. Não somar resultados M1+M5 separados e nunca escolher um time frame por lucro retrospectivo.
