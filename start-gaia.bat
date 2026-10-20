@echo off
setlocal EnableExtensions EnableDelayedExpansion
set "ROOT=%~dp0"
if exist "%ROOT%.venv\Scripts\python.exe" (
  set "PYTHON=%ROOT%.venv\Scripts\python.exe"
) else (
  set "PYTHON=python"
)
set "PORT=%LUMEN_PORT%"
if not defined PORT set "PORT=8090"
set "HOST=%LUMEN_HOST%"
if not defined HOST set "HOST=127.0.0.1"
if not defined GAIA_REMOTE_HOST_ENABLED set "GAIA_REMOTE_HOST_ENABLED=true"
if exist "%ROOT%.env" (
  for /f "tokens=1,* delims==" %%A in ('findstr /b "LUMEN_PORT=" "%ROOT%.env"') do set "PORT=%%B"
  for /f "tokens=1,* delims==" %%A in ('findstr /b "LUMEN_HOST=" "%ROOT%.env"') do set "HOST=%%B"
)
"%PYTHON%" "%ROOT%tools\gaia_startup_probe.py" --host 127.0.0.1 --port "%PORT%"
set "CODE=%ERRORLEVEL%"
if "%CODE%"=="0" (
  echo GAIA Core ya esta activo. Abriendo GUI.
  if /i "%GAIA_REMOTE_HOST_ENABLED%"=="true" start "GAIA Action Host" /b "%PYTHON%" "%ROOT%tools\run_remote_action_host.py" >> "%ROOT%lumen-core\data\logs\start-gaia-host.log" 2>&1
  "%PYTHON%" "%ROOT%lumen-pc\gui.py" --url "http://%HOST%:%PORT%"
  exit /b %ERRORLEVEL%
)
if "%CODE%"=="2" (
  echo GAIA: el puerto %PORT% esta ocupado por otra aplicacion. No iniciare una segunda instancia ni matare el proceso.
  exit /b 2
)
if not exist "%ROOT%lumen-core\data\logs" mkdir "%ROOT%lumen-core\data\logs"
start "GAIA Core" /b "%PYTHON%" "%ROOT%lumen-core\main.py" >> "%ROOT%lumen-core\data\logs\start-gaia-core.log" 2>&1
echo GAIA Core iniciado; esperando /api/health durante 30 segundos.
for /l %%N in (1,1,30) do (
  "%PYTHON%" "%ROOT%tools\gaia_startup_probe.py" --host 127.0.0.1 --port "%PORT%" > "%TEMP%\gaia_startup_probe.out" 2>&1
  set "CODE=!ERRORLEVEL!"
  if "!CODE!"=="0" (
    type "%TEMP%\gaia_startup_probe.out"
    if /i "%GAIA_REMOTE_HOST_ENABLED%"=="true" start "GAIA Action Host" /b "%PYTHON%" "%ROOT%tools\run_remote_action_host.py" >> "%ROOT%lumen-core\data\logs\start-gaia-host.log" 2>&1
    "%PYTHON%" "%ROOT%lumen-pc\gui.py" --url "http://%HOST%:%PORT%"
    exit /b !ERRORLEVEL!
  )
  if "!CODE!"=="2" (
    type "%TEMP%\gaia_startup_probe.out"
    echo GAIA: el puerto cambio a una aplicacion ajena; revisa el log.
    exit /b 2
  )
  timeout /t 1 /nobreak >nul
)
echo GAIA Core no respondio en 30 segundos. Revisa %ROOT%lumen-core\data\logs\start-gaia-core.log. No se detiene automaticamente el proceso iniciado.
exit /b 1
