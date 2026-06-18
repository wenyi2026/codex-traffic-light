#!/usr/bin/env python3
"""Lightweight Codex watcher for Codex Traffic Light.

This process intentionally avoids importing Pillow or UI code. It only waits
for Codex to start, launches the real traffic-light window, and writes a simple
status fallback.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import msvcrt
import os
import subprocess
import sys
import time
from pathlib import Path


APP_NAME = "Codex Traffic Light"
EXE_NAME = "CodexTrafficLight.exe"
LOCK_NAME = "codex_traffic_light_watcher.lock"
STATUS_NAME = "codex_status.json"
CREATE_NO_WINDOW = 0x08000000
CODEX_PROCESS_NAMES = {"codex.exe", "codex"}
CODEX_ACTIVITY_PREFIXES = ("codex-command-runner",)


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


APP_DIR = app_dir()
TARGET_EXE = APP_DIR / EXE_NAME
STATUS_FILE = APP_DIR / STATUS_NAME


def process_names() -> set[str]:
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    if snapshot == wintypes.HANDLE(-1).value:
        return set()
    names: set[str] = set()
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    try:
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            names.add(entry.szExeFile.lower())
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return names


def is_codex_running(names: set[str] | None = None) -> bool:
    names = names or process_names()
    for name in names:
        stem = Path(name).stem.lower()
        if name in CODEX_PROCESS_NAMES or stem in CODEX_PROCESS_NAMES:
            return True
    return False


def has_codex_activity(names: set[str] | None = None) -> bool:
    names = names or process_names()
    for name in names:
        stem = Path(name).stem.lower()
        if any(stem.startswith(prefix) or name.startswith(prefix) for prefix in CODEX_ACTIVITY_PREFIXES):
            return True
    return False


def write_status(state: str, message: str) -> None:
    try:
        STATUS_FILE.write_text(
            json.dumps(
                {
                    "status": state,
                    "message": message,
                    "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def launch_window() -> None:
    if not TARGET_EXE.exists():
        return
    subprocess.Popen([str(TARGET_EXE)], cwd=str(APP_DIR), close_fds=True, creationflags=CREATE_NO_WINDOW)


def acquire_lock():
    lock_path = APP_DIR / LOCK_NAME
    handle = lock_path.open("a+b")
    if handle.tell() == 0:
        handle.write(b"\0")
        handle.flush()
    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        return None
    return handle


def main() -> int:
    if sys.platform != "win32":
        return 1
    lock = acquire_lock()
    if lock is None:
        return 0
    while True:
        names = process_names()
        codex_running = is_codex_running(names)
        if codex_running:
            launch_window()
            write_status("running", "Codex started; task may be active.")
            return 0
        write_status("idle", "Codex is idle.")
        time.sleep(2.0)


if __name__ == "__main__":
    raise SystemExit(main())
