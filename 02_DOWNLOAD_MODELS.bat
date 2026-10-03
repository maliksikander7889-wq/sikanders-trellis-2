@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
".venv\Scripts\python.exe" download_models.py --textures
if errorlevel 1 (
 echo DOWNLOAD FAILED. Run this file again to resume.
 pause
 exit /b 1
)
pause
