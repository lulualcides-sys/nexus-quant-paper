@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Nexus Quant - Analise de fita Profit CSV (somente leitura)
echo.
echo NEXUS QUANT / WIN - ANALISE DE FITA HISTORICA PROFIT/NELOGICA
echo NUNCA EXECUTA ORDENS. CSV LICENCIADO PERMANECE NESTE COMPUTADOR.
echo.
if /I "%~1"=="--self-test" goto selftest
if "%~1"=="" (
  echo Arraste um CSV tick-by-tick legitimamente exportado pela Nelogica
  echo para cima deste arquivo CMD, ou passe o caminho como argumento.
  echo Ex.: iniciar_pesquisa_WIN_csv_licenciado.cmd "C:\dados\WINZ26_03NOV.csv"
  echo.
  echo Nao substitui conta, licença da Nelogica, nem o indicador Tracker original.
  pause
  exit /b 2
)
if not exist "%~1" (
  echo ERRO: CSV nao encontrado: "%~1"
  pause
  exit /b 3
)
goto setup

:selftest
set "NQ_TEST_ONLY=1"
:setup
set "PYCMD=py -3.11"
py -3.11 -c "import sys" >nul 2>nul
if errorlevel 1 set "PYCMD=py -3"
%PYCMD% -c "import sys; assert sys.version_info >= (3,9)" >nul 2>nul
if errorlevel 1 (
  echo ERRO: Python 3.9+ nao encontrado.
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
  echo Instalando apenas a base de horarios tzdata...
  "%PYEXE%" -m pip install --disable-pip-version-check --no-input tzdata
  if errorlevel 1 exit /b 6
)
if defined NQ_TEST_ONLY (
  "%PYEXE%" -m unittest discover -s tests -p test_win_licensed_tape_csv.py -v
  exit /b %errorlevel%
)
if not exist private_mt5 mkdir private_mt5
echo.
echo Verificando contrato, tempo, IDs e tamanho de cada negocio...
echo Agressores: 2 compra, 3 venda; desconhecidos nao serao estimados.
"%PYEXE%" -m research.win_licensed_tape_csv --csv "%~1" --output "private_mt5\nq_licensed_tape_research.json"
if errorlevel 1 (
  echo Falha de verificacao. Nenhum resultado foi inventado.
  pause
  exit /b 7
)
echo.
echo Arquivo local: private_mt5\nq_licensed_tape_research.json
echo Dados originais nunca foram enviados para terceiros.
echo Indicador original e lucratividade nao foram validados por esta importacao.
pause
endlocal
