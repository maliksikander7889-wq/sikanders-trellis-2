@echo off
setlocal
cd /d "%~dp0"
title Sikander's Trellis 2 - Pixal3D setup
if not exist ".venv\Scripts\python.exe" (
  echo Run INSTALL.bat first, then run this file to add Pixal3D.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" setup.py
if errorlevel 1 goto failed
".venv\Scripts\python.exe" download_models.py --textures --pixal3d
if errorlevel 1 goto failed
echo Pixal3D is ready. Refresh the studio to select it.
pause
exit /b 0
:failed
echo Setup stopped. Rerun this file to resume downloads.
pause
exit /b 1
