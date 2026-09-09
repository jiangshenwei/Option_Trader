@echo off
chcp 65001 >nul
title ETF Option Assistant Launcher
cd /d "%~dp0"

echo.
echo  ========================================
echo    ETF Option Assistant - Starting...
echo  ========================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0启动ETF期权助手.ps1"
if errorlevel 1 (
    echo.
    echo  Startup failed. See errors above.
    pause
)
