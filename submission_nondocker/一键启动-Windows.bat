@echo off
chcp 65001 >nul
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0一键启动-Windows.ps1" %*
set EXIT_CODE=%ERRORLEVEL%
echo.
if exist "%~dp0runtime_data\startup-status.txt" type "%~dp0runtime_data\startup-status.txt"
echo.
if not "%EXIT_CODE%"=="0" echo Startup failed. See logs under runtime_data\logs.
pause
exit /b %EXIT_CODE%
