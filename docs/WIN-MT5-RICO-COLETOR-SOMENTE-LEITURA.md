# MetaTrader 5 / Rico — coleta local de WIN M1 e revalidação do Nexus Quant

**Status 09/11/2026:** implementação de coleta somente leitura e testes simulados de API concluídos. A conexão ao MetaTrader 5 da Rico no computador do usuário **não ocorreu**. Não houve download de candles do usuário, nenhuma ordem real, nem lucro confirmado.

## O que foi implementado

- `research/mt5_readonly_collector.py`: coleta os últimos 1–180 dias M1 de um **único** contrato WIN da instalação local logada do MT5. Utiliza `MetaTrader5.initialize` (sessão do terminal já conectada), `terminal_info`, `symbol_info`, `symbol_select`, `copy_rates_range`, `shutdown`. **Não usa `order_send` ou credenciais no código.**
- O timestamp retornado pela API Python oficial do MT5 é UTC; a conversão para America/Sao_Paulo ocorre explicitamente na leitura. O coletor NÃO adivinha o fuso do servidor e não usa a hora local do Windows para reinterpretar preços.
- Aceita apenas o código explícito do vencimento, por exemplo `WINZ26`, exigindo grade de 5 pontos do mini-índice, volume real positivo de contratos (`real_volume`), integridade OHLC, minutos cronológicos, exclusão do candle em formação e registro das lacunas. Não preenche candles faltantes.
- O histórico e os relatórios ficam na pasta local `private_mt5/`. `.gitignore` impede que essa pasta seja adicionada acidentalmente ao repositório. **Sem upload automático para GitHub ou serviços externos.**
- Executa estratégia Sweep congelada em janelas cronológicas 70/30, apenas para pesquisa, com custo de taxas estimado R$1,40/ciclo **não confirmado** na conta e slippage de 1 ou 2 ticks por lado; compara baseline e filtro econômico líquido 1:1.
- O resultado é um JSON com ledger, lucro líquido hipotético, drawdown realizado, profit factor e flags de qualidade. Campo de aprovação para conta real sempre `false`.
- `executar_WIN_MT5_somente_leitura.cmd`: iniciador Windows com contrato WINZ26 padrão em novembro de 2026. Exige Python 3 previamente instalado, mas **cria automaticamente o ambiente `.mt5_win_venv/` e instala nele o pacote oficial `MetaTrader5` via PyPI**, quando faltar. Não instala o terminal Rico nem altera programas Python globais. `--self-test` testa o código sem terminal; `--setup-only` verifica o ambiente e as dependências sem conectar à corretora.

## Evidência de testes

- GitHub Actions Linux (10 testes da coleta com MT5 simulado): https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42666918161 . Windows (iniciador de um clique, instalação no venv e importação do pacote) tem workflow próprio: https://github.com/lulualcides-sys/nexus-quant-paper/actions/workflows/win-mt5-windows-smoke.yml ; ver conclusão da execução atual antes de afirmar validação.
- Foram executados 10 testes com dados sintéticos e API MT5 simulada, verificando sequência cronológica, timezone UTC, volume real, proteção contra duplicação, rejeição de símbolo errado, histórico indisponível, corte de candle incompleto, ausência de ordens e relatório de pesquisa sem ganhos inventados.
- O GitHub CI Linux **não consegue conectar-se ao terminal Windows MT5 do usuário**: o teste confirma funcionamento lógico, não a compatibilidade efetiva de autenticação/feeds da Rico.
- O teste com WINQ26 e WINJ26 de terceiros foi realizado anteriormente: https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42664956216 . Ainda não há lucro consistente ou evidência de vantagem fora da amostra.

## Como ativar no PC depois de instalar o MT5 pela Rico

1. Instalar o MetaTrader 5 da Rico e entrar na conta de simulação ou em uma conexão autorizada a mostrar preços, sem enviar ordens.
2. No Windows, instalar Python 3.11, se ainda não tiver. **Não é necessário executar pip manualmente**: o iniciador cria um ambiente virtual privado e instala automaticamente o pacote `MetaTrader5` oficial, desde que o computador tenha acesso à internet. Isso não instala o aplicativo MetaTrader 5 propriamente dito.
3. Baixar/clonar a branch da PR #50 para o computador e executar `executar_WIN_MT5_somente_leitura.cmd`. Ela usa WINZ26 como padrão em novembro de 2026. Depois de mudar o vencimento, chamar `executar_WIN_MT5_somente_leitura.cmd WIN<mes><ano>` com código correto, não WINFUT.
4. O programa fará leitura M1 de até 90 dias do histórico que o terminal disponibilizar e gravará os arquivos em `private_mt5` no computador do usuário. Se não houver 100 candles M1 válidos ou não vier volume real, ele falhará explicitamente.
5. Os relatórios podem ser inspecionados localmente; não publicamos arquivos dessa pasta nem pedimos senha da corretora.

## Limitações importantes

- A API oficial MetaTrader 5 para Python funciona junto ao terminal instalado localmente em Windows e depende do histórico liberado no servidor. A documentação do fabricante aponta limite `Max. bars in chart` para o histórico disponível.
- `WINZ26` é apenas o contrato atual para novembro de 2026. O ticker exato deve existir na janela do MT5 da Rico; símbolo customizado ou com sufixos precisa ser tratado separadamente, nunca assumido automaticamente.
- Quantidade real de contratos pode ser zero/indisponível na fonte MT5. Em vez de trocar por tick_volume e invalidar filtros de fluxo, o importador reprova o arquivo.
- Taxas e margem são definidas pelo contrato da Rico e situação da conta. O custo R$1,40 de taxa fixa no cenário local é uma hipótese de pesquisa derivada de estimativas públicas; não substitui extrato nem inclui todos os riscos.
- Dados M1 não verificam sequência de toques dentro do candle, book, fila de execução ou slippage real. Zero operações ou resultado positivo isolado não garante lucro.
- Não houve operações simuladas em conta MT5 real/demonstração nesta execução do GitHub; somente testes determinísticos. Não há integração automática remota com a instalação Windows através do ChatGPT.

## Referências técnicas oficiais

- https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesrange_py
- https://www.mql5.com/en/docs/python_metatrader5/mt5initialize_py
- https://www.mql5.com/en/docs/python_metatrader5/mt5symbolselect_py

**Regra de segurança:** não habilitar operação real, nem transformar relatórios em sinais automáticos; aprovação exige amostras externas suficientes, custos confirmados e observação prospectiva auditável.
