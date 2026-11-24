@echo off
title Build Standalone Windows .EXE (PyInstaller)
cd /d "%~dp0"

echo Installing/verifying PyInstaller...
python -m pip install --upgrade pyinstaller

echo Building standalone AndroidTV_Streamer_Backup.exe...
python -m PyInstaller --noconfirm --onefile --windowed --name "AndroidTV_Streamer_Backup" streamer_backup_windows.py

echo.
echo Done! Your standalone executable is located at:
echo   dist\AndroidTV_Streamer_Backup.exe
pause
