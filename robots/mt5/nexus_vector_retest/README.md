# NEXUS VECTOR RETEST EA v1.00 — MT5

**Novo robo automatico original**, independente do Nexus VWAP e do Nexus Vector H1. Estrategia de rompimento + reteste confirmado, nao usa VWAP como sinal.

## Setup e vetor matematico

1. Em cada candle **fechado**, calcula maxima/minima dos 24 candles anteriores e ATR14.
2. Confirma rompimento alem do nivel em 0,08 ATR.
3. Aguarda um **outro** candle fechado tocando e recuperando nivel, ate 8 candles posteriores, com corpo direcional. Entra apenas na abertura do proximo candle.
4. Vetor normalizado 0..1: `S=0.25*forca_rompimento+0.25*reteste+0.20*EMA21/55+0.15*momentum5+0.15*RVOL20`. Minimo `S>=0.51`, **nao e probabilidade de acerto**.
5. Nao repete na mesma direcao por padrao, exige 8 candles entre entradas e nunca abre se ja existe uma posicao no mesmo simbolo.

## TP, ordens e seguranca

- EA `.mq5` com entrada de mercado executada pela API CTrade. **Por padrao opera apenas demo**: `InpAutoTrade=true`, `InpAllowReal=false`. Ativar comercio real exige alteracao explicita no parametro e permissao do terminal.
- Risco inicial **0,50% do equity**, stop obrigatorio enviado ao servidor, tamanho do lote por `OrderCalcProfit`; se lote minimo exceder orcamento ou faltar margem, pula entrada.
- **TP1=1R, TP2=1,5R, TP3=2R.** Fecha cerca de um terco da posicao a cada alvo quando volume minimo do broker permite. Stop e TP3 permanecem na corretora. Se volume for pequeno demais para dividir em 3, **TP1/TP2 sao apenas visuais**, com TP3 para toda posicao; isso nao e contabilizado como tres fills.
- Limite diario: bloqueia **novas entradas** caso equity recue 2% do marco diario persistido na instancia; nao encerra automaticamente posicoes abertas.
- Spread maximo, slippage configuravel, 1 posicao por simbolo. Nunca modifica operacoes de outros magics. Conta REAL fica travada ate opt-in manual.
- Um painel escuro: GREEN, RED, pontos e resultado financeiro **executados e realizados**, registrados a partir de deals do broker (inclui custos registrados no historico); setas pequenas, linhas TP1/2/3, SL, entrada e texto de green/red apos o encerramento. Som ao receber confirmacao de execucao. Alertas pop-up e push opcionais.
- Estatistica historica utiliza o **magic** do EA e o simbolo, janela de `InpHistoryDays`, agrupando deals por identificador da posicao. Nao confundir numero de pontos com porcentagem da banca.

## Instalar

1. MT5 -> Arquivo -> Abrir Pasta de Dados -> `MQL5/Experts/`. Copie `Nexus_Vector_Retest_EA_v1.00.mq5`.
2. Abra no **MetaEditor** e compile (F7) ate obter **zero erros** (nao foi possivel executar MetaEditor nesta sessao).
3. Abra um par Forex ou XAUUSD M5/M15 em **conta DEMO**; habilite negociacao algoritmica apenas na demo, anexe o EA e verifique o painel.
4. Para conferir desempenho, use **Strategy Tester com ticks reais**, custos do broker, treino/teste cronologico e walk-forward. Compare VWAP com as mesmas condicoes e validacao fora da amostra.
5. O arquivo `research_oos.py` no pacote ZIP do usuario e apenas uma **aproximacao historica OHLC**, nao execucao MT5. A comparacao nao foi executada nesta sessao.

## Validacao e limites

**26 testes sintéticos locais passaram.** O workflow deste diretorio faz testes estatics focados. **Nao foi compilado nem executado no MT5; nao foi demonstrado ser melhor que o VWAP.** O codigo e entregue como candidato para teste, nao estrategia lucrativa validada.

Manter o VWAP atual intacto, sem merge de logica no indicador. Revisar especialmente preenchimentos parciais, margem, historico MQL5 e regras de volume do broker antes de conta real.

## Pesquisa histórica verificável

O script [research_oos.py](research_oos.py) baixa um CSV XAUUSD M1 de commit fixo, checa SHA256 e compara **proxy do robô Vector Retest** e **proxy VWAP** no mesmo histórico M5/M15/M30, com custo fixo equivalente, entrada na abertura seguinte, stop-primeiro e TP em 3 parcelas. **Não é compilação/executação MQL5 real, não valida Forex e não representa a versão VWAP do usuário.** Os 30% finais de cada série são reservados para validação fora da amostra; não reotimizar em cima desse período. O [workflow de pesquisa](../../../.github/workflows/nexus-vector-retest-oos.yml) publica relatório e JSON como artefatos, sem substituir estratégias anteriores.
