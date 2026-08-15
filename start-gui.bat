@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0.venv\Scripts\python.exe" (
  set "PYTHON=%~dp0.venv\Scripts\python.exe"
) else (
  set "PYTHON=python"
)
cd /d "%~dp0lumen-pc"
"%PYTHON%" gui.py %*
pause
