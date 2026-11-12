# WIN Liquidity Sweep — custos da Rico, outro vencimento e importação MT5

**09/11/2026 — pesquisa executada; NÃO aprovado para dinheiro real.**

## Evidência verificada

- [GitHub Actions — replay de WINQ26 / WINJ26 e testes](https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42663740160).
- Os relatórios detalhados JSON e Markdown com ledger são gerados no artifact do workflow. Fonte WINQ26 com SHA Git 43c50f01882f1ac497a218549e0bff2964d94aa5 e WINJ26 com SHA Git 7fcc91ebde3e674f910ac82eef00b6bf19541151.
- Ambos vêm de exportações Profit declaradas por terceiros; **não verificados independentemente pela B3**. WINJ26 é outro contrato real, mas seus 5.129 candles M1 são fragmentados em 2025, e foram inspecionados em estudos anteriores.

## Pesquisa de custos de execução

- Rico, plataforma MetaTrader 5 gratuita: https://www.rico.com.vc/plataformas/metatrader/ . Plano promocional anunciado R$0,26 por contrato para 15 mil contratos/3 meses; **não presumimos elegibilidade da sua conta nem da automação**.
- Tabela Rico de minicontratos: https://www.rico.com.vc/custos/ . Sem RLP, o valor anunciado para day trade é R$0,45/contrato. Com RLP ativo, anuncia corretagem zero, sujeita a condições.
- Página educativa B3: https://edu.b3.com.br/day-trade . Tabela apresenta custo máximo de taxas B3 de R$0,50 por roundtrip WIN para o exemplo de day trade.
- Cenários sem RLP: R$0,45 × 2 + R$0,50 B3 + 1 tick de slippage em cada lado (R$2) = **R$3,40 por operação completa**, ou 2 ticks/lado = **R$5,40**. Taxas de IR, custos extraordinários, spread, filas e tarifas reais não foram medidos.
- Cenário RLP hipotético: R$2,50 incluindo B3+1 tick/lado. Não confirmado para Expert Advisors do MT5. Nunca ativar ou presumir RLP no robô apenas porque melhora backtest.

## WIN Liquidity Sweep — resultado líquido retrospectivo

| Contrato / período | Custo / ciclo | Filtro R/R líquido >=1 | Trades | Líquido R$ | Profit factor |
|---|---:|---|---:|---:|---:|
| WINQ26 junho/2026 | R$6,00 | não | 19 | -114,00 | 0,424 |
| WINQ26 junho/2026 | R$3,40 | não | 30 | -63,00 | 0,775 |
| WINQ26 junho/2026 | R$3,40 | sim | 26 | -61,40 | 0,761 |
| WINQ26 junho/2026 | R$5,40 | não | 21 | -63,40 | 0,668 |
| WINQ26 julho parcial | R$6,00 | não | 31 | -65,00 | 0,745 |
| WINQ26 julho parcial | R$3,40 | não | 40 | +62,00 | 1,217 |
| WINQ26 julho parcial | R$3,40 | sim | 35 | +93,00 | 1,381 |
| WINQ26 julho parcial | R$5,40 | não | 32 | -65,80 | 0,752 |
| WINQ26 julho parcial | R$5,40 | sim | 3 | -19,20 | 0,505 |
| WINJ26, exportação fragmentada 2025 | Todos | ambas | 0 | 0,00 | N/D |

Um mês positivo não garante vantagem, especialmente porque o mesmo período já foi visto antes. Em junho até o cenário de custo reduzido foi negativo. O teste em WINJ26 não forneceu nenhum trade, logo **não é validação externa de lucro**.

## Importador de histórico MetaTrader 5

Adicionado `research/win_mt5_history_import.py` e testes específicos em `tests/test_win_mt5_history_import.py`. Baseado no formato de exportação oficial MetaQuotes: https://www.metatrader5.com/en/terminal/help/trading_advanced/custom_instruments .

**Função:** converter M1 bruto do MT5 (colunas DATE/TIME/OPEN/HIGH/LOW/CLOSE/TICKVOL/VOL/SPREAD) em CSV canônico de um único vencimento WIN, apenas para pesquisa. O campo `<VOL>` é volume real de contratos; `<TICKVOL>` não substitui volume real. Posições não são executadas, não há consulta a senha/corretora.

**Restrição importante:** o CSV do MT5 normalmente armazena horário do servidor. É obrigatório confirmar o deslocamento em relação ao UTC da conta Rico; o programa nunca adivinha fuso e não o configura como -3 automaticamente. Nome do arquivo deve identificar um único contrato (por exemplo, WINZ26_M1.csv), e o parâmetro de contrato deve corresponder.

**Exemplo, somente após confirmar o fuso do servidor MT5:**

```bash
python -m research.win_mt5_history_import --csv WINZ26_M1.csv --symbol WINZ26 --server-utc-offset -3 --out winz26-normalized.csv
```

No exemplo, `-3` é apenas **ilustrativo** e deve ser substituído pelo valor verificado. A rotina preserva o arquivo original, rejeita volume real zero, duplicidades, preços fora da grade, OHLC incorreto, períodos futuros e troca de vencimento; produz auditoria de lacunas e SHA256 do arquivo.

O export do MT5 por View → Symbols → Bars → Request → Export é descrito na documentação MetaQuotes; o acesso ao histórico depende da corretora e do terminal, e não podemos gerar meses não disponibilizados por ela.

## Decisão e próximos passos

- **Nenhum robô autorizado para conta real ou automação MT5.** PR em rascunho, sem publicar em main.
- Para validação financeira: dados suficientes de vários vencimentos completos e inéditos (idealmente M1 e, para execução, ticks bid/ask), custos reais da nota de corretagem, slippage por horário, stop com gaps e teste prospectivo com risco de baixa exposição.
- Não manipular parâmetros de julho para fabricar expectativa positiva; o resultado estressado contradiz lucro robusto.
