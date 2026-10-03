@echo off
setlocal
cd /d "%~dp0"
title Sikander's Trellis 2
set PYTHONUTF8=1
if not exist ".venv\Scripts\python.exe" (
  echo Please run INSTALL.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" app.py
if errorlevel 1 pause
