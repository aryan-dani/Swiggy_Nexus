#Requires -Version 5.1
<#
.SYNOPSIS
  Kill stale Nexus API/UI listeners, then start backend + frontend.

.DESCRIPTION
  Run from anywhere:
    & "C:\...\Swiggy_Nexus\start-local.ps1"
  Or from the repo root:
    .\start-local.ps1

  Defaults: uvicorn on :8000 (no --reload), Next.js `dev` on :3000.
  Use -Prod for `npm run build` + `npm start` (demo-script style).

.PARAMETER Prod
  Build then serve the frontend (next start) instead of next dev.

.PARAMETER SkipKill
  Do not kill processes on ports 8000/3000 first.

.PARAMETER NoBrowser
  Do not open the UI in the default browser.

.PARAMETER ApiPort
  Backend port (default 8000).

.PARAMETER UiPort
  Frontend port (default 3000).
#>
[CmdletBinding()]
param(
    [switch]$Prod,
    [switch]$SkipKill,
    [switch]$NoBrowser,
    [int]$ApiPort = 8000,
    [int]$UiPort = 3000
)

$ErrorActionPreference = "Stop"
$Root = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$Uvicorn = Join-Path $BackendDir ".venv\Scripts\uvicorn.exe"
$Python = Join-Path $BackendDir ".venv\Scripts\python.exe"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host "    OK  $Message" -ForegroundColor Green
}

function Write-Warn([string]$Message) {
    Write-Host "    !!  $Message" -ForegroundColor Yellow
}

function Test-CommandExists([string]$Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-PidsOnPort([int]$Port) {
    $pids = New-Object System.Collections.Generic.HashSet[int]
    try {
        Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            ForEach-Object { [void]$pids.Add([int]$_.OwningProcess) }
    } catch {
        # Fallback when Get-NetTCPConnection is unavailable / needs elevation quirks
        $lines = netstat -ano -p tcp 2>$null | Select-String ":$Port\s+.*LISTENING"
        foreach ($line in $lines) {
            $parts = ($line.ToString() -split "\s+") | Where-Object { $_ -ne "" }
            if ($parts.Count -ge 5) {
                $procId = 0
                if ([int]::TryParse($parts[-1], [ref]$procId) -and $procId -gt 0) {
                    [void]$pids.Add($procId)
                }
            }
        }
    }
    return @($pids)
}

function Stop-NexusListeners {
    param([int[]]$Ports)

    Write-Step "Stopping anything listening on $($Ports -join ', ')"

    $toKill = New-Object System.Collections.Generic.HashSet[int]
    foreach ($port in $Ports) {
        foreach ($procId in (Get-PidsOnPort $port)) {
            if ($procId -gt 0 -and $procId -ne $PID) {
                [void]$toKill.Add($procId)
            }
        }
    }

    # Also catch uvicorn / next processes started from this repo (even if port already freed)
    try {
        $escapedRoot = [regex]::Escape($Root)
        Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
            Where-Object {
                $_.CommandLine -and (
                    $_.CommandLine -match "uvicorn.*backend\.main:app" -or
                    ($_.CommandLine -match "next" -and $_.CommandLine -match $escapedRoot)
                )
            } |
            ForEach-Object {
                if ($_.ProcessId -ne $PID) { [void]$toKill.Add([int]$_.ProcessId) }
            }
    } catch {
        Write-Warn "Could not scan process command lines: $($_.Exception.Message)"
    }

    if ($toKill.Count -eq 0) {
        Write-Ok "No stale Nexus processes found"
        return
    }

    foreach ($procId in $toKill) {
        try {
            $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
            $name = if ($proc) { $proc.ProcessName } else { "pid=$procId" }
            Stop-Process -Id $procId -Force -ErrorAction Stop
            Write-Ok "Killed $name ($procId)"
        } catch {
            Write-Warn "Could not kill pid $procId : $($_.Exception.Message)"
        }
    }

    Start-Sleep -Seconds 1
}

function Wait-HttpOk {
    param(
        [string]$Url,
        [string]$Label,
        [int]$TimeoutSec = 90
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
                Write-Ok "$Label ready ($Url)"
                return $true
            }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    Write-Warn "$Label did not become ready within ${TimeoutSec}s ($Url)"
    return $false
}

# --- Preconditions -----------------------------------------------------------

Write-Host ""
Write-Host "Swiggy Nexus local launcher" -ForegroundColor White
Write-Host "  Root: $Root"

if (-not (Test-Path $Uvicorn)) {
    throw "Missing $Uvicorn - create backend\.venv and install requirements first."
}
if (-not (Test-Path (Join-Path $FrontendDir "package.json"))) {
    throw "Missing frontend\package.json"
}
if (-not (Test-CommandExists "npm")) {
    throw "npm is not on PATH. Install Node.js, then re-open the terminal."
}

# --- Kill + start ------------------------------------------------------------

if (-not $SkipKill) {
    Stop-NexusListeners -Ports @($ApiPort, $UiPort)
} else {
    Write-Warn "SkipKill set - leaving existing listeners alone"
}

$apiTitle = "Nexus API :$ApiPort"
$uiTitle = "Nexus UI :$UiPort"

Write-Step "Starting backend ($apiTitle)"
# No --reload: LangGraph interrupt state is in-memory for the process lifetime.
$apiArgs = @(
    "-NoExit",
    "-Command",
    @"
Set-Location -LiteralPath '$Root'
`$host.UI.RawUI.WindowTitle = '$apiTitle'
Write-Host 'Nexus API - uvicorn backend.main:app (no --reload)' -ForegroundColor Cyan
& '$Uvicorn' backend.main:app --host 127.0.0.1 --port $ApiPort
"@
)
Start-Process -FilePath "powershell.exe" -WorkingDirectory $Root -ArgumentList $apiArgs | Out-Null
Write-Ok "API window launched"

$null = Wait-HttpOk -Url "http://127.0.0.1:$ApiPort/health" -Label "API" -TimeoutSec 60

Write-Step "Starting frontend ($uiTitle)"
if ($Prod) {
    $uiCommand = @"
Set-Location -LiteralPath '$FrontendDir'
`$host.UI.RawUI.WindowTitle = '$uiTitle'
`$env:NEXT_PUBLIC_API_URL = 'http://127.0.0.1:$ApiPort'
Write-Host 'Nexus UI - next build + start (prod)' -ForegroundColor Cyan
npm run build
if (`$LASTEXITCODE -ne 0) { Write-Host 'build failed' -ForegroundColor Red; exit `$LASTEXITCODE }
npm start -- -p $UiPort
"@
} else {
    $uiCommand = @"
Set-Location -LiteralPath '$FrontendDir'
`$host.UI.RawUI.WindowTitle = '$uiTitle'
`$env:NEXT_PUBLIC_API_URL = 'http://127.0.0.1:$ApiPort'
Write-Host 'Nexus UI - next dev' -ForegroundColor Cyan
npm run dev -- -p $UiPort
"@
}

$uiArgs = @("-NoExit", "-Command", $uiCommand)
Start-Process -FilePath "powershell.exe" -WorkingDirectory $FrontendDir -ArgumentList $uiArgs | Out-Null
Write-Ok "UI window launched"

$null = Wait-HttpOk -Url "http://127.0.0.1:$UiPort" -Label "UI" -TimeoutSec 120

Write-Step "Ready"
Write-Host "    API  http://127.0.0.1:$ApiPort/health"
Write-Host "    UI   http://127.0.0.1:$UiPort"
Write-Host "    Agent http://127.0.0.1:$ApiPort/api/concierge/agent"
Write-Host ""
Write-Host "    Preflight: .\backend\.venv\Scripts\python.exe scripts\demo_preflight.py" -ForegroundColor DarkGray
    Write-Host "    Record:    .\run-demo-record.ps1  (teleprompter · full feature walkthrough)" -ForegroundColor DarkGray
    Write-Host "    Stop: .\stop-local.ps1  (or close the two Nexus windows / re-run this script)." -ForegroundColor DarkGray

if (-not $NoBrowser) {
    try {
        Start-Process "http://127.0.0.1:$UiPort"
    } catch {
        Write-Warn "Could not open browser: $($_.Exception.Message)"
    }
}

Write-Host ""
