@echo off
title Android TV Streamer Backup & Restore
cd /d "%~dp0"

where pythonw >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    start "" pythonw "%~dp0streamer_backup_windows.py"
    exit /b 0
)

where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    python "%~dp0streamer_backup_windows.py"
    exit /b 0
)

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py "%~dp0streamer_backup_windows.py"
    exit /b 0
)

echo [ERROR] Python 3 is not installed or not in your Windows PATH.
echo Download Python 3 from https://www.python.org/downloads/ and check "Add Python to PATH".
pause
