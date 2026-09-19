@echo off
cd /d "%~dp0"

echo === Sensible Tweaks launcher ===
echo Working dir: %CD%
echo.
echo Checking for python...
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: python not found on PATH.
    echo Install Python from python.org and tick "Add Python to PATH".
    pause
    exit /b 1
)
echo python found.
echo.
echo Launching main.py (will request admin)...
echo.

python main.py
set "RC=%errorlevel%"

echo.
echo === main.py exited with code %RC% ===
if exist "Logs\crash.log" (
    echo.
    echo Last lines of Logs\crash.log:
    echo ----------------------------------------
    powershell -NoProfile -Command "Get-Content 'Logs\crash.log' -Tail 40"
    echo ----------------------------------------
)
echo.
pause