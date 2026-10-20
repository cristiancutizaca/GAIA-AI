@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-deepseek-harness.ps1"
exit /b %ERRORLEVEL%
