@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
python setup.py
if errorlevel 1 (
 echo INSTALL FAILED. Read the error above.
 pause
 exit /b 1
)
pause
