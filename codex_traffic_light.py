#!/usr/bin/env python3
"""Floating Codex status traffic light for Windows desktop."""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import gc
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import msvcrt
except ImportError:  # pragma: no cover - Windows-only watcher lock
    msvcrt = None

LRESULT = ctypes.c_ssize_t
UINT_PTR = ctypes.c_size_t

try:
    import tkinter as tk
    from tkinter import messagebox
except Exception:  # pragma: no cover - optional fallback for broken Tcl/Tk runtimes
    tk = None
    messagebox = None

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except Exception as exc:  # pragma: no cover - import-time desktop guard
    print(f"Pillow is required for the polished traffic light renderer: {exc}", file=sys.stderr)
    raise


APP_NAME = "Codex Traffic Light"
APP_VERSION = "1.2.0"
CODEX_PROCESS_NAMES = {
    "codex.exe",
    "codex",
}
CODEX_ACTIVITY_PREFIXES = (
    "codex-command-runner",
)
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
ERROR_ALREADY_EXISTS = 183
DEFAULT_IDLE_AFTER_SECONDS = 45.0
DEFAULT_RUNNING_HOLD_SECONDS = 60.0
DEFAULT_ATTENTION_HOLD_SECONDS = 300.0
CODEX_EXIT_CLOSE_GRACE_SECONDS = 8.0
SESSION_SCAN_INTERVAL_SECONDS = 1.0
SESSION_TAIL_BYTES = 1024 * 1024
SESSION_RECENT_SECONDS = 6 * 60 * 60
DEFAULT_DISPLAY_SIZE = 86
MIN_DISPLAY_SIZE = 60
MAX_DISPLAY_SIZE = 150
CREATE_NO_WINDOW = 0x08000000
SW_SHOWNORMAL = 1
SW_HIDE = 0
SW_SHOW = 5
SW_MINIMIZE = 6
SW_RESTORE = 9
IDC_ARROW = 32512
IDC_SIZENWSE = 32642
HWND_TOPMOST = wintypes.HWND(-1)
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
WM_APP = 0x8000
WM_TRAYICON = WM_APP + 1
NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        if exe_dir.name.lower() == "dist" and (exe_dir.parent / "codex_status.json").exists():
            return exe_dir.parent
        return exe_dir
    return Path(__file__).resolve().parent


APP_DIR = app_dir()
DEFAULT_STATUS_FILE = APP_DIR / "codex_status.json"
DEFAULT_CONFIG_FILE = APP_DIR / "codex_traffic_light.config.json"
DEFAULT_ICON_FILE = APP_DIR / "codex_traffic_light.ico"
DEFAULT_PREVIEW_FILE = APP_DIR / "codex_traffic_light_preview.png"
DEFAULT_DARK_PREVIEW_FILE = APP_DIR / "codex_traffic_light_dark_preview.png"
WATCHER_EXE_FILE = APP_DIR / "CodexTrafficLightWatcher.exe"
WATCHER_LAUNCHER_FILE = APP_DIR / "CodexTrafficLightWatcher.vbs"
TRANSPARENT_COLOR = "#010203"
THEME = "dark"
WINDOW_BG = "#f4f6f8" if THEME == "light" else "#080a0f"

THEMES = {
    "light": {
        "window_bg": "#f4f6f8",
        "panel_outer": "#f7f9fc",
        "panel_inner": "#ffffff",
        "panel_outline": "#d7dde7",
        "title": "#0f172a",
        "body": "#334155",
        "footer_fill": "#eef2f7",
        "footer_outline": "#cbd5e1",
        "footer_text": "#475569",
        "row_active": "#ffffff",
        "row_inactive": "#eef2f6",
        "row_subtitle_active": "#232b36",
        "row_subtitle_inactive": "#5f6977",
        "row_title_inactive": "#485465",
        "lamp_shell": "#eef2f7",
        "lamp_shell_outline": "#b7c0cc",
        "lamp_inactive": "#f4f6f9",
        "lamp_inner_inactive": "#e8edf3",
        "button_min_fill": "#eef2f7",
        "button_min_outline": "#c5cedb",
        "button_min_stroke": "#334155",
        "button_close_fill": "#fff1f2",
        "button_close_outline": "#f0b7bd",
        "button_close_stroke": "#b42318",
        "active_text": {"attention": "#b42318", "running": "#9a6b00", "idle": "#15803d"},
    },
    "dark": {
        "window_bg": "#0b0f14",
        "panel_outer": "#101722",
        "panel_inner": "#141d2a",
        "panel_outline": "#334155",
        "title": "#f8fafc",
        "body": "#cbd5e1",
        "footer_fill": "#0f1722",
        "footer_outline": "#263545",
        "footer_text": "#a9b6c7",
        "row_active": "#172232",
        "row_inactive": "#121a25",
        "row_subtitle_active": "#d6dee9",
        "row_subtitle_inactive": "#8996a8",
        "row_title_inactive": "#aeb8c8",
        "lamp_shell": "#182231",
        "lamp_shell_outline": "#425267",
        "lamp_inactive": "#101822",
        "lamp_inner_inactive": "#1a2432",
        "button_min_fill": "#172232",
        "button_min_outline": "#475569",
        "button_min_stroke": "#cbd5e1",
        "button_close_fill": "#25161a",
        "button_close_outline": "#7f3640",
        "button_close_stroke": "#ff6b72",
        "active_text": {"attention": "#ff6b5f", "running": "#ffd44d", "idle": "#4ade80"},
    },
}

STATUS_ALIASES = {
    "green": "idle",
    "idle": "idle",
    "complete": "idle",
    "completed": "idle",
    "done": "idle",
    "\u7a7a\u95f2": "idle",
    "\u5b8c\u6210": "idle",
    "\u5df2\u5b8c\u6210": "idle",
    "yellow": "running",
    "running": "running",
    "busy": "running",
    "working": "running",
    "thinking": "running",
    "\u8fdb\u884c\u4e2d": "running",
    "\u8fd0\u884c\u4e2d": "running",
    "\u601d\u8003": "running",
    "\u601d\u8003\u4e2d": "running",
    "red": "attention",
    "attention": "attention",
    "approval": "attention",
    "approve": "attention",
    "error": "attention",
    "failed": "attention",
    "blocked": "attention",
    "\u5f02\u5e38": "attention",
    "\u5ba1\u6279": "attention",
    "\u9700\u5ba1\u6279": "attention",
    "\u9700\u8981\u5ba1\u6279": "attention",
}

LIGHTS = {
    "attention": {
        "name": "Needs attention",
        "label": "RED",
        "color": "#ff453a",
        "edge": "#ffc7c2",
        "glow": "#b7221c",
        "dim": "#3a1717",
        "dim_edge": "#78403d",
        "message": "Needs approval, error, or human intervention.",
    },
    "running": {
        "name": "Running",
        "label": "YELLOW",
        "color": "#ffd60a",
        "edge": "#fff6b8",
        "glow": "#b38400",
        "dim": "#3b320d",
        "dim_edge": "#7a691c",
        "message": "Task is running normally, or Codex is thinking.",
    },
    "idle": {
        "name": "Idle",
        "label": "GREEN",
        "color": "#32d74b",
        "edge": "#bdffc7",
        "glow": "#12a143",
        "dim": "#12351a",
        "dim_edge": "#2b6f3a",
        "message": "Task completed; Codex is idle.",
    },
}


@dataclass
class Status:
    state: str = "idle"
    message: str = LIGHTS["idle"]["message"]
    updated_at: str = ""


def normalize_state(raw: Any) -> str:
    if raw is None:
        return "idle"
    key = str(raw).strip().lower()
    return STATUS_ALIASES.get(key, "attention")


def now_text() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {"_load_error": f"Invalid JSON: {path.name}"}
    except OSError as exc:
        return {"_load_error": f"Cannot read {path.name}: {exc}"}


def save_json(path: Path, payload: dict[str, Any]) -> None:
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)


def trim_working_set() -> None:
    if sys.platform != "win32":
        return
    try:
        gc.collect()
        process = ctypes.windll.kernel32.GetCurrentProcess()
        ctypes.windll.psapi.EmptyWorkingSet(process)
    except Exception:
        pass


def launch_external_watcher() -> None:
    if sys.platform != "win32":
        return
    try:
        if WATCHER_EXE_FILE.exists():
            subprocess.Popen([str(WATCHER_EXE_FILE)], cwd=str(APP_DIR), close_fds=True, creationflags=CREATE_NO_WINDOW)
            return
        if WATCHER_LAUNCHER_FILE.exists():
            wscript = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "wscript.exe"
            if wscript.exists():
                subprocess.Popen([str(wscript), str(WATCHER_LAUNCHER_FILE)], cwd=str(APP_DIR), close_fds=True, creationflags=CREATE_NO_WINDOW)
    except OSError:
        pass


def save_app_config(path: Path, updates: dict[str, Any]) -> None:
    current = load_json(path)
    if "_load_error" in current:
        current = {}
    current.update(updates)
    save_json(path, current)


def clamp_display_size(value: Any) -> int:
    try:
        size = int(value)
    except (TypeError, ValueError):
        size = DEFAULT_DISPLAY_SIZE
    return max(MIN_DISPLAY_SIZE, min(MAX_DISPLAY_SIZE, size))


def read_status(path: Path, fallback: Status | None = None) -> Status:
    data = load_json(path)
    if "_load_error" in data:
        return fallback or Status(state="attention", message=str(data["_load_error"]))
    state = normalize_state(data.get("status", data.get("state", "idle")))
    message = str(data.get("message") or LIGHTS[state]["message"])
    updated_at = str(data.get("updated_at") or data.get("updated") or "")
    return Status(state=state, message=message, updated_at=updated_at)


def write_status(path: Path, state: str, message: str | None = None) -> None:
    normalized = normalize_state(state)
    save_json(
        path,
        {
            "status": normalized,
            "message": message or LIGHTS[normalized]["message"],
            "updated_at": now_text(),
        },
    )


def parse_event_time(raw: Any) -> float:
    if not raw:
        return 0.0
    try:
        text = str(raw).replace("Z", "+00:00")
        return datetime.fromisoformat(text).timestamp()
    except (TypeError, ValueError):
        return 0.0


def read_tail_lines(path: Path, max_bytes: int = SESSION_TAIL_BYTES) -> list[str]:
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            start = max(0, size - max_bytes)
            handle.seek(start)
            chunk = handle.read()
    except OSError:
        return []
    text = chunk.decode("utf-8", errors="replace")
    lines = text.splitlines()
    if start > 0 and lines:
        lines = lines[1:]
    return lines


class CodexSessionEventMonitor:
    """Read Codex Desktop session events; this is the authoritative local signal."""

    def __init__(
        self,
        session_dirs: list[Path] | None = None,
        scan_interval_seconds: float = SESSION_SCAN_INTERVAL_SECONDS,
    ) -> None:
        home = Path.home()
        self.session_dirs = session_dirs or [
            home / ".codex" / "sessions",
            home / ".codex" / "archived_sessions",
        ]
        self.scan_interval_seconds = scan_interval_seconds
        self.last_scan_at = 0.0
        self.cached_status: Status | None = None
        self.cached_event_time = 0.0

    def detect_status(self) -> Status | None:
        now = time.monotonic()
        if self.cached_status and now - self.last_scan_at < self.scan_interval_seconds:
            return self.cached_status
        self.last_scan_at = now
        self.cached_status, self.cached_event_time = self._scan()
        return self.cached_status

    def _session_files(self) -> list[Path]:
        cutoff = time.time() - SESSION_RECENT_SECONDS
        files: list[Path] = []
        for directory in self.session_dirs:
            if not directory.exists():
                continue
            try:
                for path in directory.rglob("rollout-*.jsonl"):
                    try:
                        if path.stat().st_mtime >= cutoff:
                            files.append(path)
                    except OSError:
                        continue
            except OSError:
                continue
        files.sort(key=lambda item: item.stat().st_mtime if item.exists() else 0.0, reverse=True)
        return files[:12]

    def _scan(self) -> tuple[Status | None, float]:
        best: tuple[float, str, str] | None = None
        attention: tuple[float, str, str] | None = None
        for path in self._session_files():
            state, message, event_time = self._classify_file(path)
            if not state:
                continue
            candidate = (event_time or path.stat().st_mtime, state, message)
            if state == "attention" and (attention is None or candidate[0] > attention[0]):
                attention = candidate
            if best is None or candidate[0] > best[0]:
                best = candidate
        chosen = attention or best
        if not chosen:
            return None, 0.0
        event_time, state, message = chosen
        return Status(state=state, message=message, updated_at=now_text()), event_time

    def _classify_file(self, path: Path) -> tuple[str | None, str, float]:
        pending_escalations: set[str] = set()
        last_state: str | None = None
        last_message = ""
        last_event_time = 0.0
        for line in read_tail_lines(path):
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            event_time = parse_event_time(event.get("timestamp")) or last_event_time
            event_type = event.get("type")
            payload = event.get("payload") or {}
            if event_time:
                last_event_time = event_time

            if event_type == "turn_context":
                last_state = "running"
                last_message = "Codex is preparing a turn."
            elif event_type == "event_msg":
                payload_type = payload.get("type")
                if payload_type == "task_complete":
                    pending_escalations.clear()
                    last_state = "idle"
                    last_message = "Task completed; Codex is idle."
                elif payload_type in {"agent_message", "token_count"}:
                    if last_state != "idle":
                        last_state = "running"
                        last_message = "Codex is running or thinking."
                elif payload_type in {"error", "turn_error", "tool_error"}:
                    last_state = "attention"
                    last_message = "Codex reported an error or needs intervention."
            elif event_type == "response_item":
                item_type = payload.get("type")
                if item_type == "function_call":
                    call_id = str(payload.get("call_id") or "")
                    arguments = str(payload.get("arguments") or "")
                    if '"sandbox_permissions":"require_escalated"' in arguments or "require_escalated" in arguments:
                        if call_id:
                            pending_escalations.add(call_id)
                        last_state = "attention"
                        last_message = "Codex is waiting for approval."
                    else:
                        last_state = "running"
                        last_message = "Codex is running a tool or command."
                elif item_type == "function_call_output":
                    call_id = str(payload.get("call_id") or "")
                    pending_escalations.discard(call_id)
                    last_state = "running"
                    last_message = "Codex is processing command results."
                elif item_type == "reasoning":
                    last_state = "running"
                    last_message = "Codex is thinking."
                elif item_type == "message":
                    role = payload.get("role")
                    if role == "user":
                        last_state = "running"
                        last_message = "Codex received a task."
                    elif role == "assistant":
                        phase = payload.get("phase")
                        if phase == "final_answer":
                            last_state = "running"
                            last_message = "Codex is finishing the response."
                        else:
                            last_state = "running"
                            last_message = "Codex is responding."

        if pending_escalations:
            return "attention", "Codex is waiting for approval.", last_event_time
        return last_state, last_message, last_event_time


def hex_to_rgba(color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16), alpha


def mix_rgba(color: str, other: str, amount: float, alpha: int = 255) -> tuple[int, int, int, int]:
    a = hex_to_rgba(color)
    b = hex_to_rgba(other)
    return (
        int(a[0] + (b[0] - a[0]) * amount),
        int(a[1] + (b[1] - a[1]) * amount),
        int(a[2] + (b[2] - a[2]) * amount),
        alpha,
    )


def theme_style(theme: str | None = None) -> dict[str, Any]:
    return THEMES.get((theme or THEME).lower(), THEMES["light"])


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return mask


def draw_centered_text(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    text_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int, int],
) -> None:
    text_box = draw.textbbox((0, 0), text, font=text_font)
    text_width = text_box[2] - text_box[0]
    text_height = text_box[3] - text_box[1]
    x = box[0] + (box[2] - box[0] - text_width) // 2
    y = box[1] + (box[3] - box[1] - text_height) // 2 - text_box[1]
    draw.text((x, y), text, font=text_font, fill=fill)


def window_button_size(width: int) -> int:
    size = max(14, int(width * 0.058))
    return size


def close_button_rect(width: int, height: int) -> tuple[int, int, int, int]:
    size = window_button_size(width)
    margin_x = max(28, int(width * 0.090))
    margin_y = max(20, int(width * 0.065))
    return (width - margin_x - size, margin_y, width - margin_x, margin_y + size)


def minimize_button_rect(width: int, height: int) -> tuple[int, int, int, int]:
    size = window_button_size(width)
    margin_x = max(28, int(width * 0.090))
    margin_y = max(20, int(width * 0.065))
    gap = max(8, int(width * 0.028))
    right = width - margin_x - size - gap
    return (right - size, margin_y, right, margin_y + size)


def title_toggle_rect(width: int, height: int) -> tuple[int, int, int, int]:
    unit = width / 3.95
    return (
        int(unit * 0.30),
        int(unit * 0.25),
        int(unit * 1.34),
        int(unit * 0.78),
    )


def resize_handle_rect(width: int, height: int) -> tuple[int, int, int, int]:
    handle = max(22, int(width * 0.095))
    inset = max(12, int(width * 0.035))
    return (width - inset - handle, height - inset - handle, width - inset, height - inset)


def draw_resize_grip(image: Image.Image, theme: str = "light") -> None:
    draw = ImageDraw.Draw(image)
    style = theme_style(theme)
    x1, y1, x2, y2 = resize_handle_rect(image.width, image.height)
    color = hex_to_rgba(style["footer_text"], 120 if theme == "dark" else 105)
    step = max(5, (x2 - x1) // 5)
    width = max(1, image.width // 200)
    for index in range(3):
        offset = step * index
        draw.line(
            (x2 - step - offset, y2, x2, y2 - step - offset),
            fill=color,
            width=width,
        )


def draw_window_button(image: Image.Image, box: tuple[int, int, int, int], kind: str, theme: str = "light") -> None:
    draw = ImageDraw.Draw(image)
    x1, y1, x2, y2 = box
    radius = (y2 - y1) // 2
    style = theme_style(theme)
    if kind == "close":
        fill = style["button_close_fill"]
        outline = style["button_close_outline"]
        stroke = style["button_close_stroke"]
    else:
        fill = style["button_min_fill"]
        outline = style["button_min_outline"]
        stroke = style["button_min_stroke"]
    draw.rounded_rectangle(
        box,
        radius=radius,
        fill=hex_to_rgba(fill, 245),
        outline=hex_to_rgba(outline),
        width=max(2, image.width // 170),
    )
    pad = int((x2 - x1) * 0.30)
    stroke_width = max(2, image.width // 135)
    if kind == "close":
        draw.line((x1 + pad, y1 + pad, x2 - pad, y2 - pad), fill=hex_to_rgba(stroke), width=stroke_width)
        draw.line((x2 - pad, y1 + pad, x1 + pad, y2 - pad), fill=hex_to_rgba(stroke), width=stroke_width)
    else:
        line_y = y1 + int((y2 - y1) * 0.58)
        draw.line((x1 + pad, line_y, x2 - pad, line_y), fill=hex_to_rgba(stroke), width=stroke_width)


def draw_window_controls(image: Image.Image, theme: str = "light") -> None:
    draw_window_button(image, minimize_button_rect(image.width, image.height), "minimize", theme)
    draw_window_button(image, close_button_rect(image.width, image.height), "close", theme)


def draw_soft_glow(
    image: Image.Image,
    center: tuple[int, int],
    radius: int,
    color: str,
    alpha: int,
    blur: int,
) -> None:
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    x, y = center
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=hex_to_rgba(color, alpha))
    image.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))


def draw_screw(draw: ImageDraw.ImageDraw, x: int, y: int, radius: int) -> None:
    draw.ellipse(
        (x - radius, y - radius, x + radius, y + radius),
        fill=hex_to_rgba("#c9b28f"),
        outline=hex_to_rgba("#f0dec2"),
        width=max(1, radius // 4),
    )
    inner = max(2, int(radius * 0.52))
    draw.ellipse(
        (x - inner, y - inner, x + inner, y + inner),
        fill=hex_to_rgba("#4d4033"),
        outline=hex_to_rgba("#211b16"),
        width=max(1, radius // 5),
    )
    slot = max(1, radius // 5)
    draw.line(
        (x - int(radius * 0.58), y + slot, x + int(radius * 0.58), y - slot),
        fill=hex_to_rgba("#f7e6c9", 180),
        width=max(1, radius // 5),
    )


def draw_led_texture(
    image: Image.Image,
    center: tuple[int, int],
    radius: int,
    color: str,
    active: bool,
) -> None:
    if not active:
        return
    x, y = center
    draw = ImageDraw.Draw(image)
    dot_gap = max(7, radius // 6)
    dot_radius = max(1, radius // 38)
    dot_fill = mix_rgba(color, "#ffffff", 0.72, 255)
    for yy in range(y - radius + dot_gap, y + radius, dot_gap):
        row_offset = 0 if ((yy - y) // dot_gap) % 2 == 0 else dot_gap // 2
        for xx in range(x - radius + dot_gap + row_offset, x + radius, dot_gap):
            if (xx - x) ** 2 + (yy - y) ** 2 < (radius * 0.86) ** 2:
                draw.ellipse(
                    (xx - dot_radius, yy - dot_radius, xx + dot_radius, yy + dot_radius),
                    fill=dot_fill,
                )


def draw_expression(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    radius: int,
    state: str,
    active: bool,
) -> None:
    x, y = center
    alpha = 198 if active else 84
    color = (26, 22, 22, alpha)
    width = max(3, radius // 10)
    eye_r = max(3, radius // 10)

    if state == "idle":
        draw.ellipse((x - int(radius * 0.38) - eye_r, y - int(radius * 0.24) - eye_r, x - int(radius * 0.38) + eye_r, y - int(radius * 0.24) + eye_r), fill=color)
        draw.ellipse((x + int(radius * 0.38) - eye_r, y - int(radius * 0.24) - eye_r, x + int(radius * 0.38) + eye_r, y - int(radius * 0.24) + eye_r), fill=color)
        draw.arc(
            (x - int(radius * 0.52), y - int(radius * 0.04), x + int(radius * 0.52), y + int(radius * 0.55)),
            start=18,
            end=162,
            fill=color,
            width=width,
        )
        return

    brow_y = y - int(radius * 0.30)
    eye_y = y - int(radius * 0.16)
    draw.line(
        (x - int(radius * 0.50), brow_y - int(radius * 0.12), x - int(radius * 0.18), brow_y + int(radius * 0.10)),
        fill=color,
        width=width,
    )
    draw.line(
        (x + int(radius * 0.50), brow_y - int(radius * 0.12), x + int(radius * 0.18), brow_y + int(radius * 0.10)),
        fill=color,
        width=width,
    )
    draw.ellipse((x - int(radius * 0.34) - eye_r, eye_y - eye_r, x - int(radius * 0.34) + eye_r, eye_y + eye_r), fill=color)
    draw.ellipse((x + int(radius * 0.34) - eye_r, eye_y - eye_r, x + int(radius * 0.34) + eye_r, eye_y + eye_r), fill=color)
    draw.arc(
        (x - int(radius * 0.52), y + int(radius * 0.18), x + int(radius * 0.52), y + int(radius * 0.72)),
        start=200,
        end=340,
        fill=color,
        width=width,
    )


def draw_module(
    image: Image.Image,
    box: tuple[int, int, int, int],
    state: str,
    active: bool,
) -> None:
    draw = ImageDraw.Draw(image)
    x1, y1, x2, y2 = box
    width = x2 - x1
    height = y2 - y1
    radius = max(12, int(width * 0.08))

    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle(
        (
            x1 + int(width * 0.018),
            y1 + int(height * 0.026),
            x2 + int(width * 0.018),
            y2 + int(height * 0.026),
        ),
        radius=radius,
        fill=(0, 0, 0, 96),
    )
    image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(max(4, width // 52))))

    draw.rounded_rectangle(
        box,
        radius=radius,
        fill=hex_to_rgba("#151414"),
        outline=hex_to_rgba("#6c665d"),
        width=max(3, width // 38),
    )
    inset = max(6, width // 18)
    draw.rounded_rectangle(
        (x1 + inset, y1 + inset, x2 - inset, y2 - inset),
        radius=max(8, radius - inset // 2),
        fill=hex_to_rgba("#08090c"),
        outline=hex_to_rgba("#292a30"),
        width=max(2, width // 70),
    )
    draw.line(
        (x1 + inset * 2, y1 + inset + 1, x2 - inset * 2, y1 + inset + 1),
        fill=hex_to_rgba("#55545a", 96),
        width=max(1, width // 110),
    )

    screw_r = max(5, width // 24)
    screw_pad = inset + screw_r
    for sx, sy in (
        (x1 + screw_pad, y1 + screw_pad),
        (x2 - screw_pad, y1 + screw_pad),
        (x1 + screw_pad, y2 - screw_pad),
        (x2 - screw_pad, y2 - screw_pad),
    ):
        draw_screw(draw, sx, sy, screw_r)

    cx = (x1 + x2) // 2
    cy = y1 + int(height * 0.53)
    lens_radius = int(min(width, height) * 0.34)
    draw_bulb(image, (cx, cy), lens_radius, state, active)


def draw_bulb(
    image: Image.Image,
    center: tuple[int, int],
    radius: int,
    state: str,
    active: bool,
) -> None:
    draw = ImageDraw.Draw(image)
    light = LIGHTS[state]
    color = light["color"] if active else light["dim"]
    edge = light["edge"] if active else light["dim_edge"]

    if active:
        draw_soft_glow(image, center, int(radius * 1.70), light["glow"], 160, max(8, radius // 4))
        draw_soft_glow(image, center, int(radius * 1.08), light["color"], 100, max(5, radius // 7))

    x, y = center
    hood = radius + int(radius * 0.22)
    draw.ellipse(
        (
            x - hood - int(radius * 0.05),
            y - hood + int(radius * 0.12),
            x + hood + int(radius * 0.05),
            y + hood + int(radius * 0.16),
        ),
        fill=hex_to_rgba("#020306"),
    )
    draw.pieslice(
        (x - hood, y - hood - int(radius * 0.22), x + hood, y + hood),
        start=180,
        end=360,
        fill=hex_to_rgba("#050608"),
    )
    draw.arc(
        (x - hood, y - hood - int(radius * 0.22), x + hood, y + hood),
        start=180,
        end=360,
        fill=hex_to_rgba("#1f242b"),
        width=max(3, radius // 12),
    )

    recess = radius + int(radius * 0.18)
    draw.ellipse(
        (x - recess, y - recess, x + recess, y + recess),
        fill=hex_to_rgba("#07090e"),
        outline=hex_to_rgba("#252b35"),
        width=max(2, radius // 9),
    )
    draw.ellipse(
        (x - radius, y - radius, x + radius, y + radius),
        fill=hex_to_rgba(color),
        outline=hex_to_rgba(edge),
        width=max(2, radius // 11),
    )

    inner = int(radius * 0.72)
    draw.ellipse(
        (x - inner, y - inner, x + inner, y + inner),
        fill=mix_rgba(color, "#ffffff", 0.20 if active else 0.06, 70 if active else 42),
    )
    draw.arc(
        (x - radius + 4, y - radius + 4, x + radius - 4, y + radius - 4),
        start=38,
        end=155,
        fill=mix_rgba(edge, "#ffffff", 0.1, 230 if active else 90),
        width=max(2, radius // 12),
    )
    draw.arc(
        (x - radius + 5, y - radius + 5, x + radius - 5, y + radius - 5),
        start=198,
        end=324,
        fill=mix_rgba(color, "#020307", 0.66, 118 if active else 190),
        width=max(2, radius // 13 if active else radius // 10),
    )

    shine_w = int(radius * 0.48)
    shine_h = int(radius * 0.34)
    shine = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shine_draw = ImageDraw.Draw(shine)
    shine_draw.ellipse(
        (
            x - int(radius * 0.48),
            y - int(radius * 0.58),
            x - int(radius * 0.48) + shine_w,
            y - int(radius * 0.58) + shine_h,
        ),
        fill=(255, 255, 255, 210 if active else 92),
    )
    image.alpha_composite(shine.filter(ImageFilter.GaussianBlur(max(1, radius // 24))))
    draw_expression(draw, center, radius, state, active)


def draw_indicator_lamp(
    image: Image.Image,
    center: tuple[int, int],
    radius: int,
    state: str,
    active: bool,
    theme: str = "light",
) -> None:
    draw = ImageDraw.Draw(image)
    light = LIGHTS[state]
    style = theme_style(theme)
    base = light["color"] if active else light["dim"]
    edge = light["edge"] if active else light["dim_edge"]
    x, y = center

    if active:
        draw_soft_glow(image, center, int(radius * 1.95), light["glow"], 115, max(8, radius // 2))
        draw_soft_glow(image, center, int(radius * 1.18), light["color"], 90, max(4, radius // 4))

    draw.ellipse(
        (x - radius - radius // 4, y - radius - radius // 4, x + radius + radius // 4, y + radius + radius // 4),
        fill=hex_to_rgba(style["lamp_shell"]),
        outline=hex_to_rgba(style["lamp_shell_outline"]),
        width=max(2, radius // 8),
    )
    draw.ellipse(
        (x - radius, y - radius, x + radius, y + radius),
        fill=hex_to_rgba(base if active else style["lamp_inactive"]),
        outline=hex_to_rgba(edge),
        width=max(2, radius // 9),
    )
    inner = int(radius * 0.68)
    draw.ellipse(
        (x - inner, y - inner, x + inner, y + inner),
        fill=mix_rgba(base if active else style["lamp_inner_inactive"], "#ffffff", 0.22 if active else 0.20, 130 if active else 105),
    )
    draw.ellipse(
        (
            x - int(radius * 0.42),
            y - int(radius * 0.52),
            x - int(radius * 0.02),
            y - int(radius * 0.22),
        ),
        fill=(255, 255, 255, 205 if active else 78),
    )


def draw_status_row(
    image: Image.Image,
    box: tuple[int, int, int, int],
    state: str,
    active: bool,
    theme: str = "light",
) -> tuple[int, int]:
    draw = ImageDraw.Draw(image)
    x1, y1, x2, y2 = box
    width = x2 - x1
    height = y2 - y1
    light = LIGHTS[state]
    style = theme_style(theme)
    radius = max(14, int(height * 0.24))
    row_radius = max(12, int(height * 0.22))
    strong_text = style["active_text"]

    if active:
        glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow)
        glow_draw.rounded_rectangle(
            box,
            radius=row_radius,
            fill=hex_to_rgba(light["glow"], 68),
        )
        image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(max(5, height // 7))))

    row_fill = style["row_active"] if active else style["row_inactive"]
    subtitle_fill = style["row_subtitle_active"] if active else style["row_subtitle_inactive"]
    title_fill = strong_text[state] if active else style["row_title_inactive"]
    draw.rounded_rectangle(
        box,
        radius=row_radius,
        fill=hex_to_rgba(row_fill, 255),
        outline=mix_rgba(light["color"], "#6b7280", 0.16 if active else 0.58),
        width=max(2, height // 20 if active else height // 28),
    )
    lamp_center = (x1 + int(width * 0.18), y1 + height // 2)
    draw_indicator_lamp(image, lamp_center, radius, state, active, theme)

    label_map = {
        "attention": ("RED", "Approval or intervention"),
        "running": ("YELLOW", "Running or thinking"),
        "idle": ("GREEN", "Completed and idle"),
    }
    title, subtitle = label_map[state]
    text_x = x1 + int(width * 0.35)
    title_y = y1 + int(height * 0.20)
    subtitle_y = y1 + int(height * 0.54)
    draw.text(
        (text_x, title_y),
        title,
        font=font(max(15, height // 4), bold=True),
        fill=hex_to_rgba(title_fill),
    )
    draw.text(
        (text_x, subtitle_y),
        subtitle,
        font=font(max(10, height // 7), bold=active),
        fill=hex_to_rgba(subtitle_fill),
    )
    return lamp_center


def render_traffic_light(status_state: str, size: int = 58, scale: int = 5, theme: str = "light") -> Image.Image:
    width = int(size * 3.95)
    height = int(size * 5.45)
    sw, sh = width * scale, height * scale
    unit = size * scale
    style = theme_style(theme)
    image = Image.new("RGBA", (sw, sh), hex_to_rgba(style["window_bg"]))
    draw = ImageDraw.Draw(image)

    cx = sw // 2
    outer_pad = int(unit * 0.05)
    outer_radius = int(unit * 0.28)
    panel = (outer_pad, outer_pad, sw - outer_pad, sh - outer_pad)
    draw.rounded_rectangle(
        panel,
        radius=outer_radius,
        fill=hex_to_rgba(style["panel_outer"]),
    )
    draw.rounded_rectangle(
        (
            panel[0] + int(unit * 0.085),
            panel[1] + int(unit * 0.085),
            panel[2] - int(unit * 0.085),
            panel[3] - int(unit * 0.085),
        ),
        radius=max(10, outer_radius - int(unit * 0.045)),
        fill=hex_to_rgba(style["panel_inner"]),
        outline=hex_to_rgba(style["panel_outline"]),
        width=max(2, unit // 32),
    )

    active = LIGHTS[status_state]
    active_text = style["active_text"][status_state]
    header_y = int(unit * 0.34)
    draw.text(
        (int(unit * 0.42), header_y),
        "CODEX",
        font=font(max(18, int(unit * 0.25)), bold=True),
        fill=hex_to_rgba(style["title"]),
    )
    badge_box = (
        sw - int(unit * 2.10),
        header_y + int(unit * 0.24),
        sw - int(unit * 0.90),
        header_y + int(unit * 0.77),
    )
    draw.rounded_rectangle(
        badge_box,
        radius=int(unit * 0.18),
        fill=mix_rgba(active["color"], style["panel_inner"], 0.58 if theme == "dark" else 0.66, 255),
        outline=mix_rgba(active["color"], style["panel_outline"], 0.20),
        width=max(2, unit // 42),
    )
    draw_centered_text(
        draw,
        badge_box,
        active["label"],
        font(max(14, int(unit * 0.17)), bold=True),
        hex_to_rgba(active_text),
    )
    draw.text(
        (int(unit * 0.42), int(unit * 0.88)),
        active["name"],
        font=font(max(14, int(unit * 0.18)), bold=True),
        fill=hex_to_rgba(active_text),
    )
    draw.text(
        (int(unit * 0.42), int(unit * 1.18)),
        active["message"],
        font=font(max(10, int(unit * 0.11)), bold=True),
        fill=hex_to_rgba(style["body"]),
    )

    row_w = int(unit * 3.15)
    row_h = int(unit * 0.86)
    row_gap = int(unit * 0.21)
    row_x = cx - row_w // 2
    row_y = int(unit * 1.70)
    centers: dict[str, tuple[int, int]] = {}
    for index, state in enumerate(("attention", "running", "idle")):
        y1 = row_y + index * (row_h + row_gap)
        centers[state] = draw_status_row(
            image,
            (row_x, y1, row_x + row_w, y1 + row_h),
            state,
            state == status_state,
            theme,
        )

    footer_box = (
        int(unit * 0.42),
        sh - int(unit * 0.60),
        sw - int(unit * 0.42),
        sh - int(unit * 0.25),
    )
    draw.rounded_rectangle(
        footer_box,
        radius=int(unit * 0.14),
        fill=hex_to_rgba(style["footer_fill"]),
        outline=hex_to_rgba(style["footer_outline"]),
        width=max(1, unit // 64),
    )
    draw_centered_text(
        draw,
        footer_box,
        "Right-click: change status   Double-click: cycle",
        font(max(8, int(unit * 0.09)), bold=True),
        hex_to_rgba(style["footer_text"]),
    )
    draw_window_controls(image, theme)
    draw_resize_grip(image, theme)

    return image.resize((width, height), Image.Resampling.LANCZOS)


def apply_rounded_window(root: tk.Tk, width: int, height: int) -> None:
    if sys.platform != "win32":
        return
    try:
        radius = max(22, int(min(width, height) * 0.14))
        hwnd = root.winfo_id()
        region = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, width + 1, height + 1, radius, radius)
        ctypes.windll.user32.SetWindowRgn(hwnd, region, True)
    except Exception:
        pass


def enable_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", wintypes.DWORD * 3),
    ]


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [
        ("hdc", wintypes.HDC),
        ("fErase", wintypes.BOOL),
        ("rcPaint", wintypes.RECT),
        ("fRestore", wintypes.BOOL),
        ("fIncUpdate", wintypes.BOOL),
        ("rgbReserved", ctypes.c_byte * 32),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HANDLE),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uTimeoutOrVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", GUID),
        ("hBalloonIcon", wintypes.HANDLE),
    ]


class FILETIME(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", wintypes.DWORD),
        ("dwHighDateTime", wintypes.DWORD),
    ]


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


def loword(value: int) -> int:
    return value & 0xFFFF


def hiword(value: int) -> int:
    return (value >> 16) & 0xFFFF


def filetime_value(value: FILETIME) -> int:
    return (int(value.dwHighDateTime) << 32) + int(value.dwLowDateTime)


def is_codex_main_process(name: str) -> bool:
    lower = name.lower()
    stem = Path(lower).stem
    return lower in CODEX_PROCESS_NAMES or stem in CODEX_PROCESS_NAMES


def is_codex_activity_process(name: str) -> bool:
    lower = name.lower()
    stem = Path(lower).stem
    if is_codex_main_process(lower):
        return True
    return any(stem.startswith(prefix) or lower.startswith(prefix) for prefix in CODEX_ACTIVITY_PREFIXES)


def list_process_names() -> set[str]:
    if sys.platform != "win32":
        return set()
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        return set()
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    names: set[str] = set()
    try:
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            names.add(entry.szExeFile.lower())
            names.add(Path(entry.szExeFile).stem.lower())
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return names


def list_process_cpu_times() -> dict[int, tuple[str, int]]:
    if sys.platform != "win32":
        return {}
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.restype = wintypes.BOOL
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetProcessTimes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
    ]
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        return {}

    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    processes: dict[int, tuple[str, int]] = {}
    try:
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            name = entry.szExeFile
            if is_codex_activity_process(name):
                handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, entry.th32ProcessID)
                if handle:
                    create_time = FILETIME()
                    exit_time = FILETIME()
                    kernel_time = FILETIME()
                    user_time = FILETIME()
                    if kernel32.GetProcessTimes(
                        handle,
                        ctypes.byref(create_time),
                        ctypes.byref(exit_time),
                        ctypes.byref(kernel_time),
                        ctypes.byref(user_time),
                    ):
                        processes[int(entry.th32ProcessID)] = (
                            name.lower(),
                            filetime_value(kernel_time) + filetime_value(user_time),
                        )
                    kernel32.CloseHandle(handle)
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return processes


def codex_is_running(process_names: set[str] | None = None) -> bool:
    names = process_names or list_process_names()
    return any(name.lower() in names for name in CODEX_PROCESS_NAMES)


def write_status_with_mirror(path: Path, state: str, message: str) -> None:
    write_status(path, state, message)
    dist_path = path.parent / "dist" / path.name
    if dist_path != path and dist_path.parent.exists():
        write_status(dist_path, state, message)


def status_age_seconds(status: Status) -> float | None:
    if not status.updated_at:
        return None
    try:
        updated = time.mktime(time.strptime(status.updated_at, "%Y-%m-%d %H:%M:%S"))
    except ValueError:
        return None
    return max(0.0, time.time() - updated)


def auto_set_status(path: Path, state: str, message: str) -> None:
    current = read_status(path)
    if current.state == "attention" and state != "attention":
        return
    if current.state == normalize_state(state) and current.message == message:
        return
    write_status_with_mirror(path, state, message)


class CodexActivityMonitor:
    def __init__(
        self,
        status_file: Path,
        idle_after_seconds: float = DEFAULT_IDLE_AFTER_SECONDS,
        running_hold_seconds: float = DEFAULT_RUNNING_HOLD_SECONDS,
        attention_hold_seconds: float = DEFAULT_ATTENTION_HOLD_SECONDS,
    ) -> None:
        self.status_file = status_file
        self.idle_after_seconds = idle_after_seconds
        self.running_hold_seconds = running_hold_seconds
        self.attention_hold_seconds = attention_hold_seconds
        self.session_monitor = CodexSessionEventMonitor()
        self.previous_cpu = list_process_cpu_times()
        self.last_active_at = time.monotonic() if codex_is_running() else 0.0

    def tick(self) -> None:
        session_status = self.session_monitor.detect_status()
        if session_status:
            current = read_status(self.status_file)
            if current.state != session_status.state or current.message != session_status.message:
                write_status_with_mirror(self.status_file, session_status.state, session_status.message)
            return

        current = read_status(self.status_file)
        if current.state == "attention":
            return

        current_cpu = list_process_cpu_times()
        codex_running = codex_is_running()
        active = codex_running and (
            has_recent_codex_activity(self.previous_cpu, current_cpu)
            or has_codex_command_runner(current_cpu)
        )
        recent_running = (
            current.state == "running"
            and (status_age_seconds(current) or 0.0) <= self.running_hold_seconds
        )

        if active or recent_running:
            self.last_active_at = time.monotonic()
            if current.state != "running":
                write_status_with_mirror(self.status_file, "running", "Codex is thinking or running.")
        elif codex_running and self.last_active_at and time.monotonic() - self.last_active_at < self.idle_after_seconds:
            if current.state != "running":
                write_status_with_mirror(self.status_file, "running", "Codex is thinking or running.")
        elif codex_running:
            if current.state != "idle":
                write_status_with_mirror(self.status_file, "idle", "Codex is idle.")
            self.last_active_at = 0.0
        else:
            if current.state != "idle":
                write_status_with_mirror(self.status_file, "idle", "Codex is idle.")
            self.last_active_at = 0.0

        self.previous_cpu = current_cpu


def existing_traffic_window() -> int:
    if sys.platform != "win32":
        return 0
    user32 = ctypes.windll.user32
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND
    hwnd = user32.FindWindowW(NativeTrafficLightApp.CLASS_NAME, None)
    return int(hwnd or 0)


def activate_existing_window() -> bool:
    hwnd = existing_traffic_window()
    if not hwnd:
        return False
    user32 = ctypes.windll.user32
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.ShowWindow(hwnd, SW_SHOWNORMAL)
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
    user32.SetForegroundWindow(hwnd)
    return True


def launch_traffic_light_window() -> None:
    if activate_existing_window():
        return
    if getattr(sys, "frozen", False):
        command = [sys.executable]
    else:
        python_exe = Path(sys.executable)
        pythonw = python_exe.with_name("pythonw.exe")
        command = [str(pythonw if pythonw.exists() else python_exe), str(Path(__file__).resolve())]
    subprocess.Popen(command, close_fds=True, creationflags=CREATE_NO_WINDOW)


def has_recent_codex_activity(
    previous: dict[int, tuple[str, int]],
    current: dict[int, tuple[str, int]],
    cpu_threshold_100ns: int = 50000,
) -> bool:
    for pid, (name, current_time) in current.items():
        if not is_codex_activity_process(name):
            continue
        previous_time = previous.get(pid, (name, current_time))[1]
        if current_time - previous_time >= cpu_threshold_100ns:
            return True
    return False


def has_codex_command_runner(current: dict[int, tuple[str, int]]) -> bool:
    for name, _cpu_time in current.values():
        lower = name.lower()
        stem = Path(lower).stem
        if any(stem.startswith(prefix) or lower.startswith(prefix) for prefix in CODEX_ACTIVITY_PREFIXES):
            return True
    return False


def watch_codex(
    poll_seconds: float = 2.0,
    once: bool = False,
    status_file: Path = DEFAULT_STATUS_FILE,
    idle_after_seconds: float = DEFAULT_IDLE_AFTER_SECONDS,
) -> int:
    lock_handle = None
    if sys.platform == "win32" and msvcrt is not None and not once:
        lock_path = APP_DIR / "codex_traffic_light_watcher.lock"
        try:
            lock_handle = lock_path.open("a+b")
            if lock_handle.tell() == 0:
                lock_handle.write(b"\0")
                lock_handle.flush()
            lock_handle.seek(0)
            msvcrt.locking(lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            try:
                if lock_handle:
                    lock_handle.close()
            except OSError:
                pass
            return 0

    mutex_handle = None
    if sys.platform == "win32" and not once:
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.GetLastError.restype = wintypes.DWORD
        mutex_handle = kernel32.CreateMutexW(None, True, "Local\\CodexTrafficLightWatcher")
        if mutex_handle and kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            return 0

    previous_cpu = list_process_cpu_times()
    codex_was_running = codex_is_running()
    last_active_at = time.monotonic() if codex_was_running else 0.0
    if codex_was_running:
        launch_traffic_light_window()
        auto_set_status(status_file, "running", "Codex is starting or active.")
        if once:
            return 0
    while True:
        current_cpu = list_process_cpu_times()
        codex_running = codex_is_running()
        active = codex_running and (
            has_recent_codex_activity(previous_cpu, current_cpu)
            or has_codex_command_runner(current_cpu)
        )
        if codex_running and not codex_was_running:
            launch_traffic_light_window()
            auto_set_status(status_file, "running", "Codex started; task may be active.")
            if once:
                return 0
        elif active:
            last_active_at = time.monotonic()
            auto_set_status(status_file, "running", "Codex is thinking or running.")
        elif codex_running and last_active_at and time.monotonic() - last_active_at >= idle_after_seconds:
            auto_set_status(status_file, "idle", "Codex is idle.")
            last_active_at = 0.0
        elif not codex_running:
            last_active_at = 0.0
        codex_was_running = codex_running
        previous_cpu = current_cpu
        if once:
            return 1
        time.sleep(poll_seconds)


class NativeTrafficLightApp:
    CLASS_NAME = "CodexTrafficLightNativeWindow"

    def __init__(
        self,
        status_file: Path,
        config_file: Path,
        size: int,
        opacity: float,
        poll_ms: int,
        theme: str = "light",
        auto_detect: bool = True,
        smoke_test_ms: int | None = None,
    ) -> None:
        self.user32 = ctypes.windll.user32
        self.gdi32 = ctypes.windll.gdi32
        self.kernel32 = ctypes.windll.kernel32
        self.shell32 = ctypes.windll.shell32
        self._configure_win32_api()
        self.status_file = status_file
        self.config_file = config_file
        self.size = max(36, size)
        self.opacity = min(1.0, max(0.25, opacity))
        self.poll_ms = max(100, poll_ms)
        self.theme = theme
        self.auto_detect = auto_detect
        self.activity_monitor = CodexActivityMonitor(status_file) if auto_detect else None
        self.codex_seen = codex_is_running()
        self.codex_missing_since = 0.0
        self.auto_close_on_codex_exit = auto_detect and smoke_test_ms is None
        self.restart_watcher_on_destroy = False
        self.status = Status()
        self.last_mtime = 0.0
        self.hwnd = None
        self.width = 0
        self.height = 0
        self.pixel_data = b""
        self.bitmap_info = None
        self._wndproc = None
        self.resizing = False
        self.resize_start_point = POINT(0, 0)
        self.resize_start_size = self.size
        self.arrow_cursor = None
        self.resize_cursor = None
        self.tray_icon = None
        self.tray_added = False

        sample = render_traffic_light("idle", self.size, theme=self.theme)
        self.width, self.height = sample.size
        self._ensure_status_file()
        self._register_class()
        self._create_window()
        self._poll_status(force=True)
        if smoke_test_ms:
            self.user32.SetTimer(self.hwnd, 2, smoke_test_ms, None)

    def _configure_win32_api(self) -> None:
        self.kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        self.kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        self.user32.LoadIconW.restype = wintypes.HANDLE
        self.user32.LoadCursorW.restype = wintypes.HANDLE
        self.user32.LoadImageW.restype = wintypes.HANDLE
        self.user32.SetCursor.argtypes = [wintypes.HANDLE]
        self.user32.SetCursor.restype = wintypes.HANDLE
        self.user32.RegisterClassW.restype = wintypes.ATOM
        self.user32.CreateWindowExW.argtypes = [
            wintypes.DWORD,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.HWND,
            wintypes.HMENU,
            wintypes.HINSTANCE,
            wintypes.LPVOID,
        ]
        self.user32.CreateWindowExW.restype = wintypes.HWND
        self.user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        self.user32.DefWindowProcW.restype = LRESULT
        self.user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        self.user32.SendMessageW.restype = LRESULT
        self.user32.SetWindowPos.argtypes = [
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        self.user32.SetWindowPos.restype = wintypes.BOOL
        self.user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        self.user32.GetMessageW.restype = wintypes.BOOL
        self.user32.BeginPaint.argtypes = [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]
        self.user32.BeginPaint.restype = wintypes.HDC
        self.user32.EndPaint.argtypes = [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]
        self.user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        self.user32.GetWindowRect.restype = wintypes.BOOL
        self.user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
        self.user32.GetCursorPos.restype = wintypes.BOOL
        self.user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(POINT)]
        self.user32.ClientToScreen.restype = wintypes.BOOL
        self.user32.SetCapture.argtypes = [wintypes.HWND]
        self.user32.SetCapture.restype = wintypes.HWND
        self.user32.ReleaseCapture.argtypes = []
        self.user32.ReleaseCapture.restype = wintypes.BOOL
        self.gdi32.SetDIBitsToDevice.argtypes = [
            wintypes.HDC,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
            wintypes.UINT,
            wintypes.LPCVOID,
            ctypes.POINTER(BITMAPINFO),
            wintypes.UINT,
        ]
        self.gdi32.SetDIBitsToDevice.restype = ctypes.c_int
        self.user32.SetTimer.argtypes = [wintypes.HWND, UINT_PTR, wintypes.UINT, wintypes.LPVOID]
        self.user32.KillTimer.argtypes = [wintypes.HWND, UINT_PTR]
        self.user32.TrackPopupMenu.restype = wintypes.UINT
        self.shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
        self.shell32.Shell_NotifyIconW.restype = wintypes.BOOL
        self.arrow_cursor = self.user32.LoadCursorW(None, IDC_ARROW)
        self.resize_cursor = self.user32.LoadCursorW(None, IDC_SIZENWSE)

    def _register_class(self) -> None:
        WNDPROC = ctypes.WINFUNCTYPE(
            LRESULT,
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        )
        self._wndproc = WNDPROC(self._window_proc)

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [
                ("style", wintypes.UINT),
                ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HANDLE),
                ("hIcon", wintypes.HANDLE),
                ("hCursor", wintypes.HANDLE),
                ("hbrBackground", wintypes.HANDLE),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
            ]

        hinstance = self.kernel32.GetModuleHandleW(None)
        wc = WNDCLASSW()
        wc.style = 0x0008  # CS_DBLCLKS
        wc.lpfnWndProc = self._wndproc
        wc.cbClsExtra = 0
        wc.cbWndExtra = 0
        wc.hInstance = hinstance
        wc.hIcon = self.user32.LoadIconW(None, IDC_ARROW)
        wc.hCursor = self.arrow_cursor or self.user32.LoadCursorW(None, IDC_ARROW)
        wc.hbrBackground = None
        wc.lpszMenuName = None
        wc.lpszClassName = self.CLASS_NAME
        self.user32.RegisterClassW(ctypes.byref(wc))

    def _create_window(self) -> None:
        config = load_json(self.config_file)
        screen_w = self.user32.GetSystemMetrics(0)
        x = int(config.get("x", screen_w - self.width - 48))
        y = int(config.get("y", 120))
        style = 0x80000000  # WS_POPUP
        ex_style = 0x00000008 | 0x00080000 | 0x00040000  # WS_EX_TOPMOST | WS_EX_LAYERED | WS_EX_APPWINDOW
        hwnd = self.user32.CreateWindowExW(
            ex_style,
            self.CLASS_NAME,
            APP_NAME,
            style,
            max(0, x),
            max(0, y),
            self.width,
            self.height,
            None,
            None,
            self.kernel32.GetModuleHandleW(None),
            None,
        )
        if not hwnd:
            raise ctypes.WinError()
        self.hwnd = hwnd
        alpha = int(self.opacity * 255)
        self.user32.SetLayeredWindowAttributes(hwnd, 0, alpha, 0x00000002)
        apply_rounded_window_handle(hwnd, self.width, self.height)
        self.user32.SetTimer(hwnd, 1, self.poll_ms, None)
        self.user32.ShowWindow(hwnd, SW_SHOW)
        self._keep_topmost()
        self._add_tray_icon()
        self.user32.UpdateWindow(hwnd)

    def _ensure_status_file(self) -> None:
        if not self.status_file.exists():
            write_status(self.status_file, "idle")

    def _poll_status(self, force: bool = False) -> None:
        if self.activity_monitor:
            self.activity_monitor.tick()
        if self._should_close_after_codex_exit():
            if self.hwnd:
                self.restart_watcher_on_destroy = True
                self.user32.DestroyWindow(self.hwnd)
            return
        try:
            mtime = self.status_file.stat().st_mtime_ns
        except OSError:
            mtime = 0.0
        next_status = read_status(self.status_file, fallback=self.status)
        status_changed = (
            next_status.state != self.status.state
            or next_status.message != self.status.message
            or next_status.updated_at != self.status.updated_at
        )
        if force or mtime != self.last_mtime or status_changed:
            self.last_mtime = mtime
            self.status = next_status
            self._render_status()

    def _render_status(self) -> None:
        image = render_traffic_light(self.status.state, self.size, theme=self.theme).convert("RGBA")
        self.pixel_data = image.tobytes("raw", "BGRA")
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = self.width
        bmi.bmiHeader.biHeight = -self.height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0
        bmi.bmiHeader.biSizeImage = len(self.pixel_data)
        self.bitmap_info = bmi
        title = f"{LIGHTS[self.status.state]['name']} - {self.status.message}"
        if self.hwnd:
            self.user32.SetWindowTextW(self.hwnd, title)
            self._update_tray_tip()
            self.user32.InvalidateRect(self.hwnd, None, True)
            self.user32.UpdateWindow(self.hwnd)
        trim_working_set()

    def _paint(self, hwnd: int) -> int:
        ps = PAINTSTRUCT()
        hdc = self.user32.BeginPaint(hwnd, ctypes.byref(ps))
        if self.pixel_data and self.bitmap_info:
            buffer = ctypes.create_string_buffer(self.pixel_data)
            self.gdi32.SetDIBitsToDevice(
                hdc,
                0,
                0,
                self.width,
                self.height,
                0,
                0,
                0,
                self.height,
                buffer,
                ctypes.byref(self.bitmap_info),
                0,
            )
        self.user32.EndPaint(hwnd, ctypes.byref(ps))
        return 0

    def _save_position(self) -> None:
        if not self.hwnd:
            return
        rect = wintypes.RECT()
        self.user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
        save_app_config(self.config_file, {"x": rect.left, "y": rect.top, "theme": self.theme, "size": self.size})

    def _should_close_after_codex_exit(self) -> bool:
        if not self.auto_close_on_codex_exit:
            return False
        if codex_is_running():
            self.codex_seen = True
            self.codex_missing_since = 0.0
            return False
        if not self.codex_seen:
            return False
        now = time.monotonic()
        if not self.codex_missing_since:
            self.codex_missing_since = now
            return False
        return now - self.codex_missing_since >= CODEX_EXIT_CLOSE_GRACE_SECONDS

    def _toggle_theme(self) -> None:
        self.theme = "light" if self.theme == "dark" else "dark"
        self._save_position()
        self._render_status()

    def _load_tray_icon(self) -> int:
        if self.tray_icon:
            return self.tray_icon
        icon = 0
        icon_path = DEFAULT_ICON_FILE
        if icon_path.exists():
            icon = self.user32.LoadImageW(None, str(icon_path), 1, 0, 0, 0x00000010 | 0x00000040)
        if not icon:
            try:
                icon = self.shell32.ExtractIconW(None, str(Path(sys.executable).resolve()), 0)
            except Exception:
                icon = 0
        if not icon:
            icon = self.user32.LoadIconW(None, 32512)
        self.tray_icon = icon
        return icon

    def _tray_data(self) -> NOTIFYICONDATAW:
        data = NOTIFYICONDATAW()
        data.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        data.hWnd = self.hwnd
        data.uID = 1
        data.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        data.uCallbackMessage = WM_TRAYICON
        data.hIcon = self._load_tray_icon()
        data.szTip = f"{APP_NAME} {APP_VERSION} - {LIGHTS[self.status.state]['name']}"
        return data

    def _add_tray_icon(self) -> None:
        if not self.hwnd or self.tray_added:
            return
        data = self._tray_data()
        self.tray_added = bool(self.shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(data)))

    def _update_tray_tip(self) -> None:
        if not self.hwnd or not self.tray_added:
            return
        data = self._tray_data()
        self.shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(data))

    def _remove_tray_icon(self) -> None:
        if not self.hwnd or not self.tray_added:
            return
        data = self._tray_data()
        self.shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(data))
        self.tray_added = False

    def _manual_set(self, state: str) -> None:
        write_status(self.status_file, state)
        self._poll_status(force=True)

    def _keep_topmost(self) -> None:
        if self.hwnd:
            self.user32.SetWindowPos(
                self.hwnd,
                HWND_TOPMOST,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
            )

    def _is_minimize_button(self, lparam: int) -> bool:
        x = ctypes.c_short(loword(lparam)).value
        y = ctypes.c_short(hiword(lparam)).value
        x1, y1, x2, y2 = minimize_button_rect(self.width, self.height)
        return x1 <= x <= x2 and y1 <= y <= y2

    def _is_close_button(self, lparam: int) -> bool:
        x = ctypes.c_short(loword(lparam)).value
        y = ctypes.c_short(hiword(lparam)).value
        x1, y1, x2, y2 = close_button_rect(self.width, self.height)
        return x1 <= x <= x2 and y1 <= y <= y2

    def _is_title_toggle(self, lparam: int) -> bool:
        x = ctypes.c_short(loword(lparam)).value
        y = ctypes.c_short(hiword(lparam)).value
        x1, y1, x2, y2 = title_toggle_rect(self.width, self.height)
        return x1 <= x <= x2 and y1 <= y <= y2

    def _is_resize_handle(self, lparam: int) -> bool:
        x = ctypes.c_short(loword(lparam)).value
        y = ctypes.c_short(hiword(lparam)).value
        x1, y1, x2, y2 = resize_handle_rect(self.width, self.height)
        return x1 <= x <= x2 and y1 <= y <= y2

    def _update_cursor(self, lparam: int | None = None) -> None:
        if not self.hwnd:
            return
        if self.resizing:
            if self.resize_cursor:
                self.user32.SetCursor(self.resize_cursor)
            return
        if lparam is not None and self._is_resize_handle(lparam):
            if self.resize_cursor:
                self.user32.SetCursor(self.resize_cursor)
            return
        if self.arrow_cursor:
            self.user32.SetCursor(self.arrow_cursor)

    def _apply_size(self, size: int, save: bool = True) -> None:
        next_size = clamp_display_size(size)
        if next_size == self.size and self.width and self.height:
            return
        self.size = next_size
        sample = render_traffic_light("idle", self.size, theme=self.theme)
        self.width, self.height = sample.size
        if self.hwnd:
            rect = wintypes.RECT()
            self.user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
            self.user32.SetWindowPos(
                self.hwnd,
                HWND_TOPMOST,
                rect.left,
                rect.top,
                self.width,
                self.height,
                SWP_NOACTIVATE,
            )
            apply_rounded_window_handle(self.hwnd, self.width, self.height)
        self._render_status()
        if save:
            self._save_position()

    def _change_size_percent(self, percent: float) -> None:
        self._apply_size(round(self.size * percent), save=True)

    def _reset_size(self) -> None:
        self._apply_size(DEFAULT_DISPLAY_SIZE, save=True)

    def _start_resize(self, hwnd: int, lparam: int) -> None:
        self.resizing = True
        self.resize_start_size = self.size
        self._update_cursor(lparam)
        point = POINT(
            ctypes.c_short(loword(lparam)).value,
            ctypes.c_short(hiword(lparam)).value,
        )
        self.user32.ClientToScreen(hwnd, ctypes.byref(point))
        self.resize_start_point = point
        self.user32.SetCapture(hwnd)

    def _resize_from_cursor(self) -> None:
        if not self.resizing:
            return
        point = POINT()
        if not self.user32.GetCursorPos(ctypes.byref(point)):
            return
        dx = point.x - self.resize_start_point.x
        dy = point.y - self.resize_start_point.y
        width_size = (int(self.resize_start_size * 3.95) + dx) / 3.95
        height_size = (int(self.resize_start_size * 5.45) + dy) / 5.45
        self._apply_size(round(max(width_size, height_size)), save=False)

    def _finish_resize(self) -> None:
        if not self.resizing:
            return
        self.resizing = False
        self.user32.ReleaseCapture()
        self._save_position()

    def _minimize(self) -> None:
        self._save_position()
        if self.hwnd:
            self.user32.ShowWindow(self.hwnd, SW_HIDE)

    def _show_window(self) -> None:
        if self.hwnd:
            self.user32.ShowWindow(self.hwnd, SW_RESTORE)
            self._keep_topmost()

    def _close(self) -> None:
        self._save_position()
        if self.hwnd:
            self.user32.DestroyWindow(self.hwnd)

    def _cycle_status(self) -> None:
        order = ["idle", "running", "attention"]
        current = order.index(self.status.state) if self.status.state in order else 0
        self._manual_set(order[(current + 1) % len(order)])

    def _show_status(self) -> None:
        updated = self.status.updated_at or "未知"
        text = (
            f"当前状态：{LIGHTS[self.status.state]['label']} / {LIGHTS[self.status.state]['name']}\n"
            f"状态说明：{self.status.message}\n"
            f"更新时间：{updated}\n"
            f"状态文件：{self.status_file}"
        )
        self.user32.MessageBoxW(self.hwnd, text, "状态信息", 0)

    def _show_about(self) -> None:
        text = (
            f"{APP_NAME}\n"
            f"版本：{APP_VERSION}\n\n"
            "状态规则：\n"
            "绿色：任务完成，当前空闲\n"
            "黄色：正在运行或正在思考\n"
            "红色：需要审批、异常、阻塞或人工介入\n\n"
            f"安装目录：\n{APP_DIR}\n\n"
            f"配置文件：\n{self.config_file}"
        )
        self.user32.MessageBoxW(self.hwnd, text, f"关于 {APP_NAME}", 0x40)

    def _popup_menu_at(self, hwnd: int, screen_x: int, screen_y: int) -> None:
        menu = self.user32.CreatePopupMenu()
        self.user32.AppendMenuW(menu, 0, 110, "显示窗口")
        self.user32.AppendMenuW(menu, 0, 111, "切换深色/浅色模式")
        self.user32.AppendMenuW(menu, 0x0800, 0, None)
        self.user32.AppendMenuW(menu, 0, 101, "绿色：空闲 / 已完成")
        self.user32.AppendMenuW(menu, 0, 102, "黄色：运行 / 思考中")
        self.user32.AppendMenuW(menu, 0, 103, "红色：需要处理")
        self.user32.AppendMenuW(menu, 0x0800, 0, None)
        self.user32.AppendMenuW(menu, 0, 107, "放大 10%")
        self.user32.AppendMenuW(menu, 0, 108, "缩小 10%")
        self.user32.AppendMenuW(menu, 0, 109, "恢复默认大小")
        self.user32.AppendMenuW(menu, 0x0800, 0, None)
        self.user32.AppendMenuW(menu, 0, 104, "最小化到托盘")
        self.user32.AppendMenuW(menu, 0, 105, "查看状态")
        self.user32.AppendMenuW(menu, 0, 112, "关于")
        self.user32.AppendMenuW(menu, 0, 106, "退出")
        self.user32.SetForegroundWindow(hwnd)
        command = self.user32.TrackPopupMenu(menu, 0x0100, screen_x, screen_y, 0, hwnd, None)
        self.user32.DestroyMenu(menu)
        if command == 110:
            self._show_window()
        elif command == 111:
            self._toggle_theme()
        elif command == 101:
            self._manual_set("idle")
        elif command == 102:
            self._manual_set("thinking")
        elif command == 103:
            self._manual_set("attention")
        elif command == 107:
            self._change_size_percent(1.10)
        elif command == 108:
            self._change_size_percent(0.90)
        elif command == 109:
            self._reset_size()
        elif command == 104:
            self._minimize()
        elif command == 105:
            self._show_status()
        elif command == 112:
            self._show_about()
        elif command == 106:
            self.user32.DestroyWindow(hwnd)

    def _popup_menu(self, hwnd: int, lparam: int) -> None:
        x = ctypes.c_short(loword(lparam)).value
        y = ctypes.c_short(hiword(lparam)).value
        point = POINT(x, y)
        self.user32.ClientToScreen(hwnd, ctypes.byref(point))
        self._popup_menu_at(hwnd, point.x, point.y)

    def _popup_tray_menu(self, hwnd: int) -> None:
        point = POINT()
        self.user32.GetCursorPos(ctypes.byref(point))
        self._popup_menu_at(hwnd, point.x, point.y)

    def _window_proc(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        if msg == 0x000F:  # WM_PAINT
            return self._paint(hwnd)
        if msg == 0x0113:  # WM_TIMER
            if wparam == 2:
                self.user32.DestroyWindow(hwnd)
                return 0
            self._poll_status()
            self._keep_topmost()
            return 0
        if msg == 0x0201:  # WM_LBUTTONDOWN
            if self._is_close_button(lparam):
                self._close()
                return 0
            if self._is_minimize_button(lparam):
                self._minimize()
                return 0
            if self._is_title_toggle(lparam):
                self._toggle_theme()
                return 0
            if self._is_resize_handle(lparam):
                self._start_resize(hwnd, lparam)
                return 0
            self.user32.ReleaseCapture()
            self.user32.SendMessageW(hwnd, 0x00A1, 2, 0)  # WM_NCLBUTTONDOWN / HTCAPTION
            return 0
        if msg == 0x0200:  # WM_MOUSEMOVE
            self._update_cursor(lparam)
            self._resize_from_cursor()
            return 0 if self.resizing else self.user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        if msg == 0x0020:  # WM_SETCURSOR
            self._update_cursor()
            return 1 if self.resizing else self.user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        if msg == 0x0202:  # WM_LBUTTONUP
            self._finish_resize()
            return 0
        if msg == 0x0203:  # WM_LBUTTONDBLCLK
            self._cycle_status()
            return 0
        if msg == 0x0204:  # WM_RBUTTONDOWN
            self._popup_menu(hwnd, lparam)
            return 0
        if msg == WM_TRAYICON:
            if lparam == 0x0203:  # WM_LBUTTONDBLCLK
                self._show_window()
                return 0
            if lparam in (0x0205, 0x0204):  # WM_RBUTTONUP / WM_RBUTTONDOWN
                self._popup_tray_menu(hwnd)
                return 0
        if msg == 0x0010:  # WM_CLOSE
            self.user32.DestroyWindow(hwnd)
            return 0
        if msg == 0x0002:  # WM_DESTROY
            self._save_position()
            self._remove_tray_icon()
            self.user32.KillTimer(hwnd, 1)
            if self.restart_watcher_on_destroy:
                launch_external_watcher()
            self.user32.PostQuitMessage(0)
            return 0
        return self.user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def run(self) -> None:
        msg = wintypes.MSG()
        while self.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            self.user32.TranslateMessage(ctypes.byref(msg))
            self.user32.DispatchMessageW(ctypes.byref(msg))


def apply_rounded_window_handle(hwnd: int, width: int, height: int) -> None:
    if sys.platform != "win32":
        return
    try:
        radius = max(22, int(min(width, height) * 0.14))
        region = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, width + 1, height + 1, radius, radius)
        ctypes.windll.user32.SetWindowRgn(hwnd, region, True)
    except Exception:
        pass


def save_preview(path: Path = DEFAULT_PREVIEW_FILE, theme: str = "light") -> None:
    preview_size = 86
    style = theme_style(theme)
    sample = render_traffic_light("idle", size=preview_size, scale=5, theme=theme)
    preview = Image.new("RGBA", (sample.width * 3 + 96, sample.height + 48), hex_to_rgba(style["window_bg"]))
    for index, state in enumerate(("attention", "running", "idle")):
        image = render_traffic_light(state, size=preview_size, scale=5, theme=theme)
        preview.alpha_composite(image, (24 + index * (sample.width + 24), 24))
    preview.save(path)


def classify_pixel(pixel: tuple[int, ...]) -> str:
    r, g, b = pixel[:3]
    if r > 180 and g < 125:
        return "red"
    if r > 170 and g > 130 and b < 100:
        return "yellow"
    if g > 145 and r < 125:
        return "green"
    return "dim"


def run_self_test() -> None:
    alias_expectations = {
        "idle": "idle",
        "done": "idle",
        "\u5df2\u5b8c\u6210": "idle",
        "running": "running",
        "thinking": "running",
        "\u601d\u8003\u4e2d": "running",
        "attention": "attention",
        "approval": "attention",
        "\u9700\u8981\u5ba1\u6279": "attention",
    }
    for raw, expected in alias_expectations.items():
        actual = normalize_state(raw)
        if actual != expected:
            raise AssertionError(f"Alias mismatch: {raw!r} -> {actual}, expected {expected}")

    expected_labels = {
        "attention": ("RED", "red"),
        "running": ("YELLOW", "yellow"),
        "idle": ("GREEN", "green"),
    }
    size = 58
    width = int(size * 3.95)
    unit = size
    cx = width // 2
    row_w = int(unit * 3.15)
    row_h = int(unit * 0.86)
    row_gap = int(unit * 0.21)
    row_x = cx - row_w // 2
    row_y = int(unit * 1.70)
    lamp_x = row_x + int(row_w * 0.18)
    centers = {
        "attention": (lamp_x, row_y + row_h // 2),
        "running": (lamp_x, row_y + (row_h + row_gap) + row_h // 2),
        "idle": (lamp_x, row_y + 2 * (row_h + row_gap) + row_h // 2),
    }
    for state, (expected_label, expected_color) in expected_labels.items():
        image = render_traffic_light(state, size=size, scale=4)
        label = LIGHTS[state]["label"]
        active_color = classify_pixel(image.getpixel(centers[state]))
        if label != expected_label or active_color != expected_color:
            raise AssertionError(
                f"Render mismatch: {state} label={label}, center={active_color}, "
                f"expected {expected_label}/{expected_color}"
            )

    session_path = DEFAULT_STATUS_FILE.with_name("__session_status_test__.jsonl")
    monitor = CodexSessionEventMonitor(session_dirs=[DEFAULT_STATUS_FILE.parent])
    try:
        approval_events = [
            {
                "timestamp": "2026-06-15T01:00:00.000Z",
                "type": "response_item",
                "payload": {"type": "message", "role": "user"},
            },
            {
                "timestamp": "2026-06-15T01:00:01.000Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "call_id": "call_test",
                    "arguments": '{"sandbox_permissions":"require_escalated"}',
                },
            },
        ]
        session_path.write_text(
            "\n".join(json.dumps(event) for event in approval_events) + "\n",
            encoding="utf-8",
        )
        state, _message, _event_time = monitor._classify_file(session_path)
        if state != "attention":
            raise AssertionError(f"Approval event should be attention, got {state}")
        completed_events = approval_events + [
            {
                "timestamp": "2026-06-15T01:00:02.000Z",
                "type": "response_item",
                "payload": {"type": "function_call_output", "call_id": "call_test"},
            },
            {
                "timestamp": "2026-06-15T01:00:03.000Z",
                "type": "event_msg",
                "payload": {"type": "task_complete"},
            },
        ]
        session_path.write_text(
            "\n".join(json.dumps(event) for event in completed_events) + "\n",
            encoding="utf-8",
        )
        state, _message, _event_time = monitor._classify_file(session_path)
        if state != "idle":
            raise AssertionError(f"Task complete event should be idle, got {state}")
    finally:
        try:
            session_path.unlink()
        except OSError:
            pass

    fallback = Status(state="running", message="fallback")
    tmp_path = DEFAULT_STATUS_FILE.with_name("__invalid_status_test__.json")
    try:
        tmp_path.write_text("{", encoding="utf-8")
        recovered = read_status(tmp_path, fallback=fallback)
        if recovered.state != "running":
            raise AssertionError("Invalid JSON fallback did not preserve previous status")
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass

    print("Self-test passed: aliases, render colors, labels, and invalid JSON fallback are consistent.")


class TrafficLightApp:
    def __init__(
        self,
        root: tk.Tk,
        status_file: Path,
        config_file: Path,
        size: int,
        opacity: float,
        poll_ms: int,
        theme: str = "light",
        auto_detect: bool = True,
    ) -> None:
        self.root = root
        self.status_file = status_file
        self.config_file = config_file
        self.size = max(36, size)
        self.poll_ms = max(100, poll_ms)
        self.theme = theme
        self.style = theme_style(theme)
        self.activity_monitor = CodexActivityMonitor(status_file) if auto_detect else None
        self.codex_seen = codex_is_running()
        self.codex_missing_since = 0.0
        self.auto_close_on_codex_exit = auto_detect
        self.drag_enabled = True
        self.resize_enabled = False
        self.drag_offset = (0, 0)
        self.resize_start_root = (0, 0)
        self.resize_start_size = self.size
        self.status = Status()
        self.last_mtime = 0.0
        self.photo: ImageTk.PhotoImage | None = None

        self.root.title(APP_NAME)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", min(1.0, max(0.25, opacity)))
        self.root.configure(bg=self.style["window_bg"])
        if DEFAULT_ICON_FILE.exists():
            try:
                self.root.iconbitmap(str(DEFAULT_ICON_FILE))
            except tk.TclError:
                pass

        sample = render_traffic_light("idle", self.size, theme=self.theme)
        self.width, self.height = sample.size
        self.canvas = tk.Canvas(
            root,
            width=self.width,
            height=self.height,
            bg=self.style["window_bg"],
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.image_item = self.canvas.create_image(0, 0, anchor="nw")

        self._build_menu()
        self._restore_position()
        self._bind_events()
        self._ensure_status_file()
        self._poll_status(force=True)

    def _build_menu(self) -> None:
        self.menu = tk.Menu(self.root, tearoff=False)
        self.menu.add_command(
            label="绿色：空闲 / 已完成",
            command=lambda: self._manual_set("idle"),
        )
        self.menu.add_command(
            label="黄色：运行 / 思考中",
            command=lambda: self._manual_set("thinking"),
        )
        self.menu.add_command(
            label="红色：需要处理",
            command=lambda: self._manual_set("attention"),
        )
        self.menu.add_separator()
        self.menu.add_command(label="放大 10%", command=lambda: self._change_size_percent(1.10))
        self.menu.add_command(label="缩小 10%", command=lambda: self._change_size_percent(0.90))
        self.menu.add_command(label="恢复默认大小", command=self._reset_size)
        self.menu.add_separator()
        self.menu.add_command(label="切换深色/浅色模式", command=self._toggle_theme)
        self.menu.add_command(label="查看状态", command=self._show_status)
        self.menu.add_command(label="关于", command=self._show_about)
        self.menu.add_command(label="退出", command=self._quit)

    def _restore_position(self) -> None:
        config = load_json(self.config_file)
        x = int(config.get("x", self.root.winfo_screenwidth() - self.width - 48))
        y = int(config.get("y", 120))
        self.root.geometry(f"{self.width}x{self.height}+{max(0, x)}+{max(0, y)}")
        self.root.update_idletasks()
        apply_rounded_window(self.root, self.width, self.height)

    def _bind_events(self) -> None:
        for widget in (self.root, self.canvas):
            widget.bind("<ButtonPress-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._drag)
            widget.bind("<ButtonRelease-1>", self._save_position)
            widget.bind("<Motion>", self._update_cursor)
            widget.bind("<Leave>", self._reset_cursor)
            widget.bind("<Button-3>", self._popup_menu)
            widget.bind("<Double-Button-1>", self._cycle_status)
            widget.bind("<Escape>", lambda _event: self._quit())

    def _ensure_status_file(self) -> None:
        if not self.status_file.exists():
            write_status(self.status_file, "idle")

    def _poll_status(self, force: bool = False) -> None:
        if self.activity_monitor:
            self.activity_monitor.tick()
        if self._should_close_after_codex_exit():
            self._quit()
            return
        try:
            mtime = self.status_file.stat().st_mtime_ns
        except OSError:
            mtime = 0.0
        next_status = read_status(self.status_file, fallback=self.status)
        status_changed = (
            next_status.state != self.status.state
            or next_status.message != self.status.message
            or next_status.updated_at != self.status.updated_at
        )
        if force or mtime != self.last_mtime or status_changed:
            self.last_mtime = mtime
            self.status = next_status
            self._render_status()
        self.root.after(self.poll_ms, self._poll_status)

    def _render_status(self) -> None:
        from PIL import ImageTk

        rendered = render_traffic_light(self.status.state, self.size, theme=self.theme)
        self.photo = ImageTk.PhotoImage(rendered)
        self.canvas.itemconfigure(self.image_item, image=self.photo)
        title = f"{LIGHTS[self.status.state]['name']} - {self.status.message}"
        self.root.title(title)
        trim_working_set()

    def _manual_set(self, state: str) -> None:
        write_status(self.status_file, state)
        self._poll_status(force=True)

    def _cycle_status(self, _event: tk.Event[Any]) -> None:
        order = ["idle", "running", "attention"]
        current = order.index(self.status.state) if self.status.state in order else 0
        self._manual_set(order[(current + 1) % len(order)])

    def _show_status(self) -> None:
        updated = self.status.updated_at or "未知"
        messagebox.showinfo(
            "状态信息",
            f"当前状态：{LIGHTS[self.status.state]['label']} / {LIGHTS[self.status.state]['name']}\n"
            f"状态说明：{self.status.message}\n"
            f"更新时间：{updated}\n"
            f"状态文件：{self.status_file}",
        )

    def _show_about(self) -> None:
        messagebox.showinfo(
            f"关于 {APP_NAME}",
            f"{APP_NAME}\n"
            f"版本：{APP_VERSION}\n\n"
            "状态规则：\n"
            "绿色：任务完成，当前空闲\n"
            "黄色：正在运行或正在思考\n"
            "红色：需要审批、异常、阻塞或人工介入\n\n"
            f"安装目录：\n{APP_DIR}\n\n"
            f"配置文件：\n{self.config_file}",
        )

    def _update_cursor(self, event: tk.Event[Any]) -> None:
        x1, y1, x2, y2 = resize_handle_rect(self.width, self.height)
        cursor = "size_nw_se" if self.resize_enabled or (x1 <= event.x <= x2 and y1 <= event.y <= y2) else ""
        self.root.configure(cursor=cursor)
        self.canvas.configure(cursor=cursor)

    def _reset_cursor(self, _event: tk.Event[Any] | None = None) -> None:
        if self.resize_enabled:
            return
        self.root.configure(cursor="")
        self.canvas.configure(cursor="")

    def _start_drag(self, event: tk.Event[Any]) -> None:
        x1, y1, x2, y2 = title_toggle_rect(self.width, self.height)
        if x1 <= event.x <= x2 and y1 <= event.y <= y2:
            self.drag_enabled = False
            self.resize_enabled = False
            self._toggle_theme()
            return
        x1, y1, x2, y2 = resize_handle_rect(self.width, self.height)
        if x1 <= event.x <= x2 and y1 <= event.y <= y2:
            self.drag_enabled = False
            self.resize_enabled = True
            self.resize_start_root = (event.x_root, event.y_root)
            self.resize_start_size = self.size
            self.root.configure(cursor="size_nw_se")
            self.canvas.configure(cursor="size_nw_se")
            return
        self.drag_enabled = True
        self.resize_enabled = False
        self.drag_offset = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _drag(self, event: tk.Event[Any]) -> None:
        if self.resize_enabled:
            dx = event.x_root - self.resize_start_root[0]
            dy = event.y_root - self.resize_start_root[1]
            width_size = (int(self.resize_start_size * 3.95) + dx) / 3.95
            height_size = (int(self.resize_start_size * 5.45) + dy) / 5.45
            self._apply_size(round(max(width_size, height_size)), save=False)
            return
        if not self.drag_enabled:
            return
        x = event.x_root - self.drag_offset[0]
        y = event.y_root - self.drag_offset[1]
        self.root.geometry(f"+{x}+{y}")

    def _save_position(self, _event: tk.Event[Any] | None = None) -> None:
        self.drag_enabled = True
        self.resize_enabled = False
        self._reset_cursor()
        save_app_config(
            self.config_file,
            {"x": self.root.winfo_x(), "y": self.root.winfo_y(), "theme": self.theme, "size": self.size},
        )

    def _apply_size(self, size: int, save: bool = True) -> None:
        next_size = clamp_display_size(size)
        if next_size == self.size and self.width and self.height:
            return
        self.size = next_size
        sample = render_traffic_light("idle", self.size, theme=self.theme)
        self.width, self.height = sample.size
        self.canvas.configure(width=self.width, height=self.height)
        self.root.geometry(f"{self.width}x{self.height}+{self.root.winfo_x()}+{self.root.winfo_y()}")
        apply_rounded_window(self.root, self.width, self.height)
        self._render_status()
        if save:
            self._save_position()

    def _change_size_percent(self, percent: float) -> None:
        self._apply_size(round(self.size * percent), save=True)

    def _reset_size(self) -> None:
        self._apply_size(DEFAULT_DISPLAY_SIZE, save=True)

    def _should_close_after_codex_exit(self) -> bool:
        if not self.auto_close_on_codex_exit:
            return False
        if codex_is_running():
            self.codex_seen = True
            self.codex_missing_since = 0.0
            return False
        if not self.codex_seen:
            return False
        now = time.monotonic()
        if not self.codex_missing_since:
            self.codex_missing_since = now
            return False
        return now - self.codex_missing_since >= CODEX_EXIT_CLOSE_GRACE_SECONDS

    def _toggle_theme(self) -> None:
        self.theme = "light" if self.theme == "dark" else "dark"
        self.style = theme_style(self.theme)
        self.root.configure(bg=self.style["window_bg"])
        self.canvas.configure(bg=self.style["window_bg"])
        self._save_position()
        self._render_status()

    def _popup_menu(self, event: tk.Event[Any]) -> None:
        self.menu.tk_popup(event.x_root, event.y_root)

    def _quit(self) -> None:
        self._save_position()
        self.root.destroy()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--status-file", type=Path, default=DEFAULT_STATUS_FILE)
    parser.add_argument("--config-file", type=Path, default=DEFAULT_CONFIG_FILE)
    parser.add_argument("--size", type=int, default=None, help="display scale; larger values are sharper")
    parser.add_argument("--opacity", type=float, default=0.96)
    parser.add_argument("--poll-ms", type=int, default=500)
    parser.add_argument("--theme", choices=["light", "dark"], default=None, help="visual theme")
    parser.add_argument("--no-auto-detect", action="store_true", help="disable built-in Codex activity detection")
    parser.add_argument(
        "--set",
        choices=[
            "idle",
            "running",
            "thinking",
            "attention",
            "approval",
            "approve",
            "error",
            "blocked",
            "done",
            "complete",
            "completed",
            "green",
            "yellow",
            "red",
        ],
        help="write status and exit instead of opening the window",
    )
    parser.add_argument("--message", help="optional message used with --set")
    parser.add_argument("--preview", action="store_true", help="render a PNG preview and exit")
    parser.add_argument("--self-test", action="store_true", help="validate status rules and rendering")
    parser.add_argument("--smoke-test", action="store_true", help="open the native window briefly and exit")
    parser.add_argument("--watch-codex", action="store_true", help="run hidden watcher and open the light when Codex starts")
    parser.add_argument("--watch-once", action="store_true", help="check once for Codex and exit; useful for diagnostics")
    parser.add_argument("--version", action="store_true", help="print product version and exit")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    status_file = args.status_file.resolve()
    config_file = args.config_file.resolve()
    config = load_json(config_file)
    theme = args.theme or str(config.get("theme") or THEME)
    if theme not in THEMES:
        theme = THEME
    size = clamp_display_size(args.size if args.size is not None else config.get("size", DEFAULT_DISPLAY_SIZE))

    if args.version:
        print(f"{APP_NAME} {APP_VERSION}")
        return 0

    if args.watch_codex or args.watch_once:
        if sys.platform != "win32":
            return 1
        return watch_codex(once=args.watch_once, status_file=status_file)

    if args.preview:
        preview_path = DEFAULT_DARK_PREVIEW_FILE if theme == "dark" else DEFAULT_PREVIEW_FILE
        save_preview(preview_path, theme=theme)
        print(f"Preview saved to {preview_path.resolve()}")
        return 0

    if args.self_test:
        run_self_test()
        return 0

    if args.set:
        write_status(status_file, args.set, args.message)
        print(f"Set {status_file} to {normalize_state(args.set)}")
        return 0

    enable_dpi_awareness()
    if sys.platform == "win32":
        if not args.smoke_test and activate_existing_window():
            return 0
        NativeTrafficLightApp(
            status_file=status_file,
            config_file=config_file,
            size=size,
            opacity=args.opacity,
            poll_ms=args.poll_ms,
            theme=theme,
            auto_detect=not args.no_auto_detect,
            smoke_test_ms=700 if args.smoke_test else None,
        ).run()
    else:
        if tk is None:
            raise RuntimeError("Tkinter is required on non-Windows platforms.")
        root = tk.Tk()
        TrafficLightApp(
            root=root,
            status_file=status_file,
            config_file=config_file,
            size=size,
            opacity=args.opacity,
            poll_ms=args.poll_ms,
            theme=theme,
            auto_detect=not args.no_auto_detect,
        )
        root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
