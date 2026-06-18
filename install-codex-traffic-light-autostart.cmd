@echo off
setlocal

set "ROOT=%~dp0"
set "TARGET=%SystemRoot%\System32\wscript.exe"
set "LAUNCHER=%ROOT%launch-codex-traffic-light.vbs"
set "WATCHER=%ROOT%watch-codex-traffic-light.vbs"

if not exist "%LAUNCHER%" (
  echo Launcher was not found:
  echo   %LAUNCHER%
  pause
  exit /b 1
)

if not exist "%WATCHER%" (
  echo Watcher launcher was not found:
  echo   %WATCHER%
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$Root = $env:ROOT.TrimEnd('\'); $Target = $env:TARGET; $Launcher = $env:LAUNCHER; $WatcherLauncher = $env:WATCHER; $IconPath = Join-Path $Root 'codex_traffic_light.ico'; $Shell = New-Object -ComObject WScript.Shell; $Desktop = [Environment]::GetFolderPath('Desktop'); $DesktopShortcut = $Shell.CreateShortcut((Join-Path $Desktop 'Codex Traffic Light.lnk')); $DesktopShortcut.TargetPath = $Target; $DesktopShortcut.Arguments = ('\"' + $Launcher + '\"'); $DesktopShortcut.WorkingDirectory = $Root; $DesktopShortcut.WindowStyle = 1; $DesktopShortcut.Description = 'Codex desktop floating traffic light'; if (Test-Path $IconPath) { $DesktopShortcut.IconLocation = $IconPath }; $DesktopShortcut.Save(); $Startup = [Environment]::GetFolderPath('Startup'); $WatcherShortcut = $Shell.CreateShortcut((Join-Path $Startup 'Codex Traffic Light Watcher.lnk')); $WatcherShortcut.TargetPath = $Target; $WatcherShortcut.Arguments = ('\"' + $WatcherLauncher + '\"'); $WatcherShortcut.WorkingDirectory = $Root; $WatcherShortcut.WindowStyle = 7; $WatcherShortcut.Description = 'Start Codex Traffic Light automatically when Codex is running'; if (Test-Path $IconPath) { $WatcherShortcut.IconLocation = $IconPath }; $WatcherShortcut.Save(); Write-Host ('Desktop shortcut: ' + $DesktopShortcut.FullName); Write-Host ('Startup watcher:  ' + $WatcherShortcut.FullName)"

if %ERRORLEVEL% NEQ 0 (
  echo Failed to install shortcuts.
  pause
  exit /b 1
)

echo.
echo Installed. The desktop icon launches the EXE directly, and the Startup watcher opens it when Codex is running.
pause
