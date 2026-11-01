[CmdletBinding()]
param(
    [switch]$SkipOllama,
    [switch]$SkipModels,
    [switch]$SkipBrowserRuntime
)
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $MyInvocation.MyCommand.Path
$install=Join-Path $Root 'install-gaia.ps1'
if (-not (Test-Path $install)) { throw 'Falta install-gaia.ps1' }
$args=@('-NoProfile','-ExecutionPolicy','Bypass','-File',$install,'-Profile','full-computer','-GenerateSecret','-SkipPipUpgrade')
if (-not $SkipOllama) { $args += '-InstallOllama' }
if (-not $SkipModels) { $args += '-InstallModels' }
if ($SkipBrowserRuntime) { $args += '-SkipBrowserRuntime' }
Write-Host 'GAIA Setup: Core/Desktop/Voice (Python 3.11) + Browser/Mem0 sidecars (3.11) + OpenHands sidecar (3.12)' -ForegroundColor Cyan
Write-Host 'No se descargan modelos LLM grandes automáticamente.' -ForegroundColor Yellow
& powershell.exe @args
exit $LASTEXITCODE
