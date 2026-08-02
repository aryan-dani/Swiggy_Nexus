#Requires -Version 5.1
<#
.SYNOPSIS
  Stop Nexus local API/UI processes started by start-local.ps1.

.DESCRIPTION
  Stops:
    - Listeners on the API port (default 8000) and UI port (default 3000)
    - uvicorn processes running backend.main:app
    - Next.js (next / node) processes whose command line references this repo
    - The "Nexus API" / "Nexus UI" PowerShell windows launched by start-local.ps1

  Does not broadly kill all node/python processes — only Nexus-related ports,
  command lines, and window titles used by start-local.ps1.

  Run from anywhere:
    & "C:\...\Swiggy_Nexus\stop-local.ps1"
  Or from the repo root:
    .\stop-local.ps1

.PARAMETER ApiPort
  Backend port (default 8000) — same as start-local.ps1.

.PARAMETER UiPort
  Frontend port (default 3000) — same as start-local.ps1.
#>
[CmdletBinding()]
param(
    [int]$ApiPort = 8000,
    [int]$UiPort = 3000
)

$ErrorActionPreference = "Stop"
$Root = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }

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

function Get-PidsOnPort([int]$Port) {
    $pids = New-Object System.Collections.Generic.HashSet[int]
    try {
        Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            ForEach-Object { [void]$pids.Add([int]$_.OwningProcess) }
    } catch {
        # Fallback when Get-NetTCPConnection is unavailable / needs elevation quirks
    }
    if ($pids.Count -eq 0) {
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

    # Close the -NoExit PowerShell wrappers start-local.ps1 opens
    try {
        Get-Process -Name powershell, pwsh -ErrorAction SilentlyContinue |
            Where-Object {
                $_.Id -ne $PID -and
                $_.MainWindowTitle -and (
                    $_.MainWindowTitle -like "Nexus API :*" -or
                    $_.MainWindowTitle -like "Nexus UI :*"
                )
            } |
            ForEach-Object { [void]$toKill.Add([int]$_.Id) }
    } catch {
        Write-Warn "Could not scan Nexus PowerShell windows: $($_.Exception.Message)"
    }

    if ($toKill.Count -eq 0) {
        Write-Ok "No Nexus processes found"
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

    $stillListening = @()
    foreach ($port in $Ports) {
        $left = @(Get-PidsOnPort $port | Where-Object { $_ -gt 0 -and $_ -ne $PID })
        if ($left.Count -gt 0) {
            $stillListening += "port $port (pids $($left -join ', '))"
        }
    }
    if ($stillListening.Count -gt 0) {
        Write-Warn "Still listening: $($stillListening -join '; ')"
    } else {
        Write-Ok "Ports $($Ports -join ', ') are free"
    }
}

# --- Main --------------------------------------------------------------------

Write-Host ""
Write-Host "Swiggy Nexus local stop" -ForegroundColor White
Write-Host "  Root: $Root"
Write-Host "  Ports: API=$ApiPort UI=$UiPort"

Stop-NexusListeners -Ports @($ApiPort, $UiPort)

Write-Host ""
Write-Host "Done. Re-start with: .\start-local.ps1" -ForegroundColor DarkGray
Write-Host ""
