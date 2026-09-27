#Requires -Version 5.1
<#
.SYNOPSIS
    Runs the Vite dev server and the app against it, with hot reload.

.DESCRIPTION
    Starts `npm run dev` in ui/ in the background, waits until the dev server answers,
    then runs the app in --dev mode in the foreground. The dev server is stopped again
    when the app exits, including on Ctrl+C.

    If something is already serving the dev port, that server is used as is and left
    running afterwards, so a Vite instance you started yourself is never killed.

.EXAMPLE
    scripts\dev.ps1
#>
[CmdletBinding()]
param(
    # Seconds to wait for the dev server to start answering before giving up.
    [int] $StartupTimeout = 60
)

$ErrorActionPreference = 'Stop'
# Invoke-WebRequest is slowed to a crawl by the progress bar in Windows PowerShell.
$ProgressPreference = 'SilentlyContinue'

# vite.config.js sets strictPort, so this is the only port the UI is ever served on.
$Port = 5173

$root = Split-Path -Parent $PSScriptRoot
$uiDir = Join-Path $root 'ui'

function Test-DevServer {
    # Probe over HTTP on the exact URL the app loads. A raw TcpClient is not enough here: on
    # Windows PowerShell it resolves 'localhost' to 127.0.0.1 only, while Vite binds ::1, so a
    # socket check reports "down" for a dev server that is up and serving.
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:$Port" -UseBasicParsing -TimeoutSec 2
        return $true
    } catch {
        return $false
    }
}

if (-not (Test-Path (Join-Path $uiDir 'node_modules'))) {
    throw "ui/node_modules is missing. Run: cd ui; npm ci"
}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'uv was not found on PATH. Run: pip install uv'
}

$vite = $null

try {
    if (Test-DevServer) {
        Write-Host "Dev server already running on port $Port, reusing it." -ForegroundColor Yellow
    } else {
        Write-Host 'Starting the Vite dev server...' -ForegroundColor Cyan
        $vite = Start-Process -FilePath 'npm.cmd' -ArgumentList 'run', 'dev' `
            -WorkingDirectory $uiDir -PassThru

        $deadline = (Get-Date).AddSeconds($StartupTimeout)
        while (-not (Test-DevServer)) {
            if ($vite.HasExited) {
                throw "The dev server exited with code $($vite.ExitCode) before it started serving. " +
                      "Is port $Port taken by another process? vite.config.js uses strictPort."
            }
            if ((Get-Date) -gt $deadline) {
                throw "The dev server did not answer on port $Port within $StartupTimeout seconds."
            }
            Start-Sleep -Milliseconds 200
        }
        Write-Host "Dev server ready on http://localhost:$Port" -ForegroundColor Green
    }

    Push-Location $root
    try {
        & uv run python app.py --dev
        $appExit = $LASTEXITCODE
    } finally {
        Pop-Location
    }

    if ($appExit -ne 0) {
        Write-Host "The app exited with code $appExit." -ForegroundColor Yellow
    }
    exit $appExit
} finally {
    if ($vite -and -not $vite.HasExited) {
        Write-Host 'Stopping the dev server...' -ForegroundColor Cyan
        # npm.cmd spawns node as a child, so the whole tree has to go, not just npm.
        & taskkill.exe /PID $vite.Id /T /F 2>&1 | Out-Null
    }
}
