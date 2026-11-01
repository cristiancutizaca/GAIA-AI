[CmdletBinding()]
param(
    [switch]$GenerateSecret,
    [switch]$SkipPipUpgrade,
    [switch]$NoDoctor,
    [switch]$PlanMigration,
    [switch]$CreateMigrationSnapshot,
    [switch]$ApplyMigration,
    [switch]$ApproveMigration,
    [switch]$SafeMode,
    [switch]$Rollback,
    [switch]$InstallOllama,
    [switch]$InstallModels,
    [switch]$SkipBrowserRuntime,
    [ValidateSet('minimal','standard','desktop','voice','browser','coding','computer','memory','full','full-computer','development','all')][string]$Profile = 'desktop',
    [string]$MigrationSourceRoot,
    [string]$MigrationSnapshotDir,
    [string]$MigrationTargetRoot,
    [string]$RollbackSnapshotDir,
    [string]$RollbackTargetRoot,
    [ValidateSet('CLONE_TO_TARGET','REUSE_EXISTING_EXTERNAL_VAULT','CLONE_TO_NEW_VAULT','KEEP_TARGET_CONFIG')][string]$DbStrategy = 'CLONE_TO_TARGET',
    [string]$NewVaultPath,
    [ValidateSet('ROLLBACK_DATABASE_ONLY','ROLLBACK_DATABASE_AND_CONFIG','ROLLBACK_TO_PREVIOUS_INSTALLATION')][string]$RollbackMode = 'ROLLBACK_DATABASE_ONLY'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Venv = Join-Path $Root '.venv'
$VenvPython = Join-Path $Venv 'Scripts\python.exe'

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $false)][string[]]$Arguments = @(),
        [Parameter(Mandatory = $true)][string]$Description
    )
    Write-Host "==> $Description" -ForegroundColor Cyan
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Description falló con código $LASTEXITCODE."
    }
}

function Get-Python311 {
    $py = Get-Command 'py' -ErrorAction SilentlyContinue
    if ($null -ne $py) {
        try {
            & $py.Source '-3.11' '-c' 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)'
            if ($LASTEXITCODE -eq 0) { return @($py.Source, '-3.11') }
        } catch { }
    }
    $python = Get-Command 'python' -ErrorAction SilentlyContinue
    if ($null -ne $python) {
        try {
            & $python.Source '-c' 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)'
            if ($LASTEXITCODE -eq 0) { return @($python.Source) }
        } catch { }
    }
    throw 'No se encontró Python 3.11. Instala Python 3.11 para Windows y vuelve a ejecutar este script.'
}

function Get-Python312 {
    $py = Get-Command 'py' -ErrorAction SilentlyContinue
    if ($null -ne $py) {
        try {
            & $py.Source '-3.12' '-c' 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)'
            if ($LASTEXITCODE -eq 0) { return @($py.Source, '-3.12') }
        } catch { }
    }
    $winget = Get-Command 'winget' -ErrorAction SilentlyContinue
    if ($null -ne $winget) {
        Write-Host 'Python 3.12 no está instalado; instalándolo solo para el sidecar OpenHands...' -ForegroundColor Yellow
        & $winget.Source install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -eq 0) {
            $py = Get-Command 'py' -ErrorAction SilentlyContinue
            if ($null -ne $py) {
                & $py.Source '-3.12' '-c' 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)'
                if ($LASTEXITCODE -eq 0) { return @($py.Source, '-3.12') }
            }
        }
    }
    throw 'OpenHands requiere Python 3.12. No se pudo encontrar ni instalar Python 3.12.'
}

function Install-Sidecar {
    param(
        [Parameter(Mandatory=$true)][string]$Name,
        [Parameter(Mandatory=$true)][string]$PythonExe,
        [string[]]$PythonArgs=@(),
        [Parameter(Mandatory=$true)][string]$VenvPath,
        [Parameter(Mandatory=$true)][string]$RequirementsFile
    )
    $sidePython = Join-Path $VenvPath 'Scripts\python.exe'
    if (-not (Test-Path $sidePython)) {
        Invoke-Checked -FilePath $PythonExe -Arguments ($PythonArgs + @('-m','venv',$VenvPath)) -Description "Crear sidecar $Name"
    }
    Invoke-Checked -FilePath $sidePython -Arguments @('-m','pip','install','setuptools>=69','wheel') -Description "Preparar herramientas del sidecar $Name"
    Invoke-Checked -FilePath $sidePython -Arguments @('-m','pip','install','-r',(Join-Path $Root $RequirementsFile)) -Description "Instalar dependencias sidecar $Name"
    Invoke-Checked -FilePath $sidePython -Arguments @('-m','pip','check') -Description "Verificar dependencias sidecar $Name"
}

function New-StrongSecret {
    $bytes = New-Object byte[] 48
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return [Convert]::ToBase64String($bytes).Replace('+', '-').Replace('/', '_').TrimEnd('=')
}

function Ensure-EnvFile {
    $envPath = Join-Path $Root '.env'
    $examplePath = Join-Path $Root '.env.example'
    if (Test-Path $envPath) {
        $existing = Get-Content -Raw -LiteralPath $envPath
        if ($existing -match '(?m)^LUMEN_SECRET=(.+)$' -and $Matches[1].Trim().Length -ge 24 -and $Matches[1].Trim() -ne 'cambia-este-token-por-uno-largo-y-privado') {
            Write-Host '==> .env existente con secreto de longitud razonable; no se sobrescribe.' -ForegroundColor Green
            return
        }
        if (-not $GenerateSecret) {
            throw '.env existe, pero LUMEN_SECRET está ausente, es débil o es el placeholder. Usa -GenerateSecret o corrígelo manualmente; no se sobrescribe silenciosamente.'
        }
        $content = $existing
    } else {
        if (-not (Test-Path $examplePath)) { throw 'Falta .env.example.' }
        $content = Get-Content -Raw -LiteralPath $examplePath
    }

    if ($GenerateSecret) {
        $secret = New-StrongSecret
    } else {
        $secret = Read-Host 'Escribe un LUMEN_SECRET de al menos 24 caracteres (no se mostrará en logs)'
        if ([string]::IsNullOrWhiteSpace($secret) -or $secret.Length -lt 24) {
            throw 'LUMEN_SECRET vacío o demasiado corto. Repite con un secreto largo o usa -GenerateSecret.'
        }
    }
    if ($content -match '(?m)^LUMEN_SECRET=.*$') {
        $content = [regex]::Replace($content, '(?m)^LUMEN_SECRET=.*$', "LUMEN_SECRET=$secret")
    } else {
        $content = "LUMEN_SECRET=$secret`r`n$content"
    }
    [System.IO.File]::WriteAllText($envPath, $content, [System.Text.UTF8Encoding]::new($false))
    Write-Host "==> .env preparado con un secreto fuerte; el valor no se imprime." -ForegroundColor Green
}

function Invoke-MigrationTool {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$Description
    )
    if (-not (Test-Path (Join-Path $Root 'tools\\gaia_migrate.py'))) { throw 'Falta tools\\gaia_migrate.py en la release.' }
    Invoke-Checked -FilePath $pythonExe -Arguments ($pythonArgs + @('tools\\gaia_migrate.py') + $Arguments) -Description $Description
}

Push-Location $Root
try {
    $pythonSpec = Get-Python311
    $pythonExe = $pythonSpec[0]
    $pythonArgs = @()
    if ($pythonSpec.Count -gt 1) { $pythonArgs = @($pythonSpec[1]) }
    Write-Host "Python launcher: $pythonExe $($pythonArgs -join ' ')" -ForegroundColor Green

    if (-not (Test-Path $VenvPython)) {
        Invoke-Checked -FilePath $pythonExe -Arguments ($pythonArgs + @('-m', 'venv', $Venv)) -Description 'Crear entorno virtual .venv'
    }
    if (-not (Test-Path $VenvPython)) { throw "No se creó $VenvPython." }

    if (-not $SkipPipUpgrade) {
        Invoke-Checked -FilePath $VenvPython -Arguments @('-m', 'pip', 'install', '--upgrade', 'pip<25', 'setuptools<70', 'wheel') -Description 'Actualizar herramientas base del entorno virtual'
    }

    Invoke-Checked -FilePath $VenvPython -Arguments @('-m', 'pip', 'install', '--no-build-isolation', '-r', (Join-Path $Root 'lumen-core\requirements.txt')) -Description 'Instalar dependencias del Core'
    # Browser Use, Mem0 and OpenHands are deliberately isolated in sidecars.

    if ($Profile -ne 'minimal') {
        Invoke-Checked -FilePath $VenvPython -Arguments @('-m', 'pip', 'install', '--no-build-isolation', '-r', (Join-Path $Root 'lumen-pc\requirements.txt')) -Description 'Instalar dependencias PC'
        Invoke-Checked -FilePath $VenvPython -Arguments @('-m', 'pip', 'install', '--no-build-isolation', '-r', (Join-Path $Root 'lumen-pc\requirements-windows.txt')) -Description 'Instalar dependencias Windows, audio y adapters'
    }
    $requirementsJson = & $VenvPython 'tools\gaia_dependencies.py' 'requirements' '--profile' $Profile
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo resolver el perfil desde gaia_dependencies.toml.' }
    $profileRequirements = @($requirementsJson | ConvertFrom-Json)
    foreach ($optionalFile in ($profileRequirements | Select-Object -Unique)) {
        if ([string]::IsNullOrWhiteSpace([string]$optionalFile)) { continue }
        Invoke-Checked -FilePath $VenvPython -Arguments @('-m','pip','install','--no-build-isolation','-r',(Join-Path $Root ([string]$optionalFile))) -Description "Instalar perfil ${Profile}: $optionalFile"
    }
    # Install conflicting providers in isolated interpreters.
    $sidecarsJson = & $VenvPython 'tools\gaia_dependencies.py' 'sidecars' '--profile' $Profile
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo resolver los sidecars desde gaia_dependencies.toml.' }
    $parsedSidecars = $sidecarsJson | ConvertFrom-Json
    $sidecars = @()
    foreach ($sidecar in $parsedSidecars) {
        $sidecars += [string]$sidecar
    }
    if ($sidecars -contains 'browser') {
        Install-Sidecar -Name 'Browser Use (Python 3.11)' -PythonExe $pythonExe -PythonArgs $pythonArgs -VenvPath (Join-Path $Root '.venv-browser') -RequirementsFile 'requirements-browser.txt'
    }
    if ($sidecars -contains 'memory') {
        Install-Sidecar -Name 'Mem0 (Python 3.11)' -PythonExe $pythonExe -PythonArgs $pythonArgs -VenvPath (Join-Path $Root '.venv-memory') -RequirementsFile 'requirements-memory.txt'
    }
    if ($sidecars -contains 'coding') {
        $py312 = Get-Python312
        $py312Exe = $py312[0]; $py312Args = @(); if ($py312.Count -gt 1) { $py312Args = @($py312[1..($py312.Count-1)]) }
        Install-Sidecar -Name 'OpenHands (Python 3.12)' -PythonExe $py312Exe -PythonArgs $py312Args -VenvPath (Join-Path $Root '.venv-coding') -RequirementsFile 'requirements-coding.txt'
    }
    Invoke-Checked -FilePath $VenvPython -Arguments @('-m','pip','check') -Description 'Verificar dependencias del entorno principal'
    $browserProfiles = @('browser','full','full-computer','development','all')
    if (($browserProfiles -contains $Profile) -and -not $SkipBrowserRuntime) {
        $browserPython = Join-Path $Root '.venv-browser\Scripts\python.exe'
        if (-not (Test-Path $browserPython)) { throw 'Falta .venv-browser después de instalar el sidecar Browser Use.' }
        Invoke-Checked -FilePath $browserPython -Arguments @('-m','playwright','install','chromium') -Description 'Instalar Chromium dentro del sidecar Browser Use'
    }
    if ($InstallOllama -and -not (Get-Command 'ollama' -ErrorAction SilentlyContinue)) {
        $winget = Get-Command 'winget' -ErrorAction SilentlyContinue
        if ($null -eq $winget) { throw 'Se solicitó -InstallOllama pero winget no está disponible.' }
        Invoke-Checked -FilePath $winget.Source -Arguments @('install','--id','Ollama.Ollama','-e','--accept-package-agreements','--accept-source-agreements') -Description 'Instalar Ollama'
    }
    $voiceProfiles = @('voice','full','full-computer','development','all')
    if ($InstallModels -and ($voiceProfiles -contains $Profile)) {
        Invoke-Checked -FilePath $VenvPython -Arguments @('tools\gaia_models.py','install','baseline') -Description 'Descargar/verificar modelos base de voz (faster-whisper + Piper)'
    }
    Invoke-Checked -FilePath 'powershell.exe' -Arguments @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $Root 'install-deepseek-harness.ps1')) -Description 'Instalar DeepSeek-Harness fijado para GAIA'

    if (-not $ApplyMigration) { Ensure-EnvFile }

    if ($PlanMigration) {
        if ([string]::IsNullOrWhiteSpace($MigrationSourceRoot)) { throw '-PlanMigration requiere -MigrationSourceRoot.' }
        $planArgs = @('--root', $MigrationSourceRoot, '--target-version', '2.0.0', '--json', '--safe-mode')
        if ($CreateMigrationSnapshot -and [string]::IsNullOrWhiteSpace($MigrationSnapshotDir)) { throw '-CreateMigrationSnapshot requiere -MigrationSnapshotDir.' }
        if (-not [string]::IsNullOrWhiteSpace($MigrationSnapshotDir)) { $planArgs += @('--snapshot-dir', $MigrationSnapshotDir) }
        if ($CreateMigrationSnapshot) { $planArgs += '--snapshot' }
        Invoke-MigrationTool -Arguments $planArgs -Description 'Inspeccionar instalación y preparar migración GAIA 2.0'
    }

    if ($ApplyMigration) {
        if ([string]::IsNullOrWhiteSpace($MigrationSourceRoot) -or [string]::IsNullOrWhiteSpace($MigrationSnapshotDir)) { throw '-ApplyMigration requiere -MigrationSourceRoot y -MigrationSnapshotDir.' }
        if (-not $ApproveMigration) { throw '-ApplyMigration requiere -ApproveMigration explícito.' }
        $applyArgs = @('--root', $MigrationSourceRoot, '--target-root', $Root, '--snapshot-dir', $MigrationSnapshotDir, '--target-version', '2.0.0', '--db-strategy', $DbStrategy, '--apply', '--approve', '--json')
        if (-not [string]::IsNullOrWhiteSpace($NewVaultPath)) { $applyArgs += @('--new-vault', $NewVaultPath) }
        if ($SafeMode) { $applyArgs += '--safe-mode' }
        Invoke-MigrationTool -Arguments $applyArgs -Description 'Aplicar migración durable GAIA 2.0 con estrategia explícita y aprobación'
        if (-not (Test-Path (Join-Path $Root '.env')) -and $DbStrategy -eq 'KEEP_TARGET_CONFIG') { Ensure-EnvFile }
    }

    if ($Rollback) {
        if ([string]::IsNullOrWhiteSpace($RollbackSnapshotDir)) { throw '-Rollback requiere -RollbackSnapshotDir.' }
        if (-not $ApproveMigration) { throw '-Rollback requiere -ApproveMigration explícito.' }
        $rollbackRoot = if ([string]::IsNullOrWhiteSpace($RollbackTargetRoot)) { $Root } else { $RollbackTargetRoot }
        $rollbackArgs = @('--root', $rollbackRoot, '--snapshot-dir', $RollbackSnapshotDir, '--rollback', '--approve', '--rollback-mode', $RollbackMode, '--safe-mode', '--json')
        Invoke-MigrationTool -Arguments $rollbackArgs -Description 'Restaurar snapshot GAIA 2.0 con modo explícito y aprobación'
    }

    Invoke-Checked -FilePath $VenvPython -Arguments @('tools\gaia_setup.py','--apply') -Description 'Activar de forma fail-closed las capacidades locales disponibles'
    Invoke-Checked -FilePath $VenvPython -Arguments @('tools\gaia_dependencies.py','status','--profile',$Profile,'--strict-python') -Description 'Verificar dependencias declaradas para el perfil'

    if (-not $NoDoctor) {
        $previousSafeMode = $env:GAIA_SAFE_MODE
        if ($SafeMode) { $env:GAIA_SAFE_MODE = 'true' }
        Invoke-Checked -FilePath $VenvPython -Arguments @('tools\gaia_doctor_v2.py') -Description 'Ejecutar GAIA Doctor 2.0 read-only'
        if ($null -eq $previousSafeMode) { Remove-Item Env:GAIA_SAFE_MODE -ErrorAction SilentlyContinue } else { $env:GAIA_SAFE_MODE = $previousSafeMode }
    }
    Write-Host ''
    Write-Host "Instalación GAIA completada. Perfil: $Profile" -ForegroundColor Green
    Write-Host "Activa el entorno con: .\.venv\Scripts\Activate.ps1"
    Write-Host 'Revisa .env. Para voz: tools\gaia_models.py status. Los LLM grandes no se descargan sin consentimiento.'
} finally {
    Pop-Location
}

