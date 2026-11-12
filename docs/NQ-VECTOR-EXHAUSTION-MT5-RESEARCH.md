# NQ Vector Exhaustion — protótipo independente para MetaTrader 5

**Escopo:** indicador educacional criado do zero a partir do método de vetores divulgado publicamente pela Greenhouse e de uma **hipótese independente** para detecção de exaustão. Não é o código original, não é cópia comprovada dos sinais, não substitui a licença do Tracker e não permite executar ordens.

## Referências públicas e observações verificadas

- Site oficial atual da oferta: https://lojadagreenhouse.com.br/ofertatracker/ (Tracker V3.0 anuncia Profit, BlackArrow e MT5).
- Loja oficial: https://lojadagreenhouse.com.br/ descreve a geometria pública de entrada 50%, alvo 200% e stop -100%, com 0% a 100% no candle que foi sinalizado após fechar.
- A empresa menciona fluxo, exaustão, manipulação e volume. **A fórmula completa para decidir qual candle recebe seta não está na página aberta.** Não podemos demonstrar equivalência dos nossos sinais com os sinais proprietários.
- A oferta mostra preço de acesso (na última consulta R$87,99/5 semanas, com renovação manual). O site público não concede acesso gratuito ao indicador original nem fornece sua fonte MQL5/NTSL. Não acessar área de membros protegida ou usar o checkout para obter arquivos sem licença.
- **Atualização REA 09/11/2026:** a instalação local falhou anteriormente por DNS, mas conseguimos executar o **REA 6.8.0 no GitHub Actions** tanto no JavaScript público (exit code 0) quanto na página aberta em Chromium (exit code 0). Foram inspecionados 108 quadros amostrados de seis vídeos públicos, além de decodificados os 43 registros publicitários de 03–04/11. **O código recuperado é apenas o frontend/demonstrador da loja, NÃO o código licenciado que determina os sinais do Tracker.** Ver [relatório completo de evidências](GREENHOUSE_TRACKER_PUBLIC_REA_AUDIT_2026-11-09.md).

## Núcleo matemático dos vetores

Se a máxima do candle de sinal é H, a mínima é L, e R=H-L:

| Linha | Compra | Venda |
|---|---|---|
| 0% | L | H |
| 50% (entrada de referência) | L + 0,5R | H − 0,5R |
| 100% | H | L |
| 200% (alvo) | L + 2R | H − 2R |
| −100% (stop) | L − R | H + R |

**Ao entrar em 50%, a distância até 200% é 1,5R e até −100% também é 1,5R: o payoff BRUTO é exatamente 1:1, não 2:1.**

Exemplo de um candle de 100 pontos no WIN, 1 minicontrato (R$0,20/ponto): ganho bruto R$30 ou perda bruta R$30. Com custo modelado de R$6/roundtrip, ganho líquido +R$24 e perda líquida −R$36, exigindo 60% de acerto só para empatar. Com limite de risco de R$20 por operação para capital R$2.000, esse candle de 100 pontos sequer é elegível.

Exemplo menor de candle com 40 pontos: ganho bruto R$12, perda bruta R$12; com R$6 de custo, resultado +R$6 ou −R$18 e taxa de acerto de equilíbrio 75%. Valores de custo são hipóteses e slippage real pode ser maior.

## Detector independente proposto

Arquivo: `indicators/mt5/NQ_Vector_Exhaustion_Research.mq5`.

- Confirma a seta somente no fechamento do candle (nunca barra `0` em formação), com `OnCalculate` e buffers de setas.
- Mede a máxima/mínima dos 20 candles anteriores completos do mesmo dia do servidor.
- Hipótese para COMPRA: mínima do candle atual varre a mínima anterior em 5 ou mais pontos, fecha novamente acima, tem candle de alta, pavio inferior mínimo de 35% do range e volume real de contratos pelo menos 1,30 vezes a média histórica.
- VENDA: regras espelhadas na máxima anterior, candle de baixa e pavio superior. Estas constantes são **escolhas iniciais de pesquisa**, não parâmetros do Tracker.
- Exige preferencialmente volume real do WIN; se o servidor devolver zero, o programa não cria sinais por default. Usar tick volume em vez de contratos é uma opção explícita diferente, não a leitura institucional original.
- Quando há sinal, desenha 50% (entrada), 200% (alvo), −100% (stop), 0% e 100% (opcionais) como linhas fixas vinculadas à hora do candle.
- Não envia ordens, não acessa conta da Rico e não instala Expert Advisor. Não incorpora lógica de Volume at Price de dados de negócios porque o MT5 OHLC M1 não equivale ao fluxo tick-by-tick do Profit.

## Testes automatizados e replay

- GitHub Actions: https://github.com/lulualcides-sys/nexus-quant-paper/actions/runs/42676030462
- **10 testes passaram:** geometria compra/venda, não repintar na função determinística, dados suficientes, volume, sessões, custo e budget 1 WIN, sinal sem fill, MQL sem métodos de envio de ordens.
- **Limitação essencial:** testes garantem o modelo Python de referência e características estáticas do arquivo MQL5. **Ainda NÃO foi compilado com MetaEditor nem executado dentro de um MT5 real**; isso depende de um terminal Windows com MetaEditor.
- `research/run_vector_exhaustion_winq26.py` executou replay com candles WINQ26 M1 de terceiro (já usados em pesquisas anteriores). Não é out-of-sample cego e não prova resultado do Greenhouse Tracker.

| Período | Custo R$3,40 estimado | Posições encerradas | Sinais detectados | Rejeitados por risco planejado 1% |
|---|---:|---:|---:|---:|
| Abr–mai 2026 | +R$20,90 | 4 | 77 | 61 |
| Junho 2026 | −R$39,60 | 9 | 101 | 88 |
| Julho parcial 2026 | +R$1,30 | 8 | 88 | 78 |

**Nenhuma versão aprovada para real.** O replay registra ambiguidade de toque dentro de M1 e lacunas durante operação como risco não verificável. A leitura do site de 22 alvos e 5 stops no pregão 13/10/2026 é uma alegação comercial de um único pregão, não validação independente de lucratividade líquida.

## Como instalar o nosso protótipo (sem comprar Profit)

1. Instalar e abrir MetaTrader 5 da Rico com acesso a gráficos. A plataforma e o indicador são coisas diferentes.
2. No MetaTrader 5, abrir **Arquivo → Abrir Pasta de Dados**. Entrar em `MQL5/Indicators` e colocar **somente** `NQ_Vector_Exhaustion_Research.mq5` nesta pasta. O código está disponível na branch de pesquisa da PR.
3. Abrir o MetaEditor (tecla F4), localizar o arquivo em Indicadores e compilar (F7). Se MetaEditor apresentar erros, **não afirmar que há `.ex5` funcional**: corrigir e revalidar antes.
4. No gráfico M1 do contrato WIN disponível na sua Rico, aplicar o indicador pelo Navegador → Indicadores. Sinais não são ordens.
5. Ativar volume real somente se a Rico fornecer `volume[]` de contratos; documentar o contrato e o horário do servidor para qualquer replay.

## Próximas verificações necessárias

- Compilar de verdade em MetaEditor 5, conferir desenhos e testar comportamento quando chega um novo candle.
- Comparar uma lista de timestamps confirmados do indicador original — caso haja licença válida ou amostras públicas suficientemente legíveis — com as hipóteses independentes. Não usar porcentagens da publicidade como ground truth.
- Testar fonte tick-by-tick verificável, bid/ask, taxas reais, stops e limites; apenas depois discutir EA em conta demo.

**PR de pesquisa em rascunho; não altera os bots ou a main.**
