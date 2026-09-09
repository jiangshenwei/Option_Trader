# ETF Option Assistant — environment setup (project root — portable)
# Double-click: 准备ETF期权助手.bat

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "scripts\portable.ps1")

$RootDir = $PSScriptRoot
$ProjectRoot = Join-Path $RootDir "Developer\etf-option-assistant"
$Backend = Join-Path $ProjectRoot "backend"
$Frontend = Join-Path $ProjectRoot "frontend"
$DataDir = Join-Path $Backend "data"

function Write-Step([string]$Message, [string]$Color = "Cyan") {
    Write-Host $Message -ForegroundColor $Color
}

function Write-Ok([string]$Message) {
    Write-Step ("  [OK] " + $Message) "Green"
}

function Write-Warn([string]$Message) {
    Write-Step ("  [!] " + $Message) "Yellow"
}

function Write-Fail([string]$Message) {
    Write-Step ("  [X] " + $Message) "Red"
}

function Get-PythonCommand {
    $py = Get-Command python -ErrorAction SilentlyContinue
    if ($py) { return "python" }
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) { return "py -3" }
    return $null
}

function Test-PythonVersion([string]$PythonCmd) {
    try {
        $versionText = Invoke-Expression "$PythonCmd -c `"import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')`"" 2>$null
        if (-not $versionText) { return $false }
        $parts = $versionText.Trim().Split(".")
        $major = [int]$parts[0]
        $minor = [int]$parts[1]
        return ($major -gt 3) -or ($major -eq 3 -and $minor -ge 10)
    } catch {
        return $false
    }
}

function Test-NodeReady {
    $node = Get-Command node -ErrorAction SilentlyContinue
    $npm = Get-Command npm -ErrorAction SilentlyContinue
    return ($null -ne $node) -and ($null -ne $npm)
}

function Try-InstallNodeWithWinget {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        return $false
    }

    Write-Warn "Detected winget. Attempting to install Node.js LTS..."
    Write-Host "        (Administrator rights may be required)" -ForegroundColor DarkGray
    & winget install --id OpenJS.NodeJS.LTS -e --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        return $false
    }

    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
        [System.Environment]::GetEnvironmentVariable("Path", "User")
    return Test-NodeReady
}

function Show-NodeInstallGuide {
    Write-Host ""
    Write-Fail "Node.js / npm not found. Frontend dependencies cannot be installed."
    Write-Host ""
    Write-Host "  Please install Node.js LTS, then re-run this setup script:" -ForegroundColor Yellow
    Write-Host "    1. Download: https://nodejs.org/en/download" -ForegroundColor White
    Write-Host "    2. Run installer, keep 'Add to PATH' checked" -ForegroundColor White
    Write-Host "    3. Close and reopen this window, then run setup again" -ForegroundColor White
    Write-Host ""
    Write-Host "  Or in an elevated PowerShell:" -ForegroundColor Yellow
    Write-Host "    winget install OpenJS.NodeJS.LTS" -ForegroundColor White
    Write-Host ""
}

$failed = $false

Write-Step "=== ETF Option Assistant — Setup ===" "Cyan"
Write-Step "Project: $ProjectRoot"
Write-Host ""

if (-not (Test-Path $ProjectRoot)) {
    Write-Fail "Project directory not found."
    Read-Host "Press Enter to exit"
    exit 1
}

# --- 1. Python ---
Write-Step "[1/4] Checking Python..." "Cyan"
$pythonCmd = Get-PythonCommand
if (-not $pythonCmd) {
    Write-Fail "Python not found."
    Write-Host "  Install Python 3.10+ from https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "  During install, check 'Add python.exe to PATH'." -ForegroundColor Yellow
    $failed = $true
} elseif (-not (Test-PythonVersion $pythonCmd)) {
    Write-Fail "Python 3.10+ required."
    $failed = $true
} else {
    $ver = Invoke-Expression "$pythonCmd --version" 2>$null
    Write-Ok $ver.Trim()
}

# --- 2. Node.js / npm ---
Write-Step "[2/4] Checking Node.js / npm..." "Cyan"
if (Test-NodeReady) {
    $nodeVer = (node --version).Trim()
    $npmVer = (npm --version).Trim()
    Write-Ok ("Node.js " + $nodeVer + ", npm " + $npmVer)
} else {
    Write-Warn "Node.js / npm not found."
    $answer = Read-Host "  Try installing Node.js LTS via winget now? [Y/N]"
    if ($answer -match '^[Yy]') {
        if (Try-InstallNodeWithWinget) {
            $nodeVer = (node --version).Trim()
            $npmVer = (npm --version).Trim()
            Write-Ok ("Installed Node.js " + $nodeVer + ", npm " + $npmVer)
        } else {
            Show-NodeInstallGuide
            $failed = $true
        }
    } else {
        Show-NodeInstallGuide
        $failed = $true
    }
}

if ($failed) {
    Write-Host ""
    Write-Fail "Prerequisites incomplete. Fix the items above and run setup again."
    Read-Host "Press Enter to exit"
    exit 1
}

# --- 3. Backend ---
Write-Step "[3/4] Setting up backend..." "Cyan"
try {
    $venvPython = Ensure-PortableVenv -Backend $Backend -PythonCmd $pythonCmd
    Write-Ok "Virtual environment ready: backend\.venv"
} catch {
    Write-Fail $_.Exception.Message
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Warn "Installing / updating Python packages (may take a few minutes)..."
try {
    Install-PythonRequirements -VenvPython $venvPython -Backend $Backend
} catch {
    Write-Fail $_.Exception.Message
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Ok "Python dependencies installed."

$envExample = Join-Path $Backend ".env.example"
$envFile = Join-Path $Backend ".env"
if (-not (Test-Path $envFile)) {
    Copy-Item $envExample $envFile
    Write-Ok "Created backend\.env from .env.example"
} else {
    Write-Ok "backend\.env already exists (not overwritten)"
}

if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
    Write-Ok "Created backend\data directory for SQLite"
} else {
    Write-Ok "backend\data directory ready"
}

# --- 4. Frontend ---
Write-Step "[4/4] Setting up frontend..." "Cyan"
Set-Location $Frontend
Write-Warn "Installing / updating npm packages (first run may take a few minutes)..."
npm install
if ($LASTEXITCODE -ne 0) {
    Write-Fail "npm install failed."
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Ok "Frontend dependencies installed."

# --- Summary ---
Write-Host ""
Write-Step "=== Setup complete ===" "Green"
Write-Host ""
Write-Host "  Next step: double-click" -ForegroundColor White
Write-Host "    启动ETF期权助手.bat" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Then open in browser:" -ForegroundColor White
Write-Host "    http://localhost:5173" -ForegroundColor Cyan
Write-Host ""
Write-Host "  API docs:" -ForegroundColor White
Write-Host "    http://localhost:8000/docs" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Tip: backend\.env has LIVE_DATA=false by default (mock data, fast startup)." -ForegroundColor DarkGray
Write-Host "       Set LIVE_DATA=true for real-time market data via AKShare." -ForegroundColor DarkGray
Write-Host ""

Read-Host "Press Enter to exit"
