@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
set "PYTHON=%ROOT%.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo GAIA requiere el entorno .venv. Ejecuta install-gaia.ps1 -GenerateSecret primero.
  exit /b 1
)
"%PYTHON%" "%ROOT%lumen-pc\gaia_desktop_launcher.py" %*
exit /b %ERRORLEVEL%
