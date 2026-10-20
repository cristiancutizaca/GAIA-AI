[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'
if (Test-Path $VenvPython) {
    $Python = $VenvPython
    $Prefix = @()
} else {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $pythonCmd) {
        $Python = $pythonCmd.Source
        $Prefix = @()
    } else {
        $pyCmd = Get-Command py -ErrorAction SilentlyContinue
        if ($null -eq $pyCmd) { throw 'Se necesita Python 3.10+ (recomendado 3.11).' }
        $Python = $pyCmd.Source
        $Prefix = @('-3.11')
    }
}
& $Python @Prefix -m pip install --disable-pip-version-check 'deepseek-harness-sdk==0.1.5rc1'
if ($LASTEXITCODE -ne 0) { throw "pip install de DeepSeek-Harness falló con código $LASTEXITCODE" }
& $Python @Prefix -c "from importlib import metadata; from deepseek_harness import DeepSeekHarness; print('DeepSeek-Harness SDK instalado: ' + metadata.version('deepseek-harness-sdk'))"
if ($LASTEXITCODE -ne 0) { throw 'DeepSeek-Harness SDK se instaló pero no pudo importarse.' }
Write-Host 'DeepSeek-Harness listo para GAIA (runtime oficial incluido en el wheel).' -ForegroundColor Green
