@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Nexus Quant - Pesquisa Tracker WIN Fluxo MT5
echo.
echo NEXUS QUANT - WINZ26: PESQUISA DE FLUXO M1
echo MODO LEITURA. NAO ENVIA ORDENS, SENHAS NEM DADOS A GITHUB.
echo.

set "PYCMD=py -3.11"
py -3.11 -c "import sys" >nul 2>nul
if errorlevel 1 set "PYCMD=py -3"
%PYCMD% -c "import sys; assert sys.version_info >= (3,9)" >nul 2>nul
if errorlevel 1 (
  echo ERRO: Python 3.9+ nao encontrado. Instale Python 3.11 para Windows.
  echo https://www.python.org/downloads/windows/
  pause
  exit /b 2
)

if not exist ".mt5_win_venv\Scripts\python.exe" (
  echo Criando Python isolado para nao afetar os outros robos...
  %PYCMD% -m venv ".mt5_win_venv"
  if errorlevel 1 (
    echo Falha ao criar ambiente Python. Nenhuma ordem executada.
    pause
    exit /b 3
  )
)

set "PYEXE=%CD%\.mt5_win_venv\Scripts\python.exe"
"%PYEXE%" -c "import MetaTrader5" >nul 2>nul
if errorlevel 1 (
  echo Instalando pacote oficial MetaTrader5 para leitura de ticks...
  "%PYEXE%" -m pip install --disable-pip-version-check --no-input MetaTrader5 tzdata
  if errorlevel 1 (
    echo Pacote nao disponivel. Confira rede e compatibilidade Python.
    pause
    exit /b 4
  )
)

"%PYEXE%" -c "from zoneinfo import ZoneInfo; ZoneInfo('America/Sao_Paulo')" >nul 2>nul
if errorlevel 1 (
  echo Instalando base de fusos horarios tzdata para America/Sao_Paulo...
  "%PYEXE%" -m pip install --disable-pip-version-check --no-input tzdata
  if errorlevel 1 (
    echo Nao foi possivel validar os horarios UTC/Sao Paulo. Interrompendo.
    pause
    exit /b 7
  )
)

if /I "%~1"=="--self-test" (
  "%PYEXE%" -m unittest discover -s tests -p test_win_mt5_tick_provenance.py -v
  if errorlevel 1 exit /b 1
  "%PYEXE%" -m unittest discover -s tests -p test_win_flow_public_label_comparison.py -v
  exit /b %errorlevel%
)

if /I "%~1"=="--setup-only" (
  "%PYEXE%" -c "import MetaTrader5 as mt5; print('Pacote MT5 OK',mt5.__version__)"
  exit /b %errorlevel%
)

echo.
echo REQUISITO: MetaTrader 5 da Rico instalado, aberto e conectado ao historico.
echo Coleta estritamente dos dias 03 e 04/11/2026 do contrato WINZ26.
echo Se nao houver volume/agressao REAL, o sistema indicara essa limitacao.
echo Nada sera publicado automaticamente.
echo.

"%PYEXE%" -m research.win_mt5_tick_provenance --symbol WINZ26 --date 2026-11-03 --date 2026-11-04 --private-dir private_mt5
if errorlevel 1 (
  echo.
  echo DADOS INDISPONIVEIS OU INVALIDOS. Nao ha resultado de indicador inventado.
  echo Verifique WINZ26, a quantidade de historico M1/ticks e a conexao Rico.
  pause
  exit /b 5
)

echo.
echo Comparando somente com as etiquetas PUBLICAS da pagina oficial...
"%PYEXE%" -m research.win_flow_public_label_comparison --input private_mt5\WINZ26_2026-11-03_flow_audit.json --input private_mt5\WINZ26_2026-11-04_flow_audit.json --fetch-public-html --out private_mt5\nq_public_labels_comparison.json
if errorlevel 1 (
  echo Historico local foi salvo mas a comparacao publica nao foi concluida.
  echo Nenhum dado local foi enviado para Greenhouse ou GitHub.
  pause
  exit /b 6
)
echo.
echo Auditoria local concluida. Leia private_mt5\nq_public_labels_comparison.json
echo RESULTADO DE PESQUISA - NAO REPLICA ORIGINAL, NAO AUTORIZADO OPERAR.
pause
endlocal
