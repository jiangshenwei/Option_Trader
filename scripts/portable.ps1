# Shared helpers for portable installs (any folder / any PC).

function Test-VenvHasPip {
    param([string]$VenvPython)

    try {
        & $VenvPython -m pip --version 2>$null | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Bootstrap-VenvPip {
    param([string]$VenvPython)

    Write-Host "  Bootstrapping pip in virtual environment..." -ForegroundColor Yellow
    & $VenvPython -m ensurepip --upgrade 2>$null | Out-Null
    if (-not (Test-VenvHasPip $VenvPython)) {
        throw "pip is unavailable in the virtual environment. Re-run 准备ETF期权助手.bat."
    }
    & $VenvPython -m pip install --upgrade pip -q
}

function Install-PythonRequirements {
    param(
        [string]$VenvPython,
        [string]$Backend,
        [switch]$Quiet
    )

    if (-not (Test-VenvHasPip $VenvPython)) {
        Bootstrap-VenvPip $VenvPython
    }

    Set-Location $Backend
    $pipArgs = @("-m", "pip", "install", "-r", "requirements.txt")
    if ($Quiet) {
        $pipArgs += "-q"
    }
    & $VenvPython @pipArgs
    if ($LASTEXITCODE -ne 0) {
        throw "pip install failed (exit code $LASTEXITCODE)."
    }
}

function Test-VenvPortable {
    param([string]$Backend)

    $venvDir = Join-Path $Backend ".venv"
    $venvPython = Join-Path $venvDir "Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        return $false
    }

    $cfg = Join-Path $venvDir "pyvenv.cfg"
    if (Test-Path $cfg) {
        $current = (Resolve-Path $venvDir).Path
        $commandLine = Get-Content $cfg | Where-Object { $_ -match '^command\s*=' } | Select-Object -First 1
        if ($commandLine -and ($commandLine -notmatch [regex]::Escape($current))) {
            return $false
        }
    }

    try {
        & $venvPython -c "import sys; raise SystemExit(0)" 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) {
            return $false
        }
    } catch {
        return $false
    }

    return (Test-VenvHasPip $VenvPython)
}

function Test-VenvPathMatches {
    param([string]$Backend)

    $venvDir = Join-Path $Backend ".venv"
    $cfg = Join-Path $venvDir "pyvenv.cfg"
    if (-not (Test-Path $cfg)) {
        return $true
    }
    $current = (Resolve-Path $venvDir).Path
    $commandLine = Get-Content $cfg | Where-Object { $_ -match '^command\s*=' } | Select-Object -First 1
    return (-not $commandLine) -or ($commandLine -match [regex]::Escape($current))
}

function Ensure-PortableVenv {
    param(
        [string]$Backend,
        [string]$PythonCmd
    )

    $venvDir = Join-Path $Backend ".venv"
    $venvPython = Join-Path $venvDir "Scripts\python.exe"

    if (Test-VenvPortable $Backend) {
        return $venvPython
    }

    if ((Test-Path $venvDir) -and (Test-VenvPathMatches $Backend) -and (Test-Path $venvPython)) {
        Write-Host "  [!] Virtual environment is missing pip, repairing..." -ForegroundColor Yellow
        try {
            Bootstrap-VenvPip $venvPython
            return $venvPython
        } catch {
            Write-Host "  [!] Repair failed, recreating virtual environment..." -ForegroundColor Yellow
        }
    }

    if (Test-Path $venvDir) {
        Write-Host "  [!] Removing broken virtual environment..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force $venvDir
    }

    Write-Host "  Creating Python virtual environment..." -ForegroundColor Yellow
    Set-Location $Backend
    Invoke-Expression "$PythonCmd -m venv .venv"
    if (-not (Test-Path $venvPython)) {
        throw "Failed to create virtual environment at $venvDir"
    }

    Bootstrap-VenvPip $venvPython
    return $venvPython
}
