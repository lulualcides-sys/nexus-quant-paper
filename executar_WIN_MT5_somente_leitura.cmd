@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title NEXUS QUANT - WIN M1 - Somente Leitura
echo.
echo NEXUS QUANT - Coleta LOCAL de historico WIN M1 / MetaTrader 5
echo Este arquivo NAO envia ordens e NAO envia dados para o GitHub.
echo.

rem Windows: prefer an installed Python 3.11 compatible with MetaTrader5.
set "PYCMD=py -3.11"
py -3.11 -c "import sys" >nul 2>nul
if errorlevel 1 set "PYCMD=py -3"
%PYCMD% -c "import sys; assert sys.version_info >= (3,9)" >nul 2>nul
if errorlevel 1 (
  echo ERRO: Python 3.9+ nao encontrado.
  echo Instale o Python oficial para Windows: https://www.python.org/downloads/windows/
  echo Nao sera instalado automaticamente pelo ChatGPT.
  pause
  exit /b 2
)

rem Safe offline self-test, no terminal/broker package needed.
if /I "%~1"=="--self-test" (
  %PYCMD% -m unittest discover -s tests -p test_mt5_readonly_collector.py -v
  exit /b %errorlevel%
)

set "CONTRACT=WINZ26"
if not "%~1"=="" set "CONTRACT=%~1"
echo Contrato solicitado: %CONTRACT%
echo.

rem Keep packages isolated from other bots, Python apps and system modules.
set "VENV_DIR=%CD%\.mt5_win_venv"
if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo Criando ambiente Python separado do sistema...
  %PYCMD% -m venv "%VENV_DIR%"
  if errorlevel 1 (
    echo Falhou ao criar ambiente Python local. Nenhuma ordem foi enviada.
    pause
    exit /b 3
  )
)
set "PYEXE=%VENV_DIR%\Scripts\python.exe"
"%PYEXE%" -c "import MetaTrader5" >nul 2>nul
if errorlevel 1 (
  echo Instalando pacote oficial MetaTrader5 do PyPI no ambiente local...
  "%PYEXE%" -m pip install --disable-pip-version-check --no-input MetaTrader5
  if errorlevel 1 (
    echo Falha na instalacao de MetaTrader5. Confira internet e versao de Python.
    echo Nenhuma ordem foi enviada.
    pause
    exit /b 4
  )
)
rem Setup-only mode validates isolated package installation without a terminal connection.
if /I "%~1"=="--setup-only" (
  "%PYEXE%" -c "import MetaTrader5 as mt5; print('MetaTrader5 instalado:', mt5.__version__)"
  exit /b %errorlevel%
)
echo.
echo O MetaTrader 5 deve estar instalado, aberto e conectado no PC.
echo Se o contrato nao estiver na Rico, a coleta sera recusada.
echo Os custos usados no backtest sao HIPOTESES, nao notas da corretora.
echo.

"%PYEXE%" -m research.mt5_readonly_collector --symbol "%CONTRACT%" --days 90 --output-dir private_mt5 --fee-roundtrip 1.40
if errorlevel 1 (
  echo.
  echo Coleta nao concluida. Confirme terminal, codigo WIN e volume real.
  echo Nenhuma ordem foi aberta. Dados nao foram enviados ao GitHub.
  pause
  exit /b 1
)
echo.
echo Pesquisa concluida SEM ordens reais.
echo Arquivos privados salvos em private_mt5, apenas neste computador.
pause
endlocal
