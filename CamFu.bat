@echo off
setlocal EnableDelayedExpansion

:: ============================================================
::  CamFu - Intelligent Surveillance System
::  1-Click Windows Batch Launcher
:: ============================================================

title CamFu Surveillance System

cd /d "%~dp0"

echo.
echo  =====================================================
echo   CamFu ^| Intelligent Surveillance System
echo  =====================================================
echo.

:: Check Java
java -version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Java is not installed or not in PATH.
    echo          Please install Java 21+ from:
    echo          https://adoptium.net/ or https://www.oracle.com/java/technologies/downloads/
    echo.
    pause
    exit /b 1
)

:: Run PowerShell launcher with execution policy bypass
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-camfu.ps1"

if errorlevel 1 (
    echo.
    echo  [NOTICE] CamFu exited with code %errorlevel%.
    pause
)

endlocal
