# Escopo operacional da pesquisa XAUUSD: 2025 em diante

Data: 2026-11-12  
**Pedido do usuário:** não pesquisar outros anos; considerar somente 2025 em diante, exclusivamente XAUUSD.

## Implementação verificada
- `robots/mt5/nexus_vector_retest/alpha_xau_adaptive.py` aplica limite de início em `2025-01-01T00:00:00Z` antes de preparar os candles M15. A execução inclui **somente** janelas cronológicas de 2025 e de 2026 que existam nas fontes verificadas.
- `.github/workflows/xau-ema21-adaptive.yml` faz sparse-checkout somente dos dados diários de **2025** e utiliza a fonte pinada de 2026. **Não baixa 2023 nem 2024**.
- Histórico anterior existente em relatórios antigos preservado por rastreabilidade, mas **não utilizado** na execução atual.
- Não equivale a teste fora da amostra: 2025/2026 já foram analisados em iterações prévias. Um resultado positivo nesses períodos pode sofrer viés de seleção.
- Somente pesquisa de XAUUSD; sinais originais EMA21/55 e VWAP preservados.

## Resultado de replay M15 — 10.000 candles por janela

Pontos líquidos estimados, com `POINT=0.01`, custo fixo hipotético de US$0,80/onça por operação; dados OHLC, **não MT5 com ticks Bid/Ask do broker**.

| 10k candles | Runner fixo 384 | Runner condicional por tendência | Parecer |
|---|---:|---:|---|
| 2025, primeira janela | +5.559,7 (119 entradas; PF 1,132) | −13.799,7 (306 entradas; PF 0,866) | Runner fixo melhor |
| 2025, segunda janela | +16.996,6 (145 entradas; PF 1,421) | −9.368,1 (335 entradas; PF 0,916) | Runner fixo melhor |
| 2026, janela disponível | +4.942,2 (149 entradas; PF 1,064) | +5.087,8 (333 entradas; PF 1,031) | Condicional tem drawdown maior |

Em 2026 o Runner384 teve MDD simulado de 20.908 pts, contra 27.838,1 do condicional. O Runner384 tem desempenho positivo nos três blocos desse recorte, mas os custos são hipotéticos, o drawdown é relevante e os parâmetros já foram pesquisados nessas janelas: **não aprovado para negociações reais**. Descartar a afirmação de lucro comprovado.

## Verificação
- GitHub Actions do recorte, concluído com sucesso: https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/43218713926
- Sintaxe e testes de regressão concluídos, conjunto diário pinado de 2025 baixado, replay de 2025/2026 executado e relatório gerado.
- Próximos testes somente em janelas a partir de 2025 e, sempre que possível, novos dados de 2026 ainda não examinados ou forward em conta demo para obter evidência genuína, sem confundir repetição de dados com validação nova.

**Proteção:** preservar os snapshots do robô 41.641 pontos brutos, Runner384 e outros robôs. Não mexer em main, real trading, Telegram nem contas do broker por consequência desta configuração.
