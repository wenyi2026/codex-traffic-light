@echo off
setlocal

set "ROOT=%~dp0"
set "SCRIPT=%ROOT%set-codex-status.ps1"

if "%~1"=="" (
  echo Usage:
  echo   set-codex-status.cmd thinking "Codex is thinking"
  echo   set-codex-status.cmd running "Codex task is running"
  echo   set-codex-status.cmd approval "Approval required"
  echo   set-codex-status.cmd done "Task completed"
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %*
