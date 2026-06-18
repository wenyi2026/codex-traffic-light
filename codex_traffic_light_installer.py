#!/usr/bin/env python3
"""Installer for Codex Traffic Light."""

from __future__ import annotations

import ctypes
from datetime import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


APP_NAME = "Codex Traffic Light"
APP_VERSION = "1.2.0"
EXE_NAME = "CodexTrafficLight.exe"
WATCHER_EXE_NAME = "CodexTrafficLightWatcher.exe"
WATCHER_SCRIPT_NAME = "CodexTrafficLightWatcher.vbs"
WATCHER_CMD_NAME = "CodexTrafficLightWatcher.cmd"
INSTALL_DIR_NAME = "CodexTrafficLight"
UNINSTALL_SCRIPT_NAME = "Uninstall Codex Traffic Light.cmd"
STARTUP_SCRIPT_NAME = "Codex Traffic Light Watcher.cmd"


def message(title: str, text: str, flags: int = 0x40) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(None, text, title, flags)
    except Exception:
        print(f"{title}: {text}")


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    payload = base / "payload" / name
    if payload.exists():
        return payload
    return base / name


def install_dir() -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / INSTALL_DIR_NAME
    return Path.home() / "AppData" / "Local" / INSTALL_DIR_NAME


def stop_existing_installed_app(target: Path) -> None:
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    if not powershell.exists():
        return
    command = (
        "$target = "
        + repr(str(target))
        + "; Get-Process -Name CodexTrafficLight,CodexTrafficLightWatcher -ErrorAction SilentlyContinue | "
        + "Where-Object { $_.Path -eq $target } | Stop-Process -Force; "
        + "Get-CimInstance Win32_Process -Filter \"name='wscript.exe'\" -ErrorAction SilentlyContinue | "
        + "Where-Object { $_.CommandLine -like '*CodexTrafficLightWatcher.vbs*' } | "
        + "ForEach-Object { Invoke-CimMethod -InputObject $_ -MethodName Terminate | Out-Null }; "
        + "Get-CimInstance Win32_Process -Filter \"name='cmd.exe'\" -ErrorAction SilentlyContinue | "
        + "Where-Object { $_.CommandLine -like '*CodexTrafficLightWatcher.cmd*' } | "
        + "ForEach-Object { Invoke-CimMethod -InputObject $_ -MethodName Terminate | Out-Null }"
    )
    subprocess.run([str(powershell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command], check=False)


def run_vbs(script: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".vbs", delete=False, encoding="utf-8") as handle:
        handle.write(script)
        path = Path(handle.name)
    try:
        wscript = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "wscript.exe"
        subprocess.run([str(wscript), str(path)], check=False)
    finally:
        try:
            path.unlink()
        except OSError:
            pass


def vbs_quote(value: Path | str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def create_shortcut(
    link_path: Path,
    target: Path,
    working_dir: Path,
    description: str,
    arguments: str = "",
) -> None:
    link_path.parent.mkdir(parents=True, exist_ok=True)
    script = f"""
Option Explicit
Dim shell, shortcut
Set shell = CreateObject("WScript.Shell")
Set shortcut = shell.CreateShortcut({vbs_quote(link_path)})
shortcut.TargetPath = {vbs_quote(target)}
shortcut.Arguments = {vbs_quote(arguments)}
shortcut.WorkingDirectory = {vbs_quote(working_dir)}
shortcut.IconLocation = {vbs_quote(str(target) + ",0")}
shortcut.Description = {vbs_quote(description)}
shortcut.Save
"""
    run_vbs(script)


def desktop_dir() -> Path:
    userprofile = Path(os.environ.get("USERPROFILE", str(Path.home())))
    onedrive = os.environ.get("OneDrive")
    candidates = []
    if onedrive:
        candidates.append(Path(onedrive) / "Desktop")
    candidates.extend([userprofile / "Desktop", userprofile / "桌面"])
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return userprofile / "Desktop"


def startup_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    return Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def start_menu_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / APP_NAME
    return Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / APP_NAME


def write_uninstaller(target_dir: Path) -> Path:
    script_path = target_dir / UNINSTALL_SCRIPT_NAME
    desktop_link = desktop_dir() / f"{APP_NAME}.lnk"
    startup_link = startup_dir() / f"{APP_NAME} Watcher.lnk"
    startup_script = startup_dir() / STARTUP_SCRIPT_NAME
    old_startup_link = startup_dir() / f"{APP_NAME}.lnk"
    program_dir = start_menu_dir()
    script = f"""@echo off
setlocal
if /I "%~1" NEQ "--run" (
  copy "%~f0" "%TEMP%\\codex_traffic_light_uninstall.cmd" >nul
  start "" "%TEMP%\\codex_traffic_light_uninstall.cmd" --run "{target_dir}"
  exit /b
)
set "INSTALL_DIR=%~2"
choice /C YN /M "Uninstall {APP_NAME}?"
if errorlevel 2 exit /b
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$install = [string]$env:INSTALL_DIR; $desktop = {repr(str(desktop_link))}; $startup = {repr(str(startup_link))}; $startupScript = {repr(str(startup_script))}; $oldStartup = {repr(str(old_startup_link))}; $programDir = {repr(str(program_dir))}; Get-Process -Name CodexTrafficLight,CodexTrafficLightWatcher -ErrorAction SilentlyContinue | Where-Object {{ $_.Path -like (Join-Path $install '*') }} | Stop-Process -Force; Get-CimInstance Win32_Process -Filter \"name='wscript.exe'\" -ErrorAction SilentlyContinue | Where-Object {{ $_.CommandLine -like '*CodexTrafficLightWatcher.vbs*' }} | ForEach-Object {{ Invoke-CimMethod -InputObject $_ -MethodName Terminate | Out-Null }}; Get-CimInstance Win32_Process -Filter \"name='cmd.exe'\" -ErrorAction SilentlyContinue | Where-Object {{ $_.CommandLine -like '*CodexTrafficLightWatcher.cmd*' }} | ForEach-Object {{ Invoke-CimMethod -InputObject $_ -MethodName Terminate | Out-Null }}; Remove-Item -LiteralPath $desktop,$startup,$startupScript,$oldStartup -Force -ErrorAction SilentlyContinue; Remove-Item -LiteralPath $programDir -Recurse -Force -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 500; Remove-Item -LiteralPath $install -Recurse -Force -ErrorAction SilentlyContinue"
echo.
echo {APP_NAME} has been uninstalled.
timeout /t 2 >nul
"""
    script_path.write_text(script, encoding="utf-8")
    return script_path


def write_product_info(target_dir: Path) -> None:
    payload = {
        "name": APP_NAME,
        "version": APP_VERSION,
        "installed_at": datetime.now().isoformat(timespec="seconds"),
        "install_dir": str(target_dir),
    }
    (target_dir / "product.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_startup_script(target_dir: Path, watcher_exe: Path) -> Path:
    script_path = startup_dir() / STARTUP_SCRIPT_NAME
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script = f"""@echo off
start "" "{watcher_exe}"
"""
    script_path.write_text(script, encoding="utf-8")
    return script_path


def write_watcher_script(target_dir: Path, target_exe: Path) -> Path:
    script_path = target_dir / WATCHER_SCRIPT_NAME
    cmd_path = target_dir / WATCHER_CMD_NAME
    cmd_script = f'''@echo off
setlocal
set "TARGET={target_exe}"

:loop
tasklist /FI "IMAGENAME eq Codex.exe" 2>NUL | find /I "Codex.exe" >NUL
if not errorlevel 1 (
  start "" "%TARGET%"
  exit /b 0
)
timeout /t 2 /nobreak >NUL
goto loop
'''
    cmd_path.write_text(cmd_script, encoding="utf-8")
    script = f'''Option Explicit
Dim shell, cmd
Set shell = CreateObject("WScript.Shell")
cmd = "cmd.exe /c " & Chr(34) & {vbs_quote(cmd_path)} & Chr(34)
shell.Run cmd, 0, False
'''
    script_path.write_text(script, encoding="utf-8")
    return script_path


def install() -> int:
    payload_exe = resource_path(EXE_NAME)
    payload_watcher = resource_path(WATCHER_EXE_NAME)
    if not payload_exe.exists():
        message(APP_NAME, f"Installer payload is missing:\n{payload_exe}", 0x10)
        return 1
    if not payload_watcher.exists():
        message(APP_NAME, f"Installer watcher payload is missing:\n{payload_watcher}", 0x10)
        return 1

    target_dir = install_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target_exe = target_dir / EXE_NAME
    target_watcher = target_dir / WATCHER_EXE_NAME
    stop_existing_installed_app(target_exe)
    shutil.copy2(payload_exe, target_exe)
    shutil.copy2(payload_watcher, target_watcher)
    for stale_name in (WATCHER_SCRIPT_NAME, WATCHER_CMD_NAME):
        try:
            (target_dir / stale_name).unlink()
        except OSError:
            pass
    write_product_info(target_dir)
    uninstall_script = write_uninstaller(target_dir)

    status_file = target_dir / "codex_status.json"
    if not status_file.exists():
        status_file.write_text(
            '{\n  "status": "idle",\n  "message": "Task completed; Codex is idle.",\n  "updated_at": ""\n}\n',
            encoding="utf-8",
        )

    create_shortcut(
        desktop_dir() / f"{APP_NAME}.lnk",
        target_exe,
        target_dir,
        "Open Codex Traffic Light",
    )

    old_startup_shortcut = startup_dir() / f"{APP_NAME}.lnk"
    old_watcher_shortcut = startup_dir() / f"{APP_NAME} Watcher.lnk"
    try:
        old_startup_shortcut.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass
    try:
        old_watcher_shortcut.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass

    write_startup_script(target_dir, target_watcher)

    program_dir = start_menu_dir()
    create_shortcut(
        program_dir / f"{APP_NAME}.lnk",
        target_exe,
        target_dir,
        "Open Codex Traffic Light",
    )
    create_shortcut(
        program_dir / f"Uninstall {APP_NAME}.lnk",
        uninstall_script,
        target_dir,
        f"Uninstall {APP_NAME}",
    )

    subprocess.Popen([str(target_watcher)], cwd=str(target_dir), close_fds=True)
    message(
        APP_NAME,
        f"Installation complete. Version {APP_VERSION}\n\n"
        f"Installed to:\n{target_dir}\n\n"
        "Created:\n"
        "- Desktop shortcut\n"
        "- Codex startup watcher\n"
        "- Start Menu launch and uninstall shortcuts\n\n"
        "The window can be minimized to the system tray.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(install())
