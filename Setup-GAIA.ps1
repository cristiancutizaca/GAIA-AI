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
$installerArguments=@('-NoProfile','-ExecutionPolicy','Bypass','-File',$install,'-Profile','full-computer','-GenerateSecret','-SkipPipUpgrade')
if (-not $SkipOllama) { $installerArguments += '-InstallOllama' }
if (-not $SkipModels) { $installerArguments += '-InstallModels' }
if ($SkipBrowserRuntime) { $installerArguments += '-SkipBrowserRuntime' }
Write-Host 'GAIA Setup: Core/Desktop/Voice (Python 3.11) + Browser/Mem0 sidecars (3.11) + OpenHands sidecar (3.12)' -ForegroundColor Cyan
Write-Host 'No se descargan modelos LLM grandes automáticamente.' -ForegroundColor Yellow
& powershell.exe @installerArguments
exit $LASTEXITCODE
