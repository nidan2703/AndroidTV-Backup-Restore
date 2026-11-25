@echo off
title Android TV Streamer Backup & Restore
cd /d "%~dp0"

set "EXE_PATH=%~dp0AndroidTV_Streamer_Backup.exe"
set "CS_PATH=%~dp0StreamerBackup.cs"

if exist "%EXE_PATH%" (
    start "" "%EXE_PATH%"
    exit /b 0
)

if not exist "%CS_PATH%" (
    echo [ERROR] Missing companion files in this folder!
    echo Please download and extract the ENTIRE Windows folder or ZIP archive
    echo ^(AndroidTV_Streamer_Backup_Windows.zip or "Code -> Download ZIP"^)
    echo from GitHub rather than downloading a single .bat or .exe file by itself.
    echo.
    pause
    exit /b 1
)

set "CSC=%SystemRoot%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%CSC%" (
    set "CSC=%SystemRoot%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
)

if not exist "%CSC%" (
    echo [ERROR] Built-in Windows .NET Framework C# compiler not found at:
    echo   %CSC%
    pause
    exit /b 1
)

echo Compiling native Windows executable (AndroidTV_Streamer_Backup.exe)...
"%CSC%" /nologo /target:winexe /optimize+ /out:"%EXE_PATH%" ^
    /r:System.dll ^
    /r:System.Core.dll ^
    /r:System.Drawing.dll ^
    /r:System.Windows.Forms.dll ^
    /r:System.IO.Compression.dll ^
    /r:System.IO.Compression.FileSystem.dll ^
    "%CS_PATH%"

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Compilation failed.
    pause
    exit /b 1
)

echo Launching AndroidTV_Streamer_Backup.exe...
start "" "%EXE_PATH%"
exit /b 0
