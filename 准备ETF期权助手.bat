@echo off
chcp 65001 >nul
title ETF Option Assistant Setup
cd /d "%~dp0"

echo.
echo  ========================================
echo    ETF Option Assistant - Setup
echo  ========================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0准备ETF期权助手.ps1"
if errorlevel 1 (
    echo.
    echo  Setup failed. See errors above.
    pause
)
