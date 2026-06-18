@echo off
setlocal

set "ROOT=%~dp0"
set "EXE=%ROOT%dist\CodexTrafficLight.exe"
set "PYTHON=python"

if exist "%EXE%" (
  start "Codex Traffic Light" "%EXE%"
  exit /b 0
)

where "%PYTHON%" >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  start "Codex Traffic Light" "%PYTHON%" "%ROOT%codex_traffic_light.py"
  exit /b 0
)

echo Python was not found.
echo Install Python 3 or use the packaged EXE from the release page.
pause
exit /b 1
