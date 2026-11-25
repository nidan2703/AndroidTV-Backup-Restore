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
    echo [ERROR] Missing required project files in this folder!
    echo Please download and extract the ENTIRE repository folder from GitHub
    echo ^(click the green "^<^> Code" button -^> "Download ZIP"^) rather than
    echo downloading a single file by itself.
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
