@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Nexus Quant - Analise local WIN Fluxo Profit
echo.
echo NEXUS QUANT - ANALISE INDEPENDENTE DE FLUXO WIN
echo ESTE PROGRAMA NAO ENVIA ORDENS, SENHAS OU DADOS DA CORRETORA.
echo O ARQUIVO DEVE CONTER NEGOCIOS, PRECO, QTD E AGRESSOR EXPLICITO.
echo.

if /I "%~1"=="--self-test" goto setup
if "%~1"=="" (
  echo Arraste um CSV de negocios do Profit/Times e Trades sobre este .CMD.
  echo Se o arquivo nao trouxer os campos obrigatorios, o programa para.
  echo Nao serve CSV apenas com candles OHLCV ou relatorio de operacoes.
  pause
  exit /b 2
)
if not exist "%~1" (
  echo CSV nao localizado: "%~1"
  pause
  exit /b 3
)

:setup
set "PYCMD=py -3.11"
py -3.11 -c "import sys" >nul 2>nul
if errorlevel 1 set "PYCMD=py -3"
%PYCMD% -c "import sys; assert sys.version_info >= (3,11)" >nul 2>nul
if errorlevel 1 (
  echo Requer Python 3.11 ou posterior.
  pause
  exit /b 4
)
if not exist ".mt5_win_venv\Scripts\python.exe" (
  %PYCMD% -m venv ".mt5_win_venv"
  if errorlevel 1 exit /b 5
)
set "PYEXE=%CD%\.mt5_win_venv\Scripts\python.exe"
"%PYEXE%" -c "from zoneinfo import ZoneInfo; ZoneInfo('America/Sao_Paulo')" >nul 2>nul
if errorlevel 1 (
  "%PYEXE%" -m pip install --disable-pip-version-check --no-input tzdata
  if errorlevel 1 exit /b 6
)

if /I "%~1"=="--self-test" (
  "%PYEXE%" -m unittest discover -s tests -p test_win_volume_bars_cvd.py -v
  if errorlevel 1 exit /b 7
  "%PYEXE%" -m unittest discover -s tests -p test_win_profit_timestrades_export.py -v
  exit /b %errorlevel%
)
echo.
echo LENDO APENAS O CSV LOCAL. SEM INSTALAR PROFITDLL OU ACESSAR CONTA.
"%PYEXE%" -m research.win_profit_timestrades_export --csv "%~1" --out "private_mt5\nq_profit_tape_analysis.json"
if errorlevel 1 (
  echo O arquivo foi rejeitado: confira se ha agressor, horario e quantidade.
  echo Nao foram inventados dados nem sinais.
  pause
  exit /b 8
)
echo.
echo Analise salva em private_mt5\nq_profit_tape_analysis.json
echo O resultado e de pesquisa, nao replica certificada do Tracker.
pause
endlocal
