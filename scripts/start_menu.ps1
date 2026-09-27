<#
.SYNOPSIS
    Adds this source checkout to the Start menu, with the app's icon, or takes it off again.

.DESCRIPTION
    The installer makes its own shortcuts (scripts/pack.ps1, --shortcuts). This one is for a
    checkout run through run.bat, which is not installed anywhere and so has no shortcut. It
    starts run.bat minimised, so the console that rebuilds the UI stays out of the way, and
    carries "(source)" in its name so it never replaces the installed app's shortcut.

    The name comes from map_overlay.core.appinfo, like every other name.

.PARAMETER Remove
    Delete the shortcut instead of making it.

.EXAMPLE
    scripts/start_menu.ps1
#>
[CmdletBinding()]
param(
    [switch]$Remove
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

$name = (& uv run --project $root python -c "from map_overlay.core.appinfo import APP_NAME; print(APP_NAME)")
if ($LASTEXITCODE -ne 0 -or -not $name) { throw "could not read APP_NAME from map_overlay" }

$programs = [Environment]::GetFolderPath("Programs")  # the user's Start menu, no admin rights
$link = Join-Path $programs "$name (source).lnk"

if ($Remove) {
    if (Test-Path $link) { Remove-Item $link }
    Write-Host "removed $link"
    exit 0
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($link)
$shortcut.TargetPath = Join-Path $root "run.bat"
$shortcut.WorkingDirectory = $root
$shortcut.IconLocation = "$(Join-Path $root 'packaging\icon.ico'),0"
$shortcut.WindowStyle = 7  # minimised
$shortcut.Description = $name
$shortcut.Save()
Write-Host "created $link"
