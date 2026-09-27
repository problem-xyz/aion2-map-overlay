<#
.SYNOPSIS
    Packs dist/<App> into a Velopack release: Setup.exe, Portable.zip, the packages and the feed.

.DESCRIPTION
    Run after scripts/build.ps1 -NoPack, which builds dist/<App>; build.ps1 without -NoPack runs
    this itself. The release workflow (.github/workflows/release.yml) runs the same script, so a
    local pack and a published one differ only in what the output folder already held.

    Every name comes from the code: the version from map_overlay.__version__, the id, title and
    publisher from map_overlay.core.appinfo. The release notes are written first, by
    scripts/release_notes.py, because vpk stores them in the package.

    A delta package is made only when the output folder already holds the previous release's
    full package, which the workflow downloads with `vpk download github` beforehand.

    vpk must be the version of the velopack wheel in uv.lock: Setup.exe and Update.exe come from
    vpk, the library in the app from the wheel, and the notices describe the binaries of that one
    version. Install it with: dotnet tool install -g vpk --version <that version>

.PARAMETER OutputDir
    Where the release goes. Defaults to Releases/ at the repository root.

.PARAMETER DryRun
    For a version that has not been cut: the notes take [Unreleased] when CHANGELOG.md has no
    section for it. Never for a release that is published.

.EXAMPLE
    scripts/pack.ps1 -OutputDir $env:TEMP\releases -DryRun
#>
[CmdletBinding()]
param(
    [string]$OutputDir = "Releases",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }

$probe = "import json, importlib.metadata as m, map_overlay as p; from map_overlay.core import appinfo as a; " +
    "print(json.dumps(dict(name=a.APP_NAME, packId=a.PACK_ID, publisher=a.PUBLISHER, " +
    "version=p.__version__, velopack=m.version('velopack'))))"
$info = (& uv run python -c $probe) | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or -not $info.version) { throw "could not read the names and the version from map_overlay" }

$vpk = (Get-Command vpk -ErrorAction SilentlyContinue).Source
if (-not $vpk) { $vpk = Join-Path $env:USERPROFILE ".dotnet\tools\vpk.exe" }
if (-not (Test-Path $vpk)) { throw "vpk is not installed: dotnet tool install -g vpk --version $($info.velopack)" }
$banner = (& $vpk -h) -join "`n"
if ($banner -notmatch "Velopack CLI (\S+?),") { throw "could not read the version of $vpk" }
if ($Matches[1] -ne $info.velopack) {
    throw "vpk is $($Matches[1]) and the velopack wheel is $($info.velopack); install vpk $($info.velopack)"
}

$packDir = Join-Path "dist" $info.name
$mainExe = "$($info.name).exe"
if (-not (Test-Path (Join-Path $packDir $mainExe))) { throw "$packDir\$mainExe is missing; run scripts/build.ps1 -NoPack" }

Step "Release notes for $($info.version)"
New-Item -ItemType Directory -Force "build" | Out-Null
$notes = Join-Path "build" "release-notes.md"
$notesArgs = @("scripts/release_notes.py", $info.version, "--output", $notes)
if ($DryRun) { $notesArgs += "--dry-run" }
& uv run python @notesArgs
if ($LASTEXITCODE -ne 0) { throw "release_notes.py failed" }

Step "vpk pack $($info.packId) $($info.version) into $OutputDir"
# The shortcuts are vpk's default, spelled out so that a change of default cannot drop the app
# from the Start menu unnoticed. They take their icon from the exe, which PyInstaller stamps
# with packaging/icon.ico.
& $vpk pack --runtime win-x64 --packId $info.packId --packVersion $info.version `
    --packDir $packDir --mainExe $mainExe --packTitle $info.name --packAuthors $info.publisher `
    --icon packaging/icon.ico --shortcuts "Desktop,StartMenuRoot" --releaseNotes $notes `
    --outputDir $OutputDir
if ($LASTEXITCODE -ne 0) { throw "vpk pack failed" }

Get-ChildItem $OutputDir -File | Sort-Object Name |
    Format-Table Name, @{ Label = "MB"; Expression = { "{0:N1}" -f ($_.Length / 1MB) }; Align = "Right" }
