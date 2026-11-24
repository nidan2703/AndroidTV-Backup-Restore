@echo off
title Compile Native AndroidTV_Streamer_Backup.exe
cd /d "%~dp0"

set "EXE_PATH=%~dp0AndroidTV_Streamer_Backup.exe"
set "CS_PATH=%~dp0StreamerBackup.cs"

set "CSC=%SystemRoot%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%CSC%" (
    set "CSC=%SystemRoot%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
)

echo Compiling %CS_PATH% using built-in Windows .NET Framework compiler:
echo   %CSC%
echo.

"%CSC%" /nologo /target:winexe /optimize+ /out:"%EXE_PATH%" ^
    /r:System.dll ^
    /r:System.Core.dll ^
    /r:System.Drawing.dll ^
    /r:System.Windows.Forms.dll ^
    /r:System.IO.Compression.dll ^
    /r:System.IO.Compression.FileSystem.dll ^
    "%CS_PATH%"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo [OK] Successfully built standalone Windows executable:
echo   %EXE_PATH%
pause
