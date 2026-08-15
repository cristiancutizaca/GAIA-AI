@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0.venv\Scripts\python.exe" (
  set "PYTHON=%~dp0.venv\Scripts\python.exe"
) else (
  set "PYTHON=python"
)
echo.
echo   Iniciando LUMEN Core...
echo   Configuracion: .env en %CD%
echo.
cd /d "%~dp0lumen-core"
"%PYTHON%" main.py
pause
