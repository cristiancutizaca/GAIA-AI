[CmdletBinding()]
param(
    [switch]$Preflight,
    [switch]$InstallDependencies,
    [switch]$ConfirmInstall,
    [switch]$RecreateVenv,
    [int]$TestTimeout = 120,
    [switch]$RunAutomated,
    [switch]$RunBenchmark,
    [switch]$PreparePhysicalValidation,
    [switch]$CleanExtraction,
    [switch]$All,
    [string]$OutputDirectory,
    [string]$Archive
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-ExternalDirectory {
    param([Parameter(Mandatory = $true)][string]$Path)
    $candidate = [System.IO.Path]::GetFullPath($Path)
    $root = [System.IO.Path]::GetFullPath($PSScriptRoot)
    $relative = [System.IO.Path]::GetRelativePath($root, $candidate)
    if ($relative -eq "." -or (-not $relative.StartsWith(".."))) {
        throw "La evidencia debe estar fuera del árbol RC6: $candidate"
    }
    [System.IO.Directory]::CreateDirectory($candidate) | Out-Null
    return $candidate
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )
    Write-Host ("Ejecutando: {0} {1}" -f $FilePath, ($Arguments -join " "))
    & $FilePath @Arguments
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        throw "El comando terminó con código $code"
    }
}

$defaultOutput = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\GAIA-AI-v1.0-RC6-validation"))
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = $defaultOutput
}
$output = Resolve-ExternalDirectory -Path $OutputDirectory
$python = ""
try {
    $python = (& py -3.11 -c "import sys; print(sys.executable)").Trim()
} catch {
    throw "Python 3.11 no está disponible; no se instala globalmente"
}
if ([string]::IsNullOrWhiteSpace($python) -or -not (Test-Path -LiteralPath $python)) {
    throw "No se pudo resolver un ejecutable Python 3.11"
}

$mode = New-Object System.Collections.Generic.List[string]
if ($All) { [void]$mode.Add("--all") }
if ($Preflight) { [void]$mode.Add("--preflight") }
if ($RunAutomated) { [void]$mode.Add("--tests") }
if ($RunBenchmark) { [void]$mode.Add("--benchmark") }
if ($PreparePhysicalValidation) { [void]$mode.Add("--physical-template") }
if ($CleanExtraction) { [void]$mode.Add("--clean-extraction") }
if ($InstallDependencies) {
    if (-not $ConfirmInstall) {
        $answer = Read-Host "Esto creará un .venv externo e instalará requirements. Escriba INSTALL para confirmar"
        if ($answer -cne "INSTALL") {
            throw "Instalación cancelada; no se modificó el sistema"
        }
    } else {
        Write-Host "Instalación no interactiva autorizada explícitamente por -ConfirmInstall" -ForegroundColor Yellow
    }
    [void]$mode.Add("--install-dependencies")
    [void]$mode.Add("--confirm-install")
}
if ($mode.Count -eq 0) { [void]$mode.Add("--preflight") }
if ($mode -contains "--clean-extraction") {
    if ([string]::IsNullOrWhiteSpace($Archive)) {
        throw "-Archive es obligatorio con -CleanExtraction"
    }
    $archivePath = [System.IO.Path]::GetFullPath($Archive)
    if (-not (Test-Path -LiteralPath $archivePath -PathType Leaf)) {
        throw "El archivo RC6 indicado no existe"
    }
    if ([System.IO.Path]::GetFileName($archivePath) -notmatch '^GAIA-AI-v1\.0-RC6.*\.zip$') {
        throw "El archive no tiene nombre de candidate RC6"
    }
}

$arguments = New-Object System.Collections.Generic.List[string]
foreach ($item in $mode) { [void]$arguments.Add($item) }
if ($RecreateVenv) { [void]$arguments.Add("--recreate-venv") }
[void]$arguments.Add("--test-timeout")
[void]$arguments.Add([string]$TestTimeout)
[void]$arguments.Add("--output-dir")
[void]$arguments.Add($output)
$runnerPath = Join-Path $PSScriptRoot "tools/validate_rc6.py"
if (-not (Test-Path -LiteralPath $runnerPath -PathType Leaf)) {
    throw "No se encontró el runner RC6: $runnerPath"
}
[void]$arguments.Insert(0, $runnerPath)
if (-not [string]::IsNullOrWhiteSpace($Archive)) {
    $archivePath = [System.IO.Path]::GetFullPath($Archive)
    [void]$arguments.Add("--archive")
    [void]$arguments.Add($archivePath)
}
[void]$arguments.Add("--json-out")
[void]$arguments.Add((Join-Path $output "validation.json"))
[void]$arguments.Add("--markdown-out")
[void]$arguments.Add((Join-Path $output "validation.md"))

Invoke-Checked -FilePath $python -Arguments ([string[]]$arguments)
exit 0
