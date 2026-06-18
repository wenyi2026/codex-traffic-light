@echo off
setlocal

set "ROOT=%~dp0"
set "TARGET=%SystemRoot%\System32\wscript.exe"
set "LAUNCHER=%ROOT%launch-codex-traffic-light.vbs"

if not exist "%LAUNCHER%" (
  echo Launcher was not found:
  echo   %LAUNCHER%
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$Desktop = [Environment]::GetFolderPath('Desktop'); $ShortcutPath = Join-Path $Desktop 'Codex Traffic Light.lnk'; $TargetPath = $env:TARGET; $Launcher = $env:LAUNCHER; $WorkingDirectory = $env:ROOT.TrimEnd('\'); $IconPath = Join-Path $WorkingDirectory 'codex_traffic_light.ico'; $Shell = New-Object -ComObject WScript.Shell; $Shortcut = $Shell.CreateShortcut($ShortcutPath); $Shortcut.TargetPath = $TargetPath; $Shortcut.Arguments = ('\"' + $Launcher + '\"'); $Shortcut.WorkingDirectory = $WorkingDirectory; $Shortcut.WindowStyle = 1; $Shortcut.Description = 'Codex desktop floating traffic light'; if (Test-Path $IconPath) { $Shortcut.IconLocation = $IconPath } else { $Shortcut.IconLocation = 'C:\Windows\System32\shell32.dll,167' }; $Shortcut.Save(); Write-Host ('Created: ' + $ShortcutPath)"

if %ERRORLEVEL% NEQ 0 (
  echo Failed to create desktop icon.
  pause
  exit /b 1
)

echo.
echo Desktop icon created. You can double-click "Codex Traffic Light" on the desktop.
pause
