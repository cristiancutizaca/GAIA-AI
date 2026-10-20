@echo off
setlocal
cd /d "%~dp0"
where powershell.exe >nul 2>&1
if errorlevel 1 (
  echo PowerShell no esta disponible. Ejecuta install-gaia.ps1 con PowerShell 5.1 o PowerShell 7.
  exit /b 1
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-gaia.ps1" %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo La instalacion GAIA fallo con codigo %RC%.
)
exit /b %RC%
