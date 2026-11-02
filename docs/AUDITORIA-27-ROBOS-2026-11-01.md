# Nexus Quant — monitoramento integral dos 27 robôs (01/11/2026)

**Escopo:** 10 robôs de ouro H4 (5 convencionais + 5 alavancados), 15 robôs experimentais H1 (3 × 5 mercados), 1 robô USD/CAD M15/H1 e 1 robô experimental Momentum60 H4. **Total planejado: 27.** Os quatro robôs de cripto pertencem a uma linha paralela e não são somados a este censo.

## Estado real x configuração

- O código do Momentum60 está inicialmente na [PR #9](https://github.com/lulualcides-sys/nexus-quant-paper/pull/9). Até a integração e primeira observação, **não deve ser considerado ativo nem lucrativo**.
- `src/all_robots_audit.py` cria **27 entradas de diagnóstico mesmo quando um mercado falhou**, diferenciando `unavailable` de P&L zero.
- Cada entrada tem o grupo, nome, status, última barra processada (quando disponível), status de dados antigos, presença de posição, número de fechamentos, entradas observadas e resultado líquido realizado da banca **virtual**. Não deduz P&L não realizado de posições abertas.
- Nos robôs H1, a contagem de entradas vem do diário `entries` da estratégia. Nos H4 originais e M15, a contagem é baseada em operações já registradas mais posições abertas; **não representa inventário completo de todos os sinais**. O campo `entries_complete` registra essa diferença.
- Status distinguem posição aberta, pré-sinal H4 para candle futuro, ausência de novo sinal, cooldown, limite de risco, lacuna, dados atrasados e estado ausente.
- A auditoria não consulta LLMs nem endpoints adicionais e **não muda código de sinais, risco, bancos de dados ou stops**.

## Saídas

- Resumo diário no Telegram continua **uma vez ao dia**, sem alertas individuais de entradas ou saídas. O título informa `27 robôs previstos`, não `27 operações efetivas`.
- Novo arquivo: `reports/robot_diagnostics/AAAA-MM-DD.json`, com os 27 identificadores, evidências disponíveis e ausência explícita de dados.
- Diagnósticos antigos H4 e H1 são preservados por compatibilidade; auditoria nova agrega sem substituir os arquivos de estados.
- Bancas virtuais de referência: US$ 50 mil nos dez H4, US$ 15 mil nos H1, US$ 1 mil no USD/CAD e US$ 5 mil no Momentum60 = **US$ 71 mil simulados**. Isso **não é capital real**, retorno obtido ou dinheiro investido.

## Regras para promover estratégias

Não aumentar frequência de entradas artificialmente. Exigir avaliação de amostra prospectiva, comparação por robô no mesmo período, custos, drawdown e qualidade de feed, com separação cronológica. Vibe-Trading e AutoHedge continuam sendo **referências arquiteturais**, sem instalar código de execução nem conectar carteiras/corretoras.

## Segurança e testes

- Nenhuma ordem real, senha, token ou carteira.
- Estado ausente não vira retorno zero.
- O Momentum60 inicia sem backfill de operações.
- Testes sintéticos cobrem 27 identificadores, indisponibilidade parcial (1 mercado H1 = 3 robôs), ausência do M15/Momentum60, status de dados antigos, imutabilidade dos estados e limite do Telegram.
- O sistema só pode ser considerado integrado após testes GitHub Actions concluídos e merge confirmado.
