@echo off
setlocal
cd /d "%~dp0"
title Sikander's Trellis 2 - Setup
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1"
if errorlevel 1 (
  echo Setup stopped. See logs\install.log for details. Run INSTALL.bat to retry.
  pause
  exit /b 1
)
call "%~dp0START.bat"
