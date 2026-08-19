from __future__ import annotations

"""Detección best-effort de la ventana activa; nunca concede autoridad de ejecución."""

import ctypes
import platform
import subprocess
from typing import Any


def get_active_window() -> dict[str, Any] | None:
    """Return ``app`` and ``title`` when the desktop exposes that information."""
    system = platform.system()
    if system == "Windows":
        return _windows_active_window()
    if system == "Linux":
        return _linux_active_window()
    if system == "Darwin":
        return _darwin_active_window()
    return None


def _windows_active_window() -> dict[str, Any] | None:
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        length = user32.GetWindowTextLengthW(hwnd)
        title_buffer = ctypes.create_unicode_buffer(max(1, length + 1))
        user32.GetWindowTextW(hwnd, title_buffer, len(title_buffer))
        title = title_buffer.value.strip()
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        app = _process_name(int(pid.value)) or "unknown"
        return {"app": app, "title": title, "pid": int(pid.value)}
    except (AttributeError, OSError, ValueError):
        return None


def _linux_active_window() -> dict[str, Any] | None:
    # xdotool is optional. The fallback uses xprop; both commands are fixed
    # utilities and receive no user or model-supplied arguments.
    title = _run_fixed(["xdotool", "getactivewindow", "getwindowname"])
    window_id = _run_fixed(["xdotool", "getactivewindow"])
    if not window_id:
        root = _run_fixed(["xprop", "-root", "_NET_ACTIVE_WINDOW"])
        window_id = _parse_xprop_id(root or "")
    if window_id and not title:
        title = _run_fixed(["xprop", "-id", window_id, "_NET_WM_NAME"])
        title = _parse_xprop_string(title or "")
    if not title:
        return None
    pid = None
    if window_id:
        raw_pid = _run_fixed(["xprop", "-id", window_id, "_NET_WM_PID"])
        try:
            pid = int((raw_pid or "").split()[-1])
        except (ValueError, IndexError):
            pid = None
    return {"app": _process_name(pid) or "unknown", "title": title.strip(), **({"pid": pid} if pid else {})}


def _darwin_active_window() -> dict[str, Any] | None:
    # Avoid AppleScript and accessibility prompts in the background client.
    return None


def _run_fixed(command: list[str]) -> str | None:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=1.5, shell=False, check=False)
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _parse_xprop_id(value: str) -> str | None:
    marker = "#"
    if marker not in value:
        return None
    candidate = value.split(marker, 1)[1].split(",", 1)[0].strip()
    return candidate if candidate and all(char in "0123456789abcdefABCDEF" for char in candidate) else None


def _parse_xprop_string(value: str) -> str:
    if "=" not in value:
        return value.strip().strip('"')
    return value.split("=", 1)[1].strip().strip('"')


def _process_name(pid: int | None) -> str | None:
    if not pid:
        return None
    try:
        import psutil
        return str(psutil.Process(pid).name())
    except (ImportError, OSError):
        return None
    except Exception:
        return None


__all__ = ["get_active_window"]
