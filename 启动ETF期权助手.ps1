# ETF Option Assistant launcher (project root — portable, any drive/path)
# Double-click: 启动ETF期权助手.bat

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "scripts\portable.ps1")

$RootDir = $PSScriptRoot
$ProjectRoot = Join-Path $RootDir "Developer\etf-option-assistant"
$Backend = Join-Path $ProjectRoot "backend"
$Frontend = Join-Path $ProjectRoot "frontend"
$AppUrl = "http://localhost:5173"
$ApiUrl = "http://localhost:8000"

function Write-Step([string]$Message, [string]$Color = "Cyan") {
    Write-Host $Message -ForegroundColor $Color
}

function Test-ServerReady([string]$Url, [int]$TimeoutSec = 2) {
    try {
        $null = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec
        return $true
    } catch {
        return $false
    }
}

function Wait-ForServer([string]$Url, [string]$Name, [int]$MaxWaitSec = 60) {
    $deadline = (Get-Date).AddSeconds($MaxWaitSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-ServerReady $Url 2) {
            Write-Step "$Name ready: $Url" "Green"
            return $true
        }
        Start-Sleep -Seconds 1
    }
    Write-Step "$Name timeout. Check the service window for errors." "Yellow"
    return $false
}

if (-not (Test-Path $ProjectRoot)) {
    Write-Step "Project not found: $ProjectRoot" "Red"
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Step "=== ETF Option Assistant ===" "Cyan"
Write-Step "Project: $ProjectRoot"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Step "Python not found. Install Python 3.10+ and add to PATH." "Red"
    Read-Host "Press Enter to exit"
    exit 1
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Step "npm not found. Install Node.js LTS." "Red"
    Read-Host "Press Enter to exit"
    exit 1
}

$pythonCmd = if (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { "py -3" }
try {
    $venvPython = Ensure-PortableVenv -Backend $Backend -PythonCmd $pythonCmd
} catch {
    Write-Step $_.Exception.Message "Red"
    Write-Step "Run 准备ETF期权助手.bat first, or install Python 3.10+." "Yellow"
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Step "Checking backend dependencies..." "Yellow"
try {
    Install-PythonRequirements -VenvPython $venvPython -Backend $Backend -Quiet
} catch {
    Write-Step $_.Exception.Message "Red"
    Write-Step "Run 准备ETF期权助手.bat to repair the environment." "Yellow"
    Read-Host "Press Enter to exit"
    exit 1
}

$envFile = Join-Path $Backend ".env"
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $Backend ".env.example") $envFile
    Write-Step "Created backend/.env from .env.example" "Yellow"
}

if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
    Write-Step "Installing frontend dependencies (first run may take a while)..." "Yellow"
    Set-Location $Frontend
    npm install
}

$backendReady = Test-ServerReady "$ApiUrl/api/v1/health"
$frontendReady = Test-ServerReady $AppUrl

if (-not $backendReady) {
    Write-Step "Starting backend $ApiUrl ..." "Green"
    $backendCmd = "Set-Location '$Backend'; Remove-Item Env:LIVE_DATA -ErrorAction SilentlyContinue; Remove-Item Env:SINA_AUXILIARY -ErrorAction SilentlyContinue; Write-Host 'ETF Assistant - Backend (8000)' -ForegroundColor Cyan; & '$venvPython' -m uvicorn app.main:app --reload --reload-dir app --port 8000"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd
} else {
    Write-Step "Backend already running, skipped." "Green"
}

if (-not $frontendReady) {
    Start-Sleep -Seconds 2
    Write-Step "Starting frontend $AppUrl ..." "Green"
    $frontendCmd = "Set-Location '$Frontend'; Write-Host 'ETF Assistant - Frontend (5173)' -ForegroundColor Cyan; npm run dev"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd
} else {
    Write-Step "Frontend already running, skipped." "Green"
}

if (-not $backendReady) {
    Wait-ForServer "$ApiUrl/api/v1/health" "Backend" 60 | Out-Null
}
if (-not $frontendReady) {
    Wait-ForServer $AppUrl "Frontend" 60 | Out-Null
}

# Give backend extra time on first live-data warm-up
Start-Sleep -Seconds 2

Write-Step "Opening browser: $AppUrl" "Green"
Start-Process $AppUrl

Write-Host ""
Write-Step "Done. Close the Backend and Frontend PowerShell windows to stop." "Cyan"
Write-Step ("API docs: " + $ApiUrl + "/docs") "DarkGray"
Start-Sleep -Seconds 3
