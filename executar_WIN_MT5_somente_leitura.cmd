@echo off
setlocal
cd /d "%~dp0"
title NEXUS WIN - Coleta MT5 somente leitura
echo.
echo NEXUS QUANT - WIN M1 / MetaTrader 5
echo Este processo NAO envia ordens, NAO acessa senhas e NAO publica dados.
echo Mantenha o terminal MT5 instalado, aberto e com historico acessivel.
echo.
set "CONTRACT=WINZ26"
if not "%~1"=="" set "CONTRACT=%~1"
where py >nul 2>nul
if errorlevel 1 (
  echo ERRO: Python 3 nao encontrado. Instale Python 3 para Windows.
  echo https://www.python.org/downloads/windows/
  pause
  exit /b 2
)
py -3 -c "import MetaTrader5" >nul 2>nul
if errorlevel 1 (
  echo ERRO: Pacote oficial MetaTrader5 para Python nao encontrado.
  echo Para instalar sem tarifa de plataforma, execute:
  echo py -3 -m pip install MetaTrader5
  echo.
  echo Nao instalamos software automaticamente no seu Windows.
  pause
  exit /b 3
)
echo Contrato: %CONTRACT%
echo Periodo solicitado: ultimos 90 dias, somente candles fechados.
echo Relatorios privados: private_mt5
echo.
py -3 -m research.mt5_readonly_collector --symbol "%CONTRACT%" --days 90 --output-dir private_mt5 --fee-roundtrip 1.40
if errorlevel 1 (
  echo.
  echo A COLETA FALHOU OU FOI RECUSADA POR DADOS INCONSISTENTES.
  echo Confira simbolo, historico e conexao do MT5. Nenhuma ordem foi aberta.
  pause
  exit /b 1
)
echo.
echo Pesquisa finalizada SOMENTE COM DADOS HISTORICOS.
echo Nada foi enviado para a Rico ou para GitHub.
echo A pasta private_mt5 permanece APENAS neste computador.
pause
endlocal
