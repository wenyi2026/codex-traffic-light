@echo off
setlocal

set "ROOT=%~dp0"
set "PYTHON=python"

where "%PYTHON%" >nul 2>nul
if errorlevel 1 (
  echo Python was not found.
  echo Install Python 3 and PyInstaller, then run this script again.
  pause
  exit /b 1
)

cd /d "%ROOT%"

"%PYTHON%" -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --onefile ^
  --name "CodexTrafficLight" ^
  --icon "%ROOT%codex_traffic_light.ico" ^
  "%ROOT%codex_traffic_light.py"

if errorlevel 1 (
  echo.
  echo Build failed. Make sure PyInstaller is installed:
  echo   "%PYTHON%" -m pip install pyinstaller
  pause
  exit /b 1
)

echo.
echo Built EXE:
echo   %ROOT%dist\CodexTrafficLight.exe
pause
