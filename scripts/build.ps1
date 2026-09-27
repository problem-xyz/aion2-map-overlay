<#
.SYNOPSIS
    Builds the frozen app into dist/<App>.

.DESCRIPTION
    Four steps: build the UI, generate the Windows version resource, run PyInstaller, then pack
    the result with scripts/pack.ps1 into Releases/ (Setup.exe, Portable.zip, the packages),
    which it empties first.

    The UI build is the slow one and rarely changes while packaging is being worked on, so
    -SkipUi exists; it refuses to run if ui/dist/index.html is missing, because PyInstaller
    would otherwise fail deep inside Analysis with a much less obvious message.

.PARAMETER SkipUi
    Reuse the existing ui/dist instead of rebuilding it.

.PARAMETER NoPack
    Stop after PyInstaller, without producing an installer. Packing needs vpk; see pack.ps1.

.EXAMPLE
    scripts/build.ps1 -NoPack
#>
[CmdletBinding()]
param(
    [switch]$SkipUi,
    [switch]$NoPack
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }

# The exe and the dist folder are named after APP_NAME, so read it from the one place that
# defines it rather than repeating the string here.
$appName = (& uv run python -c "from map_overlay.core.appinfo import APP_NAME; print(APP_NAME)").Trim()
if (-not $appName) { throw "could not read APP_NAME from map_overlay.core.appinfo" }

if ($SkipUi) {
    if (-not (Test-Path "ui/dist/index.html")) {
        throw "-SkipUi was given but ui/dist/index.html does not exist; run without it once"
    }
    Step "UI: reusing ui/dist"
} else {
    Step "UI: npm ci && npm run build"
    Push-Location ui
    try {
        & npm ci
        if ($LASTEXITCODE -ne 0) { throw "npm ci failed" }
        & npm run build
        if ($LASTEXITCODE -ne 0) { throw "npm run build failed" }
    } finally {
        Pop-Location
    }
}

Step "Version resource"
& uv run python packaging/version_info.py
if ($LASTEXITCODE -ne 0) { throw "version_info.py failed" }

Step "PyInstaller"
& uv run pyinstaller packaging/map_overlay.spec --noconfirm --clean --distpath dist --workpath build
if ($LASTEXITCODE -ne 0) { throw "pyinstaller failed" }

$exe = Join-Path "dist" (Join-Path $appName "$appName.exe")
if (-not (Test-Path $exe)) { throw "expected $exe, which PyInstaller did not produce" }

Step "Size"
# Non-zero when the folder is over budget, so a build that quietly doubles in size fails here
# rather than being noticed at release time.
& uv run python scripts/dist_report.py (Join-Path "dist" $appName) --top 15
$overBudget = $LASTEXITCODE -ne 0

$bytes = (Get-ChildItem (Join-Path "dist" $appName) -Recurse -File | Measure-Object -Property Length -Sum).Sum
Step ("Built {0} -- {1:N1} MB" -f $exe, ($bytes / 1MB))

if ($overBudget) { throw "the built folder is over its size budget; see the table above" }

if (-not $NoPack) {
    # A local build packs the version it has, released or not, so its notes may be [Unreleased].
    # The version rarely changes between local builds, and vpk refuses to pack beside a package
    # of an equal or greater version, so Releases/ is emptied first; a local pack has no delta.
    if (Test-Path "Releases") { Remove-Item "Releases" -Recurse -Force }
    & (Join-Path $PSScriptRoot "pack.ps1") -DryRun
}
