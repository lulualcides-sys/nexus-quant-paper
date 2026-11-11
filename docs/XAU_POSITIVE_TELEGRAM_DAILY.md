# GOLD / Telegram diário dos cenários historicamente positivos

## Objetivo e frequência

Aproveitar o monitor original `main` (`.github/workflows/monitor.yml`), que emite o fechamento às **19h30 America/Sao_Paulo** e faz uma segunda tentativa às **20h00** em dias úteis. Envia **uma segunda mensagem curta em texto simples** com as famílias de estratégias historicamente positivas, sem mudar as notificações antigas.

O módulo `src.xau_positive_daily` é somente leitura sobre os livros virtuais e os arquivos arquivados. Ele só grava seu próprio marcador e seu relatório:
- `state/xau_positive_daily_sent.json`, após **confirmação** do Telegram (evita reenvio no retry);
- `reports/xau_positive_daily/YYYY-MM-DD.json` (metadados do relatório, sem supor novas ordens).

Nenhum replay/backtest gera operações diárias, e nenhum snapshot de resultado positivo é incluído no P/L operacional. Não envia ordens para MT5/FBS ou abre posições reais.

## Catálogo, execução e pendências

- `research/preserved/xau_all_positive_original_robots_20261110.json`: 52 cenários positivos de pesquisas históricas, 14 famílias, não 52 robôs.
- `research/preserved/xau_v8_all_positive_h4_snapshots_20261110.json`: 30 cenários positivos H4 em cinco famílias, variando capital virtual e slippage, **não 30 robôs**.
- A união do catálogo contém **15 famílias**. **14** têm estado PAPER no projeto `main`: cinco H4 convencionais, cinco H4 alavancados virtuais, três H1 XAU e Momentum60 H4. Status é verificado por arquivo e por carteira, nunca presumido.
- **1 não tem livro XAU equivalente no monitor:** adaptação histórica BB20 XAU do teste rotulado M1. O livro `bb20_mtf_usdcad_v1.json` é de USD/CAD e não pode ser passado como ouro. O resumo informará **PENDENTE**, nunca inventará entrada/P/L.
- Os rótulos M1/M5/M15/M30 dos outros snapshots são resoluções de backtest, não novas estratégias independentes ativas. As variantes experimentais com saída por relógio M5 não foram habilitadas como robôs extras.

Cada livro disponível tem entradas e fechamentos do **dia civil brasileiro**, P/L realizado do dia, P/L acumulado desde o início do livro e posição virtual aberta. Todos os valores referem-se ao ativo indicativo **GC=F Yahoo** e aos custos de cada motor, **não BID/ASK real FBS**. A mensagem identifica data de atualização mais antiga; água de marcação inválida e arquivo ausente são reportados como **indisponíveis**, nunca interpretados como zero.

## Garantias

- Os arquivos históricos devem ter exatamente 52 e 30 cenários e a união deve coincidir exatamente com os 15 IDs previstos; caso contrário, a notificação falha sem omitir uma família.
- Nenhuma duplicação de alias H1 como se fosse estratégia distinta, nenhum somatório das carteiras independentes; não anunciar lucro fictício.
- Tentativas de enviar são repetidas só após falha não confirmada. Como o GitHub persiste marcadores via git, eventual erro no `git push` após o Telegram confirmar pode causar repetição; nenhuma promessa de entrega exatamente uma vez em falha de infraestrutura.
- A rotina já existente de fechamento permanece inalterada e é executada antes desta. Se o fechamento original falhar, o retry será feito pelo próprio monitor existente.
- O arquivo de estado de cada robô, os stops, o sizing, o risco, as regras e o monitor de negociação não são modificados.