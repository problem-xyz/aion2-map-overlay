@echo off
cd /d "%~dp0"

rem ui/dist is not in git: rebuild it on every run, so the UI is never older than the source.
rem --dev serves the UI from Vite instead, and needs no build.
set "BUILD_UI=1"
for %%a in (%*) do if /i "%%~a"=="--dev" set "BUILD_UI="
rem node_modules is reinstalled whenever package-lock.json differs from the one it was installed
rem from, so a pulled dependency change does not break the build.
if defined BUILD_UI (
    set "INSTALL_UI="
    fc /b "ui\package-lock.json" "ui\node_modules\.run-bat-lock.json" >NUL 2>&1 || set "INSTALL_UI=1"
    if defined INSTALL_UI (
        call npm --prefix ui ci
        if errorlevel 1 goto failed
        copy /y "ui\package-lock.json" "ui\node_modules\.run-bat-lock.json" >NUL
    )
    call npm --prefix ui run build
    if errorlevel 1 goto failed
)

where uv >NUL 2>&1
if errorlevel 1 (
    python app.py %*
) else (
    uv run python app.py %*
)
if errorlevel 1 pause
exit /b

:failed
echo The UI build failed; see the output above.
pause
exit /b 1
