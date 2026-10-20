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
    [ValidateSet('minimal','standard','full','voice','browser','coding','computer','memory','all')][string]$Profile = 'standard',
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
        Invoke-Checked -FilePath $VenvPython -Arguments @('-m', 'pip', 'install', '--upgrade', 'pip<25', 'setuptools<70', 'wheel') -Description 'Actualizar herramientas compatibles con Whisper'
    }

    Invoke-Checked -FilePath $VenvPython -Arguments @('-m', 'pip', 'install', '--no-build-isolation', '-r', (Join-Path $Root 'lumen-core\requirements.txt')) -Description 'Instalar dependencias del Core'
    Invoke-Checked -FilePath $VenvPython -Arguments @('-m', 'pip', 'install', '--no-build-isolation', '-r', (Join-Path $Root 'lumen-pc\requirements.txt')) -Description 'Instalar dependencias PC'
    Invoke-Checked -FilePath $VenvPython -Arguments @('-m', 'pip', 'install', '--no-build-isolation', '-r', (Join-Path $Root 'lumen-pc\requirements-windows.txt')) -Description 'Instalar dependencias Windows, audio y adapters'
    $profileFiles = @{
        voice=@('requirements-voice.txt'); browser=@('requirements-browser.txt'); coding=@('requirements-coding.txt'); computer=@('requirements-computer.txt'); memory=@('requirements-memory.txt')
        standard=@(); minimal=@(); full=@('requirements-voice.txt','requirements-browser.txt','requirements-coding.txt','requirements-memory.txt'); all=@('requirements-voice.txt','requirements-browser.txt','requirements-coding.txt','requirements-computer.txt','requirements-memory.txt')
    }
    foreach ($optionalFile in $profileFiles[$Profile]) {
        Invoke-Checked -FilePath $VenvPython -Arguments @('-m','pip','install','--no-build-isolation','-r',(Join-Path $Root $optionalFile)) -Description "Instalar perfil opcional $optionalFile"
    }
    Invoke-Checked -FilePath 'powershell.exe' -Arguments @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $Root 'install-deepseek-harness.ps1')) -Description 'Instalar DeepSeek-Harness fijado para GAIA'

    if (-not $ApplyMigration) { Ensure-EnvFile }

    if ($PlanMigration) {
        if ([string]::IsNullOrWhiteSpace($MigrationSourceRoot)) { throw '-PlanMigration requiere -MigrationSourceRoot.' }
        $planArgs = @('--root', $MigrationSourceRoot, '--target-version', '1.0.0-rc6', '--json', '--safe-mode')
        if ($CreateMigrationSnapshot -and [string]::IsNullOrWhiteSpace($MigrationSnapshotDir)) { throw '-CreateMigrationSnapshot requiere -MigrationSnapshotDir.' }
        if (-not [string]::IsNullOrWhiteSpace($MigrationSnapshotDir)) { $planArgs += @('--snapshot-dir', $MigrationSnapshotDir) }
        if ($CreateMigrationSnapshot) { $planArgs += '--snapshot' }
        Invoke-MigrationTool -Arguments $planArgs -Description 'Inspeccionar instalación y preparar migración RC6'
    }

    if ($ApplyMigration) {
        if ([string]::IsNullOrWhiteSpace($MigrationSourceRoot) -or [string]::IsNullOrWhiteSpace($MigrationSnapshotDir)) { throw '-ApplyMigration requiere -MigrationSourceRoot y -MigrationSnapshotDir.' }
        if (-not $ApproveMigration) { throw '-ApplyMigration requiere -ApproveMigration explícito.' }
        $applyArgs = @('--root', $MigrationSourceRoot, '--target-root', $Root, '--snapshot-dir', $MigrationSnapshotDir, '--target-version', '1.0.0-rc6', '--db-strategy', $DbStrategy, '--apply', '--approve', '--json')
        if (-not [string]::IsNullOrWhiteSpace($NewVaultPath)) { $applyArgs += @('--new-vault', $NewVaultPath) }
        if ($SafeMode) { $applyArgs += '--safe-mode' }
        Invoke-MigrationTool -Arguments $applyArgs -Description 'Aplicar migración durable RC6 con estrategia explícita y aprobación'
        if (-not (Test-Path (Join-Path $Root '.env')) -and $DbStrategy -eq 'KEEP_TARGET_CONFIG') { Ensure-EnvFile }
    }

    if ($Rollback) {
        if ([string]::IsNullOrWhiteSpace($RollbackSnapshotDir)) { throw '-Rollback requiere -RollbackSnapshotDir.' }
        if (-not $ApproveMigration) { throw '-Rollback requiere -ApproveMigration explícito.' }
        $rollbackRoot = if ([string]::IsNullOrWhiteSpace($RollbackTargetRoot)) { $Root } else { $RollbackTargetRoot }
        $rollbackArgs = @('--root', $rollbackRoot, '--snapshot-dir', $RollbackSnapshotDir, '--rollback', '--approve', '--rollback-mode', $RollbackMode, '--safe-mode', '--json')
        Invoke-MigrationTool -Arguments $rollbackArgs -Description 'Restaurar snapshot RC6 con modo explícito y aprobación'
    }

    $importCheck = @(
        'fastapi', 'httpx', 'dotenv', 'sounddevice', 'numpy', 'PIL', 'psutil',
        'edge_tts', 'whisper', 'comtypes', 'pycaw'
    ) -join ','
    $importProbe = "import importlib.util,sys; names='$importCheck'.split(','); missing=[n for n in names if importlib.util.find_spec(n) is None]; print('Faltan imports: '+', '.join(missing)) if missing else print('Import check OK'); sys.exit(1 if missing else 0)"
    Invoke-Checked -FilePath $VenvPython -Arguments @('-c', $importProbe) -Description 'Verificar imports Core/PC/Windows'

    if (-not $NoDoctor) {
        $previousSafeMode = $env:GAIA_SAFE_MODE
        if ($SafeMode) { $env:GAIA_SAFE_MODE = 'true' }
        $doctorArgs = @('tools\gaia_doctor.py', '--json')
        if ($PlanMigration) { $doctorArgs += @('--mode', 'preflight') }
        if ($ApplyMigration) { $doctorArgs += @('--mode', 'postflight') }
        if ($Rollback -or $SafeMode) { $doctorArgs += '--safe-mode' }
        Invoke-Checked -FilePath $VenvPython -Arguments $doctorArgs -Description 'Ejecutar GAIA Doctor RC6 read-only'
        if ($null -eq $previousSafeMode) { Remove-Item Env:GAIA_SAFE_MODE -ErrorAction SilentlyContinue } else { $env:GAIA_SAFE_MODE = $previousSafeMode }
    }
    Write-Host ''
    Write-Host 'Instalación GAIA completada.' -ForegroundColor Green
    Write-Host "Activa el entorno con: .\.venv\Scripts\Activate.ps1"
    Write-Host 'Revisa .env y confirma que GAIA_LAN_ENABLED=false salvo que necesites LAN explícitamente.'
} finally {
    Pop-Location
}
