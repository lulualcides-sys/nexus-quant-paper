# Vibe-Trading + AutoHedge: integração segura no Nexus Quant — 01/11/2026

## Proveniência e objetivo

Referências oficiais:
- [HKUDS/Vibe-Trading](https://github.com/HKUDS/Vibe-Trading), framework de pesquisa de mercado, agentes e paper trading.
- [The-Swarm-Corporation/AutoHedge](https://github.com/The-Swarm-Corporation/AutoHedge), separação entre agentes de pesquisa, quant, risco e execução; suporte anunciado para negociação em Solana.

**Atenção:** estudamos a arquitetura dos projetos, mas **não** copiamos nem instalamos suas dependências; nenhum deles foi conectado a uma corretora ou carteira. A integração feita neste patch é um estágio **observacional** de supervisão e análise sobre nosso próprio código.

## Implementação efetiva

- `src/h4_entry_audit.py`: analisa os mesmos candles H1 públicos utilizados para montar H4 completo. Compara a regra de entrada no último H4 fechado com a barra anterior, distinguindo:
  - posição virtual já aberta;
  - bloqueio por drawdown, perda diária ou saldo inválido;
  - dados antigos ou possível fechamento de mercado;
  - **transição nova candidata à abertura de candle seguinte, NÃO uma ordem**;
  - sinal persistente sem novo cruzamento;
  - ausência normal de setup.
- Exige que os dois estados sigam na mesma watermark e sejam `paper_only`; estados incorretos falham sem inventar sinais.
- `src/runner.py`: no relatório diário **já existente**, acrescenta uma única linha agregada caso haja espaço no Telegram. Grava `reports/entry_audit/AAAA-MM-DD.json` com status dos 10 robôs. Falhas na auditoria não interrompem o relatório normal.
- `tests/test_h4_entry_audit.py`: cenários sintéticos de imutabilidade dos dados, dez livros, transição/persistência, posição aberta, limites de risco, feed antigo, falta de histórico e watermark inválida.

## Evidência, limitações e próximos gates

1. **Aguardando CI da branch/PR**: testar sintaxe e suíte de regressão antes de qualquer merge no branch principal.
2. **Não altera estratégias**: `research.screen_v2.sign`, `gold_forward.evaluate_bar`, `leveraged_gold.one_bar` e os stops continuam com comportamento anterior. Não há mais entradas causadas pelo patch.
3. **Apenas previsão de sinal de abertura seguinte**: quando há novo sinal no último H4 fechado, não significa que uma posição será aberta, especialmente se houver filtro de risco, lacuna de preço ou posição ativa.
4. **Não há P&L adicional**: nenhuma amostra nova, teste fora da amostra ou validação de lucratividade foi produzida nesta etapa. Para comparar estratégias Vibe, usar dados sem vazamento temporal, registrar custos, aumentar amostra e paper trading prospectivo.
5. **AutoHedge fica como referência arquitetural**: suas APIs Solana não são conectores para FBS/GC=F; não habilitar wallets, segredos ou execução autônoma.
6. **Segurança operacional**: apenas 1 resumo por dia no Telegram, sem mensagens por trade; arquivos de estado e formato de posições são preservados; nenhuma credencial de usuário fica em logs ou arquivos públicos.

### Próxima prioridade técnica

Após observar relatórios H4 por pelo menos vários pregões, usar os estados `candidate_next_bar`, `no_new_signal` e `persistent_signal` para confirmar se a frequência baixa é esperada ou consequência de regras excessivamente rígidas. Propor alterações de estratégias **somente** como variantes independentes em paper trading com métricas de custo, slippage e validação prospectiva — sem ajustar parâmetros retroativamente para forçar lucro.
